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
    """Same visual identity as the Daily/Monthly/Fortnightly briefs (dark
    header/footer bar, lime accent, cream section bands, bordered tables) —
    see brief_monthly.py's _render_pdf for the reference implementation this
    mirrors."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    # ── Palette — identical to brief_monthly.py ──────────────────────────────
    C_BG       = (30,  35,  25)
    C_ACCENT   = (180, 220, 80)
    C_SEC_BG   = (230, 240, 220)
    C_SEC_TEXT = (50,  60,  40)
    C_TBL_HDR  = (45,  65,  40)
    C_TBL_ALT  = (245, 248, 242)

    date_from, date_to = report["date_from"], report["date_to"]
    period_label = f"{date_from} to {date_to}"
    gen_ts = report.get("generated_at", "")[:19].replace("T", " ")

    class ActivityPDF(FPDF):
        def header(self):
            self.set_fill_color(*C_BG)
            self.rect(0, 0, 210, 28, "F")
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*C_ACCENT)
            self.set_y(4)
            self.cell(0, 8, "RHINO DRISHTI", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(160, 170, 150)
            self.cell(0, 4, "NER INTELLIGENCE PLATFORM  |  USER ACTIVITY REPORT", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 7)
            self.cell(0, 4, _ascii(f"Classification: RESTRICTED  |  Period: {period_label}  |  Generated: {gen_ts} UTC"), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_y(32)

        def footer(self):
            self.set_y(-12)
            self.set_fill_color(*C_BG)
            self.rect(0, self.h - 12, 210, 12, "F")
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*C_ACCENT)
            self.cell(0, 10, _ascii(f"Rhino Drishti User Activity Report | {period_label} | Page {self.page_no()}/{{nb}} | RESTRICTED"), align="C")

        def section_title(self, title):
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*C_SEC_TEXT)
            self.set_fill_color(*C_SEC_BG)
            self.cell(0, 8, _ascii(f"  {title}"), fill=True, **NL)
            self.ln(2)

    pdf = ActivityPDF()
    pdf.alias_nb_pages()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def draw_session_table(sessions):
        headers = ["Login", "Logout", "Duration (min)", "IP Address"]
        col_ws = [50, 50, 30, 50]
        pdf.set_fill_color(*C_TBL_HDR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        for j, (h, w) in enumerate(zip(headers, col_ws)):
            kw = NL if j == len(headers) - 1 else {}
            pdf.cell(w, 6, h, fill=True, border=1, **kw)
        for i, s in enumerate(sessions):
            if pdf.get_y() > 265:
                pdf.add_page()
            logout_display = s["logout_at"][:19].replace("T", " ") if s["logout_at"] else "still active"
            row = [
                (s["login_at"] or "")[:19].replace("T", " "),
                logout_display,
                s["duration_minutes"],
                s["ip_address"],
            ]
            pdf.set_fill_color(*C_TBL_ALT if i % 2 == 0 else (255, 255, 255))
            pdf.set_text_color(40, 40, 40)
            pdf.set_font("Helvetica", "", 7)
            for j, (v, w) in enumerate(zip(row, col_ws)):
                kw = NL if j == len(row) - 1 else {}
                pdf.cell(w, 5.5, _ascii(str(v)), fill=True, border=1, **kw)

    if not report["users"]:
        pdf.section_title("No user activity recorded in this period")
        return bytes(pdf.output())

    for u in report["users"]:
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.section_title(u["username"])

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*C_SEC_TEXT)
        pdf.cell(0, 6, _ascii(
            f"Logins: {u['login_count']}   "
            f"Relevance ratings: {u['relevance_ratings_given']}   "
            f"Manual uploads: {u['manual_uploads']}   "
            f"Training actions: {u['training_actions']}"
        ), **NL)
        pdf.ln(1)

        if u["sessions"]:
            draw_session_table(u["sessions"])
        pdf.ln(4)

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
