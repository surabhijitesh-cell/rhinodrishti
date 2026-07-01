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
import re
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


def _balance_brackets(s: str) -> str:
    """Best-effort close of an unterminated JSON fragment (truncated output)."""
    out: list[str] = []
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if esc:
            out.append(ch); esc = False; continue
        if in_str and ch == "\\":
            out.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str; out.append(ch); continue
        if not in_str:
            if ch in "{[":
                stack.append(ch)
            elif ch in "}]" and stack:
                stack.pop()
        out.append(ch)
    if in_str:
        out.append('"')
    res = "".join(out).rstrip()
    while res and res[-1] in ",:":
        res = res[:-1].rstrip()
    for ch in reversed(stack):
        res += "}" if ch == "{" else "]"
    return res


def _coerce_json(raw: str) -> dict:
    """Parse model output into a dict, recovering from fences, prose wrappers,
    and truncated (unterminated) JSON."""
    if not raw:
        return {}
    s = raw.strip()
    if s.startswith("```"):
        nl = s.find("\n")
        s = s[nl + 1:] if nl != -1 else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find("{")
    if start == -1:
        return {}
    end = s.rfind("}")
    if end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            pass
    # Truncation repair: balance brackets from the first '{'
    try:
        return json.loads(_balance_brackets(s[start:]))
    except Exception:
        return {}


async def _llm_json(messages: list[dict], max_tokens: int = 1500) -> dict:
    client = get_client()
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=messages,
        timeout=90.0,
    )
    choice = resp.choices[0]
    raw = (choice.message.content or "").strip()
    finish = getattr(choice, "finish_reason", None)
    data = _coerce_json(raw)
    if not data:
        logger.warning(
            "LLM JSON parse failed (finish_reason=%s, len=%d); head: %s",
            finish, len(raw), raw[:200],
        )
    elif finish == "length":
        logger.warning("LLM JSON recovered from truncation (finish_reason=length)")
    return data


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


_ITEM_PROJECTION = {
    "_id": 0, "id": 1, "title": 1, "ai_summary": 1, "why_it_matters": 1,
    "potential_impact": 1, "state": 1, "threat_category": 1,
    "severity": 1, "published_at": 1, "actors": 1, "priority_score": 1,
    "tags": 1,
}


async def _extract_focus_keywords(commander_notes: str) -> list[str]:
    """Ask the LLM for concrete topical keywords identifying the request subject."""
    msgs = [
        {"role": "system",
         "content": "Extract concrete search keywords identifying the SUBJECT of an "
                    "intelligence-report request. Output STRICT JSON only."},
        {"role": "user",
         "content": (
             f"Request:\n\"{commander_notes}\"\n\n"
             "Return JSON: {\"keywords\": [\"...\"]} — 4 to 12 concrete topical search "
             "terms (phenomena, named entities, event types) that DISTINGUISH the subject. "
             "Include obvious synonyms (e.g. for weather: rain, rainfall, flood, landslide, "
             "monsoon, cyclone, storm, waterlogging, inundation). "
             "EXCLUDE generic filler (impact, security, update, report, concern, issue, "
             "situation, monitor, area, region) AND broad place names that over-match "
             "unrelated news (Assam, Meghalaya, Manipur, Mizoram, Nagaland, Tripura, "
             "Arunachal Pradesh, Northeast, NER, India) — geography is filtered separately."
         )},
    ]
    data = await _llm_json(msgs, max_tokens=200)
    kws = data.get("keywords") or []
    return [k.strip() for k in kws if isinstance(k, str) and len(k.strip()) >= 3]


async def _pull_topic_items(
    start_iso: str, end_iso: str, keywords: list[str], limit: int = 50,
    sort_field: str = "priority_score",
) -> list[dict]:
    """Pull medium+ severity items matching the topic keywords.

    Broad topical search (regex across multiple fields) but still gated to
    critical/high/medium severity so the section is not cluttered with routine
    low-severity noise. ``sort_field`` selects ordering — "priority_score" for
    relevance, "published_at" for recency (e.g. live weather events).
    """
    safe_kw = [re.escape(k) for k in keywords if len(k) >= 3]
    if not safe_kw:
        return []
    rx = {"$regex": "|".join(safe_kw), "$options": "i"}
    query = {
        "published_at": {"$gte": start_iso, "$lt": end_iso},
        "processed": True,
        "severity": {"$in": ["critical", "high", "medium"]},
        "$or": [
            {"title": rx}, {"ai_summary": rx}, {"why_it_matters": rx},
            {"potential_impact": rx}, {"tags": rx},
        ],
    }
    cursor = intelligence_col.find(query, _ITEM_PROJECTION).sort(
        sort_field, -1
    ).limit(limit)
    return await cursor.to_list(length=limit)


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


def _special_focus_prompt(
    commander_notes: str,
    period_label: str,
    items: list[dict],
    keywords: list[str] | None = None,
) -> list[dict]:
    """Synthesize an ad-hoc thematic section from the commander's free-text ask.

    Handles topics outside the fixed PAOI structure (e.g. weather, a named
    event, a specific actor). Grounded in the corpus, with explicit coverage
    honesty when the data is thin.
    """
    digest = _items_digest(items, max_items=30)
    kw_line = f"\nTOPIC KEYWORDS USED TO RETRIEVE THIS CORPUS: {', '.join(keywords)}" if keywords else ""
    system = (
        "You are a senior NER intelligence analyst. The commander has requested "
        "specific coverage beyond the standard Priority Areas. Output STRICT JSON only "
        "— no markdown, no commentary."
    )
    user_prompt = f"""COMMANDER'S SPECIAL REQUEST for the {period_label} report:
\"{commander_notes}\"
{kw_line}

INTELLIGENCE CORPUS ({len(items)} items — top {min(30, len(items))} shown, retrieved by topic, medium severity and above):
{digest}

INSTRUCTIONS:
- Address ONLY the commander's special request above — not the standard PAOI assessments.
- Ground EVERY claim in the corpus. DO NOT invent facts.
- Tag claims: [CONFIRMED] = direct from data | [ASSESSED] = inference | [SPECULATIVE] = forecast.
- If the corpus contains little or nothing on the requested topic, SAY SO plainly in
  coverage_note and keep key_points short — do not pad with unrelated PAOI material.

Return STRICT JSON:
{{
  "title": "Short section title reflecting the request (max 8 words)",
  "narrative": "2-3 paragraph narrative directly answering the request, with [LABEL] tags. If evidence is thin, state the limitation up front.",
  "key_points": [
    {{
      "point": "Specific finding tied to the request",
      "geography": "Exact location — district/sector/state",
      "claim_label": "CONFIRMED | ASSESSED | SPECULATIVE"
    }}
  ],
  "implications": [
    "Short implication for security / lines of communication / humanitarian posture"
  ],
  "coverage_note": "If reporting on this topic is thin or absent in the period, state it here; otherwise empty string."
}}

Include 0-6 key_points (only what the corpus supports) and 0-4 implications."""
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

    _sec_no = [0]

    def section_title(text: str):
        _sec_no[0] += 1
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(20, 80, 40)
        pdf.cell(0, 7, _safe(f"  {_sec_no[0]}. {text.upper()}"), fill=True, ln=True)
        pdf.ln(2)

    def sub_header(text: str):
        y = pdf.get_y()
        # small green marker square
        pdf.set_fill_color(20, 80, 40)
        pdf.rect(pdf.l_margin, y + 0.6, 1.6, 3.2, "F")
        pdf.set_xy(pdf.l_margin + 3.5, y)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(20, 80, 40)
        pdf.cell(0, 5, _safe(text.upper()), ln=True)
        pdf.set_draw_color(200, 215, 205)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1.8)

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

    def fl_badge(level: str) -> tuple[int, int, int]:
        return {
            "CRITICAL": (170, 30, 30),
            "ELEVATED": (200, 120, 20),
            "MONITOR": (50, 100, 180),
            "STABLE": (90, 90, 90),
        }.get((level or "").upper(), (110, 110, 110))

    def pill(text: str, rgb: tuple[int, int, int], x: float, h: float = 4.8):
        """Draw a small filled rounded-ish badge at x on the current line; returns new x."""
        pdf.set_font("Helvetica", "B", 7)
        w = pdf.get_string_width(text) + 5
        pdf.set_fill_color(*rgb)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, pdf.get_y())
        pdf.cell(w, h, _safe(text), fill=True, align="C")
        return x + w + 2

    content_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Cover page ─────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.ln(6)

    # Hero band — dark green block with reversed title
    hero_y = pdf.get_y()
    hero_h = 30
    pdf.set_fill_color(18, 70, 38)
    pdf.rect(pdf.l_margin, hero_y, content_w, hero_h, "F")
    # thin gold underline accent at base of band
    pdf.set_fill_color(198, 156, 60)
    pdf.rect(pdf.l_margin, hero_y + hero_h, content_w, 1.1, "F")

    pdf.set_xy(pdf.l_margin, hero_y + 6.5)
    pdf.set_font("Helvetica", "B", 19)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(content_w, 10, "COMMANDER'S INTELLIGENCE REPORT", align="C", ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(220, 230, 220)
    pdf.cell(content_w, 7, _safe(period_label.upper()), align="C", ln=True)
    pdf.set_y(hero_y + hero_h + 4)

    # Meta row: report-type chip (left) + RESTRICTED chip (right) + generated date (center)
    meta_y = pdf.get_y() + 1
    pill(report_type, (60, 90, 60), pdf.l_margin, h=5.2)
    pdf.set_y(meta_y)
    restricted_w = pdf.get_string_width("RESTRICTED") + 5
    pill("RESTRICTED", (150, 30, 30), pdf.w - pdf.r_margin - restricted_w, h=5.2)
    pdf.set_xy(pdf.l_margin, meta_y)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(content_w, 5.2, f"Generated: {generated_at}", align="C", ln=True)
    pdf.ln(6)

    # Commander notes on cover
    if report.get("commander_notes"):
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(0, 5, _safe(f"Commander's focus for this report: {report['commander_notes']}"), align="C")
        pdf.ln(3)

    # PAOI trajectory summary on cover — panel with pill badges
    paoi_reports = report.get("paoi_reports", [])
    if paoi_reports:
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(40, 40, 40)
        pdf.cell(content_w, 6, "  PRIORITY AREAS STATUS SUMMARY", fill=True, ln=True)
        row_h = 6.6
        for idx, pr in enumerate(paoi_reports):
            traj = pr.get("risk_trajectory", "STABLE")
            fl_level = pr.get("faultline_level", "STABLE")
            row_y = pdf.get_y()
            if idx % 2 == 0:
                pdf.set_fill_color(244, 246, 244)
                pdf.rect(pdf.l_margin, row_y, content_w, row_h, "F")
            pdf.set_xy(pdf.l_margin, row_y)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(35, 35, 35)
            pdf.cell(content_w * 0.6, row_h, _safe(f"  {pr.get('paoi_name', '')}"), ln=False)
            # right-aligned pills: FL then trajectory
            fl_txt, tr_txt = fl_level.upper(), traj
            tr_w = pdf.get_string_width(tr_txt) + 5
            fl_w = pdf.get_string_width(fl_txt) + 5
            pdf.set_y(row_y + (row_h - 4.8) / 2)
            x = pdf.w - pdf.r_margin - tr_w - fl_w - 2
            x = pill(fl_txt, fl_badge(fl_level), x)
            pill(tr_txt, traj_badge(traj), x)
            pdf.set_y(row_y + row_h)
        pdf.ln(4)

    # ── Executive Overview ────────────────────────────────────────────────────
    section_title("Executive Overview")
    body(report.get("executive_overview", "See individual PAOI assessments below."))

    # ── PAOI Deep Dives ───────────────────────────────────────────────────────
    section_title("Priority Area Deep Dives")

    for pr in paoi_reports:
        name = pr.get("paoi_name", "")
        traj = pr.get("risk_trajectory", "STABLE")
        fl_level = pr.get("faultline_level", "STABLE")
        fl_delta = pr.get("faultline_delta", 0.0)
        rc, gc, bc = traj_badge(traj)

        # PAOI header bar — content width split name | status
        pdf.ln(3)
        status_w = 74
        name_w = content_w - status_w
        status = f"{traj}  |  FL: {fl_level}  ({'+' if fl_delta >= 0 else ''}{fl_delta:.1f})"
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(40, 40, 40)
        pdf.cell(name_w, 6.5, _safe(f"  {name}"), fill=True, ln=False)
        pdf.set_fill_color(rc, gc, bc)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(status_w, 6.5, _safe(status), fill=True, ln=True, align="C")
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
                pdf.ln(1)
                # Keep a card reasonably intact: break early if little room left
                if pdf.get_y() > pdf.h - pdf.b_margin - 34:
                    pdf.add_page()

                card_top = pdf.get_y()
                card_page = pdf.page_no()

                # Amber header strip
                pdf.set_fill_color(244, 196, 92)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(85, 52, 0)
                pdf.cell(content_w, 5.8, _safe(f"  RECOMMENDATION {k}"), fill=True, ln=True)
                pdf.ln(0.6)

                field("Threat / Issue", rec.get("threat_or_issue", ""), indent=5)
                field("Geography", rec.get("geography", ""), indent=5)
                field("Why It Matters", rec.get("why_it_matters_to_paoi", ""), indent=5)
                field("Recommended Action", rec.get("recommended_action", ""),
                      indent=5, color=(150, 30, 30))
                field("Preventive Effect", rec.get("intended_preventive_effect", ""), indent=5)
                pdf.ln(0.4)

                # Card outline + left accent (only when not split across pages)
                if pdf.page_no() == card_page:
                    h = pdf.get_y() - card_top
                    pdf.set_draw_color(214, 168, 80)
                    pdf.set_line_width(0.3)
                    pdf.rect(pdf.l_margin, card_top, content_w, h)
                    pdf.set_fill_color(206, 150, 50)
                    pdf.rect(pdf.l_margin, card_top, 1.6, h, "F")
                pdf.ln(3)

        # Next Period Watch
        watches = pr.get("next_period_watch") or []
        if watches:
            sub_header("NEXT PERIOD WATCH")
            for w in watches:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(20, 80, 40)
                pdf.multi_cell(0, 4.5, _safe(f"  > {w.get('indicator', '')}  [{w.get('geography', '')}]"))
                body(f"    {w.get('significance', '')}", indent=4)

        pdf.ln(5)

    # ── Commander's Special Focus (optional) — after the PAOI deep dives ───────
    sf = report.get("special_focus")
    if sf and (sf.get("narrative") or sf.get("key_points")):
        section_title("Commander's Special Focus")
        if sf.get("title"):
            sub_header(sf["title"])
        if sf.get("narrative"):
            body(sf["narrative"])
        kps = sf.get("key_points") or []
        if kps:
            sub_header("KEY POINTS")
            for kp in kps:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(20, 80, 40)
                pdf.multi_cell(
                    0, 4.5,
                    _safe(f"  > {kp.get('point', '')}  [{kp.get('geography', '')}]  [{kp.get('claim_label', '')}]"),
                )
            pdf.ln(1)
        imps = sf.get("implications") or []
        if imps:
            sub_header("IMPLICATIONS")
            for im in imps:
                pdf.set_x(pdf.l_margin)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(20, 80, 40)
                pdf.cell(4, 4.5, "*", ln=False)
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 4.5, _safe(str(im)))
        if sf.get("coverage_note"):
            pdf.ln(1)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 4.4, _safe(f"Coverage note: {sf['coverage_note']}"))

    # ── Next Period Focus ─────────────────────────────────────────────────────
    next_focus = report.get("next_period_focus") or []
    if next_focus:
        section_title("Next Period Focus")
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

    # Weather is a first-class disruptor of NER Lines of Communication (P3):
    # floods, landslides, washed-out roads, damaged bridges. Pull these (medium+)
    # once so the P3 deep dive treats the weather situation as a LOC factor.
    LOC_WEATHER_KEYWORDS = [
        "flood", "landslide", "cloudburst", "monsoon", "rainfall", "inundation",
        "washed away", "erosion", "submerged", "mudslide", "waterlogging",
        "torrential", "deluge", "swollen river",
    ]
    P3_ID = "P3_ner_lines_of_communication"
    loc_weather_items = await _pull_topic_items(
        start_iso, end_iso, LOC_WEATHER_KEYWORDS, limit=20, sort_field="published_at",
    )

    # 3. Per-PAOI synthesis (sequential — avoids rate-limit pile-up)
    paoi_reports = []
    for p in target_paois:
        # Use the PAOI's OWN curated, relevance-ranked articles (keyword_hits).
        # This decouples each PAOI from the shared top-N pool, which is otherwise
        # dominated by whichever theatre is hottest (e.g. Manipur) and starves
        # geographically narrow PAOIs (Meghalaya) of any items.
        p_items = list((p.get("keyword_hits") or {}).get("top_articles") or [])
        focus_note = custom_focus.get(p["id"], "")

        # P3 (NER LOC): fold in weather-driven LOC disruption as an explicit factor
        if p["id"] == P3_ID and loc_weather_items:
            existing = {it.get("id") for it in p_items}
            p_items += [it for it in loc_weather_items if it.get("id") not in existing]
            weather_focus = (
                "Treat the current weather situation (floods, landslides, washed-out "
                "roads, damaged bridges, blocked highways) as a FIRST-CLASS factor "
                "disrupting NER Lines of Communication. Identify which routes/corridors "
                "are affected and the operational impact on mobility and resupply."
            )
            focus_note = f"{focus_note} {weather_focus}".strip()

        p_items = sorted(p_items, key=lambda x: -(x.get("priority_score") or 0))

        messages = _paoi_synthesis_prompt(
            paoi=p,
            items=p_items,
            period_label=period_label,
            custom_focus=focus_note,
            granularity=granularity,
            commander_notes=commander_notes,
        )
        # Larger budget — the synthesis JSON (overview + developments + recs +
        # watches) overflowed the old 2200-token cap on content-rich PAOIs,
        # truncating the JSON and yielding an empty deep dive.
        synthesis = await _llm_json(messages, max_tokens=4000)
        if not synthesis.get("situation_overview") and not synthesis.get("critical_developments"):
            logger.warning(
                "Report Agent: empty synthesis for %s (items=%d) — retrying once",
                p["id"], len(p_items),
            )
            synthesis = await _llm_json(messages, max_tokens=4000)

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

    # 4b. Commander's special focus — only when the spec carries a free-text ask.
    # Pull a broad, all-geography corpus so off-PAOI topics (weather, named
    # events, etc.) are not missed by the PAOI-scoped item set.
    special_focus = None
    if commander_notes.strip():
        # Broad topical retrieval, still gated to medium+ severity
        kws = await _extract_focus_keywords(commander_notes)
        topic_items = await _pull_topic_items(start_iso, end_iso, kws)
        broad_items = await _pull_items(start_iso, end_iso, [])
        seen: set[str] = set()
        merged: list[dict] = []
        for it in topic_items + broad_items:  # topic items first
            iid = it.get("id")
            if iid in seen:
                continue
            seen.add(iid)
            merged.append(it)
        logger.info(
            "Report Agent: special focus — %d topic items (kw=%s), %d merged",
            len(topic_items), kws, len(merged),
        )
        sf_messages = _special_focus_prompt(commander_notes, period_label, merged, kws)
        sf = await _llm_json(sf_messages, max_tokens=1800)
        if sf.get("narrative") or sf.get("key_points"):
            special_focus = {
                "title": sf.get("title") or "Commander's Special Focus",
                "narrative": sf.get("narrative", ""),
                "key_points": sf.get("key_points") or [],
                "implications": sf.get("implications") or [],
                "coverage_note": sf.get("coverage_note", ""),
            }

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
        "special_focus": special_focus,
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


@router.delete("/report-agent/reports/{report_id}")
async def delete_report(report_id: str, user: dict = Depends(_require_admin)):
    res = await agent_reports_col.delete_one(
        {"id": report_id, "created_by": user["username"]}
    )
    if res.deleted_count == 0:
        raise HTTPException(404, "Report not found")
    return {"ok": True}


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
