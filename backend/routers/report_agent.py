"""
report_agent.py — Chat-driven configurable intelligence report generation.

Admin-only. Commander describes the report they want via chat; the system
extracts a structured report_spec and generates a fully customized
narrative PDF (monthly or fortnightly), grounded in the actual intelligence
corpus and PAOI/faultline data.

Endpoints:
  POST   /report-agent/chat                — one chat turn; extracts/updates spec
  GET    /report-agent/specs               — list saved specs (latest 20)
  GET    /report-agent/specs/{id}          — get spec with conversation
  DELETE /report-agent/specs/{id}          — delete spec
  POST   /report-agent/generate            — generate report from spec + period
  GET    /report-agent/reports             — list generated reports
  GET    /report-agent/reports/{id}/pdf    — download PDF
"""

import io
import json
import logging
import uuid
from calendar import monthrange
from datetime import datetime, timezone
from typing import Optional

import paoi_brief
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from shared import db, intelligence_col
from llm_client import get_client, MODEL
from utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

specs_col = db.report_specs
agent_reports_col = db.agent_reports


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Report Agent is admin-only")
    return user


# ── Request models ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    spec_id: Optional[str] = None


class GenerateRequest(BaseModel):
    spec_id: str
    year: int
    month: int
    period: Optional[int] = None  # 1 or 2 for fortnightly; None = monthly


# ── LLM helpers ───────────────────────────────────────────────────────────────

async def _llm_text(messages: list[dict], max_tokens: int = 700) -> str:
    client = get_client()
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.5,
        messages=messages,
        timeout=45.0,
    )
    return (resp.choices[0].message.content or "").strip()


async def _llm_json(messages: list[dict], max_tokens: int = 1500) -> dict:
    client = get_client()
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=messages,
        timeout=60.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:])
        if raw.endswith("```"):
            raw = raw[:-3].rstrip()
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("LLM JSON parse failed; raw: %s", raw[:300])
        return {}


# ── System prompts ────────────────────────────────────────────────────────────

_CHAT_SYSTEM = """You are the Senior Report Configuration Assistant for the Commander, NER Theatre Command.

Your job: help the commander articulate exactly what they want in their next intelligence report. Be concise, professional, and focused. Maximum 4-5 lines per response.

Available Priority Areas of Interest (PAOIs):
  P1 — India-Bangladesh Border Security
  P2 — Jamaat-e-Islami Spread & Radicalisation
  P3 — NER Lines of Communication (LOC)
  P4 — Meghalaya Internal Security
  P5 — Tribal Dynamics — Meghalaya

Once you clearly understand the commander's requirements, summarize what the report will cover and end with:
"Shall I lock this in as your report specification?"

Do not ask more than one clarifying question at a time."""


_SPEC_EXTRACT_SYSTEM = """Extract a structured report specification from this intelligence report conversation.

Output ONLY valid JSON. No markdown fences, no commentary.

Available PAOI ids (use exact strings):
  P1_india_bangladesh_border
  P2_jamaat_radicalisation
  P3_ner_lines_of_communication
  P4_meghalaya_internal_security
  P5_meghalaya_tribal_dynamics

Schema:
{
  "report_type": "monthly" | "fortnightly",
  "focus_paoi_ids": ["paoi_id", ...],
  "custom_focus_notes": {
    "P1_india_bangladesh_border": "Specific emphasis for this PAI"
  },
  "recommendation_granularity": "tactical" | "operational" | "strategic",
  "include_faultlines": true | false,
  "include_scenarios": true | false,
  "commander_notes": "Any special emphasis or constraints"
}

Rules:
- report_type: default "fortnightly" if not specified
- focus_paoi_ids: [] means ALL PAOIs; list specific IDs if mentioned
- recommendation_granularity: tactical = unit/route/location specific; operational = sector/agency specific; strategic = pattern/theme level. Default "operational"
- commander_notes: capture verbatim any special instructions or phrasing from the commander"""


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@router.post("/report-agent/chat")
async def chat_turn(req: ChatRequest, user: dict = Depends(_require_admin)):
    """One turn of the spec-building conversation. Returns {reply, spec, spec_id}."""
    # Build conversation for the assistant response
    convo = [{"role": "system", "content": _CHAT_SYSTEM}]
    for m in req.messages:
        convo.append({"role": m.role, "content": m.content})

    reply = await _llm_text(convo, max_tokens=350)

    # Extract spec from full conversation (including this new reply)
    convo_text = "\n\n".join(
        f"[{m.role.upper()}]: {m.content}" for m in req.messages
    ) + f"\n\n[ASSISTANT]: {reply}"

    spec_data = await _llm_json(
        [{"role": "system", "content": _SPEC_EXTRACT_SYSTEM},
         {"role": "user", "content": convo_text}],
        max_tokens=500,
    )

    # Append assistant reply to conversation history
    all_messages = [{"role": m.role, "content": m.content} for m in req.messages]
    all_messages.append({"role": "assistant", "content": reply})

    now = datetime.now(timezone.utc).isoformat()

    if req.spec_id:
        existing = await specs_col.find_one(
            {"id": req.spec_id, "created_by": user["username"]}, {"_id": 0}
        )
        if not existing:
            raise HTTPException(404, "Spec not found")
        updated_spec = {**existing, "updated_at": now, "conversation": all_messages, **spec_data}
        await specs_col.replace_one({"id": req.spec_id}, updated_spec)
        spec_id = req.spec_id
        return_spec = {k: v for k, v in updated_spec.items() if k != "_id"}
    else:
        spec_id = str(uuid.uuid4())[:8]
        new_spec = {
            "id": spec_id,
            "created_at": now,
            "updated_at": now,
            "created_by": user["username"],
            "conversation": all_messages,
            **spec_data,
        }
        await specs_col.insert_one(new_spec)
        return_spec = {k: v for k, v in new_spec.items() if k != "_id"}

    return {"reply": reply, "spec": return_spec, "spec_id": spec_id}


# ── Spec management ───────────────────────────────────────────────────────────

@router.get("/report-agent/specs")
async def list_specs(user: dict = Depends(_require_admin)):
    specs = await specs_col.find(
        {"created_by": user["username"]},
        {"_id": 0, "conversation": 0},
    ).sort("updated_at", -1).to_list(length=20)
    return specs


@router.get("/report-agent/specs/{spec_id}")
async def get_spec(spec_id: str, user: dict = Depends(_require_admin)):
    spec = await specs_col.find_one({"id": spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(404, "Spec not found")
    return spec


@router.delete("/report-agent/specs/{spec_id}")
async def delete_spec(spec_id: str, user: dict = Depends(_require_admin)):
    await specs_col.delete_one({"id": spec_id, "created_by": user["username"]})
    return {"ok": True}


# ── Period helpers ────────────────────────────────────────────────────────────

def _period_range(year: int, month: int, period: Optional[int]) -> tuple[str, str, str]:
    """Return (start_iso, end_iso, label)."""
    if period is None:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )
        label = start.strftime("%B %Y")
    elif period == 1:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, 16, tzinfo=timezone.utc)
        label = f"1-15 {start.strftime('%B %Y')}"
    else:
        start = datetime(year, month, 16, tzinfo=timezone.utc)
        last_day = monthrange(year, month)[1]
        end = (
            datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            if month == 12
            else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        )
        label = f"16-{last_day} {start.strftime('%B %Y')}"
    return start.isoformat(), end.isoformat(), label


# ── Focus resolution ──────────────────────────────────────────────────────────

def _resolve_focus(focus_ids: list[str], all_paois: list[dict]) -> list[dict]:
    """Match spec focus ids to actual PAOI ids.

    Robust to LLM emitting slightly-off slugs (e.g. 'P2_jem_radicalisation'
    vs actual 'P2_jamaat_radicalisation') by falling back to the P-number
    prefix. Empty focus_ids => all PAOIs.
    """
    if not focus_ids:
        return all_paois
    valid = {p["id"] for p in all_paois}
    chosen: set[str] = set()
    for fid in focus_ids:
        if fid in valid:
            chosen.add(fid)
            continue
        prefix = fid.split("_", 1)[0].upper()  # 'P2'
        for p in all_paois:
            if p["id"].split("_", 1)[0].upper() == prefix:
                chosen.add(p["id"])
    matched = [p for p in all_paois if p["id"] in chosen]
    return matched or all_paois


# ── Data helpers ──────────────────────────────────────────────────────────────

async def _pull_items(start_iso: str, end_iso: str, geography: list[str]) -> list[dict]:
    """Pull top intelligence items for the period, optionally filtered by geography."""
    query: dict = {
        "published_at": {"$gte": start_iso, "$lt": end_iso},
        "processed": True,
        "severity": {"$in": ["critical", "high", "medium"]},
    }
    if geography:
        query["state"] = {"$in": list(set(geography))}

    cursor = intelligence_col.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "ai_summary": 1, "why_it_matters": 1,
         "potential_impact": 1, "state": 1, "threat_category": 1,
         "severity": 1, "published_at": 1, "actors": 1, "priority_score": 1,
         "tags": 1},
    ).sort("priority_score", -1).limit(100)
    return await cursor.to_list(length=100)


def _items_digest(items: list[dict], max_items: int = 25) -> str:
    """Format items as an LLM-readable digest."""
    lines = []
    for i, it in enumerate(items[:max_items]):
        sev = (it.get("severity") or "").upper()
        state = it.get("state", "Unknown")
        dt = (it.get("published_at") or "")[:10]
        title = it.get("title", "")
        summary = it.get("ai_summary") or it.get("why_it_matters") or ""
        impact = it.get("potential_impact") or ""
        actors = ", ".join((it.get("actors") or [])[:4])
        line = (
            f"[{i+1}] [{sev}] [{state}] [{dt}]\n"
            f"  Title: {title}\n"
            f"  Summary: {summary[:300]}\n"
        )
        if impact:
            line += f"  Impact: {impact[:200]}\n"
        if actors:
            line += f"  Key actors: {actors}\n"
        lines.append(line)
    return "\n".join(lines) if lines else "(No relevant intelligence items found for this period.)"


# ── Synthesis prompts ─────────────────────────────────────────────────────────

_GRANULARITY_INSTRUCTION = {
    "tactical": (
        "Recommendations must name SPECIFIC UNITS, EXACT LOCATIONS (district/town/village/sector names), "
        "specific routes, and named entity categories. Operate at field-operations level."
    ),
    "operational": (
        "Recommendations must name SPECIFIC SECTORS, CORRIDORS, AGENCIES, and OPERATIONAL MECHANISMS. "
        "Be concrete about geography and method."
    ),
    "strategic": (
        "Recommendations must identify SPECIFIC PATTERNS, POLICY LEVERS, and INSTITUTIONAL ACTIONS. "
        "Still be geographically grounded — name the district or corridor even at strategic level."
    ),
}


def _paoi_synthesis_prompt(
    paoi: dict,
    items: list[dict],
    period_label: str,
    custom_focus: str,
    granularity: str,
    commander_notes: str,
) -> list[dict]:
    name = paoi.get("name", "")
    description = paoi.get("description", "")
    geo = ", ".join((paoi.get("geography") or []) + (paoi.get("watch_geography") or []))
    actors_of_interest = ", ".join(paoi.get("actors_of_interest") or [])

    fl = paoi.get("faultline_movement") or {}
    fl_level = fl.get("level", "STABLE")
    fl_delta = fl.get("delta", 0.0)
    fl_dominant = fl.get("dominant") or {}
    fl_name = fl_dominant.get("name", "N/A")
    subissues = ", ".join(
        s.get("name", "") for s in (fl.get("top_subissues") or [])[:4]
    ) or "none identified"

    digest = _items_digest(items, max_items=22)
    gran_instruction = _GRANULARITY_INSTRUCTION.get(granularity, _GRANULARITY_INSTRUCTION["operational"])

    focus_block = f"\nCOMMANDER'S SPECIFIC FOCUS: {custom_focus}" if custom_focus else ""
    notes_block = f"\nCOMMANDER'S SPECIAL EMPHASIS: {commander_notes}" if commander_notes else ""

    system = "You are a senior NER intelligence analyst. Output STRICT JSON only — no markdown, no commentary."

    user_prompt = f"""PAOI ASSESSMENT TASK — {name} ({period_label})

PAOI: {description}
PRIMARY GEOGRAPHY: {geo}
ACTORS OF INTEREST: {actors_of_interest or "Multiple actors"}
FAULTLINE STATUS: {fl_level} | Delta: {'+' if fl_delta >= 0 else ''}{fl_delta:.1f} | Dominant faultline: {fl_name} | Active sub-issues: {subissues}
{focus_block}{notes_block}

INTELLIGENCE CORPUS ({len(items)} items — top {min(22, len(items))} shown):
{digest}

INSTRUCTIONS:
- Ground EVERY claim in the intelligence above. DO NOT invent facts.
- If evidence is weak or thin, explicitly state so.
- Distinguish: [CONFIRMED] = direct fact from data | [ASSESSED] = inference from pattern | [SPECULATIVE] = forecast
- Recommendations: {gran_instruction}
- BAD recommendation: "Increase monitoring" or "Remain alert"
- GOOD recommendation: "Coordinate with BSF 42nd Bn to establish dedicated surveillance posts at [named crossing point] in [named district], where [specific pattern] has been observed repeatedly in this period."

Return STRICT JSON:
{{
  "situation_overview": "3-4 paragraph narrative. What happened regarding {name} in this period? Overall trajectory? Most significant developments? Use [LABEL] tags throughout.",
  "critical_developments": [
    {{
      "heading": "Short descriptive heading (max 12 words)",
      "location": "Specific district/town/sector — never just state name",
      "what_happened": "2-3 sentences describing the event/development with [LABEL] tags",
      "why_it_matters_to_paoi": "1-2 sentences on direct linkage to {name}",
      "actors_involved": ["actor1", "actor2"],
      "claim_label": "CONFIRMED | ASSESSED | SPECULATIVE"
    }}
  ],
  "overall_assessment": "2-3 sentences: Is the situation improving, stable, or deteriorating? Trajectory? End with a concise commander's bottom line.",
  "risk_trajectory": "IMPROVING | STABLE | DETERIORATING",
  "actionable_recommendations": [
    {{
      "threat_or_issue": "The specific threat or instability driver",
      "geography": "Exact location — district/sector/corridor/town name",
      "why_it_matters_to_paoi": "Direct linkage to {name} and why action is needed now",
      "recommended_action": "SPECIFIC ACTION with named agency, mechanism, and geography. Not vague.",
      "intended_preventive_effect": "What specific instability this action prevents or arrests"
    }}
  ],
  "next_period_watch": [
    {{
      "indicator": "Specific observable indicator to watch",
      "geography": "Exact location to monitor",
      "significance": "Why this indicator matters for {name}"
    }}
  ]
}}

Include 2-5 critical_developments (rank by significance to the PAI), 2-4 recommendations, and 2-3 next_period_watch items."""

    return [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]


def _executive_overview_prompt(
    paoi_summaries: list[dict],
    period_label: str,
    all_items: list[dict],
    commander_notes: str,
) -> list[dict]:
    paoi_lines = "\n".join(
        f"  - {p.get('paoi_name', '')} [{p.get('risk_trajectory', 'STABLE')}]: "
        f"{(p.get('situation_overview') or '')[:300]}"
        for p in paoi_summaries
    )
    top_digest = _items_digest(all_items, max_items=12)
    notes_block = f"\nCOMMANDER'S SPECIAL EMPHASIS: {commander_notes}" if commander_notes else ""

    system = "You are the Chief Intelligence Analyst, NER Theatre Command. Write in military briefing prose. Use [CONFIRMED], [ASSESSED], [SPECULATIVE] labels on every substantive claim. No filler phrases."

    user_prompt = f"""Write the EXECUTIVE OVERVIEW for {period_label}.

PAOI STATUS SUMMARY:
{paoi_lines}

TOP INTELLIGENCE ITEMS:
{top_digest}
{notes_block}

Write 3 focused paragraphs:
  Para 1: Overall NER security landscape in this period. Dominant pattern and regional trajectory.
  Para 2: Most critical PAI dynamics and why they matter right now.
  Para 3: Commander's most urgent focus for the NEXT period.

No headers. No bullets. Prose only. Maximum 350 words."""

    return [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]


# ── PDF rendering ─────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Sanitize text for latin-1 PDF encoding."""
    if not text:
        return ""
    replacements = {
        "’": "'", "‘": "'", "“": '"', "”": '"',
        "–": "-", "—": "--", "…": "...", "•": "*",
        "·": "*", "→": "->", "←": "<-",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _render_pdf(report: dict) -> bytes:
    from fpdf import FPDF

    period_label = report.get("period_label", "")
    generated_at = (report.get("generated_at") or "")[:10]
    report_type = "MONTHLY" if report.get("report_type") == "monthly" else "FORTNIGHTLY"

    class PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(20, 80, 40)
            self.cell(0, 5, "RHINO DRISHTI  //  COMMANDER'S INTELLIGENCE REPORT  //  RESTRICTED",
                      align="C", ln=1)
            self.ln(1)
            self.set_draw_color(20, 80, 40)
            self.set_line_width(0.4)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(3)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(130, 130, 130)
            self.cell(
                0, 4,
                f"Page {self.page_no()}  |  {period_label}  |  {generated_at}",
                align="C",
            )

    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def section_title(text: str):
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(20, 80, 40)
        pdf.cell(0, 7, _safe(f"  {text.upper()}"), fill=True, ln=True)
        pdf.ln(2)

    def sub_header(text: str):
        pdf.set_font("Helvetica", "BI", 8.5)
        pdf.set_text_color(20, 80, 40)
        pdf.cell(0, 5, _safe(text), ln=True)
        pdf.set_draw_color(20, 80, 40)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 60, pdf.get_y())
        pdf.ln(1.5)

    def body(text: str, indent: float = 0):
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(30, 30, 30)
        if indent:
            pdf.set_x(pdf.l_margin + indent)
            pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - indent, 4.5, _safe(text))
        else:
            pdf.multi_cell(0, 4.5, _safe(text))
        pdf.ln(0.5)

    def field(label: str, value: str, indent: float = 3,
              color: tuple[int, int, int] = (30, 30, 30)):
        """One flowing row: bold inline label + value, indented as a block.

        Uses a single multi_cell (markdown bold label) so auto page-breaks
        are handled natively — no manual y juggling that can orphan pages.
        """
        if not value:
            return
        saved_margin = pdf.l_margin
        pdf.set_left_margin(saved_margin + indent)
        pdf.set_x(saved_margin + indent)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*color)
        pdf.multi_cell(0, 4.6, _safe(f"**{label}:**  {value}"), markdown=True)
        pdf.set_left_margin(saved_margin)
        pdf.set_x(saved_margin)
        pdf.ln(0.8)

    def traj_badge(traj: str) -> tuple[int, int, int]:
        return {
            "DETERIORATING": (180, 30, 30),
            "STABLE": (50, 100, 180),
            "IMPROVING": (20, 130, 20),
        }.get(traj, (100, 100, 100))

    # ── Cover page ─────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 80, 40)
    pdf.cell(0, 12, "COMMANDER'S INTELLIGENCE REPORT", align="C", ln=True)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 8, _safe(period_label), align="C", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f"{report_type}  |  Generated: {generated_at}", align="C", ln=True)
    pdf.ln(4)

    # Divider
    pdf.set_draw_color(20, 80, 40)
    pdf.set_line_width(1.0)
    pdf.line(pdf.l_margin + 20, pdf.get_y(), pdf.w - pdf.r_margin - 20, pdf.get_y())
    pdf.ln(5)

    # Commander notes on cover
    if report.get("commander_notes"):
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, _safe(f"Commander's focus for this report: {report['commander_notes']}"), align="C")
        pdf.ln(3)

    # PAOI trajectory summary on cover
    paoi_reports = report.get("paoi_reports", [])
    if paoi_reports:
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 5, "PRIORITY AREAS STATUS SUMMARY", align="C", ln=True)
        pdf.ln(1)
        for pr in paoi_reports:
            traj = pr.get("risk_trajectory", "STABLE")
            rc, gc, bc = traj_badge(traj)
            fl_level = pr.get("faultline_level", "STABLE")
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(95, 5.5, _safe(f"  {pr.get('paoi_name', '')}"), ln=False)
            pdf.set_text_color(rc, gc, bc)
            pdf.cell(0, 5.5, _safe(f"[{traj}]  [{fl_level}]"), ln=True)
        pdf.ln(3)

    # ── Section 1: Executive Overview ─────────────────────────────────────────
    section_title("1. Executive Overview")
    body(report.get("executive_overview", "See individual PAOI assessments below."))

    # ── Section 2: PAOI Deep Dives ────────────────────────────────────────────
    section_title("2. Priority Area Deep Dives")

    for pr in paoi_reports:
        name = pr.get("paoi_name", "")
        traj = pr.get("risk_trajectory", "STABLE")
        fl_level = pr.get("faultline_level", "STABLE")
        fl_delta = pr.get("faultline_delta", 0.0)
        rc, gc, bc = traj_badge(traj)

        # PAOI header bar
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(40, 40, 40)
        pdf.cell(130, 6, _safe(f"  {name}"), fill=True, ln=False)
        pdf.set_fill_color(rc, gc, bc)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(0, 6, _safe(f"  {traj}  |  FL: {fl_level}  ({'+' if fl_delta >= 0 else ''}{fl_delta:.1f})"), fill=True, ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(2)

        # Situation Overview
        sub_header("SITUATION OVERVIEW")
        body(pr.get("situation_overview", ""))

        # Critical Developments
        devs = pr.get("critical_developments") or []
        if devs:
            sub_header("CRITICAL DEVELOPMENTS")
            for j, dev in enumerate(devs):
                heading = dev.get("heading", "")
                loc = dev.get("location", "")
                cl = dev.get("claim_label", "")
                actors = ", ".join(dev.get("actors_involved") or [])

                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(30, 30, 30)
                pdf.set_fill_color(245, 245, 245)
                pdf.multi_cell(0, 5, _safe(f"  [{j+1}]  {heading}  |  {loc}  [{cl}]"), fill=True)

                body(dev.get("what_happened", ""), indent=5)
                if dev.get("why_it_matters_to_paoi"):
                    field("Impact on PAI", dev["why_it_matters_to_paoi"], indent=5)
                if actors:
                    field("Actors", actors, indent=5)
                pdf.ln(1.5)

        # Overall Assessment
        sub_header("OVERALL ASSESSMENT")
        body(pr.get("overall_assessment", ""))

        # Actionable Recommendations
        recs = pr.get("actionable_recommendations") or []
        if recs:
            sub_header("ACTIONABLE RECOMMENDATIONS")
            for k, rec in enumerate(recs, 1):
                # Amber header strip
                pdf.ln(1)
                pdf.set_fill_color(247, 207, 110)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(90, 55, 0)
                pdf.cell(0, 5.5, _safe(f"  RECOMMENDATION {k}"), fill=True, ln=True)

                # Body of the box — record bounds for the accent bar
                box_start_y = pdf.get_y()
                box_start_page = pdf.page_no()

                field("Threat / Issue", rec.get("threat_or_issue", ""), indent=4)
                field("Geography", rec.get("geography", ""), indent=4)
                field("Why It Matters", rec.get("why_it_matters_to_paoi", ""), indent=4)
                field("Recommended Action", rec.get("recommended_action", ""),
                      indent=4, color=(150, 30, 30))
                field("Preventive Effect", rec.get("intended_preventive_effect", ""), indent=4)

                # Left accent bar (only when the box did not break across pages)
                if pdf.page_no() == box_start_page:
                    pdf.set_fill_color(210, 150, 40)
                    pdf.rect(pdf.l_margin, box_start_y, 1.3, pdf.get_y() - box_start_y, "F")
                pdf.ln(2.5)

        # Next Period Watch
        watches = pr.get("next_period_watch") or []
        if watches:
            sub_header("NEXT PERIOD WATCH")
            for w in watches:
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(20, 80, 40)
                pdf.multi_cell(0, 4.5, _safe(f"  > {w.get('indicator', '')}  [{w.get('geography', '')}]"))
                body(f"    {w.get('significance', '')}", indent=4)

        pdf.ln(5)

    # ── Section 3: Next Period Focus ──────────────────────────────────────────
    next_focus = report.get("next_period_focus") or []
    if next_focus:
        section_title("3. Next Period Focus")
        for item in next_focus:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(20, 80, 40)
            pdf.cell(4, 4.5, "*", ln=False)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 4.5, _safe(str(item)))
            pdf.ln(0.5)

    return bytes(pdf.output())


# ── Generate report ───────────────────────────────────────────────────────────

@router.post("/report-agent/generate")
async def generate_report(req: GenerateRequest, user: dict = Depends(_require_admin)):
    """
    Generate a customized narrative intelligence report from a saved spec.
    Returns full report JSON (PDF download via /reports/{id}/pdf).
    """
    spec = await specs_col.find_one({"id": req.spec_id}, {"_id": 0})
    if not spec:
        raise HTTPException(404, "Spec not found")

    start_iso, end_iso, period_label = _period_range(req.year, req.month, req.period)

    report_type = spec.get("report_type", "fortnightly")
    granularity = spec.get("recommendation_granularity", "operational")
    focus_paoi_ids: list[str] = spec.get("focus_paoi_ids") or []
    custom_focus: dict = spec.get("custom_focus_notes") or {}
    commander_notes: str = spec.get("commander_notes") or ""

    logger.info(
        "Report Agent: generating %s for %s (spec=%s, focus=%s)",
        report_type, period_label, req.spec_id, focus_paoi_ids or "ALL",
    )

    # 1. PAOI aggregation (reuse existing paoi_brief pipeline)
    agg = await paoi_brief.aggregate_paoi_period(db, start_iso, end_iso)
    all_paois = agg.get("paois") or []

    target_paois = _resolve_focus(focus_paoi_ids, all_paois)

    # 2. Pull intelligence items for all relevant geography
    all_geo: list[str] = []
    for p in target_paois:
        all_geo.extend(p.get("geography") or [])
        all_geo.extend(p.get("watch_geography") or [])

    all_items = await _pull_items(start_iso, end_iso, all_geo)

    # 3. Per-PAOI synthesis (sequential — avoids rate-limit pile-up)
    paoi_reports = []
    for p in target_paois:
        p_geo = set((p.get("geography") or []) + (p.get("watch_geography") or []))
        geo_items = [it for it in all_items if it.get("state") in p_geo]

        # Also include items matched via keyword pull
        kw_ids = {
            a["id"]
            for a in ((p.get("keyword_hits") or {}).get("top_articles") or [])
        }
        kw_items = [it for it in all_items if it.get("id") in kw_ids and it not in geo_items]
        p_items = sorted(geo_items + kw_items, key=lambda x: -(x.get("priority_score") or 0))

        messages = _paoi_synthesis_prompt(
            paoi=p,
            items=p_items,
            period_label=period_label,
            custom_focus=custom_focus.get(p["id"], ""),
            granularity=granularity,
            commander_notes=commander_notes,
        )
        synthesis = await _llm_json(messages, max_tokens=2200)

        fl = p.get("faultline_movement") or {}
        paoi_reports.append({
            "paoi_id": p["id"],
            "paoi_name": p.get("name", ""),
            "faultline_level": fl.get("level", "STABLE"),
            "faultline_delta": fl.get("delta", 0.0),
            "situation_overview": synthesis.get("situation_overview", ""),
            "critical_developments": synthesis.get("critical_developments") or [],
            "overall_assessment": synthesis.get("overall_assessment", ""),
            "risk_trajectory": synthesis.get("risk_trajectory", "STABLE"),
            "actionable_recommendations": synthesis.get("actionable_recommendations") or [],
            "next_period_watch": synthesis.get("next_period_watch") or [],
        })

    # 4. Executive overview
    exec_messages = _executive_overview_prompt(paoi_reports, period_label, all_items, commander_notes)
    executive_overview = await _llm_text(exec_messages, max_tokens=800)

    # 5. Aggregate next-period focus
    next_focus = []
    for pr in paoi_reports:
        for w in (pr.get("next_period_watch") or [])[:1]:
            next_focus.append(
                f"[{pr['paoi_name']}] {w.get('indicator', '')} — {w.get('geography', '')}"
            )

    # 6. Persist report
    now = datetime.now(timezone.utc).isoformat()
    report_id = str(uuid.uuid4())[:8]
    report = {
        "id": report_id,
        "spec_id": req.spec_id,
        "created_by": user["username"],
        "generated_at": now,
        "report_type": report_type,
        "period_label": period_label,
        "year": req.year,
        "month": req.month,
        "period": req.period,
        "commander_notes": commander_notes,
        "executive_overview": executive_overview,
        "paoi_reports": paoi_reports,
        "next_period_focus": next_focus,
    }
    await agent_reports_col.insert_one({k: v for k, v in report.items() if k != "_id"})
    report.pop("_id", None)

    logger.info("Report Agent: %s done — %d PAOIs, report_id=%s", period_label, len(paoi_reports), report_id)
    return report


@router.get("/report-agent/reports")
async def list_reports(user: dict = Depends(_require_admin)):
    reports = await agent_reports_col.find(
        {"created_by": user["username"]},
        {"_id": 0, "paoi_reports": 0, "executive_overview": 0},
    ).sort("generated_at", -1).to_list(length=30)
    return reports


@router.get("/report-agent/reports/{report_id}/pdf")
async def download_pdf(report_id: str, user: dict = Depends(_require_admin)):
    report = await agent_reports_col.find_one({"id": report_id}, {"_id": 0})
    if not report:
        raise HTTPException(404, "Report not found")
    pdf_bytes = _render_pdf(report)
    label = (report.get("period_label") or "report").replace(" ", "_").replace("-", "_")
    filename = f"RDRISHTI_{label}_{report_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
