# RhinoDrishti — Project History (append-only log)

Read this at session start. After each completed feature/fix, append:
`## YYYY-MM-DD — <branch>` + 2–3 lines of what changed and why.
Older detail: UPDATES_*.md, HANDOFF.md, USER_HANDBOOK.md, git log.

## Pre-June 2026 (condensed)
Platform built up over ~6 months: ingestion (RSS/Twitter/Telegram/Facebook/
YouTube/Firecrawl), LLM classification pipeline, multi-stage filtering,
Knowledge Graph, patterns/fusion engines, dashboards with NER map, daily
brief, auth (admin/analyst/viewer), deployed Vercel + Render + Atlas.

## 2026-06-10 — (multiple branches)
Eight features shipped: Faultline Intelligence (40→66 faultlines, daily 0-100
scoring), Monthly Strategic Brief, Trends Centre, social-media upgrades, KG
improvements, notifications, daily-brief enhancements, faultline PDF report.
Handbook v10.0.

## 2026-06-19 — feature/notifications-and-flagging
Push notifications (Android + iOS PWA), red-flag indicator, faultline
time-decay scoring, PAOI monitoring, keyword limit 300→500. Handbook v12.0;
27-slide PPTX generated.

## 2026-07-01..05 — feature/notifications-and-flagging
Custom Brief Generator (report_agent): admin chat-driven briefs — fixed PAOI id
mismatches, JSON-truncation emptying deep dives, weather/special-focus section,
PDF polish; renamed from "Report Agent", delete-brief endpoint added.

## 2026-07-05..06 — feature/notifications-and-flagging
Periodic briefs adopted the Custom Brief Generator format: Critical
Developments/Recommendations/Watch sections, per-PAOI period comparison +
trendline (3+ months), situation maps (dashboard-style state outlines,
clustered severity markers), new RAS parent grouping (Meghalaya IS + RAS
Locations sub-PAOI), NH/rail priority weighting in P3, auto "Commander's
Attention Required" section (after deep dives). 26 tests in
tests/test_periodic_report_v36.py.

## 2026-07-10 — fix/qa-findings-jul07 + feature/apify-social-scraping
Full-app QA pass on the live deployment: fixed faultline severity badges
(all showed the same lime-green background), a blank dead-page for unknown
routes, silent session-expiry with no message, and mobile stat-card
cramming. Separately: replaced the dead twitter_fetcher.py/facebook_fetcher.py
(both failed completely on official-API cost/access) with Apify-based
Instagram/Facebook/Twitter scraping — Throttled (~$0, fits the $5 free
credit) vs Firehose (~$11/mo) toggle in API & Pipeline Monitor. Needs
APIFY_TOKEN added before it can run.

## 2026-07-11..12 — feature/apify-social-scraping
Fixed two production bugs found via live debugging: non-dict LLM classify
results crashed silently, and Apify social items missing an `id` field froze
the entire 15-min unprocessed-item retry job. Shipped Facebook dashboard
widget, source emblems (RSS/YouTube/Telegram/Facebook), and real comment
sentiment (separate Apify comment-scraper actor + batched LLM call, not
just reaction counts). After Rohit upgraded to Apify Starter ($29/mo),
confirmed live that it lifted every free-tier block hit earlier (Twitter's
API block, Instagram's once-daily cap, Facebook's rate limit) — re-enabled
Twitter, generalized the Facebook-only sentiment module into
social_comment_sentiment.py, and brought Instagram + Twitter to full
feature parity with Facebook (widget, emblem, Social Pulse, sentiment).
