"""Pipeline endpoints: fetch, scrape, analyze, scan status."""
from fastapi import APIRouter, BackgroundTasks
from datetime import datetime, timezone, timedelta
import asyncio
import os
import uuid
from shared import (
    db, intelligence_col, sources_col,
    scan_status, ws_manager, IntelligenceItem,
    logger, invalidate_stats_cache, has_non_latin_chars,
)

router = APIRouter()


@router.post("/scrape-elite")
async def trigger_elite_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_elite_scrape)
    return {"message": "Elite scraping started"}


@router.post("/fetch-news")
async def trigger_fetch(background_tasks: BackgroundTasks):
    background_tasks.add_task(fetch_and_process_news)
    return {"message": "News fetch triggered"}


@router.post("/bulk-scrape")
async def trigger_bulk_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(bulk_scrape_all_feeds)
    return {"message": "Bulk scrape triggered - articles will be stored for gradual AI processing"}


@router.get("/scan-status")
async def get_scan_status():
    return scan_status


@router.post("/analyze-news")
async def trigger_analysis(background_tasks: BackgroundTasks):
    background_tasks.add_task(analyze_unprocessed_items)
    return {"message": "Analysis triggered"}


@router.get("/pipeline/status")
async def pipeline_status():
    total = await intelligence_col.count_documents({})
    processed = await intelligence_col.count_documents({"processed": True})
    unprocessed = await intelligence_col.count_documents({"processed": False})
    sources = await sources_col.count_documents({})

    yesterday = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_processed = await intelligence_col.count_documents({
        "processed": True,
        "fetched_at": {"$gte": yesterday}
    })

    return {
        "total_items": total,
        "ai_processed": processed,
        "pending_retry": unprocessed,
        "processing_rate": f"{(processed / total * 100):.1f}%" if total > 0 else "N/A",
        "recent_24h_processed": recent_processed,
        "rss_sources": sources,
        "rate_limit_config": {
            "max_articles_per_cycle": 25,
            "batch_size": 3,
            "batch_pause_seconds": 5,
            "inter_article_delay_seconds": 1.5,
            "max_retry_per_cycle": 15
        },
        "filter_stats": {
            "last_filtered_out": scan_status.get("filtered_out", 0),
            "last_translated": scan_status.get("translated", 0),
        },
        "scheduler": "grassroots/60min, standard/30min, established/12hr, retry/15min, brief/0600 IST, embeddings/6hr, fusion/30min"
    }


# ============================================================
# Background Task Functions
# ============================================================

async def _run_elite_scrape():
    from web_scraper import scrape_all_targets
    articles = await scrape_all_targets()
    if articles:
        logger.info(f"Elite scrape: {len(articles)} articles found, merging into pipeline")
        for article in articles[:15]:
            existing = await intelligence_col.find_one(
                {"source_url": article["source_url"]}, {"_id": 1}
            )
            if not existing:
                article["processed"] = False
                await intelligence_col.insert_one(article)


async def fetch_and_process_news(source_filter: str = None):
    from rss_fetcher import fetch_all_feeds, RSS_SOURCES, get_sources_by_priority

    MAX_ARTICLES_PER_CYCLE = 25
    BATCH_SIZE = 3
    BATCH_PAUSE = 5
    INTER_ARTICLE_DELAY = 1.5

    if source_filter:
        active_sources = get_sources_by_priority(source_filter)
        logger.info(f"Filtered to {len(active_sources)} {source_filter} sources")
    else:
        active_sources = RSS_SOURCES

    scan_status["is_scanning"] = True
    scan_status["progress"] = 0
    scan_status["total_sources"] = len(active_sources)
    scan_status["sources_scanned"] = 0
    scan_status["current_source"] = ""
    scan_status["articles_found"] = 0
    scan_status["relevant_found"] = 0
    scan_status["scan_log"] = []

    async def on_source_progress(idx, total, source_name):
        scan_status["sources_scanned"] = idx
        scan_status["current_source"] = source_name
        scan_status["progress"] = int((idx / total) * 100) if total > 0 else 0
        if source_name != "Complete":
            scan_status["scan_log"].append(source_name)
            if len(scan_status["scan_log"]) > 10:
                scan_status["scan_log"] = scan_status["scan_log"][-10:]

    logger.info(f"=== Starting news fetch cycle ({source_filter or 'all'}) ===")
    try:
        # Load dynamic keywords
        dynamic_kw_weights = None
        try:
            from keyword_engine import generate_keywords, get_dynamic_keywords_for_matching
            keywords = await generate_keywords(db, use_ai=False)
            dynamic_kw_weights = get_dynamic_keywords_for_matching(keywords)
            logger.info(f"Loaded {len(dynamic_kw_weights)} dynamic keywords for RSS filtering")
        except Exception as e:
            logger.warning(f"Dynamic keywords unavailable, using static: {e}")

        articles = await fetch_all_feeds(
            progress_callback=on_source_progress,
            sources=active_sources if source_filter else None,
            dynamic_keyword_weights=dynamic_kw_weights
        )
        scan_status["articles_found"] = len(articles)
        logger.info(f"Fetched {len(articles)} relevant articles from RSS feeds")

        # Dedup
        import re
        def normalize_for_dedup(title):
            t = (title or "").lower().strip()
            t = re.sub(r'[^a-z0-9\s]', '', t)
            t = re.sub(r'\s+', ' ', t).strip()
            return t

        def title_is_similar(t1, existing_titles, threshold=0.65):
            words1 = set(t1.split())
            for t2 in existing_titles:
                words2 = set(t2.split())
                if not words2:
                    continue
                overlap = len(words1 & words2)
                total = max(len(words1), len(words2))
                if total > 0 and overlap / total >= threshold:
                    return True
            return False

        recent_db_items = await intelligence_col.find(
            {"processed": True},
            {"title": 1, "source_url": 1, "_id": 0}
        ).sort("fetched_at", -1).limit(500).to_list(500)

        existing_urls = set(item.get("source_url", "") for item in recent_db_items)
        existing_titles = [normalize_for_dedup(item.get("title", "")) for item in recent_db_items]

        new_articles = []
        url_dupes = 0
        title_dupes = 0
        for article in articles:
            url = article.get("source_url", "")
            title = article.get("title", "")
            if not url:
                continue
            if url in existing_urls:
                url_dupes += 1
                continue
            norm_title = normalize_for_dedup(title)
            if len(norm_title) > 10 and title_is_similar(norm_title, existing_titles):
                title_dupes += 1
                continue
            new_articles.append(article)
            existing_urls.add(url)
            existing_titles.append(norm_title)

        skipped = url_dupes + title_dupes
        logger.info(f"Deduplication: {url_dupes} URL dupes, {title_dupes} title dupes, {len(new_articles)} new articles")

        # Intelligence filter
        from intelligence_filter import hard_filter, detect_language, run_filter_pipeline

        filtered_articles = []
        filter_rejected = 0
        translated_count = 0
        for article in new_articles:
            passed, reason = hard_filter(article)
            if not passed:
                filter_rejected += 1
                logger.debug(f"  Filtered out: {article.get('title', '')[:50]} ({reason})")
                continue

            lang = detect_language(f"{article.get('title', '')} {article.get('raw_content', '')[:200]}")
            article["detected_language"] = lang

            if lang != "en":
                try:
                    filter_result = await run_filter_pipeline(article)
                    if filter_result.get("translated_title"):
                        article["original_title"] = article["title"]
                        article["title"] = filter_result["translated_title"]
                        translated_count += 1
                    if filter_result.get("translated_content"):
                        article["original_content"] = article.get("raw_content", "")
                        article["raw_content"] = filter_result["translated_content"]
                except Exception as e:
                    logger.warning(f"Translation failed, using original: {e}")

            filtered_articles.append(article)

        scan_status["filtered_out"] = filter_rejected
        scan_status["translated"] = translated_count
        scan_status["relevant_found"] = len(filtered_articles)
        logger.info(f"Intelligence Filter: {filter_rejected} rejected, {translated_count} translated, {len(filtered_articles)} passed")
        new_articles = filtered_articles

        if not new_articles:
            logger.info("No new articles to process after filtering. Cycle complete.")
            scan_status["is_scanning"] = False
            scan_status["progress"] = 100
            scan_status["current_source"] = ""
            scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
            scan_status["last_scan_result"] = {
                "feeds_scanned": len(RSS_SOURCES),
                "total_articles": len(articles),
                "new_relevant": 0,
                "duplicates_skipped": skipped,
                "filtered_out": filter_rejected,
                "translated": translated_count
            }
            return

        if len(new_articles) > MAX_ARTICLES_PER_CYCLE:
            logger.info(f"Limiting to {MAX_ARTICLES_PER_CYCLE} articles this cycle")
            new_articles = new_articles[:MAX_ARTICLES_PER_CYCLE]

        # Process with Sifter
        from sifter import sift_article
        success_count = 0
        fail_count = 0
        skip_count = 0
        rate_limit_hits = 0

        for batch_start in range(0, len(new_articles), BATCH_SIZE):
            batch = new_articles[batch_start:batch_start + BATCH_SIZE]
            batch_num = (batch_start // BATCH_SIZE) + 1
            total_batches = (len(new_articles) + BATCH_SIZE - 1) // BATCH_SIZE

            logger.info(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} articles)...")

            for article in batch:
                await asyncio.sleep(INTER_ARTICLE_DELAY)

                sift_result = sift_article(article)
                article["_sifter"] = sift_result

                result, was_rate_limited = await _classify_with_retry_v2(article)

                if was_rate_limited:
                    rate_limit_hits += 1

                if result is None:
                    raw_doc = _make_raw_doc(article)
                    await intelligence_col.insert_one(raw_doc)
                    fail_count += 1
                elif result.get("is_relevant", True):
                    sifter_boost = sift_result.get("boost_score", 0)
                    result["priority_score"] = min(100, result.get("priority_score", 30) + sifter_boost)
                    result["sifter_level"] = sift_result["level"]
                    result["sifter_triggers"] = sift_result["triggers"]

                    if result.get("entities"):
                        ents = result["entities"]
                        relationships = []
                        for person in (ents.get("persons") or [])[:3]:
                            for loc in (ents.get("locations") or [])[:3]:
                                relationships.append({
                                    "actor": person, "location": loc,
                                    "context": result.get("threat_category", ""),
                                    "date": result.get("published_at", "")
                                })
                        for org in (ents.get("organizations") or [])[:3]:
                            for loc in (ents.get("locations") or [])[:3]:
                                relationships.append({
                                    "actor": org, "location": loc,
                                    "context": result.get("threat_category", ""),
                                    "date": result.get("published_at", "")
                                })
                        if relationships:
                            result["relationships"] = relationships[:10]

                    item = IntelligenceItem(**result)
                    doc = item.model_dump()
                    await intelligence_col.insert_one(doc)
                    success_count += 1
                    invalidate_stats_cache()

                    try:
                        from embedding_service import generate_embedding
                        emb_text = f"{doc.get('title', '')}. {doc.get('ai_summary', '')}"
                        emb = await generate_embedding(emb_text)
                        if emb:
                            await intelligence_col.update_one(
                                {"id": doc["id"]},
                                {"$set": {"embedding": emb}}
                            )
                    except Exception as emb_err:
                        logger.debug(f"Embedding generation skipped: {emb_err}")

                    try:
                        from keyword_engine import adaptive_feedback
                        await adaptive_feedback(db, article, result)
                    except Exception as af_err:
                        logger.debug(f"Adaptive feedback skipped: {af_err}")

                    try:
                        ws_msg = {
                            "type": "new_item",
                            "item": {
                                "id": doc.get("id"),
                                "title": doc.get("title"),
                                "severity": doc.get("severity"),
                                "priority_score": doc.get("priority_score", 0),
                                "confidence_score": doc.get("confidence_score", 70),
                                "threat_trajectory": doc.get("threat_trajectory", "INDETERMINATE"),
                                "state": doc.get("state"),
                                "source": doc.get("source"),
                                "threat_category": doc.get("threat_category"),
                                "published_at": doc.get("published_at"),
                                "ai_summary": doc.get("ai_summary", "")[:200],
                            }
                        }
                        if sift_result["level"] == 2 or doc.get("severity") in ("critical", "high"):
                            ws_msg["type"] = "elite_alert"
                            ws_msg["sifter_triggers"] = sift_result["triggers"]
                        await ws_manager.broadcast(ws_msg)
                    except Exception as ws_err:
                        logger.debug(f"WS broadcast error: {ws_err}")
                else:
                    skip_count += 1

            if batch_start + BATCH_SIZE < len(new_articles):
                pause_time = BATCH_PAUSE * 2 if rate_limit_hits > 2 else BATCH_PAUSE
                logger.info(f"  Batch {batch_num} done. Success: {success_count}, Failed: {fail_count}. "
                            f"Pausing {pause_time}s...")
                await asyncio.sleep(pause_time)

        logger.info("=== Fetch cycle complete ===")
        logger.info(f"  Processed: {success_count} | Failed: {fail_count} | Not relevant: {skip_count}")
        logger.info(f"  Duplicates skipped: {skipped} | Filtered out: {filter_rejected} | Translated: {translated_count}")
        logger.info(f"  Rate limit hits: {rate_limit_hits}")

        scan_status["is_scanning"] = False
        scan_status["progress"] = 100
        scan_status["current_source"] = ""
        scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        scan_status["last_scan_result"] = {
            "feeds_scanned": scan_status["total_sources"],
            "total_articles": len(articles),
            "new_relevant": success_count,
            "duplicates_skipped": skipped,
            "filtered_out": filter_rejected,
            "translated": translated_count,
            "failed": fail_count,
            "not_relevant": skip_count
        }

        try:
            from pattern_engine import detect_patterns
            asyncio.create_task(detect_patterns(db))
        except Exception as e:
            logger.warning(f"Pattern detection trigger failed: {e}")

        try:
            await ws_manager.broadcast({
                "type": "scan_complete",
                "result": scan_status["last_scan_result"]
            })
        except Exception:
            pass

    except Exception as e:
        logger.error(f"News fetch cycle failed: {e}")
        scan_status["is_scanning"] = False
        scan_status["progress"] = 100
        scan_status["current_source"] = ""
        scan_status["last_scan_at"] = datetime.now(timezone.utc).isoformat()
        scan_status["last_scan_result"] = {"error": str(e)}


async def _classify_with_retry(article, max_retries=3):
    result, _ = await _classify_with_retry_v2(article, max_retries)
    return result


async def _classify_with_retry_v2(article, max_retries=4):
    """
    Classify an article via Claude with exponential back-off on failure.

    NOTE: classify_and_analyze_article is already async — we call it directly
    on the running event loop.  The old asyncio.to_thread(_sync_classify)
    pattern created a *new* event loop in a worker thread, which broke the
    AsyncAnthropic singleton (bound to the main loop) causing silent failures.
    """
    from ai_pipeline import classify_and_analyze_article

    RATE_LIMIT_INDICATORS = ['rate', '429', 'limit', 'quota', 'too many', 'throttle']
    was_rate_limited = False

    for attempt in range(max_retries):
        try:
            result = await asyncio.wait_for(
                classify_and_analyze_article(article),
                timeout=90,
            )
            return result, was_rate_limited

        except asyncio.TimeoutError:
            wait = 5 * (2 ** attempt)
            logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] Timeout for: "
                           f"{article.get('title', '')[:40]}... retrying in {wait}s")
            await asyncio.sleep(wait)

        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(ind in err_str for ind in RATE_LIMIT_INDICATORS)
            if is_rate_limit:
                was_rate_limited = True
                wait = 15 * (2 ** attempt)
                logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] RATE LIMIT for: "
                               f"{article.get('title', '')[:40]}... backing off {wait}s")
            else:
                wait = 3 * (2 ** attempt)
                logger.warning(f"  [Attempt {attempt + 1}/{max_retries}] Error ({str(e)[:80]}) for: "
                               f"{article.get('title', '')[:40]}... retrying in {wait}s")
            await asyncio.sleep(wait)

    logger.error(f"  All {max_retries} retries exhausted for: {article.get('title', '')[:50]}")
    return None, was_rate_limited


def _make_raw_doc(article):
    return {
        "id": str(uuid.uuid4()),
        "title": article.get("title", ""),
        "source": article.get("source", "Unknown"),
        "source_url": article.get("source_url", ""),
        "published_at": article.get("published_at", datetime.now(timezone.utc).isoformat()),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw_content": article.get("raw_content", "")[:5000],
        "ai_summary": article.get("raw_content", "")[:200],
        "why_it_matters": "Pending AI analysis.",
        "potential_impact": "Assessment pending.",
        "attention_level": "Monitor",
        "state": "",
        "threat_category": "",
        "severity": "low",
        "is_cross_border": article.get("region", "") in ("Bangladesh", "Myanmar"),
        "countries_involved": [article["region"]] if article.get("region") in ("Bangladesh", "Myanmar") else [],
        "processed": False,
        "tags": ["unprocessed"]
    }


async def bulk_scrape_all_feeds():
    from rss_fetcher import fetch_all_feeds

    logger.info("=" * 60)
    logger.info("=== BULK SCRAPE: Fetching ALL articles from RSS feeds ===")
    logger.info("=" * 60)

    try:
        articles = await fetch_all_feeds()
        logger.info(f"Fetched {len(articles)} total articles from RSS feeds")

        new_articles = []
        for article in articles:
            url = article.get("source_url", "")
            if not url:
                continue
            existing = await intelligence_col.find_one({"source_url": url}, {"_id": 1})
            if not existing:
                new_articles.append(article)

        skipped = len(articles) - len(new_articles)
        logger.info(f"Deduplication: {skipped} already in DB, {len(new_articles)} new articles to store")

        if not new_articles:
            logger.info("No new articles to store. Bulk scrape complete.")
            return {"stored": 0, "skipped": skipped, "total_fetched": len(articles)}

        stored_count = 0
        for article in new_articles:
            raw_doc = _make_raw_doc(article)
            await intelligence_col.insert_one(raw_doc)
            stored_count += 1

            if stored_count % 50 == 0:
                logger.info(f"  Stored {stored_count}/{len(new_articles)} articles...")

        logger.info("=" * 60)
        logger.info("=== BULK SCRAPE COMPLETE ===")
        logger.info(f"  Stored: {stored_count} new articles (unprocessed)")
        logger.info(f"  Skipped: {skipped} duplicates")
        logger.info(f"  Total in DB: {await intelligence_col.count_documents({})}")
        logger.info(f"  Pending AI processing: {await intelligence_col.count_documents({'processed': False})}")
        logger.info("=" * 60)
        logger.info("Articles will be AI-processed gradually via scheduled retries (every 15 min)")

        return {"stored": stored_count, "skipped": skipped, "total_fetched": len(articles)}

    except Exception as e:
        logger.error(f"Bulk scrape failed: {e}")
        raise


async def analyze_unprocessed_items():
    MAX_RETRY_PER_CYCLE = 25  # 25 items/15min = 100/hr — keeps up with normal ingestion without burning tokens
    INTER_ARTICLE_DELAY = 2.5

    # Sort NEWEST first so today's news is always classified before old backlog items.
    # Without this sort, MongoDB returns items in insertion order (oldest first),
    # meaning a 3000-item backlog would hide all fresh articles for days.
    unprocessed = await intelligence_col.find(
        {"processed": False}, {"_id": 0}
    ).sort("published_at", -1).limit(MAX_RETRY_PER_CYCLE).to_list(MAX_RETRY_PER_CYCLE)

    if not unprocessed:
        logger.info("No unprocessed items to retry.")
        return

    total_unprocessed = await intelligence_col.count_documents({"processed": False})
    logger.info(f"=== AI Processing Cycle: {len(unprocessed)}/{total_unprocessed} unprocessed items ===")

    success = 0
    not_relevant = 0
    rate_limit_hits = 0

    for idx, item in enumerate(unprocessed):
        await asyncio.sleep(INTER_ARTICLE_DELAY)
        result, was_rate_limited = await _classify_with_retry_v2(item, max_retries=3)

        if was_rate_limited:
            rate_limit_hits += 1
            if rate_limit_hits >= 3:
                logger.warning(f"  Hit {rate_limit_hits} rate limits, stopping retry cycle early. "
                               f"Will continue in next cycle.")
                break

        if result and result.get("is_relevant", True):
            update_fields = {k: v for k, v in result.items() if k != "_id"}
            update_fields["processed"] = True
            update_fields.pop("is_relevant", None)

            # Real-time fusion: check for duplicates before saving
            try:
                from fusion_engine import find_and_merge_cluster
                merged = await find_and_merge_cluster(db, {**item, **update_fields})
                # Copy cluster fields if fusion found a match
                for fkey in ("cluster_id", "is_cluster_primary", "cluster_sources", "cluster_size"):
                    if fkey in merged:
                        update_fields[fkey] = merged[fkey]
            except Exception as e:
                logger.warning(f"Real-time fusion failed for {item.get('id','')}: {e}")

            await intelligence_col.update_one(
                {"id": item["id"]},
                {"$set": update_fields}
            )
            success += 1
        elif result and not result.get("is_relevant", True):
            await intelligence_col.update_one(
                {"id": item["id"]},
                {"$set": {"processed": True, "tags": ["not_relevant"]}}
            )
            not_relevant += 1

        if (idx + 1) % 5 == 0:
            logger.info(f"  Progress: {idx + 1}/{len(unprocessed)} | Success: {success} | Not relevant: {not_relevant}")

    remaining = total_unprocessed - success - not_relevant
    logger.info("=== AI Processing Complete ===")
    logger.info(f"  Processed: {success} relevant | {not_relevant} not relevant")
    logger.info(f"  Remaining unprocessed: {remaining}")
    logger.info(f"  Rate limit hits: {rate_limit_hits}")


# Scheduler wrappers
async def fetch_grassroots_sources():
    from rss_fetcher import get_sources_by_priority
    grassroots = get_sources_by_priority("grassroots")
    logger.info(f"=== Grassroots fetch: {len(grassroots)} sources ===")
    await fetch_and_process_news(source_filter="grassroots")


async def fetch_established_sources():
    from rss_fetcher import get_sources_by_priority
    established = get_sources_by_priority("established")
    logger.info(f"=== Established fetch: {len(established)} sources ===")
    await fetch_and_process_news(source_filter="established")


async def run_embedding_backfill():
    try:
        from embedding_service import backfill_embeddings
        count = await backfill_embeddings(db, 30)
        logger.info(f"Embedding backfill: {count} items processed")
    except Exception as e:
        logger.warning(f"Embedding backfill failed: {e}")
