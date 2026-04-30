"""
Drishti Intelligence Fading Engine
====================================
Computes a time-decayed visibility_score for every intelligence item using
the formula:

    V(t) = P₀ × e^(−t / τ_s) × W_cb × W_fb × W_traj × W_flag

Where:
  P₀     = stored priority_score (AI judgement, 0–100, never mutated)
  t      = item age in hours
  τ_s    = severity-specific time constant (controls decay speed)
  W_cb   = cross-border / India-relevance weight
  W_fb   = analyst feedback weight
  W_traj = threat trajectory weight
  W_flag = special intelligence flags weight

Visibility thresholds:
  V ≥ 50   → full display (opacity 1.0)
  30–50    → slight fade  (opacity 0.80)
  15–30    → heavy fade   (opacity 0.55)
  V < 15   → archived     (hidden from default feed)

Run schedule: every hour via the scheduler in server.py.
"""

import math
import logging
from datetime import datetime, timezone
from shared import intelligence_col, db

logger = logging.getLogger(__name__)

# ─── Severity time constants (τ in hours) ────────────────────────────────────
# After t = τ hours, V falls to P₀/e ≈ 37% of its birth value.

TAU = {
    "critical": 1440,   # 60 days  — critical items persist longest
    "high":      720,   # 30 days
    "medium":    336,   # 14 days
    "low":        72,   #  3 days
}

# ─── Trajectory multipliers ───────────────────────────────────────────────────

TRAJ_WEIGHT = {
    "ESCALATING":    1.20,
    "NEW_THREAT":    1.15,
    "STABLE":        1.00,
    "INDETERMINATE": 0.95,
    "DE-ESCALATING": 0.85,
}

# ─── Visibility thresholds ────────────────────────────────────────────────────

def visibility_band(v: float) -> str:
    """Return display band for a visibility score."""
    if v >= 50:
        return "full"
    if v >= 30:
        return "fading"
    if v >= 15:
        return "dim"
    return "archived"


# ─── Core formula ─────────────────────────────────────────────────────────────

def compute_visibility(item: dict, now: datetime | None = None) -> float:
    """
    Compute the visibility score V(t) for a single intelligence item.

    Returns a float in [0, ~140] (can exceed 100 due to multipliers on a P₀=100 item,
    but in practice stays well under 120).  Callers should cap display at 100.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # ── Base score ────────────────────────────────────────────────────────────
    p0 = float(item.get("priority_score") or 50)

    # ── Age in hours ──────────────────────────────────────────────────────────
    published_at = item.get("published_at", "")
    try:
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        age_hours = max((now - pub_dt).total_seconds() / 3600, 0.0)
    except Exception:
        age_hours = 0.0  # treat as brand-new if unparseable

    # ── Time decay ────────────────────────────────────────────────────────────
    severity = (item.get("severity") or "low").lower()
    tau = TAU.get(severity, TAU["medium"])
    decay = math.exp(-age_hours / tau)

    # ── Cross-border / India-relevance weight  (1.00 → 1.45) ─────────────────
    w_cb = 1.0
    if item.get("is_cross_border"):
        w_cb += 0.25
    india_rel = float(item.get("india_relevance_score") or 0)
    w_cb += (india_rel / 20.0) * 0.20   # max +0.20 at full relevance (20/20)
    w_cb = min(w_cb, 1.45)

    # ── Analyst feedback weight  (0.70 → 1.30) ───────────────────────────────
    # analyst_rating is the average star rating (1–5) for this item, if any
    avg_rating = float(item.get("analyst_avg_rating") or 0)
    if avg_rating > 0:
        # map [1, 5] → [0.70, 1.30]
        w_fb = 0.70 + (avg_rating / 5.0) * 0.60
    else:
        w_fb = 1.0  # no feedback yet — neutral

    # ── Threat trajectory weight ──────────────────────────────────────────────
    traj = (item.get("threat_trajectory") or "INDETERMINATE").upper()
    w_traj = TRAJ_WEIGHT.get(traj, 1.0)

    # ── Special intelligence flags weight  (each +0.10, cap 1.40) ────────────
    flags = item.get("special_flags") or []
    w_flag = min(1.0 + 0.10 * len(flags), 1.40)

    # ── Final score ───────────────────────────────────────────────────────────
    v = p0 * decay * w_cb * w_fb * w_traj * w_flag
    return round(v, 2)


def score_breakdown(item: dict, now: datetime | None = None) -> dict:
    """
    Return a detailed breakdown of how V(t) was computed — useful for the
    Settings / debug panel.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    p0 = float(item.get("priority_score") or 50)
    published_at = item.get("published_at", "")
    try:
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        age_hours = max((now - pub_dt).total_seconds() / 3600, 0.0)
    except Exception:
        age_hours = 0.0

    severity = (item.get("severity") or "low").lower()
    tau = TAU.get(severity, TAU["medium"])
    decay = math.exp(-age_hours / tau)

    w_cb = 1.0
    if item.get("is_cross_border"):
        w_cb += 0.25
    india_rel = float(item.get("india_relevance_score") or 0)
    w_cb += (india_rel / 20.0) * 0.20
    w_cb = min(w_cb, 1.45)

    avg_rating = float(item.get("analyst_avg_rating") or 0)
    w_fb = (0.70 + (avg_rating / 5.0) * 0.60) if avg_rating > 0 else 1.0

    traj = (item.get("threat_trajectory") or "INDETERMINATE").upper()
    w_traj = TRAJ_WEIGHT.get(traj, 1.0)

    flags = item.get("special_flags") or []
    w_flag = min(1.0 + 0.10 * len(flags), 1.40)

    v = p0 * decay * w_cb * w_fb * w_traj * w_flag

    return {
        "visibility_score":    round(v, 2),
        "visibility_band":     visibility_band(v),
        "p0_priority":         p0,
        "age_hours":           round(age_hours, 1),
        "severity":            severity,
        "tau_hours":           tau,
        "decay_factor":        round(decay, 4),
        "w_cross_border":      round(w_cb, 3),
        "w_feedback":          round(w_fb, 3),
        "w_trajectory":        round(w_traj, 3),
        "w_special_flags":     round(w_flag, 3),
        "special_flags":       flags,
        "india_relevance":     india_rel,
        "trajectory":          traj,
        "avg_analyst_rating":  avg_rating,
    }


# ─── Batch job ────────────────────────────────────────────────────────────────

async def run_fading_pass(batch_size: int = 500) -> dict:
    """
    Hourly background job.  Recomputes visibility_score for recent processed
    items and marks fully-faded items as archived.

    Returns a summary dict with counts.
    """
    now = datetime.now(timezone.utc)
    stats = {"updated": 0, "archived": 0, "errors": 0}

    # Only recompute items that haven't been manually pinned
    query = {
        "processed": True,
        "pinned": {"$ne": True},          # pinned items never fade
    }

    cursor = intelligence_col.find(query, {
        "_id": 1, "id": 1, "priority_score": 1, "severity": 1,
        "published_at": 1, "is_cross_border": 1, "india_relevance_score": 1,
        "analyst_avg_rating": 1, "threat_trajectory": 1, "special_flags": 1,
    }).limit(batch_size)

    async for item in cursor:
        try:
            v = compute_visibility(item, now)
            band = visibility_band(v)

            update = {
                "$set": {
                    "visibility_score": v,
                    "visibility_band": band,
                    "visibility_updated_at": now.isoformat(),
                }
            }
            # Items that fall below threshold get soft-archived (not deleted)
            if band == "archived":
                update["$set"]["is_archived"] = True
                stats["archived"] += 1
            else:
                # Unarchive if they somehow get a boost (e.g. analyst rate up)
                update["$set"]["is_archived"] = False

            await intelligence_col.update_one({"_id": item["_id"]}, update)
            stats["updated"] += 1

        except Exception as e:
            logger.warning(f"Fading error on item {item.get('id')}: {e}")
            stats["errors"] += 1

    logger.info(
        f"Fading pass complete — updated:{stats['updated']} "
        f"archived:{stats['archived']} errors:{stats['errors']}"
    )
    return stats
