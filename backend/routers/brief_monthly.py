"""
Monthly Strategic Intelligence Brief — comprehensive playbook for senior commanders.

Endpoints:
  POST /brief/monthly/generate?year=Y&month=M   — kick off generation (background)
  GET  /brief/monthly/{year}/{month}             — fetch generated brief
  GET  /brief/monthly/list                       — list available months
  GET  /brief/monthly/{year}/{month}/pdf         — PDF download
  GET  /brief/monthly/{year}/{month}/notebooklm  — markdown text optimized for
                                                    NotebookLM Video Overview generation

Architecture:
  - MongoDB collection: monthly_briefs ({ year, month, status, generated_at, data })
  - Generation is async/background — initial POST returns immediately
  - LLM = Gemini 2.5 Flash via OpenRouter (existing llm_client)
  - Per-state synthesis runs in parallel via asyncio.gather
  - Statistics computed from intelligence_col aggregation (no hallucination)
  - Contact directory = static ner_contacts (offices only, no incumbent names)
  - PDF via fpdf2 (already in deps)

Claim labeling convention (passed to LLM, enforced in prompt):
  [CONFIRMED]   — direct factual claim from intel items
  [ASSESSED]    — inference from patterns + evidence
  [SPECULATIVE] — forecast / probability statement
"""
import asyncio
import io
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse

from shared import db, intelligence_col, NER_STATES, logger
from ner_contacts import get_contacts_for_state, NER_REGIONAL_CONTACTS
from llm_client import get_client, MODEL

router = APIRouter()

monthly_briefs_col = db.monthly_briefs

NER_STATES_FULL = list(dict.fromkeys(NER_STATES + ["Nagaland", "Sikkim"]))
BORDER_COUNTRIES = {"Bangladesh", "Myanmar", "Bhutan", "China", "Nepal"}
_SEV_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _month_range(year: int, month: int) -> tuple[str, str]:
    """Return ISO start (inclusive) and end (exclusive) for the given month."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()


async def _aggregate_month_stats(year: int, month: int) -> dict:
    """Pull and aggregate the month's intelligence_items for downstream synthesis."""
    start_iso, end_iso = _month_range(year, month)
    q = {
        "published_at": {"$gte": start_iso, "$lt": end_iso},
        "processed": True,
        "severity": {"$nin": ["filtered_out"]},
        "tags": {"$nin": ["not_relevant", "stage0_filtered", "stage05_filtered", "stage1_filtered"]},
    }

    total = 0
    sev_counts = Counter()
    state_stats = defaultdict(lambda: {
        "total": 0, "sev_counts": Counter(),
        "actors": Counter(), "locations": Counter(),
        "categories": Counter(), "daily": Counter(),
        "critical_items": [], "high_items": [], "analyst_notes": [],
    })
    overall_actors    = Counter()
    overall_locations = Counter()
    overall_cats      = Counter()
    daily_severity    = defaultdict(lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0})
    cross_border_count = 0
    # Bangladesh-border states + Myanmar-border states (for cross-border classification)
    _BD_STATES = {"Assam", "Tripura", "Meghalaya"}
    _MM_STATES = {"Manipur", "Nagaland", "Mizoram", "Arunachal Pradesh"}
    cb_bangladesh: list = []
    cb_myanmar: list = []

    async for item in intelligence_col.find(q, {
        "id": 1, "title": 1, "severity": 1, "state": 1, "threat_category": 1,
        "published_at": 1, "entities": 1, "summary": 1, "ai_summary": 1,
        "analyst_enhancement": 1, "is_cross_border": 1, "countries_involved": 1, "_id": 0,
    }):
        total += 1
        sev = item.get("severity") or "low"
        sev_counts[sev] += 1
        state = item.get("state") or "Unknown"
        cat = item.get("threat_category") or "Other"
        overall_cats[cat] += 1
        pub_date = (item.get("published_at") or "")[:10]
        if pub_date:
            daily_severity[pub_date][sev] += 1
            daily_severity[pub_date]["total"] += 1

        locs = (item.get("entities") or {}).get("locations") or []
        orgs = (item.get("entities") or {}).get("organizations") or []
        for a in orgs[:5]:
            if a:
                overall_actors[a] += 1
        for l in locs[:5]:
            if l and l not in NER_STATES_FULL and l not in BORDER_COUNTRIES:
                overall_locations[l] += 1
        if any(c in BORDER_COUNTRIES for c in locs) or state in BORDER_COUNTRIES:
            cross_border_count += 1

        if item.get("is_cross_border"):
            countries = item.get("countries_involved") or []
            _cb_rec = {
                "title": (item.get("title") or "")[:180],
                "severity": sev, "state": state,
                "category": cat, "date": pub_date,
                "summary": (item.get("ai_summary") or item.get("summary") or "")[:200],
            }
            if "Bangladesh" in countries or state in _BD_STATES:
                if len(cb_bangladesh) < 10:
                    cb_bangladesh.append(_cb_rec)
            elif "Myanmar" in countries or state in _MM_STATES:
                if len(cb_myanmar) < 10:
                    cb_myanmar.append(_cb_rec)

        # Per-state breakdown (only for NER states)
        if state in NER_STATES_FULL:
            s = state_stats[state]
            s["total"] += 1
            s["sev_counts"][sev] += 1
            s["categories"][cat] += 1
            for a in orgs[:5]:
                if a:
                    s["actors"][a] += 1
            for l in locs[:5]:
                if l and l not in NER_STATES_FULL and l not in BORDER_COUNTRIES:
                    s["locations"][l] += 1
            if pub_date:
                s["daily"][pub_date] += 1
            if sev == "critical" and len(s["critical_items"]) < 8:
                s["critical_items"].append({
                    "id": item.get("id"), "title": (item.get("title") or "")[:200],
                    "date": pub_date, "summary": (item.get("summary") or "")[:300],
                })
            elif sev == "high" and len(s["high_items"]) < 8:
                s["high_items"].append({
                    "id": item.get("id"), "title": (item.get("title") or "")[:200],
                    "date": pub_date,
                })
            enh = item.get("analyst_enhancement") or {}
            if enh.get("is_enhanced") and enh.get("analyst_note") and len(s["analyst_notes"]) < 6:
                s["analyst_notes"].append({
                    "note": enh["analyst_note"][:500],
                    "by": enh.get("enhanced_by_name", "Analyst"),
                    "date": pub_date,
                    "item_title": (item.get("title") or "")[:150],
                    "severity": sev,
                })

    # Convert per-state Counters to ordered lists for JSON
    states_out = {}
    for st, s in state_stats.items():
        states_out[st] = {
            "total":          s["total"],
            "sev_counts":     dict(s["sev_counts"]),
            "top_actors":     s["actors"].most_common(8),
            "top_locations":  s["locations"].most_common(8),
            "top_categories": s["categories"].most_common(8),
            "daily_volume":   sorted(s["daily"].items()),
            "critical_items": s["critical_items"],
            "high_items":     s["high_items"],
            "analyst_notes":  s["analyst_notes"],
        }

    # Stability score per state (reusing the trends scoring formula)
    stability = []
    days = (datetime.fromisoformat(end_iso) - datetime.fromisoformat(start_iso)).days or 1
    third_days = max(days // 3, 1)
    early_cutoff = (datetime.fromisoformat(start_iso) + timedelta(days=third_days)).isoformat()
    late_cutoff  = (datetime.fromisoformat(end_iso)   - timedelta(days=third_days)).isoformat()
    max_sev_w = 1
    for st in NER_STATES_FULL:
        s_total = states_out.get(st, {}).get("total", 0)
        s_sev   = states_out.get(st, {}).get("sev_counts", {})
        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in s_sev.items())
        max_sev_w = max(max_sev_w, sw)

    # Re-pull lightweight pass for early/late counts per state
    early_late = defaultdict(lambda: [0, 0])  # state -> [early, late]
    async for item in intelligence_col.find(q, {"published_at": 1, "state": 1, "_id": 0}):
        st = item.get("state") or ""
        if st not in NER_STATES_FULL:
            continue
        pub = item.get("published_at") or ""
        if pub < early_cutoff:
            early_late[st][0] += 1
        if pub >= late_cutoff:
            early_late[st][1] += 1

    for st in NER_STATES_FULL:
        s_sev = states_out.get(st, {}).get("sev_counts", {})
        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in s_sev.items())
        severity_load = sw / max_sev_w if max_sev_w else 0
        early, late  = early_late[st]
        velocity = 0.0
        if early > 0:
            velocity = min(late / early / 3, 1.0)
        elif late > 0:
            velocity = 0.8
        actors_count = len(states_out.get(st, {}).get("top_actors", []))
        actor_spread = min(actors_count / 8, 1.0)
        cb_share = 0.0  # per-state cross-border not tracked here for simplicity
        concern = severity_load * 0.40 + velocity * 0.25 + actor_spread * 0.20 + cb_share * 0.15
        score = max(0, round(100 - concern * 100))
        if   score >= 75: level = "STABLE"
        elif score >= 50: level = "MONITOR"
        elif score >= 25: level = "ELEVATED"
        else:             level = "CRITICAL"
        stability.append({"state": st, "score": score, "level": level,
                          "severity_load": round(severity_load, 2),
                          "velocity": round(velocity, 2)})
    stability.sort(key=lambda x: x["score"])  # most concerning first

    return {
        "month_start":       start_iso,
        "month_end":         end_iso,
        "total":             total,
        "sev_counts":        dict(sev_counts),
        "cross_border_count": cross_border_count,
        "states":            states_out,
        "stability":         stability,
        "top_actors":        overall_actors.most_common(15),
        "top_locations":     overall_locations.most_common(15),
        "top_categories":    overall_cats.most_common(10),
        "daily_severity":    [{"date": d, **v} for d, v in sorted(daily_severity.items())],
        "cb_bangladesh":     cb_bangladesh,
        "cb_myanmar":        cb_myanmar,
    }


# ── LLM synthesis prompts ─────────────────────────────────────────────────────

def _exec_summary_prompt(stats: dict, year: int, month: int) -> str:
    month_name = datetime(year, month, 1).strftime("%B %Y")
    top_actors = ", ".join([f"{a[0]} ({a[1]})" for a in stats["top_actors"][:8]])
    top_cats   = ", ".join([f"{c[0]} ({c[1]})" for c in stats["top_categories"][:6]])
    top_concern = ", ".join([f"{s['state']} ({s['score']}/100 {s['level']})" for s in stats["stability"][:3]])
    return f"""You are the Chief Intelligence Analyst, NER Theatre Command. Write the EXECUTIVE STRATEGIC ASSESSMENT section of the monthly intelligence brief for {month_name}.

DATA FOR THE MONTH:
- Total intelligence items processed: {stats['total']}
- Severity breakdown: {stats['sev_counts']}
- Cross-border items: {stats['cross_border_count']}
- Top actors: {top_actors}
- Top threat categories: {top_cats}
- Most-concerning states: {top_concern}

REQUIREMENTS:
- 4-6 paragraphs maximum.
- Open with regional overview (one paragraph). Then emerging instability (one paragraph). Then key operational concerns (one paragraph). Then likely future developments (one paragraph).
- Tone: senior military intelligence briefing. Crisp, declarative. NO vague filler ("various", "several", "many").
- Label EVERY substantive claim with one of:
    [CONFIRMED]   — direct fact from data above
    [ASSESSED]    — inference from observable pattern
    [SPECULATIVE] — forecast / probability
- No hedging without label. Be specific about states, actors, categories, numbers.

Output: prose only. No headers, no markdown bullets."""


def _state_section_prompt(state: str, state_data: dict, stability_entry: dict, month_name: str) -> str:
    top_actors = ", ".join([f"{a[0]} ({a[1]})" for a in state_data.get("top_actors", [])[:6]])
    top_locs   = ", ".join([f"{l[0]} ({l[1]})" for l in state_data.get("top_locations", [])[:6]])
    top_cats   = ", ".join([f"{c[0]} ({c[1]})" for c in state_data.get("top_categories", [])[:5]])
    crits = "\n".join([f"  - [{c['date']}] {c['title']}" for c in state_data.get("critical_items", [])[:5]])
    highs = "\n".join([f"  - [{h['date']}] {h['title']}" for h in state_data.get("high_items", [])[:5]])

    notes = state_data.get("analyst_notes", [])
    analyst_notes_block = ""
    if notes:
        lines = []
        for n in notes:
            lines.append(f"  - [{n['date']}] ({n['severity'].upper()}) re: \"{n['item_title']}\" — {n['note']} [Analyst: {n['by']}]")
        analyst_notes_block = "\nANALYST ENHANCEMENTS (ground-truth corrections / human intelligence from field analysts — treat as highest-confidence inputs and incorporate into your assessment):\n" + "\n".join(lines)

    return f"""You are the State Analyst for {state} on the NER Theatre Command intel desk. Write the {state} section of the monthly brief for {month_name}.

DATA:
- Total items this month: {state_data.get('total', 0)}
- Severity counts: {state_data.get('sev_counts', {})}
- Stability score: {stability_entry['score']}/100 ({stability_entry['level']})
- Top actors: {top_actors}
- Top hotspot locations: {top_locs}
- Dominant threat categories: {top_cats}

CRITICAL incidents this month (top 5):
{crits or "  (none)"}

HIGH-severity incidents this month (top 5):
{highs or "  (none)"}
{analyst_notes_block}
REQUIRED OUTPUT — return STRICT JSON only (no markdown fences, no commentary). Schema:
{{
  "severity_summary":   "2-3 sentences on severity profile, trajectory, and stability assessment with [LABEL] tags.",
  "escalation_pattern": "2-3 sentences describing how the situation evolved through the month — was activity front-loaded, accelerating, clustered around events? Include [LABEL] tags.",
  "key_actors":         "1-2 sentences naming the actors driving activity and their pattern (locations, methods). [LABEL] tags.",
  "district_hotspots":  "1-2 sentences on geographic concentration — which districts/locations are hottest and why. [LABEL] tags.",
  "operational_concerns": "2-3 specific operational concerns a commander should track. Each must be concrete, no vague phrasing."
}}

Tone: military intel briefing. Specific. No filler. Numbers + names from data only — never invent. If a field has no actionable content, write "Insufficient data for the month."."""


def _mitigation_playbook_prompt(state: str, stability_entry: dict, top_actors_str: str, top_cats_str: str) -> str:
    return f"""You are advising the Apex Commander, NER Theatre, on stabilizing {state} (concern level: {stability_entry['level']}).

Context: Top actors operating in {state} this month: {top_actors_str}. Dominant threats: {top_cats_str}.

Generate a 4-HORIZON MITIGATION PLAYBOOK. Return STRICT JSON only:
{{
  "immediate": [
    {{"action": "specific action verb + concrete target", "lead_agency": "agency/office name", "rationale": "why this works"}},
    ...3-4 items total
  ],
  "short_term": [...3 items, 1-4 weeks],
  "medium_term": [...3 items, 1-3 months],
  "long_term": [...2 items, 3-12 months]
}}

REQUIREMENTS:
- Each action must be executable. NOT vague ("improve coordination"). YES specific ("Deploy 2 additional Assam Rifles companies along NH-2 between Imphal–Senapati for 30 days; establish convoy security protocol with 4-hourly intervals 0600-1800").
- Lead agencies: DGP {state}, CS {state}, GOC corresponding mountain division, Assam Rifles HQ, BSF Frontier HQ, Eastern Command HQ, MHA NE Division, NIA NER Branch, IB NE region — use these or other real Indian security/civil structures. NEVER invent agencies.
- Mix: military / police / intelligence / civil admin / political outreach / border / information warfare countermeasures.
- Do NOT name individual incumbents (they rotate). Reference offices only."""


def _scenarios_prompt(stats: dict, year: int, month: int) -> str:
    month_name = datetime(year, month, 1).strftime("%B %Y")
    top_concern = ", ".join([f"{s['state']} ({s['score']}/100 {s['level']})" for s in stats["stability"][:4]])
    return f"""You are the Predictive Intelligence Cell. Generate 3 STRATEGIC SCENARIOS for the NER region for the 30-90 days following {month_name}.

Context: Most-concerning states this month: {top_concern}. Top actors: {", ".join([a[0] for a in stats["top_actors"][:8]])}. Cross-border incidents: {stats["cross_border_count"]}.

Return STRICT JSON only:
{{
  "scenarios": [
    {{
      "title": "Concise scenario name (e.g. 'Manipur Communal Escalation H+30')",
      "narrative": "3-4 sentences. What unfolds, where, who drives it.",
      "confidence_pct": 35,
      "warning_indicators": ["specific observable 1", "specific observable 2", "specific observable 3"],
      "horizon": "H+30" | "H+60" | "H+90",
      "trigger_factors": "1-2 sentences on what would push probability higher"
    }},
    ...3 scenarios total, ordered most-likely first
  ]
}}

REQUIREMENTS:
- Confidence pct = 0-100. Don't anchor everything at 50.
- Warning indicators must be OBSERVABLE in our intel pipeline (e.g. "Spike in arms-seizure reports along Moreh corridor", NOT "increased tension").
- Tone: defense analysis. Crisp."""


def _cross_border_prompt(cb_bd: list, cb_mm: list, period_label: str) -> str:
    def _fmt(items):
        return "\n".join([f"  - [{i['date']}] ({i['severity'].upper()}) [{i['state']}] {i['title']}"
                          + (f"\n      Summary: {i['summary']}" if i.get("summary") else "")
                          for i in items]) or "  (no items this period)"

    bd_count = len(cb_bd)
    mm_count = len(cb_mm)

    return f"""You are the NER Cross-Border Intelligence Cell. Write the CROSS-BORDER THREAT ANALYSIS section for {period_label}.

BANGLADESH BORDER DATA ({bd_count} cross-border items):
Border states: Assam, Tripura, Meghalaya
{_fmt(cb_bd[:7])}

MYANMAR BORDER DATA ({mm_count} cross-border items):
Border states: Manipur, Nagaland, Mizoram, Arunachal Pradesh
{_fmt(cb_mm[:7])}

THREAT CONTEXT:
- Bangladesh border: infiltration, illegal immigration, Rohingya movement, narcotics, arms, militant sanctuary in CHT areas, recent Bangladesh political instability (Hasina govt collapse Aug 2024, Yunus-led interim govt, student-led protests, anti-India sentiment)
- Myanmar border: Arakan Army operations, Chin National Front, drug trafficking Golden Triangle corridor, displaced persons / refugee inflow, arms smuggling, NLFT/ULFA cross-border movement

RETURN STRICT JSON ONLY:
{{
  "bangladesh_border": {{
    "threat_level": "CRITICAL|HIGH|MEDIUM|LOW",
    "overview": "2-3 sentences. Overall security picture on Bangladesh border this period.",
    "primary_threats": "Specific threat types active on Bangladesh border — exact. No vague language.",
    "hotspot_corridors": "Named border corridors or districts seeing highest activity.",
    "key_actors": "Named actors or groups active on Bangladesh border.",
    "indo_bd_dimension": "2-3 sentences specifically on India-Bangladesh bilateral security dynamic — diplomatic friction, BSF-BGB coordination, border fence gaps, recent Bangladesh political context affecting security cooperation.",
    "operational_concerns": "2-3 specific operational concerns for BSF/state police on this border."
  }},
  "myanmar_border": {{
    "threat_level": "CRITICAL|HIGH|MEDIUM|LOW",
    "overview": "2-3 sentences. Overall security picture on Myanmar border this period.",
    "primary_threats": "Specific threat types active on Myanmar border.",
    "hotspot_corridors": "Named corridors or districts.",
    "key_actors": "Named actors or groups.",
    "displacement_pressure": "Assessment of refugee/IDP inflow pressure on NER border districts.",
    "operational_concerns": "2-3 specific operational concerns for AR/state police on this border."
  }}
}}

REQUIREMENTS:
- Label EVERY factual claim: [CONFIRMED] from data above, [ASSESSED] from pattern inference, [SPECULATIVE] forecast.
- No vague filler. Every field must contain actionable intelligence.
- If data insufficient for a border, write "Insufficient cross-border data this period" for that border.
- Tone: military intelligence briefing. Crisp."""


async def _call_llm_json(prompt: str, max_tokens: int = 600, model_override: str = None) -> dict:
    """Call Gemini, expect JSON in response, parse and return dict (empty dict on failure)."""
    try:
        client = get_client()
        resp = await client.chat.completions.create(
            model=model_override or MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.4,
            extra_body={"include_reasoning": False},
        )
        text = resp.choices[0].message.content.strip()
        # Strip code fences if present
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text[3:] else text[3:]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip().rstrip("`").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Monthly brief JSON parse failed: {e} -- text was: {text[:300] if 'text' in dir() else 'n/a'}")
        return {}
    except Exception as e:
        logger.error(f"Monthly brief LLM call failed: {e}")
        return {}


async def _call_llm_text(prompt: str, max_tokens: int = 800) -> str:
    try:
        client = get_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.5,
            extra_body={"include_reasoning": False},
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Monthly brief text LLM call failed: {e}")
        return ""


_STR_FIELDS = {"severity_summary", "escalation_pattern", "key_actors", "district_hotspots", "operational_concerns"}

def _coerce_state_section(sec: dict) -> dict:
    for f in _STR_FIELDS:
        v = sec.get(f)
        if isinstance(v, list):
            sec[f] = "; ".join(str(x) for x in v)
        elif v is not None and not isinstance(v, str):
            sec[f] = str(v)
    return sec


def _build_action_matrix(stats: dict) -> list:
    """Derive Commander Action Matrix from observed data (NOT LLM hallucination).
    Each row pairs a real threat signal with a recommended action template."""
    matrix = []
    cat_actions = {
        "Insurgency":          ("Joint AR + state police flush ops in flagged hotspot districts; ROP on key corridors", "GOC Mountain Div / DGP State"),
        "Drug Smuggling":      ("Targeted source-corridor interdiction with NCB + Assam Rifles + state police", "Assam Rifles HQ / DGP State"),
        "Arms Smuggling":      ("BSF/AR interdiction belt activation; NIA case build-up on seizures", "BSF Frontier / NIA NER Branch"),
        "Ethnic Violence":     ("Re-deploy CAPF mobile teams to fault-line zones; civil admin liaison cell at SP level", "MHA NE Division / DC of district"),
        "Border Tension":      ("BGB/BSF flag meetings; pol-mil liaison with neighbouring HQ", "BSF Frontier / Eastern Command"),
        "Cross-Border":        ("Intel fusion request — IB NE + R&AW liaison; tighter ICP checks", "IB NE Region / MEA"),
        "Cyber":               ("CERT-In coordination; state cyber-crime cell brief-up", "CERT-In / state CID-cyber"),
        "Communal":            ("Local-admin de-escalation; community liaison; preventive 144 selectively", "CS State / DC of district"),
        "Political Unrest":    ("Civil admin lead; preventive section orders; political dialogue track", "CS State / Governor's secretariat"),
        "Military Operations": ("Coordinate operational tempo; deconfliction with civil admin", "GOC Mountain Div"),
    }
    for cat, count in stats["top_categories"][:8]:
        sev_marker = "CRITICAL" if count > 25 else "HIGH" if count > 10 else "MEDIUM"
        prob = "HIGH" if count > 20 else "MODERATE" if count > 5 else "LOW"
        action, lead = cat_actions.get(cat, ("Direct operational review with state DGP/CS", "DGP / CS State"))
        matrix.append({
            "threat":         cat,
            "incident_count": count,
            "severity":       sev_marker,
            "probability":    prob,
            "likely_impact":  f"Sustained or escalating activity in affected NER states across {sev_marker.lower()} band",
            "action":         action,
            "lead_agency":    lead,
            "time_horizon":   "0-30 days" if prob == "HIGH" else "30-90 days",
        })
    return matrix


# ── NotebookLM script builder ─────────────────────────────────────────────────

def _build_notebooklm_script(brief: dict, year: int, month: int) -> str:
    """Markdown formatted brief — optimized as a source document for NotebookLM
    Video Overview generation. Structure favors section headers, bullet anchors,
    and concrete data points (NotebookLM uses these as narrative beats)."""
    month_name = datetime(year, month, 1).strftime("%B %Y")
    md = []
    md.append(f"# NER Strategic Intelligence Brief — {month_name}")
    md.append("")
    md.append("**Theatre:** North-East Region (NER) — Indian Army Eastern Command")
    md.append(f"**Period:** {month_name}")
    md.append(f"**Total intel items processed:** {brief['stats']['total']}")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Executive Strategic Assessment")
    md.append("")
    md.append(brief.get("executive_summary", "_Synthesis pending._"))
    md.append("")

    # Stability ranking
    md.append("## Regional Stability Index Ranking")
    md.append("")
    for s in brief["stats"]["stability"]:
        md.append(f"- **{s['state']}** — {s['score']}/100 — `{s['level']}`")
    md.append("")

    # Per-state
    md.append("## State-wise Security Assessment")
    md.append("")
    for state, st_brief in brief.get("state_sections", {}).items():
        md.append(f"### {state}")
        st_stats = brief["stats"]["states"].get(state, {})
        md.append(f"Total items: **{st_stats.get('total', 0)}**. Severity: {st_stats.get('sev_counts', {})}.")
        md.append("")
        for k, label in [("severity_summary", "Severity Profile"),
                          ("escalation_pattern", "Escalation Pattern"),
                          ("key_actors", "Key Actors"),
                          ("district_hotspots", "District Hotspots"),
                          ("operational_concerns", "Operational Concerns")]:
            v = st_brief.get(k)
            if v:
                md.append(f"**{label}.** {v}")
                md.append("")

    # Action matrix
    md.append("## Commander Action Matrix")
    md.append("")
    md.append("| Threat | Severity | Probability | Action | Lead Agency | Horizon |")
    md.append("|--------|----------|-------------|--------|-------------|---------|")
    for row in brief.get("action_matrix", []):
        md.append(f"| {row['threat']} | {row['severity']} | {row['probability']} | {row['action']} | {row['lead_agency']} | {row['time_horizon']} |")
    md.append("")

    # Predictive scenarios
    md.append("## Predictive Intelligence — Scenarios for the Next 30-90 Days")
    md.append("")
    for sc in brief.get("scenarios", []):
        md.append(f"### {sc.get('title', 'Scenario')} ({sc.get('horizon', 'H+30')})")
        md.append(f"**Confidence: {sc.get('confidence_pct', '?')}%**. {sc.get('narrative', '')}")
        md.append("")
        if sc.get("warning_indicators"):
            md.append("**Warning indicators to monitor:**")
            for w in sc["warning_indicators"]:
                md.append(f"- {w}")
            md.append("")
        if sc.get("trigger_factors"):
            md.append(f"**Trigger factors:** {sc['trigger_factors']}")
            md.append("")

    # Mitigation
    md.append("## Mitigation Playbook (per Unstable State)")
    md.append("")
    for state, plan in brief.get("mitigation_playbook", {}).items():
        md.append(f"### {state}")
        for horizon, label in [("immediate", "Immediate (0-72 hrs)"),
                                ("short_term", "Short Term (1-4 weeks)"),
                                ("medium_term", "Medium Term (1-3 months)"),
                                ("long_term", "Long Term (3-12 months)")]:
            actions = plan.get(horizon, [])
            if not actions:
                continue
            md.append(f"**{label}:**")
            for a in actions:
                md.append(f"- {a.get('action', '')} — Lead: *{a.get('lead_agency', '')}*. Rationale: {a.get('rationale', '')}")
            md.append("")

    # Contacts
    md.append("## Contact Directory")
    md.append("")
    md.append("_Public offices only — verify incumbent via respective .gov.in portal before engagement._")
    md.append("")
    for state in brief.get("state_sections", {}).keys():
        contacts = get_contacts_for_state(state)["state_contacts"]
        if not contacts:
            continue
        md.append(f"### {state}")
        for c in contacts:
            md.append(f"- **{c['office']}** ({c['hq']}) — {c['phone']} · {c['email']}")
        md.append("")
    md.append("### Regional / National")
    for c in NER_REGIONAL_CONTACTS:
        md.append(f"- **{c['office']}** ({c['hq']}) — {c['phone']} · {c['email']}")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"_Prepared: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Rhino Drishti NER Intelligence Platform._")
    return "\n".join(md)


# ── Generation orchestrator ───────────────────────────────────────────────────

async def _run_generation(year: int, month: int) -> dict:
    """The actual heavy generator — called via background task or directly."""
    logger.info(f"Monthly brief generation start: {year}-{month:02d}")

    # 1. Aggregate stats
    stats = await _aggregate_month_stats(year, month)

    if stats["total"] == 0:
        return {
            "year": year, "month": month, "status": "empty",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": "No intelligence items found for this month",
        }

    # 2. LLM calls
    month_name = datetime(year, month, 1).strftime("%B %Y")

    # 2a. Executive summary (sequential — informs other prompts)
    exec_summary = await _call_llm_text(_exec_summary_prompt(stats, year, month), max_tokens=900)

    # 2b. Per-state sections (parallel — only NER states with activity)
    state_section_tasks = []
    target_states = [st for st, sd in stats["states"].items() if sd["total"] > 0]
    stability_map = {s["state"]: s for s in stats["stability"]}
    for st in target_states:
        sd = stats["states"][st]
        stab = stability_map.get(st, {"score": 50, "level": "MONITOR"})
        state_section_tasks.append(_call_llm_json(_state_section_prompt(st, sd, stab, month_name), max_tokens=600))

    state_results = await asyncio.gather(*state_section_tasks)
    state_sections = {st: _coerce_state_section(res) for st, res in zip(target_states, state_results) if res}

    # 2c. Mitigation playbook (parallel — only for states with concern level >= ELEVATED)
    mitigation_tasks = []
    mitigation_states = []
    for s in stats["stability"]:
        if s["level"] in ("ELEVATED", "CRITICAL", "MONITOR") and stats["states"].get(s["state"], {}).get("total", 0) > 3:
            mitigation_states.append(s["state"])
            sd = stats["states"][s["state"]]
            actors_str = ", ".join([a[0] for a in sd["top_actors"][:5]]) or "various"
            cats_str   = ", ".join([c[0] for c in sd["top_categories"][:4]]) or "mixed"
            mitigation_tasks.append(_call_llm_json(_mitigation_playbook_prompt(s["state"], s, actors_str, cats_str), max_tokens=700))
    mitigation_results = await asyncio.gather(*mitigation_tasks)
    mitigation_playbook = {st: res for st, res in zip(mitigation_states, mitigation_results) if res}

    # 2d. Cross-border analysis (Bangladesh + Myanmar deep dive)
    cross_border_analysis = await _call_llm_json(
        _cross_border_prompt(stats.get("cb_bangladesh", []), stats.get("cb_myanmar", []), month_name),
        max_tokens=1000,
    )

    # 2e. Predictive scenarios
    scenarios_payload = await _call_llm_json(_scenarios_prompt(stats, year, month), max_tokens=900)
    scenarios = scenarios_payload.get("scenarios", []) if isinstance(scenarios_payload, dict) else []

    # 3. Build action matrix (derived from data, not LLM)
    action_matrix = _build_action_matrix(stats)

    # 4. Assemble brief
    brief = {
        "year": year, "month": month,
        "status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "executive_summary": exec_summary,
        "state_sections": state_sections,
        "action_matrix": action_matrix,
        "mitigation_playbook": mitigation_playbook,
        "scenarios": scenarios,
        "cross_border_analysis": cross_border_analysis,
        "contact_directory": {
            st: get_contacts_for_state(st) for st in target_states
        },
    }

    # 5. NotebookLM markdown
    brief["notebooklm_script"] = _build_notebooklm_script(brief, year, month)

    # 6. Persist
    await monthly_briefs_col.replace_one(
        {"year": year, "month": month}, brief, upsert=True,
    )
    logger.info(f"Monthly brief generation complete: {year}-{month:02d}")
    return brief


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/brief/monthly/generate")
async def generate_monthly_brief(
    background_tasks: BackgroundTasks,
    year:  int = Query(...),
    month: int = Query(..., ge=1, le=12),
):
    """Kick off (re)generation. Marks brief as 'generating' immediately, then
    runs full LLM synthesis in background. Poll /brief/monthly/{y}/{m} for status."""
    # Mark as generating
    await monthly_briefs_col.replace_one(
        {"year": year, "month": month},
        {"year": year, "month": month, "status": "generating",
         "started_at": datetime.now(timezone.utc).isoformat()},
        upsert=True,
    )

    async def _bg():
        try:
            await _run_generation(year, month)
        except Exception as e:
            logger.exception("monthly brief generation crashed")
            await monthly_briefs_col.update_one(
                {"year": year, "month": month},
                {"$set": {"status": "error", "error": str(e)[:300]}},
            )

    background_tasks.add_task(_bg)
    return {"status": "generating", "year": year, "month": month}


@router.get("/brief/monthly/list")
async def list_monthly_briefs():
    """List all available monthly briefs (newest first)."""
    cursor = monthly_briefs_col.find(
        {}, {"_id": 0, "year": 1, "month": 1, "status": 1, "generated_at": 1}
    ).sort([("year", -1), ("month", -1)]).limit(36)
    return {"briefs": [b async for b in cursor]}


@router.get("/brief/monthly/{year}/{month}")
async def get_monthly_brief(year: int, month: int):
    brief = await monthly_briefs_col.find_one({"year": year, "month": month}, {"_id": 0})
    if not brief:
        raise HTTPException(404, "Brief not generated for this month — POST to /brief/monthly/generate first")
    return brief


@router.get("/brief/monthly/{year}/{month}/notebooklm", response_class=PlainTextResponse)
async def get_monthly_brief_notebooklm(year: int, month: int):
    """Returns the markdown script optimized for NotebookLM Video Overview generation.
    Frontend exposes this as a 'Copy for NotebookLM' button."""
    brief = await monthly_briefs_col.find_one({"year": year, "month": month}, {"notebooklm_script": 1})
    if not brief or not brief.get("notebooklm_script"):
        raise HTTPException(404, "Brief not generated or markdown not ready")
    return brief["notebooklm_script"]


@router.get("/brief/monthly/{year}/{month}/pdf")
async def get_monthly_brief_pdf(year: int, month: int):
    """PDF export of the monthly brief — fpdf2 based, ASCII-clean, embeds all sections."""
    brief = await monthly_briefs_col.find_one({"year": year, "month": month}, {"_id": 0})
    if not brief:
        raise HTTPException(404, "Brief not generated")
    if brief.get("status") != "ready":
        raise HTTPException(425, f"Brief status: {brief.get('status')} — wait for generation to complete")

    pdf_bytes = _render_pdf(brief)
    filename = f"NER_Monthly_Brief_{year}_{month:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── PDF rendering ─────────────────────────────────────────────────────────────

def _ascii(s) -> str:
    """fpdf2 default fonts are Latin-1 — strip non-encodable chars."""
    if not s:
        return ""
    if isinstance(s, list):
        s = "; ".join(str(x) for x in s)
    elif not isinstance(s, str):
        s = str(s)
    replacements = {
        '“': '"', '”': '"', '‘': "'", '’': "'",
        '–': '-', '—': '-', '…': '...', '•': '*',
        '​': '', ' ': ' ',
    }
    for o, r in replacements.items():
        s = s.replace(o, r)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _render_pdf(brief: dict) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}  # replaces deprecated ln=True

    year, month = brief["year"], brief["month"]
    month_name = datetime(year, month, 1).strftime("%B %Y")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, _ascii(f"NER Strategic Intelligence Brief"), **NL)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, _ascii(f"Period: {month_name}"), **NL)
    pdf.cell(0, 6, _ascii(f"Generated: {brief.get('generated_at', '')[:19].replace('T', ' ')}"), **NL)
    pdf.ln(4)

    # Stats summary
    stats = brief.get("stats", {})
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Regional Overview", **NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _ascii(
        f"Total items: {stats.get('total', 0)} | "
        f"Critical: {stats.get('sev_counts', {}).get('critical', 0)} | "
        f"High: {stats.get('sev_counts', {}).get('high', 0)} | "
        f"Cross-border: {stats.get('cross_border_count', 0)}"
    ))
    pdf.ln(2)

    # Stability ranking
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Stability Index Ranking", **NL)
    pdf.set_font("Helvetica", "", 9)
    for s in stats.get("stability", []):
        pdf.cell(0, 5, _ascii(f"  {s['state']}: {s['score']}/100  ({s['level']})"), **NL)
    pdf.ln(2)

    # Executive Summary
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Executive Strategic Assessment", **NL)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _ascii(brief.get("executive_summary", "")))
    pdf.ln(3)

    # State sections
    for state, st_brief in brief.get("state_sections", {}).items():
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, _ascii(f"State: {state}"), **NL)
        st_stats = stats.get("states", {}).get(state, {})
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _ascii(f"  Items: {st_stats.get('total', 0)} | Severity: {st_stats.get('sev_counts', {})}"), **NL)
        pdf.set_font("Helvetica", "", 10)
        for k, label in [("severity_summary", "Severity Profile"),
                          ("escalation_pattern", "Escalation Pattern"),
                          ("key_actors", "Key Actors"),
                          ("district_hotspots", "Hotspots"),
                          ("operational_concerns", "Operational Concerns")]:
            v = st_brief.get(k)
            if v:
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 5, _ascii(label), **NL)
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(0, 5, _ascii(v))
                pdf.ln(1)
        pdf.ln(2)

    # Action Matrix
    if brief.get("action_matrix"):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, "Commander Action Matrix", **NL)
        pdf.set_font("Helvetica", "", 9)
        for row in brief["action_matrix"]:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, _ascii(f"{row['threat']} ({row['severity']} / Prob: {row['probability']})"), **NL)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 4, _ascii(f"  Action: {row['action']}"))
            pdf.multi_cell(0, 4, _ascii(f"  Lead: {row['lead_agency']} | Horizon: {row['time_horizon']}"))
            pdf.ln(1)

    # Scenarios
    if brief.get("scenarios"):
        if pdf.get_y() > 230: pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, "Predictive Scenarios", **NL)
        for sc in brief["scenarios"]:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 5, _ascii(f"{sc.get('title', 'Scenario')} (conf {sc.get('confidence_pct', '?')}%, {sc.get('horizon', 'H+30')})"), **NL)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 4, _ascii(sc.get("narrative", "")))
            if sc.get("warning_indicators"):
                pdf.set_font("Helvetica", "I", 8)
                for w in sc["warning_indicators"]:
                    pdf.cell(0, 4, _ascii(f"  > Warning: {w}"), **NL)
            pdf.ln(2)

    # Mitigation Playbook
    if brief.get("mitigation_playbook"):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, "Mitigation Playbook", **NL)
        for state, plan in brief["mitigation_playbook"].items():
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, _ascii(state), **NL)
            for horizon, label in [("immediate", "Immediate"), ("short_term", "Short Term"),
                                    ("medium_term", "Medium Term"), ("long_term", "Long Term")]:
                actions = plan.get(horizon, [])
                if not actions:
                    continue
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(0, 5, _ascii(label + ":"), **NL)
                pdf.set_font("Helvetica", "", 9)
                for a in actions:
                    pdf.multi_cell(0, 4, _ascii(f"  - {a.get('action', '')} | Lead: {a.get('lead_agency', '')}"))
                pdf.ln(1)
            pdf.ln(2)

    # Cross-border analysis
    cba = brief.get("cross_border_analysis") or {}
    if cba:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 7, "Cross-Border Threat Analysis", **NL)
        for border_key, border_label in [("bangladesh_border", "Indo-Bangladesh Border"), ("myanmar_border", "Indo-Myanmar Border")]:
            b = cba.get(border_key) or {}
            if not b:
                continue
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 6, _ascii(f"{border_label} — Threat Level: {b.get('threat_level', '?')}"), **NL)
            pdf.set_font("Helvetica", "", 9)
            for field, label in [
                ("overview", "Overview"), ("primary_threats", "Primary Threats"),
                ("hotspot_corridors", "Hotspot Corridors"), ("key_actors", "Key Actors"),
                ("indo_bd_dimension", "Indo-Bangladesh Dimension"),
                ("displacement_pressure", "Displacement Pressure"),
                ("operational_concerns", "Operational Concerns"),
            ]:
                v = b.get(field)
                if v:
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(0, 4, _ascii(label + ":"), **NL)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.multi_cell(0, 4, _ascii(v))
            pdf.ln(2)

    # Contacts
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Contact Directory", **NL)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, _ascii("Public offices only — verify incumbent via state .gov.in portal."))
    pdf.ln(2)
    for state, c_block in brief.get("contact_directory", {}).items():
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, _ascii(state), **NL)
        pdf.set_font("Helvetica", "", 9)
        for c in c_block.get("state_contacts", []):
            pdf.multi_cell(0, 4, _ascii(f"  {c['office']} ({c['hq']}) - {c['phone']} | {c['email']}"))
        pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Regional / National", **NL)
    pdf.set_font("Helvetica", "", 9)
    for c in NER_REGIONAL_CONTACTS:
        pdf.multi_cell(0, 4, _ascii(f"  {c['office']} ({c['hq']}) - {c['phone']} | {c['email']}"))

    return bytes(pdf.output())
