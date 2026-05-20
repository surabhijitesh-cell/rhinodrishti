"""
seed_updates.py — Populates the app_updates collection with full version history.

Run once from the backend directory:
    python seed_updates.py

Reads MONGO_URL from the same environment as the main app (or .env file).
Skips any version that already exists (idempotent).
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "rhino_drishti")

# ── Full update history ──────────────────────────────────────────────────────

UPDATES = [
    {
        "version": "1.0",
        "priority": "major",
        "message": "Initial release — RSS intelligence ingestion from 72 NER, national and international news sources with Claude AI classification pipeline.",
        "created_at": "2025-10-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "1.5",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2025-10-15T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "2.0",
        "priority": "major",
        "message": "Auto-translation added — Bengali, Assamese, Hindi, Burmese, Thai, Chinese, Arabic and 8 other scripts now automatically translated to English before classification.",
        "created_at": "2025-11-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "2.5",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2025-11-10T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "3.0",
        "priority": "major",
        "message": "Cross-Border Intelligence module launched — dedicated Bangladesh and Myanmar intelligence view with Diplomatic, Defence, Internal Politics and Economics category classification.",
        "created_at": "2025-11-20T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "4.0",
        "priority": "major",
        "message": "Knowledge Graph introduced — actor-location relationship network extracted from the full intelligence corpus. Find connections across articles no single story reveals.",
        "created_at": "2025-12-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "5.0",
        "priority": "major",
        "message": "Pattern Detection Engine launched — automatically identifies recurring threat clusters (region + threat type + actor) and assigns escalation risk levels (CRITICAL / HIGH / MODERATE / LOW).",
        "created_at": "2025-12-15T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "6.0",
        "priority": "major",
        "message": "Dynamic Keyword Engine added — AI-managed keyword bank with 6 types, automatic boost/decay, synonym expansion and manual addition. Drives weighted relevance scoring during RSS fetch.",
        "created_at": "2026-01-05T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "7.0",
        "priority": "major",
        "message": "Training & Feedback system launched — 1-6 analyst rating scale, training queue for URL/document uploads, Active Feedback Bias pipeline injection, and activity log with AI impact summaries.",
        "created_at": "2026-01-20T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "7.5",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2026-02-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "8.0",
        "priority": "major",
        "message": "Daily Intelligence Brief — auto-generated every day at 06:00 IST with NER Key Developments, Cross-Border Intelligence, Pattern Insights and Document Insights. PDF export included.",
        "created_at": "2026-02-10T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "8.5",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2026-02-20T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "9.0",
        "priority": "major",
        "message": "Reports module launched — generate Regional Threat Summaries, Cross-Border SITREPs (Bangladesh/Myanmar) and fully customised PDF reports with any combination of region, severity, threat and date filters.",
        "created_at": "2026-03-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "9.2",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2026-03-10T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "9.5",
        "priority": "major",
        "message": "Role-Based Access Control (RBAC) — Admin, Analyst and Viewer roles. User Management page for admins to create, deactivate and reset passwords for analyst accounts.",
        "created_at": "2026-03-20T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "9.8",
        "priority": "major",
        "message": "Multi-Article Fusion — when multiple sources cover the same event, articles are automatically clustered into one card. Blue badge shows source count; click to expand all covering sources.",
        "created_at": "2026-04-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "9.9",
        "priority": "minor",
        "message": "Performance improvements and bug fixes.",
        "created_at": "2026-04-10T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.0",
        "priority": "major",
        "message": "Expanded intelligence ingest from RSS-only to 6 source types — YouTube, Facebook, Telegram, X/Twitter and Firecrawl web crawler added alongside 89 RSS feeds. Dashboard shows a live scanner panel with per-source status, drill-down source lists and individual FETCH triggers.",
        "created_at": "2026-04-15T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.1",
        "priority": "major",
        "message": "Local Database Setup Wizard — intelligence collection centres can now migrate from MongoDB Atlas to a local 1 TB hard disk using the Tailscale WireGuard VPN architecture. Settings page shows live connection status, database size and migration log.",
        "created_at": "2026-04-18T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.2",
        "priority": "minor",
        "message": "Source Effectiveness card added to Settings — shows intelligence yield from each non-RSS source including item count, severity distribution bar, AI processing rate and latest catch.",
        "created_at": "2026-04-20T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.3",
        "priority": "minor",
        "message": "Dashboard scanner panel now open by default. Fetch Intel button triggers all 6 sources simultaneously. Scan Social Media button triggers the 5 non-RSS sources only. Scanner panel collapses on header click.",
        "created_at": "2026-04-22T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.4",
        "priority": "major",
        "message": "Guided page walkthroughs — each page auto-tours on first visit, spotlighting key sections with contextual briefings. Re-trigger at any time via the ? button in the top bar. Admins can reset all tours to re-enable auto-walkthrough for demonstration purposes.",
        "created_at": "2026-04-24T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "10.5",
        "priority": "major",
        "message": "Comprehensive tooltip system — every button, stat card, source scanner card, chart heading and intelligence card parameter now has a hover tooltip with contextual explanation. P-score, C-score, severity, trajectory, cluster, actors, early warning, special flags and attention level all explained in-situ.",
        "created_at": "2026-04-26T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "11.0",
        "priority": "major",
        "message": "Section heading tooltips on all pages, descriptive nav sidebar tooltips, User Handbook updated to v11.0 with full documentation for all new features including social media integrations, local database wizard, guided tours and tooltip system.",
        "created_at": "2026-04-28T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "11.1",
        "priority": "major",
        "message": "NER Situation Map rebuilt on Leaflet with NASA Blue Marble satellite tiles. Intelligence items now show exact GPS-location pulsating markers on the map. Dashboard sections are click-to-scroll. Admin panel gains Twitter free-tier alert and Anthropic API spend monitor.",
        "created_at": "2026-05-01T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "11.2",
        "priority": "major",
        "message": "Reprocess button on each intelligence card lets analysts force AI re-classification of a single item. Analyst role restrictions applied — action buttons hidden from Viewer accounts across the map and intelligence feed.",
        "created_at": "2026-05-09T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "11.3",
        "priority": "major",
        "message": "Admin Monitoring dashboard added — real-time multi-provider API cost tracker, 4-stage filter cascade visualiser with per-stage pass/reject counts, and a threshold simulator to tune rejection rates. West Bengal added to state coverage. Map state-filter added.",
        "created_at": "2026-05-12T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "12.0",
        "priority": "major",
        "message": "Temporal Intelligence Map launched — interactive timeline slider lets the commander scrub through any date range and watch state threat-borders change colour in real time. Map supports compact and fullscreen overlay modes with dense axis graduations.",
        "created_at": "2026-05-14T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "13.0",
        "priority": "major",
        "message": "Trends Intelligence Center launched — state stability index, 7-day severity trend charts, district hotspot evolution, and actor evolution across time periods. Custom Analytics Workspace added to Dashboard — build and save personal chart panels from any combination of metrics.",
        "created_at": "2026-05-18T06:00:00+00:00",
        "created_by": "system",
    },
    {
        "version": "13.1",
        "priority": "major",
        "message": "Strategic Intelligence Briefs suite — Monthly and Fortnightly briefs generated by AI from the full intelligence corpus. Each brief includes Executive Assessment, State-wise Security Assessment sorted by severity, Cross-Border Analysis, Predictive Scenarios and Commander Action Matrix. Analyst Enhancement notes attach inline to any intelligence card and are included in brief generation. Briefs export to a fully styled PDF.",
        "created_at": "2026-05-18T06:30:00+00:00",
        "created_by": "system",
    },
    {
        "version": "13.2",
        "priority": "major",
        "message": "Stability Trend – Historical chart in briefs redesigned into a 2×4 minigraph panel (one per NER state) with a Heatmap toggle. Period selector filters last 3/6/12 fortnights or all periods. All brief sections now sorted with most critical state first.",
        "created_at": "2026-05-20T06:00:00+00:00",
        "created_by": "system",
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    col = db.app_updates

    inserted = 0
    skipped = 0

    for update in UPDATES:
        existing = await col.find_one({"version": update["version"]})
        if existing:
            print(f"  [skip]   v{update['version']} — already exists")
            skipped += 1
            continue

        doc = {
            "id": str(uuid.uuid4()),
            **update,
        }
        await col.insert_one(doc)
        print(f"  [insert] v{update['version']} [{update['priority']}] — {update['message'][:60]}...")
        inserted += 1

    client.close()
    print(f"\nDone. Inserted {inserted}, skipped {skipped} (already existed).")


if __name__ == "__main__":
    asyncio.run(seed())
