"""Role and IOD access checks shared by routers (kept out of utils/auth.py)."""
from fastapi import Depends, HTTPException

from utils.auth import get_current_user


async def require_analyst_or_admin(user: dict = Depends(get_current_user)) -> dict:
    """Refuse viewers: used on actions that spend money or change/delete data."""
    if user.get("role") not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="Analyst or admin role required")
    return user


def user_iod(user: dict) -> str:
    from iod_registry import resolve_user_iod
    return user.get("iod") or resolve_user_iod(user.get("username", ""))


def can_access_faultline(user: dict, faultline: dict) -> bool:
    """Admins see everything; IOD-1 (no filter) sees everything; others see
    their IOD's watchlist plus custom faultlines they made or tagged to their IOD."""
    if user.get("role") == "admin":
        return True
    from iod_registry import get_iod_faultline_ids
    iod = user_iod(user)
    allowed = get_iod_faultline_ids(iod)
    if allowed is None or faultline.get("id") in allowed:
        return True
    if faultline.get("created_by") and faultline.get("created_by") == user.get("username"):
        return True
    return bool(faultline.get("iod")) and faultline.get("iod") == iod
