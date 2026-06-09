"""
brief_pdf_style.py — shared visual identity for all Rhino Drishti PDFs.

Single source of truth for the palette, header/footer styling, ASCII text
sanitization, and section helpers used by:
  - Monthly Strategic Brief PDF (routers/brief_monthly.py)
  - Fortnightly Strategic Brief PDF (routers/brief_monthly.py via _render_pdf)
  - Faultline Analysis Report PDF (routers/faultlines.py)

Keeping the palette + BriefPDF class here means a single tweak updates every
PDF — no drift between the Monthly Brief and the Faultline Analysis report.
"""
from fpdf import FPDF
from fpdf.enums import XPos, YPos


# ── Palette (shared across all briefs) ────────────────────────────────────────
C_BG       = (30,  35,  25)
C_ACCENT   = (180, 220, 80)
C_SEC_BG   = (230, 240, 220)
C_SEC_TEXT = (50,  60,  40)
C_TBL_HDR  = (45,  65,  40)
C_TBL_ALT  = (245, 248, 242)

SEV_COLORS = {
    "critical": (200,  50,  50),
    "high":     (200, 100,  30),
    "medium":   (200, 170,  30),
    "low":      (100, 160,  60),
}

# Concern bands (faultline scoring). Higher = worse.
CONCERN_COLORS = {
    "CRITICAL": (200,  50,  50),   # red
    "ELEVATED": (200, 110,  30),   # amber
    "MONITOR":  (200, 170,  30),   # yellow
    "STABLE":   (100, 160,  60),   # green
}


# ── Layout helpers ────────────────────────────────────────────────────────────
NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}


def ascii_safe(s) -> str:
    """fpdf2 default fonts are Latin-1 only — strip non-encodable chars and
    replace common Unicode punctuation with ASCII equivalents."""
    if not s:
        return ""
    if isinstance(s, list):
        s = "; ".join(str(x) for x in s)
    elif not isinstance(s, str):
        s = str(s)
    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "…": "...", "•": "*",
        "​": "", " ": " ",
        "▲": "^", "▼": "v", "↑": "^", "↓": "v",
        "→": "->", "←": "<-",
        "Δ": "D", "δ": "d", "±": "+/-", "°": " deg",
    }
    for o, r in replacements.items():
        s = s.replace(o, r)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def concern_level(score: float) -> str:
    """Map a faultline score (0-100, higher=worse) to a concern band."""
    if score >= 75:
        return "CRITICAL"
    if score >= 55:
        return "ELEVATED"
    if score >= 35:
        return "MONITOR"
    return "STABLE"


# ── Shared PDF class — same header/footer for all briefs ──────────────────────
class BriefPDF(FPDF):
    """
    Branded PDF base. Subclasses or callers set:
      pdf.brief_type     — e.g. "MONTHLY STRATEGIC BRIEF", "FAULTLINE ANALYSIS REPORT"
      pdf.display_period — e.g. "June 2026"
      pdf.gen_ts         — ISO timestamp (truncated to YYYY-MM-DD HH:MM:SS)
    These default to placeholders if not set so the PDF still renders.
    """

    # Defaults — caller overrides via attribute assignment after construction.
    brief_type = "STRATEGIC BRIEF"
    display_period = ""
    gen_ts = ""

    def header(self) -> None:
        self.set_fill_color(*C_BG)
        self.rect(0, 0, 210, 28, "F")
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*C_ACCENT)
        self.set_y(4)
        self.cell(0, 8, "RHINO DRISHTI", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(160, 170, 150)
        self.cell(0, 4, f"NER INTELLIGENCE PLATFORM  |  {self.brief_type}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 7)
        self.cell(
            0, 4,
            ascii_safe(f"Classification: RESTRICTED  |  Period: {self.display_period}"
                       f"  |  Generated: {self.gen_ts}"),
            align="C", new_x="LMARGIN", new_y="NEXT",
        )
        self.set_y(32)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_fill_color(*C_BG)
        self.rect(0, self.h - 12, 210, 12, "F")
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*C_ACCENT)
        self.cell(
            0, 10,
            ascii_safe(f"Rhino Drishti Intel Brief | {self.display_period} | "
                       f"Page {self.page_no()}/{{nb}} | RESTRICTED"),
            align="C",
        )

    def section_title(self, title: str, sub: str = "") -> None:
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*C_SEC_TEXT)
        self.set_fill_color(*C_SEC_BG)
        label = f"  {title}" + (f"  |  {sub}" if sub else "")
        self.cell(0, 8, ascii_safe(label), fill=True, **NL)
        self.ln(2)

    def sub_band(self, text: str, fill_rgb=(50, 70, 45),
                 text_rgb=(255, 255, 255), height: float = 6) -> None:
        """Coloured sub-section band (used for state / PAOI headers)."""
        self.set_fill_color(*fill_rgb)
        self.set_text_color(*text_rgb)
        self.set_font("Helvetica", "B", 10)
        self.cell(0, height, ascii_safe(f"  {text}"), fill=True, **NL)

    def concern_pill(self, level: str, score: float | int | None,
                      width: float = 28, height: float = 5) -> None:
        """Draws a coloured pill: '92 CRITICAL' style. Caller positions cursor."""
        col = CONCERN_COLORS.get(level, (120, 120, 120))
        self.set_fill_color(*col)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 8)
        label = level if score is None else f"{int(round(score))} {level}"
        self.cell(width, height, ascii_safe(label), fill=True, align="C", **NL)


__all__ = [
    "BriefPDF",
    "NL",
    "ascii_safe",
    "concern_level",
    "C_BG", "C_ACCENT", "C_SEC_BG", "C_SEC_TEXT", "C_TBL_HDR", "C_TBL_ALT",
    "SEV_COLORS", "CONCERN_COLORS",
]
