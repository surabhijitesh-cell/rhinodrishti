# Rhino Drishti — Cost Proposal for Full-Scale Deployment
## Prepared for CFO Review | April 2026

---

## 1. Executive Summary

Rhino Drishti is an AI-powered OSINT (Open Source Intelligence) platform currently operational for monitoring India's North Eastern Region (NER), Bangladesh, and Myanmar. This proposal outlines the costs for:

1. **Current operational costs** (already deployed)
2. **New feature additions**: Firecrawl API, X (Twitter) monitoring, Instagram/Facebook monitoring
3. **Long-term data archival** to external storage
4. **Recurring monthly/annual costs** for the lifetime of the platform

**Total estimated monthly cost (all features): INR 18,500 – 45,000/month (~$220 – $540/month)**
**One-time setup cost: INR 0 (all services are subscription-based, no hardware required)**

---

## 2. Current Operational Costs (Already Active)

| Service | Purpose | Monthly Cost (USD) | Monthly Cost (INR) | Notes |
|---------|---------|-------------------|---------------------|-------|
| **Render Hosting (Standard)** | Backend + Frontend hosting | $25 | ~INR 2,100 | 24/7 uptime, 2GB RAM, 1 vCPU |
| **MongoDB Atlas (M10)** | Database | $58 | ~INR 4,850 | 10GB storage, dedicated cluster |
| **Emergent LLM Key (Claude Haiku 4.5)** | AI classification & analysis | $15–30 | ~INR 1,250–2,500 | Usage-based: ~$1/M input tokens, $5/M output tokens. Current usage ~$2.50/day |
| **Domain + SSL** | Custom domain (if applicable) | $1–2 | ~INR 80–170 | Optional — Render provides free SSL |
| **SUBTOTAL (Current)** | | **$99–115** | **~INR 8,280–9,620** | |

---

## 3. New Feature: Firecrawl API (Enhanced Web Scraping)

Firecrawl provides superior web scraping compared to basic HTTP fetching — handles JavaScript-rendered pages, paywalled sites, and complex layouts.

| Plan | Monthly Cost (USD) | Monthly Cost (INR) | Credits/Month | Recommendation |
|------|-------------------|---------------------|---------------|----------------|
| Hobby | $16 | ~INR 1,340 | 3,000 pages | Insufficient for daily ops |
| **Standard** | **$83** | **~INR 6,950** | **100,000 pages** | **Recommended** — covers daily scraping of 72+ RSS sources + manual URL analysis |
| Growth | $333 | ~INR 27,900 | 500,000 pages | Only if scaling to 200+ sources |

**Recommendation**: Standard plan at **$83/month (INR 6,950)**. At 72 sources fetched 2-3x daily + manual URL analyses, expected usage is ~15,000–30,000 credits/month, well within the 100,000 limit.

---

## 4. New Feature: X (Twitter) Monitoring

X API moved to pay-per-use pricing in February 2026. Costs depend on monitoring volume.

| Usage Level | What You Get | Est. Monthly Cost (USD) | Est. Monthly Cost (INR) |
|-------------|-------------|------------------------|--------------------------|
| **Low** (monitoring) | 5,000 post reads + 500 searches/month | $30–50 | ~INR 2,500–4,200 |
| **Medium** (active monitoring) | 20,000 reads + 2,000 searches + keyword tracking | $100–150 | ~INR 8,400–12,600 |
| **High** (comprehensive OSINT) | 50,000+ reads + real-time streams | $300–500 | ~INR 25,200–42,000 |

**Key X API rates:**
- Post read: $0.005/post
- User lookup: $0.01/lookup
- Search: $0.005/result
- 24-hour deduplication applies (same resource fetched multiple times counts once)

**Recommendation**: Start with **Low-Medium tier at ~$50–100/month (INR 4,200–8,400)** monitoring 10-15 key accounts and NER-related hashtags. Scale up based on intelligence value.

---

## 5. New Feature: Instagram & Facebook Monitoring

Meta's Graph API is **free** for basic access but has severe limitations for OSINT monitoring (rate limits, no public data scraping, complex approvals). Third-party tools are recommended.

### Option A: Meta Graph API (Direct — Free but Limited)
| Item | Cost | Notes |
|------|------|-------|
| API Access | Free | Requires Business account, app review, permissions approval |
| Rate Limits | N/A | 50 posts/24hr on Instagram, limited hashtag search |
| Setup Time | 2-4 weeks | Meta approval process is slow |

### Option B: Third-Party Monitoring Tool (Recommended)
| Tool | Monthly Cost (USD) | Monthly Cost (INR) | Coverage |
|------|-------------------|---------------------|----------|
| **Data365** | $49–149 | ~INR 4,100–12,500 | Instagram + Facebook, bypasses API limits |
| **Zernio** | $19–79 | ~INR 1,600–6,600 | Multi-platform including Meta |
| **SociaVault** | $39–99 | ~INR 3,270–8,300 | Public data access, post-CrowdTangle replacement |

**Recommendation**: **Data365 or Zernio at ~$50–80/month (INR 4,200–6,700)**. Direct Meta API is free but impractical for OSINT — approval takes weeks, rate limits are too restrictive, and CrowdTangle (the previous monitoring tool) was shut down. Third-party tools provide broader, faster data access.

---

## 6. Long-Term Data Archival (Intelligence Storage)

### Option A: MongoDB Atlas (Scale Existing Database)

| Storage Tier | Monthly Cost (USD) | Monthly Cost (INR) | Storage | Notes |
|-------------|-------------------|---------------------|---------|-------|
| M10 (current) | $58 | ~INR 4,850 | 10 GB | Sufficient for ~6 months of daily data |
| **M20** | **$140** | **~INR 11,750** | **20 GB** | Recommended for 1-2 years of data |
| M30 | $310 | ~INR 26,000 | 40 GB | For multi-year archival |
| Extra storage | $0.30/GB/month | ~INR 25/GB | Add-on | Above default capacity |

**Data volume estimate:**
- Daily intelligence items: ~100-200 articles (after filtering)
- Average item size: ~3-5 KB (with embeddings: ~10-15 KB)
- Monthly data: ~100-450 MB (with embeddings)
- Annual data: ~1.2-5.4 GB
- 5-year projection: ~6-27 GB

### Option B: External Cold Storage (AWS S3 / Google Cloud Storage)

For archival retrieval (not live queries), external storage is significantly cheaper:

| Service | Cost per GB/Month (USD) | Cost per GB/Month (INR) | 10 GB Annual (USD) | Notes |
|---------|------------------------|--------------------------|---------------------|-------|
| AWS S3 Standard | $0.023 | ~INR 1.93 | $2.76/year | Fast retrieval |
| AWS S3 Glacier | $0.004 | ~INR 0.34 | $0.48/year | Archival, minutes-to-hours retrieval |
| Google Cloud Storage (Nearline) | $0.010 | ~INR 0.84 | $1.20/year | 30-day minimum storage |

**Recommendation**: Keep **M20 MongoDB Atlas ($140/month)** as the live operational database for 1-2 years of active data. Set up a **monthly automated export to AWS S3 Glacier (~$5-10/year)** for permanent archival beyond the active window. This gives instant access to recent data and low-cost permanent storage for historical intelligence.

---

## 7. Cost Summary — All Scenarios

### Scenario 1: Essential (Current + Firecrawl + X Monitoring)

| Component | Monthly (USD) | Monthly (INR) | Annual (USD) | Annual (INR) |
|-----------|--------------|----------------|-------------|---------------|
| Render Hosting (Standard) | $25 | 2,100 | $300 | 25,200 |
| MongoDB Atlas (M10) | $58 | 4,850 | $696 | 58,200 |
| Emergent LLM Key | $25 | 2,100 | $300 | 25,200 |
| Firecrawl (Standard) | $83 | 6,950 | $996 | 83,400 |
| X/Twitter API | $50 | 4,200 | $600 | 50,400 |
| **TOTAL** | **$241** | **~20,200** | **$2,892** | **~2,42,400** |

### Scenario 2: Full Suite (All Features)

| Component | Monthly (USD) | Monthly (INR) | Annual (USD) | Annual (INR) |
|-----------|--------------|----------------|-------------|---------------|
| Render Hosting (Standard) | $25 | 2,100 | $300 | 25,200 |
| MongoDB Atlas (M20) | $140 | 11,750 | $1,680 | 1,41,000 |
| Emergent LLM Key | $30 | 2,500 | $360 | 30,000 |
| Firecrawl (Standard) | $83 | 6,950 | $996 | 83,400 |
| X/Twitter API | $100 | 8,400 | $1,200 | 1,00,800 |
| Instagram/FB (Data365) | $80 | 6,700 | $960 | 80,400 |
| AWS S3 Archival | $5 | 420 | $60 | 5,040 |
| **TOTAL** | **$463** | **~38,820** | **$5,556** | **~4,65,840** |

### Scenario 3: Enterprise Scale (High Volume + Pro Hosting)

| Component | Monthly (USD) | Monthly (INR) | Annual (USD) | Annual (INR) |
|-----------|--------------|----------------|-------------|---------------|
| Render Hosting (Pro) | $85 | 7,130 | $1,020 | 85,560 |
| MongoDB Atlas (M30) | $310 | 26,000 | $3,720 | 3,12,000 |
| Emergent LLM Key | $50 | 4,200 | $600 | 50,400 |
| Firecrawl (Growth) | $333 | 27,900 | $3,996 | 3,34,800 |
| X/Twitter API (Medium-High) | $300 | 25,200 | $3,600 | 3,02,400 |
| Instagram/FB (Data365 Pro) | $149 | 12,500 | $1,788 | 1,50,000 |
| AWS S3 Archival | $10 | 840 | $120 | 10,080 |
| **TOTAL** | **$1,237** | **~1,03,770** | **$14,844** | **~12,45,240** |

---

## 8. Five-Year Total Cost of Ownership (TCO)

| Scenario | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 | **5-Year Total** |
|----------|--------|--------|--------|--------|--------|-----------------|
| **Essential** | $2,892 | $2,892 | $2,892 | $2,892 | $2,892 | **$14,460 (~INR 12,12,000)** |
| **Full Suite** | $5,556 | $5,556 | $5,556 | $5,556 | $5,556 | **$27,780 (~INR 23,30,000)** |
| **Enterprise** | $14,844 | $14,844 | $14,844 | $14,844 | $14,844 | **$74,220 (~INR 62,26,000)** |

*Note: Costs may increase 5-10% annually due to API pricing changes. Storage costs grow with data volume (~$5-15/year increment for archival).*

---

## 9. One-Time Setup Costs

| Item | Cost | Notes |
|------|------|-------|
| Infrastructure setup | $0 | All cloud-based, no hardware |
| API account creation | $0 | All services offer self-service signup |
| Firecrawl integration development | Included | Built by Emergent during development sessions |
| X/Twitter integration development | Included | Built by Emergent during development sessions |
| Meta integration development | Included | Built by Emergent during development sessions |
| Data archival pipeline | Included | Automated export scripts built during development |
| **TOTAL ONE-TIME** | **$0** | All development included in Emergent platform usage |

---

## 10. Implementation Timeline

| Phase | Duration | Components |
|-------|----------|------------|
| Phase 1 (Immediate) | 1-2 sessions | Firecrawl API integration |
| Phase 2 (Week 2) | 1-2 sessions | X/Twitter monitoring integration |
| Phase 3 (Week 3) | 1-2 sessions | Instagram/Facebook monitoring via third-party API |
| Phase 4 (Week 4) | 1 session | Data archival pipeline (MongoDB → S3 automated export) |
| Phase 5 (Ongoing) | Continuous | Monitoring, tuning, source expansion |

---

## 11. Recommendation

**Start with Scenario 1 (Essential) at ~INR 20,200/month** and scale to Scenario 2 as social media monitoring proves its intelligence value. This approach:

1. Minimizes upfront commitment while delivering immediate OSINT capability
2. Adds Firecrawl for superior web scraping (handles paywalled/JS-heavy sites)
3. Adds X/Twitter for real-time social media intelligence
4. Can scale Instagram/Facebook and archival within 2-4 weeks when needed
5. All costs are subscription-based with no lock-in — can scale up or down monthly

---

*Document prepared: 20 April 2026*
*Platform: Rhino Drishti v9.2*
*All prices in USD converted at 1 USD = INR 83.85 (approximate)*
*Prices subject to change based on API provider updates*
