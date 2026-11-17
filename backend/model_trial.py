"""Model trial: re-scores a sample of stored items with the cheaper models and
compares with what the current model decided. Read-only on intelligence_items;
progress and results go to db.model_trials. Calls here are tagged in the usage
widget as their own feature (model_trial__*)."""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from model_routing import FIRST_PASS_MODEL, FULL_MODEL_FROM_SCORE, FIRST_PASS_CONTENT_CHARS

logger = logging.getLogger(__name__)

DEFAULT_N = 300
MAX_N = 400
STALE_AFTER = timedelta(hours=2)
SLEEP_S = 0.3
HIGH = ("critical", "high")
RETRY_KINDS = ("social", "youtube", "telegram")
# Rough flash-lite prices (USD per million tokens) for the cost estimate.
_IN_PER_M, _OUT_PER_M = 0.10, 0.40


def can_start(latest: dict | None, now: datetime) -> tuple[bool, bool]:
    """(allowed, mark_stale_failed). One trial at a time; a run older than 2 h is dead."""
    if not latest or latest.get("status") != "running":
        return True, False
    started = latest.get("started_at")
    if isinstance(started, datetime) and now - started > STALE_AFTER:
        return True, True
    return False, False


def severity_of(score) -> str:
    s = score if isinstance(score, (int, float)) else 0
    return "critical" if s >= 80 else "high" if s >= 60 else "medium" if s >= 40 else "low"


def _examples(rows: list, k: int = 15) -> list:
    return [r.get("title", "")[:140] for r in rows[:k]]


def summarise(results: list) -> dict:
    ok = [r for r in results if not r.get("error")]
    by_sev: dict = {}
    for r in ok:
        by_sev[r["stored_severity"]] = by_sev.get(r["stored_severity"], 0) + 1

    # A pre-filter failure answers "keep"; count those apart so a broken filter can't look safe.
    stage1_failed = [r for r in ok if str(r.get("stage1_reason", "")).startswith("stage1_")]
    rejected = [r for r in ok if r.get("stage1_relevant") is False]
    rejected_high = [r for r in rejected if r["stored_severity"] in HIGH]

    confusion: dict = {}
    for r in ok:
        key = f'{r["stored_severity"]}->{r["first_pass_severity"]}'
        confusion[key] = confusion.get(key, 0) + 1

    stored_high = [r for r in ok if r["stored_severity"] in HIGH]
    missed = [r for r in stored_high if r["first_pass_priority"] < FULL_MODEL_FROM_SCORE]
    to_full = [r for r in ok if r["first_pass_priority"] >= FULL_MODEL_FROM_SCORE]
    n_ok = len(ok)
    return {
        "scored": n_ok,
        "errors": len(results) - n_ok,
        "stored_by_severity": by_sev,
        "stage1": {
            "would_reject": len(rejected),
            "filter_failed": len(stage1_failed),
            "of_which_critical_high": len(rejected_high),
            "examples": _examples(rejected_high),
        },
        "first_pass": {
            "confusion": confusion,
            "stored_critical_high": len(stored_high),
            "critical_high_kept_pct": round(100 * (1 - len(missed) / len(stored_high)), 1) if stored_high else None,
            "critical_high_missed": len(missed),
            "missed_examples": _examples(missed),
            "share_to_full_model_pct": round(100 * len(to_full) / n_ok, 1) if n_ok else None,
        },
    }


def estimate_cost_usd(done: int) -> float:
    # ~7k-token prompt + 1.2k chars of article, ~600 tokens out; plus the small pre-filter call.
    per_item = (7500 + 400) * _IN_PER_M / 1e6 + 600 * _OUT_PER_M / 1e6 + (500 * _IN_PER_M + 60 * _OUT_PER_M) / 1e6
    return round(done * per_item, 3)


async def _sample(db, n: int) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    # published_at, not fetched_at: older social items were stored without fetched_at.
    base = {"processed": True, "published_at": {"$gte": cutoff}, "title": {"$nin": [None, ""]}}
    third = max(n // 3, 1)
    seen, out = set(), []

    async def take(extra: dict, k: int):
        pipe = [{"$match": {**base, **extra}}, {"$sample": {"size": k * 2}}]
        async for d in db.intelligence_items.aggregate(pipe):
            if len(out) >= n:
                return
            key = str(d.get("id") or d.get("_id"))
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
            k -= 1
            if k <= 0:
                return

    await take({"severity": {"$in": list(HIGH)}}, third)
    await take({"severity": {"$in": ["medium", "low"]}}, third)
    await take({"source_type": {"$in": list(RETRY_KINDS)}}, n - len(out))
    return out[:n]


async def _score_item(d: dict) -> dict:
    from ai_pipeline import classify_once
    import cheap_classifier
    row = {
        "id": str(d.get("id") or d.get("_id")), "title": d.get("title", ""),
        "source_type": d.get("source_type", ""),
        "stored_severity": d.get("severity", "low"), "stored_priority": d.get("priority_score"),
    }
    try:
        s1 = await cheap_classifier.cheap_filter(d)
        row["stage1_relevant"] = bool(s1.get("relevant", True))
        row["stage1_reason"] = s1.get("reason", "")
        res = await classify_once(d, FIRST_PASS_MODEL, FIRST_PASS_CONTENT_CHARS)
        score = res.get("priority_score", 0)
        row["first_pass_priority"] = score
        row["first_pass_severity"] = severity_of(score)
        row["would_go_to_full_model"] = score >= FULL_MODEL_FROM_SCORE
    except Exception as e:  # one bad item must not stop the trial
        row["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return row


async def run_trial(db, n: int = DEFAULT_N, trial_id: str | None = None) -> str:
    n = max(1, min(int(n), MAX_N))
    tid = trial_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.model_trials.update_one(
        {"id": tid},
        {"$set": {"id": tid, "started_at": now, "finished_at": None, "status": "running",
                  "n": n, "done_count": 0, "results": [], "summary": None}},
        upsert=True)
    try:
        items = await _sample(db, n)
        results: list = []
        for i, d in enumerate(items, 1):
            results.append(await _score_item(d))
            if i % 10 == 0 or i == len(items):
                await db.model_trials.update_one({"id": tid}, {"$set": {"done_count": i, "results": results}})
            await asyncio.sleep(SLEEP_S)
        summary = summarise(results)
        summary["estimated_cost_usd"] = estimate_cost_usd(len(results))
        await db.model_trials.update_one({"id": tid}, {"$set": {
            "status": "done", "finished_at": datetime.now(timezone.utc),
            "n": len(results), "done_count": len(results), "results": results, "summary": summary}})
    except Exception as e:
        logger.error(f"model trial failed: {e}")
        await db.model_trials.update_one({"id": tid}, {"$set": {
            "status": "failed", "finished_at": datetime.now(timezone.utc), "error": str(e)[:200]}})
    return tid
