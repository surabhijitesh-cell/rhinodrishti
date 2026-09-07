"""
User Activity endpoints (admin-only): Currently Online + date-range Activity
Report (JSON + PDF), backing the User Management > Activity tab.
"""
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from utils.auth import require_admin_role
from user_activity import get_online_sessions, build_activity_report

router = APIRouter()


@router.get("/admin/user-activity/online")
async def currently_online(admin: dict = Depends(require_admin_role)):
    sessions = await get_online_sessions()
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/admin/user-activity/report")
async def activity_report(
    date_from: str = Query(..., description="ISO date, e.g. 2026-09-01"),
    date_to: str = Query(..., description="ISO date, e.g. 2026-09-07"),
    admin: dict = Depends(require_admin_role),
):
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to")
    return await build_activity_report(date_from, date_to)


def _ascii(s) -> str:
    """fpdf2 default fonts are Latin-1 — strip non-encodable chars."""
    if not s:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _render_report_pdf(report: dict) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "RHINO DRISHTI - User Activity Report", **NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, _ascii(f"Period: {report['date_from']} to {report['date_to']}"), **NL)
    pdf.cell(0, 6, _ascii(f"Generated: {report['generated_at'][:19].replace('T', ' ')} UTC"), **NL)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    if not report["users"]:
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 8, "No user activity recorded in this period.", **NL)
        return bytes(pdf.output())

    for u in report["users"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(230, 240, 220)
        pdf.cell(0, 8, _ascii(u["username"]), fill=True, **NL)

        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, _ascii(
            f"Logins: {u['login_count']}   "
            f"Relevance ratings: {u['relevance_ratings_given']}   "
            f"Manual uploads: {u['manual_uploads']}   "
            f"Training actions: {u['training_actions']}"
        ), **NL)

        if u["sessions"]:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_x(pdf.l_margin)
            pdf.cell(55, 5.5, "Login", border="B")
            pdf.cell(55, 5.5, "Logout", border="B")
            pdf.cell(30, 5.5, "Duration (min)", border="B")
            pdf.cell(40, 5.5, "IP Address", border="B", **NL)
            pdf.set_font("Helvetica", "", 8)
            for s in u["sessions"]:
                logout_display = s["logout_at"][:19].replace("T", " ") if s["logout_at"] else "still active"
                pdf.set_x(pdf.l_margin)
                pdf.cell(55, 5.5, _ascii((s["login_at"] or "")[:19].replace("T", " ")))
                pdf.cell(55, 5.5, _ascii(logout_display))
                pdf.cell(30, 5.5, _ascii(s["duration_minutes"]))
                pdf.cell(40, 5.5, _ascii(s["ip_address"]), **NL)
        pdf.ln(3)

    return bytes(pdf.output())


@router.get("/admin/user-activity/report/pdf")
async def activity_report_pdf(
    date_from: str = Query(...),
    date_to: str = Query(...),
    admin: dict = Depends(require_admin_role),
):
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must not be after date_to")
    report = await build_activity_report(date_from, date_to)
    try:
        pdf_bytes = _render_report_pdf(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF render error: {type(e).__name__}: {e}")
    filename = f"user_activity_{date_from}_to_{date_to}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
