import feedparser
import logging
import asyncio
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ============================================================
# RSS SOURCES - Comprehensive list for NER intelligence monitoring
# ============================================================

RSS_SOURCES = [
    # ---- REGIONAL NER SOURCES (English) ----
    {"name": "NE Now", "url": "https://nenow.in/feed", "category": "regional", "language": "en", "region": "NER"},
    {"name": "The Sentinel Assam", "url": "https://sentinelassam.com/feed", "category": "regional", "language": "en", "region": "NER"},
    {"name": "The Assam Tribune", "url": "https://assamtribune.com/feed", "category": "regional", "language": "en", "region": "NER"},
    {"name": "Assam Times", "url": "https://assamtimes.org/rss.xml", "category": "regional", "language": "en", "region": "NER"},
    {"name": "EastMojo", "url": "https://www.eastmojo.com/feed/", "category": "regional", "language": "en", "region": "NER"},
    {"name": "North East Live", "url": "https://northeastlivetv.com/feed/", "category": "regional", "language": "en", "region": "NER"},

    # ---- INDIAN NATIONAL SOURCES ----
    {"name": "The Hindu - National", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "category": "national", "language": "en", "region": "India"},
    {"name": "The Hindu - International", "url": "https://www.thehindu.com/news/international/feeder/default.rss", "category": "national", "language": "en", "region": "India"},
    {"name": "Indian Express - North East", "url": "https://indianexpress.com/section/north-east-india/feed/", "category": "national", "language": "en", "region": "NER"},
    {"name": "NDTV India News", "url": "https://feeds.feedburner.com/ndtvnews-india-news", "category": "national", "language": "en", "region": "India"},
    {"name": "Times of India", "url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "category": "national", "language": "en", "region": "India"},
    {"name": "PIB Press Releases", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "category": "government", "language": "en", "region": "India"},
    {"name": "News18 India", "url": "https://www.news18.com/rss/india.xml", "category": "national", "language": "en", "region": "India"},

    # ---- INTERNATIONAL SOURCES ----
    {"name": "BBC Asia/India", "url": "http://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "category": "international", "language": "en", "region": "International"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "international", "language": "en", "region": "International"},
    {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best", "category": "international", "language": "en", "region": "International"},

    # ---- BANGLADESH SOURCES ----
    {"name": "Prothom Alo (Bangla)", "url": "https://www.prothomalo.com/feed/", "category": "bangladesh", "language": "bn", "region": "Bangladesh"},
    {"name": "Prothom Alo (English)", "url": "https://en.prothomalo.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh"},
    {"name": "The Daily Star BD", "url": "https://www.thedailystar.net/frontpage/rss.xml", "category": "bangladesh", "language": "en", "region": "Bangladesh"},
    {"name": "Kaler Kantho (Bangla)", "url": "https://www.kalerkantho.com/rss.xml", "category": "bangladesh", "language": "bn", "region": "Bangladesh"},
    {"name": "Jugantor (Bangla)", "url": "https://www.jugantor.com/feed/rss.xml", "category": "bangladesh", "language": "bn", "region": "Bangladesh"},

    # ---- MYANMAR SOURCES ----
    {"name": "The Irrawaddy", "url": "https://www.irrawaddy.com/feed", "category": "myanmar", "language": "en", "region": "Myanmar"},
    {"name": "Mizzima News", "url": "https://www.mizzima.com/rss.xml", "category": "myanmar", "language": "en", "region": "Myanmar"},
    {"name": "Myanmar Now", "url": "https://myanmar-now.org/en/feed", "category": "myanmar", "language": "en", "region": "Myanmar"},
    {"name": "Frontier Myanmar", "url": "https://frontiermyanmar.net/en/feed", "category": "myanmar", "language": "en", "region": "Myanmar"},
]

# ============================================================
# NER + Border Keywords (English, Bengali, Assamese transliterated)
# ============================================================

NER_KEYWORDS_EN = [
    # NER States & Cities
    "assam", "meghalaya", "mizoram", "manipur", "arunachal", "tripura",
    "nagaland", "sikkim", "northeast india", "north east india", "north-east",
    "guwahati", "shillong", "imphal", "itanagar", "agartala", "aizawl",
    "dimapur", "kohima", "tinsukia", "dibrugarh", "jorhat", "silchar",
    "tezpur", "bongaigaon", "kokrajhar", "barpeta", "goalpara", "lumding",
    "churachandpur", "ukhrul", "champhai", "moreh", "dawki", "tawang",
    "changlang", "tirap", "dhalai", "jaintia",

    # Security Terms
    "insurgent", "insurgency", "militant", "militancy", "separatist",
    "ulfa", "nscn", "ndfb", "klo", "hnlc", "nlft", "attf", "bnlf",
    "bodo", "meitei", "kuki", "naga", "chin", "rohingya",
    "ied", "ambush", "encounter", "ceasefire", "peace accord",
    "extortion", "kidnapping", "abduction",

    # Cross-border
    "myanmar", "bangladesh", "border", "bsf", "assam rifles",
    "cross-border", "infiltration", "illegal entry",
    "mcmahon line", "lac", "line of actual control",

    # Threat Categories
    "drug", "narcotics", "heroin", "methamphetamine", "opium", "poppy",
    "smuggling", "trafficking", "contraband",
    "arms", "weapons", "ammunition", "firearms",
    "immigration", "immigrant", "refugee", "deportation",
    "ethnic", "communal", "riot", "violence", "curfew", "tension",
    "cyber", "hack", "data breach",
    "infrastructure", "strategic", "military base", "airfield",
    "drone", "surveillance",

    # Bangladesh specific
    "dhaka", "chittagong", "sylhet", "rajshahi", "rohingya camp",
    "jamaat", "awami league", "bnp", "hasina", "yunus",
    "padma", "teesta", "brahmaputra",
    "bangladesh navy", "bangladesh army", "border guard bangladesh",
    "st martin", "bay of bengal", "chittagong port",

    # Myanmar specific
    "naypyidaw", "yangon", "mandalay", "rakhine", "chin state",
    "shan state", "kachin", "sagaing",
    "tatmadaw", "junta", "coup", "arakan army",
    "ethnic armed", "resistance", "pdf", "nug",
    "min aung hlaing", "suu kyi",

    # Foreign Power Influence (HIGH PRIORITY keywords)
    "china", "chinese", "beijing", "belt and road", "bri",
    "pakistan", "pakistani", "islamabad", "isi",
    "united states", "usa", "american", "washington",
    "chinese investment", "chinese loan", "chinese military",
    "pakistan influence", "pakistan support",
    "us aid", "us military", "quad", "indo-pacific",
    "deep sea port", "sonadia", "hambantota",
    "chinese base", "military cooperation",
]

# Bengali/Assamese transliterated keywords for local language sources
NER_KEYWORDS_LOCAL = [
    # Bengali (transliterated from Bangla newspapers)
    "সীমান্ত", "অনুপ্রবেশ", "মাদক", "চোরাচালান",
    "সন্ত্রাসী", "জঙ্গি", "রোহিঙ্গা", "শরণার্থী",
    "ত্রিপুরা", "মেঘালয়", "মিজোরাম", "মণিপুর", "অসম", "অরুণাচল",
    "বাংলাদেশ", "মিয়ানমার",
    "সংঘর্ষ", "দাঙ্গা", "হত্যা", "গ্রেপ্তার",
    "বিএসএফ",

    # Assamese transliterated
    "সীমা", "উগ্ৰপন্থী", "আলফা", "মাদক দ্ৰব্য",
    "অসম", "গুৱাহাটী", "তিনিচুকীয়া", "ডিব্ৰুগড়",
]

# Combine all keywords
ALL_KEYWORDS = NER_KEYWORDS_EN + NER_KEYWORDS_LOCAL

executor = ThreadPoolExecutor(max_workers=6)


def parse_feed(source: dict) -> list:
    """Parse a single RSS feed (blocking operation)"""
    try:
        feed = feedparser.parse(source["url"])
        articles = []

        for entry in feed.entries[:25]:
            title = entry.get("title", "")
            description = entry.get("description", "") or entry.get("summary", "")
            link = entry.get("link", "")

            # Parse published date
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                try:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    published_at = pub_dt.isoformat()
                except (ValueError, TypeError):
                    published_at = datetime.now(timezone.utc).isoformat()
            else:
                published_at = datetime.now(timezone.utc).isoformat()

            articles.append({
                "title": title,
                "source": source["name"],
                "source_url": link,
                "published_at": published_at,
                "raw_content": description[:5000],
                "description": description[:2000],
                "language": source.get("language", "en"),
                "category": source.get("category", "general"),
                "region": source.get("region", "Unknown"),
            })

        logger.info(f"Parsed {len(articles)} articles from {source['name']}")
        return articles

    except Exception as e:
        logger.error(f"Failed to parse {source['name']} ({source['url']}): {e}")
        return []


def is_ner_relevant(article: dict) -> bool:
    """Check if article is relevant to NER intelligence monitoring.
    
    For Bangladesh/Myanmar-specific feeds, all content is considered relevant
    since those feeds are specifically subscribed for border monitoring.
    For Indian national/international feeds, keyword matching is applied.
    """
    region = article.get("region", "")
    category = article.get("category", "")

    # All content from Bangladesh and Myanmar feeds is relevant
    if category in ("bangladesh", "myanmar") or region in ("Bangladesh", "Myanmar"):
        return True

    # All content from NER regional feeds is relevant
    if category == "regional" or region == "NER":
        return True

    # For national/international sources, apply keyword filtering
    text = f"{article.get('title', '')} {article.get('raw_content', '')}".lower()
    return any(kw in text for kw in ALL_KEYWORDS)


async def fetch_all_feeds(progress_callback=None) -> list:
    """Fetch and filter articles from all RSS sources"""
    loop = asyncio.get_event_loop()
    all_articles = []

    source_summary = {}
    for i, source in enumerate(RSS_SOURCES):
        source_name = source["name"]
        if progress_callback:
            await progress_callback(i, len(RSS_SOURCES), source_name)
        
        try:
            result = await loop.run_in_executor(executor, parse_feed, source)
        except Exception as e:
            logger.error(f"Feed fetch error for {source_name}: {e}")
            source_summary[source_name] = {"fetched": 0, "relevant": 0, "error": str(e)}
            continue
        
        relevant = [a for a in result if is_ner_relevant(a)]
        all_articles.extend(relevant)
        source_summary[source_name] = {"fetched": len(result), "relevant": len(relevant)}

    if progress_callback:
        await progress_callback(len(RSS_SOURCES), len(RSS_SOURCES), "Complete")

    logger.info(f"=== RSS Fetch Summary ===")
    for name, stats in source_summary.items():
        if "error" in stats:
            logger.info(f"  {name}: ERROR - {stats['error'][:80]}")
        else:
            logger.info(f"  {name}: {stats['fetched']} fetched, {stats['relevant']} relevant")
    logger.info(f"Total relevant articles: {len(all_articles)}")

    return all_articles
