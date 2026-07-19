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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, PlainTextResponse

from shared import db, intelligence_col, NER_STATES, logger
from llm_client import get_client, MODEL
from utils.auth import get_current_user


def _require_brief_author(current_user: dict) -> None:
    """Gate brief (re)generation to analyst/admin — protects LLM budget."""
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(403, "Only analysts and admins can generate briefs")


def _iod_query_filter(iod: str) -> dict:
    """Match stored briefs for the given IOD. Briefs generated before IOD-scoping
    have no `iod` field at all — treat those as IOD-1 so existing monthly/
    fortnightly briefs keep working unchanged."""
    if iod == "IOD-1":
        return {"$or": [{"iod": "IOD-1"}, {"iod": {"$exists": False}}]}
    return {"iod": iod}


def _effective_iod(current_user: dict, iod_override: Optional[str]) -> str:
    """Admins may override via ?iod=; everyone else always gets their own IOD."""
    if iod_override and current_user.get("role") == "admin":
        from iod_registry import ALL_IODS
        if iod_override in ALL_IODS:
            return iod_override
    return current_user.get("iod", "IOD-1")

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

    # ── Bangladesh + Myanmar cards (commander ask) ─────────────────────────────
    # These regions live in regions[]/countries_involved, not the `state` field,
    # so they aren't captured by the NER loop above. Compute the same inverted
    # stability score (higher = more stable) for each, using cross-border items.
    for region_name, region_match in [
        ("Bangladesh", {"$or": [
            {"regions": "Bangladesh"},
            {"countries_involved": "Bangladesh"},
            {"state": "Bangladesh"},
        ]}),
        ("Myanmar", {"$or": [
            {"regions": "Myanmar"},
            {"countries_involved": "Myanmar"},
            {"state": "Myanmar"},
        ]}),
    ]:
        rq = {**q, **region_match}
        r_sev_counts: Counter = Counter()
        r_actors_counter: Counter = Counter()  # for top_actors (mitigation playbook)
        r_cats_counter: Counter = Counter()    # for top_categories
        r_total = 0
        r_early = r_late = 0
        async for item in intelligence_col.find(
            rq,
            {"published_at": 1, "severity": 1, "actors": 1,
             "threat_category": 1, "tags": 1, "_id": 0},
        ):
            r_total += 1
            r_sev_counts[item.get("severity", "low")] += 1
            for a in (item.get("actors") or []):
                if a:
                    r_actors_counter[a] += 1
            # threat_category preferred; fall back to first tag
            cat = item.get("threat_category")
            if not cat:
                tags = item.get("tags") or []
                cat = tags[0] if tags else None
            if cat:
                r_cats_counter[cat] += 1
            pub = item.get("published_at") or ""
            if pub < early_cutoff:
                r_early += 1
            if pub >= late_cutoff:
                r_late += 1

        sw = sum(_SEV_WEIGHT.get(k, 0) * v for k, v in r_sev_counts.items())
        severity_load = sw / max_sev_w if max_sev_w else 0
        velocity = 0.0
        if r_early > 0:
            velocity = min(r_late / r_early / 3, 1.0)
        elif r_late > 0:
            velocity = 0.8
        actor_spread = min(len(r_actors_counter) / 8, 1.0)
        # Cross-border regions ARE cross-border by definition → full cb weight
        cb_share = 1.0
        concern = severity_load * 0.40 + velocity * 0.25 + actor_spread * 0.20 + cb_share * 0.15
        score = max(0, round(100 - concern * 100))
        if   score >= 75: level = "STABLE"
        elif score >= 50: level = "MONITOR"
        elif score >= 25: level = "ELEVATED"
        else:             level = "CRITICAL"
        stability.append({
            "state": region_name, "score": score, "level": level,
            "severity_load": round(severity_load, 2),
            "velocity": round(velocity, 2),
            "is_cross_border_region": True,
        })

        # Populate states_out so the mitigation_playbook loop picks up BD/Myanmar
        # (commander ask). The loop gates on stats["states"][st].total > 3.
        states_out[region_name] = {
            "total":          r_total,
            "sev_counts":     dict(r_sev_counts),
            "top_actors":     r_actors_counter.most_common(8),
            "top_locations":  [],
            "top_categories": r_cats_counter.most_common(8),
            "daily_volume":   [],
            "critical_items": [],
            "high_items":     [],
            "is_cross_border_region": True,
        }

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
    text = ""
    try:
        client = get_client()
        resp = await client.chat.completions.create(
            model=model_override or MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        text = resp.choices[0].message.content or ""
        # Strip <think>...</think> blocks (Gemini 2.5 Flash reasoning tokens)
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        # Strip code fences if present
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text[3:] else text[3:]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip().rstrip("`").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Brief JSON parse failed: {e} -- raw: {text[:400]}")
        return {}
    except Exception as e:
        logger.error(f"Brief LLM JSON call failed: {type(e).__name__}: {e}")
        return {}


async def _call_llm_text(prompt: str, max_tokens: int = 800) -> str:
    try:
        client = get_client()
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.5,
        )
        text = resp.choices[0].message.content or ""
        # Strip <think>...</think> blocks
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return text
    except Exception as e:
        logger.error(f"Brief LLM text call failed: {type(e).__name__}: {e}")
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

    md.append("---")
    md.append("")
    md.append(f"_Prepared: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Rhino Drishti NER Intelligence Platform._")
    return "\n".join(md)


# ── Generation orchestrator ───────────────────────────────────────────────────

# ── Faultline section (Phase 5a) ─────────────────────────────────────────────

async def _aggregate_faultline_section(year: int, month: int, iod: str = "IOD-1") -> dict:
    """
    Aggregate faultline_scores for the calendar month, grouped by state.
    Returns:
      {
        "available": bool,             # True if any scores exist for this month
        "by_state": {                  # state → list of {faultline + month stats}
          "Manipur": [
            {faultline_id, faultline_name, first, last, peak, avg, delta, level, days_observed},
            ...
          ]
        },
        "rising": [...top 10 by delta...],
        "declining": [...top 5...],
        "critical": [...current CRITICAL...],
      }
    """
    from collections import defaultdict
    start = datetime(year, month, 1, tzinfo=timezone.utc).date()
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc).date()
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc).date()

    match: dict = {"date": {"$gte": start.isoformat(), "$lt": end.isoformat()}}
    if iod != "IOD-1":
        from iod_registry import get_iod_faultline_ids
        watchlist = get_iod_faultline_ids(iod)
        if watchlist:
            match["faultline_id"] = {"$in": watchlist}

    cursor = db.faultline_scores.find(
        match,
        {"_id": 0},
    ).sort([("faultline_id", 1), ("date", 1)])
    all_scores = [s async for s in cursor]

    if not all_scores:
        return {"available": False, "by_state": {}, "rising": [], "declining": [], "critical": []}

    by_fl: dict = defaultdict(list)
    for s in all_scores:
        by_fl[s["faultline_id"]].append(s)

    fl_summaries = []
    for fl_id, series in by_fl.items():
        series = sorted(series, key=lambda x: x["date"])
        first = series[0]["score"]
        last = series[-1]["score"]
        peak = max(s["score"] for s in series)
        avg = sum(s["score"] for s in series) / len(series)
        fl_summaries.append({
            "faultline_id": fl_id,
            "faultline_name": series[-1]["faultline_name"],
            "state": series[-1]["state"],
            "first": round(first, 1),
            "last": round(last, 1),
            "peak": round(peak, 1),
            "avg": round(avg, 1),
            "delta": round(last - first, 1),
            "level": series[-1]["level"],
            "days_observed": len(series),
        })

    by_state: dict = defaultdict(list)
    for summary in fl_summaries:
        by_state[summary["state"]].append(summary)
    # Sort each state's faultlines by current score desc
    for st in by_state:
        by_state[st] = sorted(by_state[st], key=lambda x: -x["last"])

    rising = sorted([s for s in fl_summaries if s["delta"] >= 10],
                    key=lambda x: -x["delta"])[:10]
    declining = sorted([s for s in fl_summaries if s["delta"] <= -10],
                       key=lambda x: x["delta"])[:5]
    critical = sorted([s for s in fl_summaries if s["last"] >= 75],
                      key=lambda x: -x["last"])

    return {
        "available": True,
        "by_state": dict(by_state),
        "rising": rising,
        "declining": declining,
        "critical": critical,
        "total_faultlines": len(fl_summaries),
    }


def _faultline_narrative_prompt(state: str, faultlines: list, month_name: str) -> str:
    """LLM prompt for state-level faultline narrative summary."""
    lines = []
    for f in faultlines[:8]:
        arrow = "rising" if f["delta"] > 2 else ("falling" if f["delta"] < -2 else "flat")
        lines.append(
            f"- {f['faultline_name']}: {f['last']:.0f}/100 ({f['level']}), "
            f"{arrow} {f['delta']:+.1f} pts over {f['days_observed']} days "
            f"(peak {f['peak']:.0f}, avg {f['avg']:.0f})"
        )
    fl_summary = "\n".join(lines)

    return f"""You are writing the faultline analysis section of a monthly strategic intelligence brief.

State: {state}
Period: {month_name}

Faultline data for this month:
{fl_summary}

Write a tight 4-6 sentence narrative that:
1. Names the 2-3 most concerning faultlines for {state} this month and why
2. Calls out direction (rising / falling / flat) with the delta
3. Connects related faultlines through their underlying drivers (don't list — synthesize)
4. Ends with one concrete recommendation for what to monitor next month

Use label conventions: [CONFIRMED] for direct data points (e.g. "Score rose 18 pts [CONFIRMED]"),
[ASSESSED] for inferences, [SPECULATIVE] for forecasts.

Return strict JSON:
{{
  "summary": "your narrative paragraph here",
  "manual_review_advisory": "2-3 sentence advisory on what to inspect manually for {state} - mention specific local news cycles, social media channels, or narratives worth checking"
}}
"""


async def _build_paoi_analysis(year: int, month: int, month_name: str, force_rich: bool = False, iod: str = "IOD-1") -> dict:
    """
    Build the Priority Area of Interest analysis block:
      commander_dashboard, paois (deep-dives), synthesis (rich/lean),
      other_movements.

    Tier selection: RICH on first generation or when force_rich=True; LEAN otherwise.
    """
    import paoi_brief

    start_iso, end_iso = _month_range(year, month)

    # Determine synthesis tier from prior generation count (per-IOD — each IOD
    # gets its own rich-first-then-lean cadence, since each starts empty).
    prior = await monthly_briefs_col.find_one(
        {"year": year, "month": month, **_iod_query_filter(iod)}, {"_id": 0, "generation_count": 1}
    )
    prior_count = (prior or {}).get("generation_count", 0)
    tier = "rich" if (prior_count == 0 or force_rich) else "lean"

    try:
        agg = await paoi_brief.aggregate_paoi_period(db, start_iso, end_iso, iod=iod)
        dashboard = paoi_brief.build_commander_dashboard(agg)
        synthesis = await paoi_brief.run_paoi_synthesis(
            db, agg, dashboard, month_name, tier, _call_llm_json
        )
        other = await paoi_brief.other_faultline_movements(db, start_iso, end_iso, iod=iod)
        return {
            "available": bool(agg.get("paois")),
            "commander_dashboard": dashboard,
            "paois": agg.get("paois", []),
            "synthesis": synthesis,
            "other_movements": other,
            "synthesis_tier": tier,
            "_next_generation_count": prior_count + 1,
        }
    except Exception as e:
        logger.exception(f"PAOI analysis build failed: {e}")
        return {
            "available": False, "commander_dashboard": [], "paois": [],
            "synthesis": {}, "other_movements": {},
            "synthesis_tier": tier, "_next_generation_count": prior_count + 1,
        }


# ── Per-PAOI map layers + Commander's Attention Required ─────────────────────

async def _paoi_window_map_points(keyword_pull: dict, start_iso: str, end_iso: str) -> tuple[list, list]:
    """Geocoded critical items (topped up with high when critical < 3) matching
    a PAOI keyword pull in [start, end) — one period's map layer."""
    import paoi_brief
    import brief_visuals

    keywords = [k.lower() for k in (keyword_pull or {}).get("keywords", [])]
    excludes = [k.lower() for k in (keyword_pull or {}).get("exclude_keywords", [])]
    if not keywords:
        return [], []
    q: dict = {
        "published_at": {"$gte": start_iso[:10], "$lt": end_iso[:10]},
        "processed": True,
        "severity": {"$in": ["critical", "high"]},
    }
    regions = (keyword_pull or {}).get("regions", [])
    if regions:
        q["$or"] = [{"regions": {"$in": regions}}, {"state": {"$in": regions}}]
    cursor = intelligence_col.find(q, {
        "_id": 0, "title": 1, "ai_summary": 1, "entities": 1,
        "state": 1, "district": 1, "severity": 1, "priority_score": 1,
    }).sort("priority_score", -1).limit(300)
    matched = []
    async for art in cursor:
        if paoi_brief.article_matches_pull(art, keywords, excludes):
            matched.append(art)
        if len(matched) >= 30:
            break
    crit = [a for a in matched if a.get("severity") == "critical"]
    high = [a for a in matched if a.get("severity") == "high"]
    chosen = crit[:10]
    if len(chosen) < 3:
        chosen = chosen + high[:3 - len(chosen)]
    return brief_visuals.geocode_points(chosen)


async def _build_paoi_map_points(paoi_ids: list, start_iso: str, end_iso: str,
                                 prev_start_iso: str, prev_end_iso: str) -> dict:
    """Per-PAOI map layers for current + previous period. Reads keyword_pull
    from the priority_areas registry directly so the shared aggregation output
    shape (also consumed by the report agent) stays untouched."""
    out = {}
    for pid in paoi_ids:
        pa = await db.priority_areas.find_one({"id": pid}, {"_id": 0, "keyword_pull": 1})
        kp = (pa or {}).get("keyword_pull") or {}
        cur_pts, cur_unres = await _paoi_window_map_points(kp, start_iso, end_iso)
        prev_pts, _ = await _paoi_window_map_points(kp, prev_start_iso, prev_end_iso)
        if cur_pts or prev_pts:
            out[pid] = {
                "current": cur_pts,
                "previous": prev_pts,
                "unresolved_current": cur_unres,
            }
    return out


def _category_covered_by_paoi(category: str) -> bool:
    """True when a threat category shares a substantive word with a PAOI name
    (approximation of 'already the lead topic of an existing PAOI')."""
    import re
    from priority_areas_seed import PRIORITY_AREAS
    cat_words = {w for w in re.split(r"[^a-z]+", category.lower()) if len(w) > 3}
    for pa in PRIORITY_AREAS:
        pa_words = {w for w in re.split(r"[^a-z]+", pa["name"].lower()) if len(w) > 3}
        if cat_words & pa_words:
            return True
    return False


def _detect_attention_items(stats: dict, prev_stats: Optional[dict],
                            category_baselines: list, other_movements: dict) -> list:
    """Pure outlier scan for Commander's Attention Required. Deterministic —
    every number in the output comes straight from the inputs, no LLM."""
    from periodic_report_config import ATTENTION_CONFIG as CFG

    candidates = []

    # 1. Sharp movement on faultlines NOT covered by any PAOI
    for fl in (other_movements.get("rising", []) + other_movements.get("declining", [])):
        delta = fl.get("delta") or 0
        if abs(delta) >= CFG["faultline_delta_threshold"]:
            direction = "rose" if delta > 0 else "fell"
            state_tag = f" ({fl['state']})" if fl.get("state") else ""
            candidates.append({
                "type": "faultline_shift",
                "magnitude": abs(delta) / CFG["faultline_delta_threshold"],
                "headline": f"Non-PAOI faultline moved sharply: {fl.get('name', '')}{state_tag}",
                "significance": (
                    f"Concern score {direction} {abs(delta):.0f} points this period "
                    "on a faultline not tracked by any priority area."
                ),
                "numbers": f"now {fl.get('last', 0):.0f}/100 ({fl.get('level', '')}), delta {delta:+.0f} pts",
            })

    # 2. State Stability Index swings vs previous period
    if prev_stats:
        prev_map = {s["state"]: s for s in prev_stats.get("stability", [])}
        for s in stats.get("stability", []):
            p = prev_map.get(s["state"])
            if not p:
                continue
            d = (s.get("score") or 0) - (p.get("score") or 0)
            if abs(d) >= CFG["stability_delta_threshold"]:
                direction = "improved" if d > 0 else "deteriorated"
                candidates.append({
                    "type": "stability_shift",
                    "magnitude": abs(d) / CFG["stability_delta_threshold"],
                    "headline": f"{s['state']} Stability Index {direction} sharply",
                    "significance": (
                        f"Period-over-period swing of {abs(d)} points crosses the "
                        f"{CFG['stability_delta_threshold']}-point alert threshold."
                    ),
                    "numbers": (
                        f"{p.get('score')}/100 ({p.get('level')}) -> "
                        f"{s.get('score')}/100 ({s.get('level')}), delta {d:+d}"
                    ),
                })

    # 3. Threat-category volume spikes vs trailing baseline
    if category_baselines:
        base_counts: dict = {}
        for cats in category_baselines:
            for entry in cats or []:
                name, cnt = entry[0], entry[1]
                base_counts.setdefault(name, []).append(cnt)
        for entry in stats.get("top_categories", []):
            name, cnt = entry[0], entry[1]
            base = base_counts.get(name)
            if not base:
                continue
            mean = sum(base) / len(base)
            if mean <= 0:
                continue
            ratio = cnt / mean
            if (cnt >= CFG["category_spike_min_count"]
                    and ratio >= CFG["category_spike_ratio"]
                    and not _category_covered_by_paoi(name)):
                candidates.append({
                    "type": "category_spike",
                    "magnitude": ratio / CFG["category_spike_ratio"],
                    "headline": f"'{name}' report volume spiked",
                    "significance": (
                        f"{ratio:.1f}x the trailing {len(base)}-period average and "
                        "not the lead topic of any priority area."
                    ),
                    "numbers": f"{cnt} items this period vs {mean:.0f} avg over prior {len(base)} period(s)",
                })

    candidates.sort(key=lambda c: -c["magnitude"])
    return [{k: v for k, v in c.items() if k != "magnitude"}
            for c in candidates[:CFG["max_items"]]]


async def _build_attention_required(stats: dict, prev_stats: Optional[dict],
                                    category_baselines: list,
                                    start_iso: str, end_iso: str, iod: str = "IOD-1") -> list:
    """Assemble Commander's Attention Required items for the period."""
    import paoi_brief
    try:
        other = await paoi_brief.other_faultline_movements(db, start_iso, end_iso, limit=20, iod=iod)
    except Exception:
        logger.exception("other_faultline_movements failed for attention scan")
        other = {"rising": [], "declining": []}
    return _detect_attention_items(stats, prev_stats, category_baselines, other)


async def _run_generation_core(year: int, month: int, iod: str = "IOD-1", force_rich: bool = False) -> dict:
    """The actual heavy generator — called via background task or directly.

    Builds the FULL brief for one IOD, including the shared-core sections
    (stats, executive summary, state sections, mitigation playbook, scenarios,
    cross-border analysis) that are objective ground truth, not IOD-specific.
    IOD-1 always runs this in full. For IOD-4/5/CIJ, `_run_generation` below
    reuses IOD-1's shared-core output instead of calling this again — see
    that function for the cost-saving path."""
    logger.info(f"Monthly brief generation start: {year}-{month:02d} ({iod})")

    # 1. Aggregate stats
    stats = await _aggregate_month_stats(year, month)

    if stats["total"] == 0:
        return {
            "year": year, "month": month, "iod": iod, "status": "empty",
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
            mitigation_tasks.append(_call_llm_json(_mitigation_playbook_prompt(s["state"], s, actors_str, cats_str), max_tokens=1400))
    mitigation_results = await asyncio.gather(*mitigation_tasks)
    for st, res in zip(mitigation_states, mitigation_results):
        if not res:
            logger.warning(f"Mitigation playbook empty for {st} — LLM returned no parseable JSON")
        else:
            logger.info(f"Mitigation playbook OK for {st}: keys={list(res.keys())}")
    mitigation_playbook = {st: res for st, res in zip(mitigation_states, mitigation_results) if res}

    # 2d. Cross-border analysis (Bangladesh + Myanmar deep dive)
    cross_border_analysis = await _call_llm_json(
        _cross_border_prompt(stats.get("cb_bangladesh", []), stats.get("cb_myanmar", []), month_name),
        max_tokens=1000,
    )

    # 2e. Predictive scenarios
    scenarios_payload = await _call_llm_json(_scenarios_prompt(stats, year, month), max_tokens=900)
    scenarios = scenarios_payload.get("scenarios", []) if isinstance(scenarios_payload, dict) else []

    # 2f. Faultline analysis section (Phase 5a)
    faultline_section = await _aggregate_faultline_section(year, month, iod=iod)
    if faultline_section["available"]:
        narrative_tasks = []
        narrative_states = []
        for st, fls in faultline_section["by_state"].items():
            if not fls:
                continue
            narrative_states.append(st)
            narrative_tasks.append(
                _call_llm_json(_faultline_narrative_prompt(st, fls, month_name), max_tokens=500)
            )
        narrative_results = await asyncio.gather(*narrative_tasks)
        narratives = {st: res for st, res in zip(narrative_states, narrative_results) if res}
        faultline_section["state_narratives"] = narratives
    else:
        faultline_section["state_narratives"] = {}

    # 2g. PAOI sections (Commander Priority Dashboard + deep-dives + inference).
    #     Rich synthesis on first generation of this period, lean on regen.
    paoi_analysis = await _build_paoi_analysis(year, month, month_name, force_rich=force_rich, iod=iod)

    # 2h. Per-PAOI map layers — current vs previous month critical items
    start_iso, end_iso = _month_range(year, month)
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_start_iso, prev_end_iso = _month_range(prev_y, prev_m)
    try:
        paoi_analysis["map_points"] = await _build_paoi_map_points(
            [p["id"] for p in paoi_analysis.get("paois", [])],
            start_iso, end_iso, prev_start_iso, prev_end_iso,
        )
    except Exception:
        logger.exception("PAOI map point build failed")
        paoi_analysis["map_points"] = {}

    # 2i. Commander's Attention Required — deterministic outlier scan
    prev_doc = await monthly_briefs_col.find_one(
        {"year": prev_y, "month": prev_m, "status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod)},
        {"_id": 0, "stats.stability": 1},
    )
    from periodic_report_config import ATTENTION_CONFIG
    baseline_cursor = monthly_briefs_col.find(
        {"status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod),
         "$nor": [{"year": year, "month": month}]},
        {"_id": 0, "stats.top_categories": 1},
    ).sort([("year", -1), ("month", -1)]).limit(ATTENTION_CONFIG["category_baseline_periods"])
    category_baselines = [
        (b.get("stats") or {}).get("top_categories", [])
        async for b in baseline_cursor
    ]
    attention_required = await _build_attention_required(
        stats, (prev_doc or {}).get("stats"), category_baselines, start_iso, end_iso, iod=iod,
    )

    # 3. Assemble brief
    # Detect partial failure — LLM calls silently returned empty
    llm_ok = bool(exec_summary and state_sections)
    if not llm_ok:
        logger.error(
            f"Monthly brief LLM content missing: exec_summary={bool(exec_summary)}, "
            f"state_sections={len(state_sections)}/{len(target_states)} states"
        )

    brief = {
        "year": year, "month": month, "iod": iod,
        "status": "ready" if llm_ok else "partial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "executive_summary": exec_summary,
        "state_sections": state_sections,
        "mitigation_playbook": mitigation_playbook,
        "scenarios": scenarios,
        "cross_border_analysis": cross_border_analysis,
        "faultline_analysis": faultline_section,
        "paoi_analysis": paoi_analysis,
        "attention_required": attention_required,
        # pop (not get) so the internal key doesn't persist in the stored doc
        "generation_count": paoi_analysis.pop("_next_generation_count", 1),
    }
    if not llm_ok:
        brief["_llm_error"] = "LLM calls returned empty — check OpenRouter API key and rate limits. Re-generate to retry."

    # 4b. Social Media Pulse — sentiment for this period's own window (shared
    # ground truth, same for every IOD — not filtered)
    from social_pulse import get_social_pulse_for_period
    brief["social_pulse"] = await get_social_pulse_for_period(db, start_iso, end_iso)

    # 5. NotebookLM markdown
    brief["notebooklm_script"] = _build_notebooklm_script(brief, year, month)

    # 6. Persist
    await monthly_briefs_col.replace_one(
        {"year": year, "month": month, **_iod_query_filter(iod)}, brief, upsert=True,
    )
    logger.info(f"Monthly brief generation {'complete' if llm_ok else 'partial (LLM empty)'}: {year}-{month:02d} ({iod})")
    return brief


async def _run_generation(year: int, month: int, iod: str = "IOD-1", force_rich: bool = False) -> dict:
    """Entry point used by the generate endpoint / background task.

    IOD-1 runs the full generator unchanged (byte-for-byte the same behavior
    as before IOD-scoping). IOD-4/5/CIJ reuse IOD-1's shared-core sections
    (stats, executive summary, state sections, mitigation playbook, scenarios,
    cross-border analysis, social pulse — objective ground truth, identical
    for every IOD) and only recompute the IOD-specific parts: faultline
    analysis (filtered to that IOD's watch-list) and PAOI analysis (that IOD's
    own priority areas). This matches the plan's cost design — no IOD pays for
    LLM calls that would just reproduce IOD-1's own output."""
    if iod == "IOD-1":
        return await _run_generation_core(year, month, iod="IOD-1", force_rich=force_rich)

    core_doc = await monthly_briefs_col.find_one(
        {"year": year, "month": month, **_iod_query_filter("IOD-1"),
         "status": {"$in": ["ready", "partial"]}},
        {"_id": 0},
    )
    if not core_doc:
        core_doc = await _run_generation_core(year, month, iod="IOD-1", force_rich=force_rich)
    if core_doc.get("status") not in ("ready", "partial"):
        # No items this month at all — same "empty" outcome applies to every IOD.
        return {**core_doc, "iod": iod}

    month_name = datetime(year, month, 1).strftime("%B %Y")
    start_iso, end_iso = _month_range(year, month)
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_start_iso, prev_end_iso = _month_range(prev_y, prev_m)

    faultline_section = await _aggregate_faultline_section(year, month, iod=iod)
    if faultline_section["available"]:
        narrative_tasks = []
        narrative_states = []
        for st, fls in faultline_section["by_state"].items():
            if not fls:
                continue
            narrative_states.append(st)
            narrative_tasks.append(
                _call_llm_json(_faultline_narrative_prompt(st, fls, month_name), max_tokens=500)
            )
        narrative_results = await asyncio.gather(*narrative_tasks)
        faultline_section["state_narratives"] = {
            st: res for st, res in zip(narrative_states, narrative_results) if res
        }
    else:
        faultline_section["state_narratives"] = {}

    paoi_analysis = await _build_paoi_analysis(year, month, month_name, force_rich=force_rich, iod=iod)
    try:
        paoi_analysis["map_points"] = await _build_paoi_map_points(
            [p["id"] for p in paoi_analysis.get("paois", [])],
            start_iso, end_iso, prev_start_iso, prev_end_iso,
        )
    except Exception:
        logger.exception("PAOI map point build failed")
        paoi_analysis["map_points"] = {}

    prev_doc = await monthly_briefs_col.find_one(
        {"year": prev_y, "month": prev_m, "status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod)},
        {"_id": 0, "stats.stability": 1},
    )
    from periodic_report_config import ATTENTION_CONFIG
    baseline_cursor = monthly_briefs_col.find(
        {"status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod),
         "$nor": [{"year": year, "month": month}]},
        {"_id": 0, "stats.top_categories": 1},
    ).sort([("year", -1), ("month", -1)]).limit(ATTENTION_CONFIG["category_baseline_periods"])
    category_baselines = [
        (b.get("stats") or {}).get("top_categories", [])
        async for b in baseline_cursor
    ]
    attention_required = await _build_attention_required(
        core_doc["stats"], (prev_doc or {}).get("stats"), category_baselines, start_iso, end_iso, iod=iod,
    )

    brief = {
        **{k: core_doc[k] for k in (
            "status", "stats", "executive_summary", "state_sections",
            "mitigation_playbook", "scenarios", "cross_border_analysis", "social_pulse",
        ) if k in core_doc},
        "year": year, "month": month, "iod": iod,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "faultline_analysis": faultline_section,
        "paoi_analysis": paoi_analysis,
        "attention_required": attention_required,
        "generation_count": paoi_analysis.pop("_next_generation_count", 1),
    }
    brief["notebooklm_script"] = _build_notebooklm_script(brief, year, month)

    await monthly_briefs_col.replace_one(
        {"year": year, "month": month, "iod": iod}, brief, upsert=True,
    )
    logger.info(f"Monthly brief generation complete: {year}-{month:02d} ({iod}, reused IOD-1 shared core)")
    return brief


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/brief/monthly/generate")
async def generate_monthly_brief(
    background_tasks: BackgroundTasks,
    year:  int = Query(...),
    month: int = Query(..., ge=1, le=12),
    force_rich: bool = Query(False, description="Force rich LLM synthesis even on regen"),
    iod: Optional[str] = Query(None, description="Admin-only override — generate another IOD's brief"),
    current_user: dict = Depends(get_current_user),
):
    """Kick off (re)generation. Marks brief as 'generating' immediately, then
    runs full LLM synthesis in background. Poll /brief/monthly/{y}/{m} for status."""
    _require_brief_author(current_user)
    effective_iod = _effective_iod(current_user, iod)

    # Preserve generation_count across regenerations so the rich/lean tier
    # selection works. The stub below otherwise wipes it (replace_one), forcing
    # every regen back to the expensive rich tier.
    prior = await monthly_briefs_col.find_one(
        {"year": year, "month": month, **_iod_query_filter(effective_iod)}, {"_id": 0, "generation_count": 1}
    )
    prior_count = (prior or {}).get("generation_count", 0)

    # Mark as generating
    await monthly_briefs_col.replace_one(
        {"year": year, "month": month, **_iod_query_filter(effective_iod)},
        {"year": year, "month": month, "iod": effective_iod, "status": "generating",
         "generation_count": prior_count,
         "started_at": datetime.now(timezone.utc).isoformat()},
        upsert=True,
    )

    async def _bg():
        try:
            await _run_generation(year, month, iod=effective_iod, force_rich=force_rich)
        except Exception as e:
            logger.exception("monthly brief generation crashed")
            await monthly_briefs_col.update_one(
                {"year": year, "month": month, **_iod_query_filter(effective_iod)},
                {"$set": {"status": "error", "error": str(e)[:300]}},
            )

    background_tasks.add_task(_bg)
    return {"status": "generating", "year": year, "month": month, "iod": effective_iod}


@router.get("/brief/monthly/list")
async def list_monthly_briefs(iod: str = Query("IOD-1", description="Which IOD's briefs to list")):
    """List all available monthly briefs for the given IOD (newest first)."""
    cursor = monthly_briefs_col.find(
        {**_iod_query_filter(iod)}, {"_id": 0, "year": 1, "month": 1, "status": 1, "generated_at": 1}
    ).sort([("year", -1), ("month", -1)]).limit(36)
    return {"briefs": [b async for b in cursor]}


@router.get("/brief/monthly/stability-history")
async def monthly_stability_history(iod: str = Query("IOD-1")):
    """Return stability scores + sev_counts for all ready monthly briefs (for trend chart)."""
    cursor = monthly_briefs_col.find(
        {"status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod)},
        {"_id": 0, "year": 1, "month": 1,
         "stats.stability": 1, "stats.sev_counts": 1, "stats.total": 1},
    ).sort([("year", 1), ("month", 1)])
    results = []
    async for b in cursor:
        stats = b.get("stats") or {}
        results.append({
            "year": b["year"],
            "month": b["month"],
            "label": datetime(b["year"], b["month"], 1).strftime("%b %Y"),
            "stability": stats.get("stability", []),
            "sev_counts": stats.get("sev_counts", {}),
            "total": stats.get("total", 0),
        })
    return {"history": results}


@router.get("/brief/monthly/{year}/{month}")
async def get_monthly_brief(year: int, month: int, iod: str = Query("IOD-1")):
    brief = await monthly_briefs_col.find_one({"year": year, "month": month, **_iod_query_filter(iod)}, {"_id": 0})
    if not brief:
        raise HTTPException(404, "Brief not generated for this month — POST to /brief/monthly/generate first")
    return brief


@router.get("/brief/monthly/{year}/{month}/notebooklm", response_class=PlainTextResponse)
async def get_monthly_brief_notebooklm(year: int, month: int, iod: str = Query("IOD-1")):
    """Returns the markdown script optimized for NotebookLM Video Overview generation.
    Frontend exposes this as a 'Copy for NotebookLM' button."""
    brief = await monthly_briefs_col.find_one(
        {"year": year, "month": month, **_iod_query_filter(iod)}, {"notebooklm_script": 1}
    )
    if not brief or not brief.get("notebooklm_script"):
        raise HTTPException(404, "Brief not generated or markdown not ready")
    return brief["notebooklm_script"]


@router.get("/brief/monthly/{year}/{month}/pdf")
async def get_monthly_brief_pdf(
    year: int,
    month: int,
    include_faultlines: bool = Query(True, description="Set false to exclude the Faultline Analysis section from the combined PDF."),
    iod: str = Query("IOD-1"),
):
    """PDF export of the monthly brief.

    Default behavior includes the Faultline Analysis section (full Monthly
    Strategic Brief). Pass include_faultlines=false to get the Monthly Brief
    portion only (commander option from the UI)."""
    brief = await monthly_briefs_col.find_one({"year": year, "month": month, **_iod_query_filter(iod)}, {"_id": 0})
    if not brief:
        raise HTTPException(404, "Brief not generated")
    if brief.get("status") not in ("ready", "partial"):
        raise HTTPException(425, f"Brief status: {brief.get('status')} — wait for generation to complete")

    # Fetch previous month for comparison snapshot
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_brief = await monthly_briefs_col.find_one(
        {"year": prev_year, "month": prev_month, "status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod)},
        {"_id": 0},
    )

    # Per-PAOI score history across all stored briefs (for trendline at 3+ periods)
    paoi_history = defaultdict(list)
    hist_cursor = monthly_briefs_col.find(
        {"status": {"$in": ["ready", "partial"]}, **_iod_query_filter(iod)},
        {"_id": 0, "year": 1, "month": 1, "paoi_analysis.commander_dashboard": 1},
    ).sort([("year", 1), ("month", 1)])
    async for b in hist_cursor:
        if (b["year"], b["month"]) > (year, month):
            continue  # future periods don't belong on this brief's trendline
        label = datetime(b["year"], b["month"], 1).strftime("%b %y")
        for row in (b.get("paoi_analysis") or {}).get("commander_dashboard", []):
            if row.get("score") is not None:
                paoi_history[row["id"]].append({
                    "label": label, "score": row["score"], "level": row.get("level", ""),
                })

    try:
        pdf_bytes = _render_pdf(brief, prev_brief=prev_brief, include_faultlines=include_faultlines,
                                paoi_history=dict(paoi_history))
    except Exception as e:
        import traceback
        logger.error(f"PDF render failed: {traceback.format_exc()}")
        raise HTTPException(500, f"PDF render error: {type(e).__name__}: {e}")
    suffix = "" if include_faultlines else "_brief_only"
    filename = f"NER_Monthly_Strategic_{year}_{month:02d}{suffix}.pdf"
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


def _render_pdf(brief: dict, prev_brief: dict = None, include_faultlines: bool = True,
                paoi_history: dict = None) -> bytes:
    """paoi_history: {paoi_id: [{label, score, level}, ...]} oldest→newest,
    supplied by the PDF routes for the per-PAOI trendline (drawn at 3+ periods)."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    # ── Palette ────────────────────────────────────────────────────────────────
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

    year, month  = brief["year"], brief["month"]
    month_name   = datetime(year, month, 1).strftime("%B %Y")
    gen_ts       = brief.get("generated_at", "")[:19].replace("T", " ")
    # Detect brief type — fortnightly briefs carry a "period" key
    period       = brief.get("period")
    period_label = brief.get("period_label", month_name)
    brief_type   = "FORTNIGHTLY STRATEGIC BRIEF" if period else "MONTHLY STRATEGIC BRIEF"
    display_period = period_label if period else month_name
    stats        = brief.get("stats", {})
    sev_counts   = stats.get("sev_counts", {})
    total        = stats.get("total", 0)
    crit         = sev_counts.get("critical", 0)
    high_        = sev_counts.get("high", 0)
    cross        = stats.get("cross_border_count", 0)
    stability    = stats.get("stability", [])

    class BriefPDF(FPDF):
        def header(self):
            self.set_fill_color(*C_BG)
            self.rect(0, 0, 210, 28, "F")
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*C_ACCENT)
            self.set_y(4)
            self.cell(0, 8, "RHINO DRISHTI", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 8)
            self.set_text_color(160, 170, 150)
            self.cell(0, 4, f"NER INTELLIGENCE PLATFORM  |  {brief_type}", align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_font("Helvetica", "", 7)
            self.cell(0, 4, _ascii(f"Classification: RESTRICTED  |  Period: {display_period}  |  Generated: {gen_ts}"), align="C", new_x="LMARGIN", new_y="NEXT")
            self.set_y(32)

        def footer(self):
            self.set_y(-12)
            self.set_fill_color(*C_BG)
            self.rect(0, self.h - 12, 210, 12, "F")
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*C_ACCENT)
            self.cell(0, 10, _ascii(f"Rhino Drishti Intel Brief | {display_period} | Page {self.page_no()}/{{nb}} | RESTRICTED"), align="C")

        def section_title(self, title, sub=""):
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*C_SEC_TEXT)
            self.set_fill_color(*C_SEC_BG)
            label = f"  {title}" + (f"  |  {sub}" if sub else "")
            self.cell(0, 8, _ascii(label), fill=True, **NL)
            self.ln(2)

    pdf = BriefPDF()
    pdf.alias_nb_pages()
    pdf.set_margins(10, 10, 10)
    pdf.set_auto_page_break(auto=True, margin=18)

    # ── Helper: draw 4 colored stat boxes across the page ─────────────────────
    def draw_stat_boxes(labels, values, colors, box_h=18):
        box_w = 46
        y0 = pdf.get_y()
        for i, (lbl, val, col) in enumerate(zip(labels, values, colors)):
            bx = 10 + i * (box_w + 1)
            pdf.set_fill_color(*col)
            pdf.rect(bx, y0, box_w, box_h, "F")
            pdf.set_xy(bx, y0 + 2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(box_w, 8, val, align="C")
            pdf.set_xy(bx, y0 + 11)
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(220, 220, 220)
            pdf.cell(box_w, 5, lbl, align="C")
        pdf.set_y(y0 + box_h + 4)

    # ── Helper: horizontal severity bar chart ─────────────────────────────────
    def draw_severity_bars(sev_dict):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*C_SEC_TEXT)
        pdf.cell(0, 5, "Severity Distribution", **NL)
        bar_h    = 5
        label_w  = 30
        max_cnt  = max((sev_dict.get(s, 0) for s in SEV_COLORS), default=1) or 1
        bar_max  = 120
        for sev_label in ["critical", "high", "medium", "low"]:
            cnt    = sev_dict.get(sev_label, 0)
            bar_w  = max(1, int(cnt / max_cnt * bar_max)) if cnt else 0
            cy     = pdf.get_y()
            pdf.set_xy(10, cy)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(label_w, bar_h, _ascii(f"  {sev_label.capitalize()}:"))
            if bar_w > 0:
                pdf.set_fill_color(*SEV_COLORS[sev_label])
                pdf.rect(10 + label_w, cy, bar_w, bar_h, "F")
            pdf.set_xy(10 + label_w + bar_max + 3, cy)
            pdf.cell(15, bar_h, str(cnt), **NL)
        pdf.ln(2)

    # ── Helper: bordered table ────────────────────────────────────────────────
    def draw_table(headers, col_ws, rows, row_h=5):
        pdf.set_fill_color(*C_TBL_HDR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 7)
        for j, (h, w) in enumerate(zip(headers, col_ws)):
            kw = NL if j == len(headers) - 1 else {}
            pdf.cell(w, 6, _ascii(str(h)), fill=True, border=1, **kw)
        for i, row_vals in enumerate(rows):
            if pdf.get_y() > 265:
                pdf.add_page()
            pdf.set_fill_color(*C_TBL_ALT if i % 2 == 0 else (255, 255, 255))
            pdf.set_text_color(40, 40, 40)
            pdf.set_font("Helvetica", "", 7)
            for j, (v, w) in enumerate(zip(row_vals, col_ws)):
                kw = NL if j == len(row_vals) - 1 else {}
                pdf.cell(w, row_h, _ascii(str(v))[:int(w * 1.4)], fill=True, border=1, **kw)

    # ══════════════════════════════════════════════════════════════════════════
    # 1. COMMANDER'S PRIORITY DASHBOARD + PAOI DEEP DIVES
    # ══════════════════════════════════════════════════════════════════════════
    paoi = brief.get("paoi_analysis") or {}
    if paoi.get("available"):
        pdf.add_page()
        pdf.set_fill_color(150, 30, 30)  # red header — priority
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _ascii("  COMMANDER'S PRIORITY DASHBOARD"), fill=True, **NL)
        pdf.ln(2)

        # Verbal status strip (no raw numbers)
        dash = paoi.get("commander_dashboard", [])
        if dash:
            parts = [
                f"P{r.get('rank')} {r.get('name','')[:22]}: {r.get('level','')} {r.get('trend','')}"
                for r in dash
            ]
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            pdf.set_fill_color(245, 248, 242)
            pdf.multi_cell(0, 5, _ascii("   |   ".join(parts)), fill=True, **NL)
            pdf.ln(2)

        # Bottom line + focus next period (rich LLM analysis)
        overall = (paoi.get("synthesis") or {}).get("overall", {})
        if overall.get("bottom_line"):
            pdf.set_fill_color(240, 230, 230)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(150, 30, 30)
            pdf.cell(0, 6, _ascii("  BOTTOM LINE"), fill=True, **NL)
            pdf.set_fill_color(252, 245, 245)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 5, _ascii(str(overall["bottom_line"])), fill=True, **NL)
            pdf.ln(2)
        focus = overall.get("top_3_focus_next") or []
        if focus:
            pdf.set_fill_color(240, 245, 235)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.cell(0, 6, _ascii("  FOCUS NEXT PERIOD"), fill=True, **NL)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            for i, f in enumerate(focus, 1):
                pdf.multi_cell(0, 5, _ascii(f"  {i}. {f}"), **NL)
            pdf.ln(2)

        # Per-PAOI narrative deep-dives
        per = (paoi.get("synthesis") or {}).get("per_paoi", {})
        if paoi.get("paois"):
            pdf.set_fill_color(150, 30, 30)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, _ascii("  PRIORITY AREA DEEP DIVES"), fill=True, **NL)
            pdf.ln(2)

        # Previous-period PAOI dashboard rows, for the period comparison block
        prev_dash_map = {}
        if prev_brief:
            for r in (prev_brief.get("paoi_analysis") or {}).get("commander_dashboard", []):
                prev_dash_map[r.get("id")] = r
        paoi_history = paoi_history or {}
        map_points_all = paoi.get("map_points") or {}

        def _trend_word(delta_val, risk_trajectory=""):
            rt = (risk_trajectory or "").upper()
            if rt in ("IMPROVING", "DETERIORATING"):
                return rt
            if rt == "STABLE":
                return "STEADY"
            # Concern scale: rising score = deteriorating situation
            if delta_val >= 5:
                return "DETERIORATING"
            if delta_val <= -5:
                return "IMPROVING"
            return "STEADY"

        last_group = None
        for p in paoi.get("paois", []):
            if pdf.get_y() > 230:
                pdf.add_page()
            mv = p.get("faultline_movement", {})
            syn = per.get(p["id"], {})
            level = mv.get("level", "STABLE")
            delta = mv.get("delta", 0) or 0
            trend = _trend_word(delta, syn.get("risk_trajectory", ""))

            # Group banner when a parent grouping (e.g. RAS) starts
            group = p.get("parent_group") or ""
            if group and group != last_group:
                pdf.set_fill_color(60, 40, 20)
                pdf.set_text_color(240, 220, 170)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 7, _ascii(f"  {group.upper()}"), fill=True, **NL)
                pdf.ln(1)
            last_group = group

            # PAOI header band: name + STATUS | TREND | FL: LEVEL (delta)
            pdf.set_fill_color(30, 60, 40)
            pdf.set_text_color(200, 230, 80)
            pdf.set_font("Helvetica", "B", 10)
            sub_tag = "  >" if group else ""
            hdr = _ascii(f" {sub_tag} P{p.get('rank')} {p.get('name', '')}"[:52])
            status_tag = _ascii(f"{level} | {trend} | FL: {level} ({delta:+.1f})  ")
            pdf.cell(102, 7, hdr, fill=True)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.cell(0, 7, status_tag, fill=True, align="R", **NL)

            # Period comparison: prev status -> current, FL delta, trendline (3+)
            prev_row = prev_dash_map.get(p["id"])
            hist = paoi_history.get(p["id"]) or []
            if prev_row or len(hist) >= 3:
                pdf.set_fill_color(238, 242, 246)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(40, 60, 90)
                pdf.cell(0, 5, _ascii("  PERIOD COMPARISON"), fill=True, **NL)
                if prev_row:
                    p_sc = prev_row.get("score")
                    c_sc = mv.get("last")
                    fl_d = (c_sc - p_sc) if (c_sc is not None and p_sc is not None) else None
                    line = (
                        f"  Previous: {prev_row.get('level', '?')}"
                        + (f" ({p_sc:.0f})" if p_sc is not None else "")
                        + f"  ->  Current: {level}"
                        + (f" ({c_sc:.0f})" if c_sc is not None else "")
                        + (f"   |   FL delta {fl_d:+.1f} pts" if fl_d is not None else "")
                    )
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(40, 40, 40)
                    pdf.cell(0, 5, _ascii(line), **NL)
                if len(hist) >= 3:
                    import brief_visuals
                    if pdf.get_y() > 240:
                        pdf.add_page()
                    y_after = brief_visuals.draw_paoi_trendline(
                        pdf, hist[-12:], pdf.l_margin, pdf.get_y() + 1, w=120, h=28
                    )
                    pdf.set_y(y_after)
                pdf.ln(1)

            if syn.get("situation_overview"):
                # A: Situation Overview
                pdf.set_fill_color(230, 240, 220)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(50, 70, 40)
                pdf.cell(0, 5, _ascii("  A. SITUATION OVERVIEW"), fill=True, **NL)
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.multi_cell(0, 5, _ascii(str(syn["situation_overview"])), **NL)
                pdf.ln(1)

                # B: Critical Developments (new schema; falls back to legacy events)
                devs = syn.get("critical_developments") or []
                legacy_events = syn.get("events") or []
                if devs:
                    pdf.set_fill_color(235, 235, 245)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(30, 30, 80)
                    pdf.cell(0, 5, _ascii(f"  B. CRITICAL DEVELOPMENTS ({len(devs)})"), fill=True, **NL)
                    for di, dv in enumerate(devs, 1):
                        if pdf.get_y() > 252:
                            pdf.add_page()
                        pdf.set_fill_color(210, 215, 228)
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_text_color(20, 20, 60)
                        conf = (dv.get("confidence") or "").upper()
                        conf_tag = f"  [{conf}]" if conf else ""
                        pdf.cell(0, 5, _ascii(f"  {di}. {(dv.get('heading') or '')[:66]}{conf_tag}"), fill=True, **NL)
                        if dv.get("location"):
                            pdf.set_font("Helvetica", "I", 7)
                            pdf.set_text_color(80, 80, 100)
                            pdf.set_x(pdf.l_margin)
                            pdf.cell(0, 4, _ascii(f"  Location: {dv['location'][:85]}"), **NL)
                        if dv.get("description"):
                            pdf.set_font("Helvetica", "", 8)
                            pdf.set_text_color(40, 40, 40)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  {dv['description']}"), **NL)
                        if dv.get("impact_on_pai"):
                            pdf.set_font("Helvetica", "B", 8)
                            pdf.set_text_color(120, 60, 20)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  Impact on PAI: {dv['impact_on_pai']}"), **NL)
                        actors = dv.get("actors") or []
                        if actors:
                            if isinstance(actors, list):
                                actors = ", ".join(str(a) for a in actors)
                            pdf.set_font("Helvetica", "I", 7)
                            pdf.set_text_color(60, 100, 80)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  Actors: {actors}"), **NL)
                        pdf.ln(1)
                elif legacy_events:
                    pdf.set_fill_color(235, 235, 245)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(30, 30, 80)
                    pdf.cell(0, 5, _ascii(f"  B. CRITICAL DEVELOPMENTS ({len(legacy_events)})"), fill=True, **NL)
                    for ei, ev in enumerate(legacy_events, 1):
                        if pdf.get_y() > 252:
                            pdf.add_page()
                        pdf.set_fill_color(210, 215, 228)
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_text_color(20, 20, 60)
                        pdf.cell(0, 5, _ascii(f"  {ei}. {(ev.get('heading') or '')[:78]}"), fill=True, **NL)
                        if ev.get("location"):
                            pdf.set_font("Helvetica", "I", 7)
                            pdf.set_text_color(80, 80, 100)
                            pdf.set_x(pdf.l_margin)
                            pdf.cell(0, 4, _ascii(f"  Location: {ev['location'][:80]}"), **NL)
                        if ev.get("what_happened"):
                            pdf.set_font("Helvetica", "", 8)
                            pdf.set_text_color(40, 40, 40)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  What happened: {ev['what_happened']}"), **NL)
                        if ev.get("why_it_matters"):
                            pdf.set_font("Helvetica", "B", 8)
                            pdf.set_text_color(120, 60, 20)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  Impact on PAI: {ev['why_it_matters']}"), **NL)
                        if ev.get("linkages"):
                            pdf.set_font("Helvetica", "I", 7)
                            pdf.set_text_color(60, 100, 80)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  Linkages: {ev['linkages']}"), **NL)
                        pdf.ln(1)

                # Map view: current (green ring) vs previous (brown ring) items
                mp = map_points_all.get(p["id"]) or {}
                if mp.get("current") or mp.get("previous"):
                    import brief_visuals
                    map_h = 82
                    if pdf.get_y() + map_h + 14 > 275:
                        pdf.add_page()
                    pdf.set_fill_color(230, 240, 220)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(50, 70, 40)
                    pdf.cell(0, 5, _ascii("  SITUATION MAP - CRITICAL ITEM LOCATIONS"), fill=True, **NL)
                    y_after = brief_visuals.draw_paoi_map(
                        pdf, mp.get("current") or [], mp.get("previous") or [],
                        pdf.l_margin, pdf.get_y() + 1, w=130, h=map_h,
                        unresolved=mp.get("unresolved_current") or [],
                    )
                    pdf.set_y(y_after)
                    pdf.ln(1)

                # C: Overall Assessment
                if syn.get("overall_assessment"):
                    if pdf.get_y() > 255:
                        pdf.add_page()
                    pdf.set_fill_color(255, 243, 200)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(120, 80, 0)
                    pdf.cell(0, 5, _ascii("  C. OVERALL ASSESSMENT"), fill=True, **NL)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(60, 40, 0)
                    pdf.multi_cell(0, 5, _ascii(str(syn["overall_assessment"])), **NL)
                    pdf.ln(1)

                # D: Actionable Recommendations (falls back to legacy commander_focus)
                recs = syn.get("actionable_recommendations") or []
                focus = syn.get("commander_focus") or []
                if recs:
                    pdf.set_fill_color(250, 230, 230)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(150, 30, 30)
                    pdf.cell(0, 5, _ascii(f"  D. ACTIONABLE RECOMMENDATIONS ({len(recs)})"), fill=True, **NL)
                    for ri, rec in enumerate(recs, 1):
                        if pdf.get_y() > 250:
                            pdf.add_page()
                        pdf.set_fill_color(252, 240, 240)
                        pdf.set_font("Helvetica", "B", 8)
                        pdf.set_text_color(150, 30, 30)
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(0, 5, _ascii(f"  {ri}. {rec.get('threat_issue', '')}"), fill=True, **NL)
                        for fkey, flabel in [
                            ("geography", "Geography"),
                            ("why_it_matters", "Why It Matters"),
                            ("recommended_action", "Recommended Action"),
                            ("preventive_effect", "Preventive Effect"),
                        ]:
                            v = rec.get(fkey)
                            if not v:
                                continue
                            pdf.set_font("Helvetica", "B", 7)
                            pdf.set_text_color(90, 40, 40)
                            pdf.set_x(pdf.l_margin)
                            pdf.cell(32, 4, _ascii(f"     {flabel}:"))
                            pdf.set_font("Helvetica", "", 7.5)
                            pdf.set_text_color(40, 40, 40)
                            pdf.multi_cell(0, 4, _ascii(str(v)), **NL)
                        pdf.ln(1)
                elif focus:
                    pdf.set_fill_color(250, 230, 230)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(150, 30, 30)
                    pdf.cell(0, 5, _ascii("  D. ACTIONABLE RECOMMENDATIONS"), fill=True, **NL)
                    for fi, fitem in enumerate(focus, 1):
                        if isinstance(fitem, dict):
                            loc = fitem.get("location") or ""
                            action = fitem.get("action") or ""
                            if loc:
                                pdf.set_font("Helvetica", "B", 8)
                                pdf.set_text_color(150, 30, 30)
                                pdf.set_x(pdf.l_margin)
                                pdf.multi_cell(0, 4, _ascii(f"  {fi}. [{loc}]"), **NL)
                                pdf.set_font("Helvetica", "", 8)
                                pdf.set_text_color(40, 40, 40)
                                pdf.set_x(pdf.l_margin)
                                pdf.multi_cell(0, 4, _ascii(f"     {action}"), **NL)
                            else:
                                pdf.set_font("Helvetica", "", 8)
                                pdf.set_text_color(40, 40, 40)
                                pdf.set_x(pdf.l_margin)
                                pdf.multi_cell(0, 4, _ascii(f"  {fi}. {action}"), **NL)
                        else:
                            pdf.set_font("Helvetica", "", 8)
                            pdf.set_text_color(40, 40, 40)
                            pdf.set_x(pdf.l_margin)
                            pdf.multi_cell(0, 4, _ascii(f"  {fi}. {fitem}"), **NL)

                # E: Next Period Watch
                watch = syn.get("next_period_watch") or []
                if watch:
                    if pdf.get_y() > 255:
                        pdf.add_page()
                    pdf.set_fill_color(235, 242, 235)
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(40, 90, 50)
                    pdf.cell(0, 5, _ascii("  E. NEXT PERIOD WATCH"), fill=True, **NL)
                    for wi in watch:
                        if isinstance(wi, dict):
                            geo = wi.get("geography") or ""
                            item_txt = wi.get("item") or ""
                            line = f"  - [{geo}] {item_txt}" if geo else f"  - {item_txt}"
                        else:
                            line = f"  - {wi}"
                        pdf.set_font("Helvetica", "", 8)
                        pdf.set_text_color(40, 40, 40)
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(0, 4, _ascii(line), **NL)

            else:
                # Fallback: lean tier or synthesis unavailable
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(60, 60, 60)
                for f in (mv.get("per_faultline") or [])[:4]:
                    pdf.cell(0, 4, _ascii(f"    {f['name'][:55]}  ({f['level']}) {f['delta']:+.0f}"), **NL)
                if syn.get("period_impact"):
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(40, 40, 40)
                    pdf.multi_cell(0, 5, _ascii(str(syn["period_impact"])), **NL)
                if syn.get("forward_concerns"):
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(120, 80, 20)
                    pdf.multi_cell(0, 4, _ascii(f"Watch next: {syn['forward_concerns']}"), **NL)
                if syn.get("manual_review"):
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(40, 90, 110)
                    pdf.multi_cell(0, 4, _ascii(f"Manual review: {syn['manual_review']}"), **NL)

            pdf.ln(3)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. COMMANDER'S ATTENTION REQUIRED — auto-detected outliers
    #    (positioned after the PAOI deep dives per commander direction)
    # ══════════════════════════════════════════════════════════════════════════
    attention = brief.get("attention_required") or []
    if attention:
        if pdf.page == 0 or pdf.get_y() > 215:
            pdf.add_page()
        else:
            pdf.ln(2)
        pdf.set_fill_color(120, 60, 10)
        pdf.set_text_color(255, 240, 210)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, _ascii("  COMMANDER'S ATTENTION REQUIRED"), fill=True, **NL)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(120, 100, 70)
        pdf.cell(0, 4, _ascii("  Auto-detected statistical outliers outside standing priority-area coverage"), **NL)
        pdf.ln(1)
        for ai, item in enumerate(attention, 1):
            if pdf.get_y() > 255:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(120, 60, 10)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, _ascii(f"  {ai}. {item.get('headline', '')}"), **NL)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 4, _ascii(f"     {item.get('significance', '')}"), **NL)
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_text_color(100, 100, 100)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 4, _ascii(f"     Data: {item.get('numbers', '')}"), **NL)
            pdf.ln(1)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. FAULTLINE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    fl_section = brief.get("faultline_analysis") or {}
    if include_faultlines and fl_section.get("available"):
        pdf.add_page()
        pdf.set_fill_color(*C_TBL_HDR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, _ascii("  Faultline Analysis"), fill=True, **NL)
        pdf.ln(2)

        # Overview line
        pdf.set_text_color(*C_SEC_TEXT)
        pdf.set_font("Helvetica", "", 9)
        rising = fl_section.get("rising", [])
        declining = fl_section.get("declining", [])
        critical = fl_section.get("critical", [])
        pdf.multi_cell(0, 5, _ascii(
            f"Faultlines monitored this period: {fl_section.get('total_faultlines', 0)}. "
            f"Currently CRITICAL: {len(critical)}. Rising (delta >= +10): {len(rising)}. "
            f"Declining (delta <= -10): {len(declining)}."
        ), **NL)
        pdf.ln(2)

        # Per-state table + narrative
        for state in sorted(fl_section.get("by_state", {}).keys()):
            if pdf.get_y() > 230:
                pdf.add_page()
            state_fls = fl_section["by_state"][state]
            pdf.set_fill_color(50, 70, 45)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, _ascii(f"  {state}"), fill=True, **NL)

            # Narrative summary (if LLM produced one)
            narratives = fl_section.get("state_narratives", {})
            n = narratives.get(state) or {}
            if n.get("summary"):
                pdf.set_text_color(*C_SEC_TEXT)
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 5, _ascii(n["summary"]), **NL)
                pdf.ln(1)
            if n.get("manual_review_advisory"):
                pdf.set_text_color(80, 100, 60)
                pdf.set_font("Helvetica", "I", 8)
                pdf.multi_cell(0, 4, _ascii(f"Manual review: {n['manual_review_advisory']}"), **NL)
                pdf.ln(1)

            # Top faultline table
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_fill_color(*C_TBL_HDR)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(95, 5, _ascii("  Faultline"), fill=True)
            pdf.cell(20, 5, "Score",   fill=True, align="C")
            pdf.cell(25, 5, "Level",   fill=True, align="C")
            pdf.cell(20, 5, "Delta",   fill=True, align="C")
            pdf.cell(20, 5, "Peak",    fill=True, align="C", **NL)
            for i, fl in enumerate(state_fls[:8]):
                if pdf.get_y() > 270:
                    pdf.add_page()
                pdf.set_text_color(40, 40, 40)
                pdf.set_font("Helvetica", "", 8)
                if i % 2 == 0:
                    pdf.set_fill_color(*C_TBL_ALT)
                    fill = True
                else:
                    fill = False
                name = fl["faultline_name"][:50]
                pdf.cell(95, 5, _ascii(f"  {name}"), fill=fill)
                pdf.cell(20, 5, f"{fl['last']:.0f}", fill=fill, align="C")
                pdf.cell(25, 5, fl["level"],         fill=fill, align="C")
                delta_str = f"{fl['delta']:+.1f}"
                pdf.cell(20, 5, delta_str, fill=fill, align="C")
                pdf.cell(20, 5, f"{fl['peak']:.0f}", fill=fill, align="C", **NL)
            pdf.ln(2)

        # Rising / declining roll-up + cross-state advisory
        if rising:
            if pdf.get_y() > 230:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.cell(0, 6, _ascii("  Rising faultlines this period (top 10 by delta)"), **NL)
            pdf.set_font("Helvetica", "", 8)
            for r in rising[:10]:
                line = f"  [{r['state']}] {r['faultline_name'][:55]:55s} now {r['last']:.0f}, +{r['delta']:.0f}"
                pdf.cell(0, 4, _ascii(line), **NL)
            pdf.ln(2)

        # General manual review advisory
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(80, 100, 60)
        pdf.multi_cell(0, 4, _ascii(
            "Manual review supplement: for rising or borderline faultlines, inspect regional language news "
            "(Assamese, Bengali, Manipuri, Mizo, Naga), Twitter/X and Telegram narrative spikes, influencer "
            "amplification patterns, and repeated cross-posted claims aligned with foreign-influence indicators."
        ), **NL)

    # ══════════════════════════════════════════════════════════════════════════
    # 3. REGIONAL OVERVIEW — stat boxes + severity chart + stability table
    # ══════════════════════════════════════════════════════════════════════════
    if pdf.page == 0 or pdf.get_y() > 220:
        pdf.add_page()
    else:
        pdf.ln(4)
    pdf.section_title("REGIONAL OVERVIEW", display_period)

    draw_stat_boxes(
        ["TOTAL ITEMS", "CRITICAL", "HIGH PRIORITY", "CROSS-BORDER"],
        [str(total), str(crit), str(high_), str(cross)],
        [(50, 80, 60), (180, 40, 40), (180, 100, 30), (50, 100, 160)],
    )

    draw_severity_bars(sev_counts)

    if stability:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*C_SEC_TEXT)
        pdf.cell(0, 5, "State Stability Index", **NL)
        stable_rows = [
            [s.get("state", ""), s.get("score", "?"), s.get("level", ""),
             stats.get("states", {}).get(s.get("state", ""), {}).get("total", 0)]
            for s in stability
        ]
        draw_table(["State", "Score/100", "Level", "Intel Items"], [65, 32, 55, 38], stable_rows)

    pdf.ln(4)

    # ══════════════════════════════════════════════════════════════════════════
    # 3b. SOCIAL MEDIA PULSE
    # ══════════════════════════════════════════════════════════════════════════
    pulse = brief.get("social_pulse")
    if pulse and pulse.get("platforms"):
        if pdf.get_y() > 240:
            pdf.add_page()
        pdf.section_title("SOCIAL MEDIA PULSE", display_period)
        platform_labels = {"facebook": "Facebook", "instagram": "Instagram", "twitter": "Twitter/X", "youtube": "YouTube"}
        pulse_rows = [
            [platform_labels.get(p, p.title()), f"{s['positive_pct']}%", f"{s['negative_pct']}%", s["post_count"]]
            for p, s in pulse["platforms"].items()
        ]
        combined = pulse.get("combined")
        if combined:
            pulse_rows.append(["Combined", f"{combined['positive_pct']}%", f"{combined['negative_pct']}%", combined["post_count"]])
        draw_table(["Platform", "Positive", "Negative", "Posts Scored"], [55, 35, 35, 45], pulse_rows)
        pdf.ln(4)

    # ══════════════════════════════════════════════════════════════════════════
    # 4. PREVIOUS PERIOD RECAP (if available)
    # ══════════════════════════════════════════════════════════════════════════
    if prev_brief:
        pdf.add_page()
        prev_year_  = prev_brief.get("year", year)
        prev_month_ = prev_brief.get("month", month - 1)
        try:
            prev_month_name = datetime(prev_year_, prev_month_, 1).strftime("%B %Y")
        except Exception:
            prev_month_name = "Previous Period"

        pdf.section_title("PREVIOUS PERIOD RECAP", prev_month_name)

        prev_stats  = prev_brief.get("stats", {})
        prev_sev    = prev_stats.get("sev_counts", {})
        prev_total  = prev_stats.get("total", 0)
        prev_crit   = prev_sev.get("critical", 0)
        prev_high   = prev_sev.get("high", 0)
        prev_cross  = prev_stats.get("cross_border_count", 0)

        def _delta(curr, prev):
            d = curr - prev
            return f"+{d}" if d > 0 else str(d)

        # Delta stat boxes — show prev values with deltas vs current
        box_h2 = 22
        y0 = pdf.get_y()
        box_data = [
            ("TOTAL",   str(prev_total), _delta(total, prev_total),  (70, 90,  70)),
            ("CRITICAL",str(prev_crit),  _delta(crit, prev_crit),    (160, 50, 50)),
            ("HIGH",    str(prev_high),  _delta(high_, prev_high),   (160, 90, 30)),
            ("X-BORDER",str(prev_cross), _delta(cross, prev_cross),  (50, 100, 150)),
        ]
        box_w2 = 46
        for i, (lbl, val, delta, col) in enumerate(box_data):
            bx = 10 + i * (box_w2 + 1)
            pdf.set_fill_color(*col)
            pdf.rect(bx, y0, box_w2, box_h2, "F")
            pdf.set_xy(bx, y0 + 2)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(box_w2, 7, val, align="C")
            pdf.set_xy(bx, y0 + 10)
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(210, 210, 210)
            pdf.cell(box_w2, 4, lbl, align="C")
            pdf.set_xy(bx, y0 + 15)
            pdf.set_font("Helvetica", "I", 6)
            d_num = int(delta.replace("+", "") or "0")
            d_col = (140, 255, 140) if d_num > 0 else (255, 160, 160) if d_num < 0 else (210, 210, 210)
            pdf.set_text_color(*d_col)
            pdf.cell(box_w2, 5, _ascii(f"Now: {delta}"), align="C")
        pdf.set_y(y0 + box_h2 + 4)

        # Stability comparison table
        prev_stability  = prev_stats.get("stability", [])
        curr_stable_map = {s["state"]: s for s in stability}
        prev_stable_map = {s["state"]: s for s in prev_stability}
        all_states      = list(dict.fromkeys(
            [s["state"] for s in prev_stability] + [s["state"] for s in stability]
        ))[:10]

        if all_states:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.cell(0, 5, _ascii(f"Stability Comparison: {prev_month_name} → {month_name}"), **NL)
            cmp_rows = []
            for st in all_states:
                p = prev_stable_map.get(st, {})
                c = curr_stable_map.get(st, {})
                p_sc = p.get("score", 0) or 0
                c_sc = c.get("score", 0) or 0
                d    = c_sc - p_sc
                trend = f"+{d}" if d > 0 else str(d)
                cmp_rows.append([st, str(p_sc), p.get("level", "-"), str(c_sc), c.get("level", "-"), trend])
            draw_table(
                ["State", f"Score ({prev_month_name[:3]})", "Level", f"Score ({month_name[:3]})", "Level", "Trend"],
                [50, 27, 33, 27, 33, 20],
                cmp_rows,
            )

        # Exec summary excerpt from previous period
        prev_exec = prev_brief.get("executive_summary", "")
        if prev_exec:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.cell(0, 5, _ascii(f"Strategic Assessment — {prev_month_name}"), **NL)
            pdf.set_fill_color(248, 252, 245)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(70, 80, 60)
            excerpt = _ascii(prev_exec[:700]) + ("..." if len(prev_exec) > 700 else "")
            pdf.multi_cell(0, 4, excerpt, fill=True, **NL)

    # ══════════════════════════════════════════════════════════════════════════
    # 5. PERIOD OVERVIEW
    # ══════════════════════════════════════════════════════════════════════════
    if pdf.get_y() > 220:
        pdf.add_page()
    else:
        pdf.ln(4)

    pdf.section_title("PERIOD OVERVIEW", display_period)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(0, 5, _ascii(brief.get("executive_summary", "")), **NL)
    pdf.ln(3)

    # ══════════════════════════════════════════════════════════════════════════
    # 6. STATE SECTIONS
    # ══════════════════════════════════════════════════════════════════════════
    for state, st_brief in brief.get("state_sections", {}).items():
        if pdf.get_y() > 230:
            pdf.add_page()
        else:
            pdf.ln(2)

        st_stats = stats.get("states", {}).get(state, {})
        st_sev   = st_stats.get("sev_counts", {})

        pdf.set_fill_color(*C_TBL_HDR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, _ascii(f"  {state.upper()}"), fill=True, **NL)

        sev_parts = [f"{k.capitalize()}: {v}" for k, v in st_sev.items() if v]
        sev_str   = "  |  ".join(sev_parts) if sev_parts else "No incidents recorded"
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 4, _ascii(f"  Items: {st_stats.get('total', 0)}   {sev_str}"), **NL)
        pdf.ln(1)

        for k, label in [
            ("severity_summary",    "Severity Profile"),
            ("escalation_pattern",  "Escalation Pattern"),
            ("key_actors",          "Key Actors"),
            ("district_hotspots",   "District Hotspots"),
            ("operational_concerns","Operational Concerns"),
        ]:
            v = st_brief.get(k)
            if not v:
                continue
            if pdf.get_y() > 265:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*C_SEC_TEXT)
            pdf.cell(0, 5, _ascii(f"  {label}"), **NL)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 4, _ascii(str(v)), **NL)
            pdf.ln(1)

        note = st_brief.get("analyst_note")
        if note:
            pdf.set_fill_color(255, 248, 220)
            pdf.set_text_color(120, 80, 20)
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 4, _ascii(f"  Analyst Note: {note}"), fill=True, **NL)

        pdf.ln(2)

    # ══════════════════════════════════════════════════════════════════════════
    # 7. CROSS-BORDER THREAT ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    cba = brief.get("cross_border_analysis") or {}
    if cba:
        pdf.add_page()
        pdf.section_title("CROSS-BORDER THREAT ANALYSIS")

        for border_key, border_label in [
            ("bangladesh_border", "INDO-BANGLADESH BORDER"),
            ("myanmar_border",    "INDO-MYANMAR BORDER"),
        ]:
            b = cba.get(border_key) or {}
            if not b:
                continue
            if pdf.get_y() > 240:
                pdf.add_page()

            tl     = _ascii(b.get("threat_level", "?"))
            tl_col = SEV_COLORS.get(tl.lower(), (80, 80, 80))

            pdf.set_fill_color(50, 70, 45)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(140, 6, _ascii(f"  {border_label}"), fill=True)
            pdf.set_fill_color(*tl_col)
            pdf.cell(50, 6, _ascii(f"Threat: {tl}"), fill=True, align="C", **NL)

            for field, label in [
                ("overview",              "Overview"),
                ("primary_threats",       "Primary Threats"),
                ("hotspot_corridors",     "Hotspot Corridors"),
                ("key_actors",            "Key Actors"),
                ("indo_bd_dimension",     "Indo-Bangladesh Dimension"),
                ("displacement_pressure", "Displacement Pressure"),
                ("operational_concerns",  "Operational Concerns"),
            ]:
                v = b.get(field)
                if v:
                    pdf.set_font("Helvetica", "B", 8)
                    pdf.set_text_color(*C_SEC_TEXT)
                    pdf.cell(0, 4, _ascii(f"  {label}:"), **NL)
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(40, 40, 40)
                    pdf.multi_cell(0, 4, _ascii(str(v)), **NL)
            pdf.ln(3)

    # ══════════════════════════════════════════════════════════════════════════
    # 8. PREDICTIVE SCENARIOS
    # ══════════════════════════════════════════════════════════════════════════
    if brief.get("scenarios"):
        if pdf.get_y() > 220:
            pdf.add_page()
        else:
            pdf.ln(4)
        pdf.section_title("PREDICTIVE SCENARIOS")

        for sc in brief["scenarios"]:
            if pdf.get_y() > 250:
                pdf.add_page()
            conf    = sc.get("confidence_pct", "?")
            horizon = sc.get("horizon", "H+30")
            title_s = _ascii(sc.get("title", "Scenario"))

            pdf.set_fill_color(240, 245, 235)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(45, 65, 40)
            pdf.cell(0, 6, _ascii(f"  {title_s}  |  Confidence: {conf}%  |  Horizon: {horizon}"), fill=True, **NL)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 4, _ascii(sc.get("narrative", "")), **NL)

            if sc.get("warning_indicators"):
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(180, 60, 30)
                pdf.cell(0, 4, "  Warning Indicators:", **NL)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(150, 50, 30)
                for w in sc["warning_indicators"][:5]:
                    pdf.cell(0, 4, _ascii(f"    > {w}"), **NL)
            pdf.ln(3)

    # ══════════════════════════════════════════════════════════════════════════
    # 9. MITIGATION PLAYBOOK
    # ══════════════════════════════════════════════════════════════════════════
    if brief.get("mitigation_playbook"):
        pdf.add_page()
        pdf.section_title("MITIGATION PLAYBOOK")

        for state, plan in brief["mitigation_playbook"].items():
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(45, 65, 40)
            pdf.cell(0, 5, _ascii(state), **NL)

            for horizon, label in [
                ("immediate",   "IMMEDIATE"),
                ("short_term",  "SHORT TERM"),
                ("medium_term", "MEDIUM TERM"),
                ("long_term",   "LONG TERM"),
            ]:
                actions = plan.get(horizon, [])
                if not actions:
                    continue
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(80, 100, 60)
                pdf.cell(0, 4, f"  {label}:", **NL)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(40, 40, 40)
                for a in actions:
                    action_txt = _ascii(a.get("action", ""))
                    lead       = _ascii(a.get("lead_agency", ""))
                    pdf.multi_cell(0, 4, f"    - {action_txt}  [Lead: {lead}]", **NL)
            pdf.ln(2)

    return bytes(pdf.output())
