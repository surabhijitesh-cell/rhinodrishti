"""
Watchlist router — per-user faultline priority rankings.

Endpoints:
  GET    /api/watchlist/me                    — current user's ranked list
  PUT    /api/watchlist/me                    — full-replace ranked list (max 10)
  DELETE /api/watchlist/me/{faultline_id}     — remove one entry
  PUT    /api/admin/watchlist/{username}       — admin override for any user
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shared import db
from utils.auth import get_current_user, require_admin_role

router = APIRouter()

watchlist_col = db.user_faultline_priorities
faultlines_col = db.faultlines


# ── Models ────────────────────────────────────────────────────────────────────
class WatchlistEntry(BaseModel):
    faultline_id: str
    rank: int = Field(..., ge=1, le=10)


class WatchlistPayload(BaseModel):
    entries: List[WatchlistEntry] = Field(..., max_length=10)


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _validate_and_replace(username: str, entries: List[WatchlistEntry]) -> dict:
    if len(entries) != len({e.rank for e in entries}):
        raise HTTPException(status_code=422, detail="Ranks must be unique")
    if len(entries) != len({e.faultline_id for e in entries}):
        raise HTTPException(status_code=422, detail="Duplicate faultline_id in payload")

    fl_ids = [e.faultline_id for e in entries]
    existing = {f["id"] async for f in faultlines_col.find({"id": {"$in": fl_ids}}, {"id": 1, "_id": 0})}
    unknown = [fid for fid in fl_ids if fid not in existing]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown faultline IDs: {unknown}")

    now = datetime.now(timezone.utc).isoformat()
    # Remove all existing entries for user then bulk-insert new ones
    await watchlist_col.delete_many({"username": username})
    if entries:
        docs = [
            {
                "username": username,
                "faultline_id": e.faultline_id,
                "rank": e.rank,
                "updated_at": now,
            }
            for e in entries
        ]
        await watchlist_col.insert_many(docs)

    return {"username": username, "count": len(entries)}


async def _get_populated(username: str) -> list:
    """Return ranked list with faultline docs attached, sorted by rank."""
    cursor = watchlist_col.find({"username": username}, {"_id": 0}).sort("rank", 1)
    entries = [e async for e in cursor]
    if not entries:
        return []

    fl_ids = [e["faultline_id"] for e in entries]
    fl_map = {}
    async for fl in faultlines_col.find({"id": {"$in": fl_ids}}, {"_id": 0}):
        fl_map[fl["id"]] = fl

    # Attach latest score
    from shared import db as _db
    scores_col = _db.faultline_scores
    pipeline = [
        {"$match": {"faultline_id": {"$in": fl_ids}}},
        {"$sort": {"date": -1}},
        {"$group": {"_id": "$faultline_id", "doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$project": {"_id": 0, "faultline_id": 1, "score": 1, "level": 1, "date": 1}},
    ]
    scores_map = {s["faultline_id"]: s async for s in scores_col.aggregate(pipeline)}

    result = []
    for e in entries:
        fid = e["faultline_id"]
        fl = fl_map.get(fid, {"id": fid, "name": fid, "state": ""})
        fl["latest_score"] = scores_map.get(fid)
        result.append({**e, "faultline": fl})
    return result


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("/watchlist/me")
async def get_my_watchlist(current_user: dict = Depends(get_current_user)):
    username = current_user["username"]
    return {"entries": await _get_populated(username)}


@router.put("/watchlist/me")
async def replace_my_watchlist(
    payload: WatchlistPayload,
    current_user: dict = Depends(get_current_user),
):
    result = await _validate_and_replace(current_user["username"], payload.entries)
    return {"status": "ok", **result}


@router.delete("/watchlist/me/{faultline_id}")
async def remove_from_my_watchlist(
    faultline_id: str,
    current_user: dict = Depends(get_current_user),
):
    res = await watchlist_col.delete_one(
        {"username": current_user["username"], "faultline_id": faultline_id}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found in watchlist")
    return {"status": "ok"}


@router.put("/admin/watchlist/{username}")
async def admin_override_watchlist(
    username: str,
    payload: WatchlistPayload,
    current_user: dict = Depends(require_admin_role),
):
    user = await db.users.find_one({"username": username}, {"_id": 0, "username": 1})
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    result = await _validate_and_replace(username, payload.entries)
    return {"status": "ok", **result}
