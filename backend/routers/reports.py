"""Reports — PDF generation for filtered intelligence, regional threat summaries,
cross-border SITREPs, and custom filtered reports."""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timezone, timedelta
from fpdf import FPDF
from shared import db, intelligence_col, logger
from utils.auth import get_current_user

router = APIRouter()

NER_STATES = ["Assam", "Manipur", "Meghalaya", "Mizoram", "Tripura",
              "Nagaland", "Arunachal Pradesh", "Sikkim"]

IST_OFFSET = timedelta(hours=5, minutes=30)


def _now_ist():
    return datetime.now(timezone.utc) + IST_OFFSET


def _to_ddmmyyyy_ist(iso_str):
    """Convert ISO date string to ddmmyyyy in IST."""
    if not iso_str:
        return _now_ist().strftime("%d%m%Y")
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt + IST_OFFSET
        return ist_dt.strftime("%d%m%Y")
    except Exception:
        # Fallback: parse YYYY-MM-DD
        parts = iso_str[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"
        return _now_ist().strftime("%d%m%Y")


def _clean(text, max_len=500):
    if not text:
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')[:max_len]


class ReportPDF(FPDF):
    def __init__(self, title="INTELLIGENCE REPORT", subtitle="", date_str=""):
        super().__init__()
        self._report_title = title
        self._subtitle = subtitle
        self._date_str = date_str or datetime.now(timezone.utc).strftime("%d %b %Y")

    def header(self):
        self.set_fill_color(30, 35, 25)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(180, 220, 80)
        self.set_y(5)
        self.cell(0, 8, 'RHINO DRISHTI', align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_font('Helvetica', '', 8)
        self.set_text_color(160, 170, 150)
        self.cell(0, 4, _clean(self._subtitle or self._report_title), align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_font('Helvetica', '', 7)
        self.cell(0, 4, f'Classification: RESTRICTED  |  Generated: {self._date_str}', align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_y(34)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Rhino Drishti Report | Page {self.page_no()}/{{nb}} | RESTRICTED', align='C')

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(50, 60, 40)
        self.set_fill_color(230, 240, 220)
        self.cell(0, 7, f'  {_clean(title, 120)}', fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_section(self, title):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(80, 100, 60)
        self.cell(0, 5, _clean(title, 100), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def stat_line(self, label, value):
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(60, 60, 60)
        self.cell(50, 4, _clean(label, 50), new_x="END")
        self.set_font('Helvetica', '', 8)
        self.set_text_color(40, 40, 40)
        self.cell(0, 4, _clean(str(value), 100), new_x="LMARGIN", new_y="NEXT")

    def news_item(self, index, item):
        if self.get_y() > 240:
            self.add_page()
        title = item.get('title', '')
        summary = item.get('ai_summary', '') or item.get('summary', '')
        severity = item.get('severity', '')
        state = item.get('state', '')
        priority = item.get('priority_score', 0)
        source = item.get('source', '')
        url = item.get('source_url', '')

        sev_label = f' [{severity.upper()}]' if severity else ''
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(40, 60, 80)
        self.multi_cell(0, 5, _clean(f'{index}. {title}{sev_label}', 180), new_x="LMARGIN", new_y="NEXT")

        meta_parts = []
        if state:
            meta_parts.append(f'Region: {state}')
        if priority:
            meta_parts.append(f'Priority: {priority}')
        if source:
            meta_parts.append(f'Source: {source}')
        if item.get('threat_category'):
            meta_parts.append(f'Threat: {item["threat_category"]}')
        if meta_parts:
            self.set_font('Helvetica', 'I', 7)
            self.set_text_color(100, 100, 100)
            self.cell(0, 4, _clean(' | '.join(meta_parts), 200), new_x="LMARGIN", new_y="NEXT")

        if summary:
            self.set_font('Helvetica', '', 8)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 4, _clean(summary, 500), new_x="LMARGIN", new_y="NEXT")

        why = item.get('why_it_matters', '')
        if why:
            if self.get_y() > 265:
                self.add_page()
            self.set_font('Helvetica', 'B', 7)
            self.set_text_color(50, 120, 50)
            self.cell(28, 4, 'Why it matters: ', new_x="END")
            self.set_font('Helvetica', '', 7)
            self.set_text_color(80, 80, 80)
            self.multi_cell(0, 4, _clean(why, 300), new_x="LMARGIN", new_y="NEXT")

        if url and len(url) > 5:
            self.set_font('Helvetica', 'I', 6)
            self.set_text_color(70, 100, 150)
            self.cell(0, 3, _clean(url, 80), new_x="LMARGIN", new_y="NEXT", link=url)

        ts = item.get('published_at', '')
        if ts:
            self.set_font('Helvetica', 'I', 6)
            self.set_text_color(140, 140, 140)
            self.cell(0, 3, _clean(f'Published: {ts[:19]}'), new_x="LMARGIN", new_y="NEXT")

        self.ln(2)


def _build_query(state=None, threat_type=None, severity=None, search=None,
                 date_from=None, date_to=None, is_cross_border=None,
                 min_priority=None):
    query = {
        "processed": True,
        "is_cluster_primary": {"$ne": False},
        "severity": {"$nin": ["low", "LOW"]},
    }
    if state:
        query["state"] = state
    if threat_type:
        query["threat_category"] = threat_type
    if severity:
        query["severity"] = severity.lower()
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"ai_summary": {"$regex": search, "$options": "i"}},
        ]
    if date_from:
        query.setdefault("published_at", {})["$gte"] = date_from
    if date_to:
        query.setdefault("published_at", {})["$lte"] = date_to
    if is_cross_border is not None:
        query["is_cross_border"] = is_cross_border
    if min_priority is not None:
        query["priority_score"] = {"$gte": min_priority}
    if not date_from and not date_to:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        query["published_at"] = {"$gte": cutoff}
    return query


def _generate_pdf(pdf):
    pdf.alias_nb_pages()
    if pdf.page == 0:
        pdf.add_page()
    return bytes(pdf.output())


def _severity_stats(items):
    stats = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for it in items:
        s = (it.get("severity") or "").lower()
        if s in stats:
            stats[s] += 1
    return stats


def _threat_stats(items):
    cats = {}
    for it in items:
        c = it.get("threat_category", "Unclassified")
        cats[c] = cats.get(c, 0) + 1
    return dict(sorted(cats.items(), key=lambda x: -x[1])[:10])


def _region_stats(items):
    regions = {}
    for it in items:
        r = it.get("state", "Unknown")
        regions[r] = regions.get(r, 0) + 1
    return dict(sorted(regions.items(), key=lambda x: -x[1])[:10])


# ============================================================
# 1. Filtered Feed PDF Export
# ============================================================
@router.get("/reports/filtered-feed")
async def filtered_feed_pdf(
    state: Optional[str] = None,
    threat_type: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_cross_border: Optional[bool] = None,
    min_priority: Optional[int] = None,
    sort_by: Optional[str] = "priority_score",
    user: dict = Depends(get_current_user),
):
    query = _build_query(state, threat_type, severity, search, date_from, date_to, is_cross_border, min_priority)
    items = await intelligence_col.find(query, {"_id": 0}).sort("priority_score", -1).limit(200).to_list(200)

    if not items:
        raise HTTPException(status_code=404, detail="No items match the current filters")

    filter_desc = []
    if state:
        filter_desc.append(f"Region: {state}")
    if severity:
        filter_desc.append(f"Severity: {severity.upper()}")
    if threat_type:
        filter_desc.append(f"Threat: {threat_type}")
    if search:
        filter_desc.append(f"Search: {search}")
    if date_from:
        filter_desc.append(f"From: {date_from[:10]}")
    if date_to:
        filter_desc.append(f"To: {date_to[:10]}")
    if min_priority:
        filter_desc.append(f"Min Priority: {min_priority}")
    filter_str = " | ".join(filter_desc) if filter_desc else "All Intelligence"

    pdf = ReportPDF(
        title="FILTERED INTELLIGENCE BRIEF",
        subtitle=f"FILTERED INTELLIGENCE BRIEF  |  {filter_str}",
    )
    pdf.add_page()

    # Summary box
    sev = _severity_stats(items)
    pdf.section_title(f"SUMMARY — {len(items)} Items")
    pdf.stat_line("Filters Applied:", filter_str or "None")
    pdf.stat_line("Total Items:", str(len(items)))
    pdf.stat_line("Severity Breakdown:", f"Critical: {sev['critical']}  |  High: {sev['high']}  |  Medium: {sev['medium']}")
    pdf.stat_line("Generated By:", user.get("name", user.get("username", "Unknown")))
    pdf.ln(4)

    # Items
    pdf.section_title("INTELLIGENCE ITEMS")
    for i, item in enumerate(items, 1):
        pdf.news_item(i, item)

    content = _generate_pdf(pdf)
    from_str = _to_ddmmyyyy_ist(date_from) if date_from else ""
    to_str = _to_ddmmyyyy_ist(date_to) if date_to else _now_ist().strftime("%d%m%Y")
    date_range = f"_{from_str}_to_{to_str}" if from_str else f"_{to_str}"
    fn = f"Rhino_Drishti_Filtered{date_range}.pdf"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fn}"})


# ============================================================
# 2. Regional Threat Summary
# ============================================================
@router.get("/reports/regional-threat")
async def regional_threat_report(
    region: str = Query(..., description="NER state name"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if not date_from:
        date_from = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    query = _build_query(state=region, date_from=date_from, date_to=date_to)
    items = await intelligence_col.find(query, {"_id": 0}).sort("priority_score", -1).limit(200).to_list(200)

    period_from = date_from[:10] if date_from else "N/A"
    period_to = (date_to[:10] if date_to else datetime.now(timezone.utc).strftime('%Y-%m-%d'))

    pdf = ReportPDF(
        title=f"REGIONAL THREAT SUMMARY — {region.upper()}",
        subtitle=f"REGIONAL THREAT SUMMARY  |  {region.upper()}  |  {period_from} to {period_to}",
    )
    pdf.add_page()

    sev = _severity_stats(items)
    threats = _threat_stats(items)

    # Executive Summary
    pdf.section_title(f"EXECUTIVE SUMMARY — {region}")
    pdf.stat_line("Reporting Period:", f"{period_from} to {period_to}")
    pdf.stat_line("Total Intelligence Items:", str(len(items)))
    pdf.stat_line("Critical:", str(sev['critical']))
    pdf.stat_line("High:", str(sev['high']))
    pdf.stat_line("Medium:", str(sev['medium']))
    pdf.stat_line("Generated By:", user.get("name", user.get("username", "Unknown")))
    pdf.ln(4)

    # Threat Category Distribution
    if threats:
        pdf.section_title("THREAT CATEGORY DISTRIBUTION")
        for cat, count in threats.items():
            pdf.stat_line(f"  {cat}:", str(count))
        pdf.ln(4)

    # Critical & High Priority Items
    critical_high = [it for it in items if it.get("severity") in ("critical", "high")]
    if critical_high:
        pdf.section_title(f"CRITICAL & HIGH PRIORITY ({len(critical_high)} items)")
        for i, item in enumerate(critical_high, 1):
            pdf.news_item(i, item)

    # Medium Items
    medium = [it for it in items if it.get("severity") == "medium"]
    if medium:
        pdf.section_title(f"MEDIUM PRIORITY ({len(medium)} items)")
        for i, item in enumerate(medium, 1):
            pdf.news_item(i, item)

    if not items:
        pdf.section_title("NO DATA")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, f"No intelligence items found for {region} in the selected period.")

    content = _generate_pdf(pdf)
    fn = f"Rhino_Drishti_{region.replace(' ', '_')}_Threat_{_to_ddmmyyyy_ist(date_from)}_{_to_ddmmyyyy_ist(date_to)}.pdf"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fn}"})


# ============================================================
# 3. Cross-Border SITREP
# ============================================================
@router.get("/reports/cross-border-sitrep")
async def cross_border_sitrep(
    country: str = Query(..., description="Bangladesh or Myanmar"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if country not in ("Bangladesh", "Myanmar"):
        raise HTTPException(status_code=400, detail="Country must be 'Bangladesh' or 'Myanmar'")

    if not date_from:
        date_from = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    query = _build_query(state=country, date_from=date_from, date_to=date_to, is_cross_border=True)
    items = await intelligence_col.find(query, {"_id": 0}).sort("priority_score", -1).limit(200).to_list(200)

    # Also get items that mention the country but have different state
    alt_query = _build_query(date_from=date_from, date_to=date_to, is_cross_border=True)
    alt_query["$or"] = [
        {"title": {"$regex": country, "$options": "i"}},
        {"ai_summary": {"$regex": country, "$options": "i"}},
    ]
    alt_items = await intelligence_col.find(alt_query, {"_id": 0}).sort("priority_score", -1).limit(50).to_list(50)
    seen_ids = {it["id"] for it in items}
    for it in alt_items:
        if it["id"] not in seen_ids:
            items.append(it)
            seen_ids.add(it["id"])

    items.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

    period_from = date_from[:10] if date_from else "N/A"
    period_to = (date_to[:10] if date_to else datetime.now(timezone.utc).strftime('%Y-%m-%d'))

    pdf = ReportPDF(
        title=f"CROSS-BORDER SITREP — {country.upper()}",
        subtitle=f"SITUATION REPORT  |  {country.upper()} BORDER  |  {period_from} to {period_to}",
    )
    pdf.add_page()

    sev = _severity_stats(items)
    threats = _threat_stats(items)

    # Situation Overview
    pdf.section_title(f"SITUATION OVERVIEW — {country}")
    pdf.stat_line("Reporting Period:", f"{period_from} to {period_to}")
    pdf.stat_line("Total Cross-Border Signals:", str(len(items)))
    pdf.stat_line("Critical:", str(sev['critical']))
    pdf.stat_line("High:", str(sev['high']))
    pdf.stat_line("Medium:", str(sev['medium']))
    pdf.stat_line("Generated By:", user.get("name", user.get("username", "Unknown")))
    pdf.ln(4)

    # Threat Distribution
    if threats:
        pdf.section_title("THREAT DISTRIBUTION")
        for cat, count in threats.items():
            pdf.stat_line(f"  {cat}:", str(count))
        pdf.ln(4)

    # Group by cross_border_category if available
    categories = {"diplomatic": [], "defence": [], "internal_politics": [], "economics": [], "other": []}
    for it in items:
        cat = (it.get("cross_border_category") or "other").lower()
        if cat in categories:
            categories[cat].append(it)
        else:
            categories["other"].append(it)

    cat_labels = {
        "diplomatic": "DIPLOMATIC SIGNALS",
        "defence": "DEFENCE & SECURITY",
        "internal_politics": "INTERNAL POLITICS",
        "economics": "ECONOMICS & TRADE",
        "other": "OTHER SIGNALS",
    }
    for cat_key, label in cat_labels.items():
        cat_items = categories.get(cat_key, [])
        if cat_items:
            pdf.section_title(f"{label} ({len(cat_items)})")
            for i, item in enumerate(cat_items, 1):
                pdf.news_item(i, item)

    if not items:
        pdf.section_title("NO DATA")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 5, f"No cross-border intelligence found for {country} in the selected period.")

    content = _generate_pdf(pdf)
    fn = f"Rhino_Drishti_{country}_SITREP_{_to_ddmmyyyy_ist(date_from)}_{_to_ddmmyyyy_ist(date_to)}.pdf"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fn}"})


# ============================================================
# 4. Custom Filtered Report
# ============================================================
@router.get("/reports/custom")
async def custom_report(
    title: str = Query("Custom Intelligence Report", description="Report title"),
    state: Optional[str] = None,
    threat_type: Optional[str] = None,
    severity: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_cross_border: Optional[bool] = None,
    min_priority: Optional[int] = None,
    source: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query = _build_query(state, threat_type, severity, search, date_from, date_to, is_cross_border, min_priority)
    if source:
        query["source"] = {"$regex": source, "$options": "i"}

    items = await intelligence_col.find(query, {"_id": 0}).sort("priority_score", -1).limit(300).to_list(300)

    if not items:
        raise HTTPException(status_code=404, detail="No items match the selected filters")

    period_from = (date_from[:10] if date_from else "N/A")
    period_to = (date_to[:10] if date_to else datetime.now(timezone.utc).strftime('%Y-%m-%d'))

    pdf = ReportPDF(
        title=title.upper(),
        subtitle=f"{title.upper()}  |  {period_from} to {period_to}",
    )
    pdf.add_page()

    sev = _severity_stats(items)
    threats = _threat_stats(items)
    regions = _region_stats(items)

    # Executive Summary
    pdf.section_title("EXECUTIVE SUMMARY")
    pdf.stat_line("Report Title:", title)
    pdf.stat_line("Reporting Period:", f"{period_from} to {period_to}")
    pdf.stat_line("Total Items:", str(len(items)))
    pdf.stat_line("Severity:", f"Critical: {sev['critical']}  |  High: {sev['high']}  |  Medium: {sev['medium']}")
    filter_parts = []
    if state:
        filter_parts.append(f"Region: {state}")
    if threat_type:
        filter_parts.append(f"Threat: {threat_type}")
    if severity:
        filter_parts.append(f"Severity: {severity}")
    if search:
        filter_parts.append(f"Search: {search}")
    if source:
        filter_parts.append(f"Source: {source}")
    if min_priority:
        filter_parts.append(f"Min Priority: {min_priority}")
    if is_cross_border:
        filter_parts.append("Cross-Border Only")
    pdf.stat_line("Filters:", " | ".join(filter_parts) if filter_parts else "None")
    pdf.stat_line("Generated By:", user.get("name", user.get("username", "Unknown")))
    pdf.ln(4)

    # Regional Distribution
    if regions and len(regions) > 1:
        pdf.section_title("REGIONAL DISTRIBUTION")
        for reg, count in regions.items():
            pdf.stat_line(f"  {reg}:", str(count))
        pdf.ln(4)

    # Threat Category Distribution
    if threats:
        pdf.section_title("THREAT CATEGORY DISTRIBUTION")
        for cat, count in threats.items():
            pdf.stat_line(f"  {cat}:", str(count))
        pdf.ln(4)

    # All Items grouped by severity
    critical_items = [it for it in items if it.get("severity") == "critical"]
    high_items = [it for it in items if it.get("severity") == "high"]
    medium_items = [it for it in items if it.get("severity") == "medium"]

    if critical_items:
        pdf.section_title(f"CRITICAL ITEMS ({len(critical_items)})")
        for i, item in enumerate(critical_items, 1):
            pdf.news_item(i, item)

    if high_items:
        pdf.section_title(f"HIGH PRIORITY ITEMS ({len(high_items)})")
        for i, item in enumerate(high_items, 1):
            pdf.news_item(i, item)

    if medium_items:
        pdf.section_title(f"MEDIUM PRIORITY ITEMS ({len(medium_items)})")
        for i, item in enumerate(medium_items, 1):
            pdf.news_item(i, item)

    content = _generate_pdf(pdf)
    safe_title = title.replace(' ', '_')[:30]
    from_str = _to_ddmmyyyy_ist(date_from) if date_from else ""
    to_str = _to_ddmmyyyy_ist(date_to) if date_to else _now_ist().strftime("%d%m%Y")
    date_range = f"_{from_str}_to_{to_str}" if from_str else f"_{to_str}"
    fn = f"Rhino_Drishti_{safe_title}{date_range}.pdf"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={fn}"})
