"""Switches for the cheaper-model routes. Both start OFF and are turned on only
after the model trial has been reviewed (db.admin_settings key "model_routing")."""
import time

FIRST_PASS_MODEL = "google/gemini-2.5-flash-lite"
STAGE1_MODEL = "google/gemini-2.5-flash-lite"
# Items the cheap first pass scores at or above this go on to the full model.
FULL_MODEL_FROM_SCORE = 60
# The trial and the first pass send at most this much article text.
FIRST_PASS_CONTENT_CHARS = 1200

DEFAULTS = {"stage1_on_news": False, "two_step_scoring": False}
_cache = {"at": 0.0, "value": dict(DEFAULTS)}
_TTL_S = 300


async def get_routing(db) -> dict:
    """Current switches, cached for 5 minutes; defaults (all off) on any error."""
    if time.time() - _cache["at"] < _TTL_S:
        return _cache["value"]
    value = dict(DEFAULTS)
    try:
        doc = await db.admin_settings.find_one({"key": "model_routing"}, {"_id": 0})
        if doc:
            value.update({k: bool(doc.get(k)) for k in DEFAULTS})
    except Exception:
        pass
    _cache.update(at=time.time(), value=value)
    return value


def clear_cache() -> None:
    _cache["at"] = 0.0
