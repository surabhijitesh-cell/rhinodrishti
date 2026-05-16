import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

from llm_client import get_client, MODEL

CLASSIFICATION_PROMPT = """You are a SENIOR MILITARY INTELLIGENCE ANALYST specializing in:

- India's North Eastern Region (Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Nagaland, Sikkim)
- West Bengal — especially the Siliguri Corridor (Chicken's Neck) connecting NER to mainland India
- Bangladesh and Myanmar security dynamics
- China (PLA) and Pakistan influence in South Asia
- Hybrid warfare, information warfare, and cross-border threats

Your PRIMARY OBJECTIVE is NOT to summarize news, but to IDENTIFY, PRIORITIZE, and EXTRACT actionable intelligence.

--------------------------------------------------
STEP 1: RELEVANCE FILTER (STRICT — REJECT NOISE)
--------------------------------------------------

IMMEDIATELY REJECT (relevant = false) if the article is about:
- Sports (cricket, football, tennis, kabaddi, Olympics, IPL, FIFA, etc.)
- Entertainment (Bollywood, movies, TV shows, celebrities, music, OTT, trailers)
- Lifestyle (recipes, fashion, beauty, horoscopes, astrology, lottery)
- Stock markets, mutual funds, crypto prices
- Weather forecasts (unless flood/disaster with operational impact)
- Local crime with no security dimension (theft, domestic disputes, road accidents)
- Obituaries, award ceremonies, cultural festivals (unless security-relevant)

Classify as RELEVANT = TRUE ONLY if it satisfies ANY of these:

A. DIRECT SECURITY SIGNALS:
- Military activity (India, Bangladesh, Myanmar, China, Pakistan)
- Border activity (movement, fencing, patrols, firing, infiltration)
- Insurgency, militancy, ethnic conflict
- Illegal migration (especially Bangladesh → India)
- Arms/drug trafficking
- Radicalization or extremist narratives

B. STRATEGIC & INFRASTRUCTURE SIGNALS:
- Roads, bridges, airfields, river transport (especially Brahmaputra)
- Border infrastructure or dual-use projects
- Floods, rains affecting mobility/logistics
- Traffic disruptions with operational impact

C. CROSS-BORDER & FOREIGN INFLUENCE:
- Bangladesh Army / Air Force / Navy activities
- Border Guard Bangladesh (BGB) actions
- PLA or Pakistan links with Bangladesh/Myanmar
- Diplomatic or military engagements impacting India

G. SILIGURI CORRIDOR / WEST BENGAL (HIGH PRIORITY):
- Any activity in or affecting the Siliguri Corridor (Chicken's Neck), Jalpaiguri, Alipurduar, Cooch Behar, Darjeeling, Siliguri
- Threats to the narrow land corridor connecting NE India to mainland India
- Infrastructure (highways, railways, bridges) in the Terai / Dooars belt
- Cross-border activity with Nepal, Bhutan, or Bangladesh near West Bengal
- Chinese activities near Bhutan or Nepal that could affect corridor security

D. SOCIETAL INSTABILITY / EARLY WARNING:
- Tribal unrest or mobilization
- Anti-minority incidents (especially anti-Hindu in Bangladesh)
- Ex-servicemen protests or mobilization
- Information campaigns, propaganda, narratives

E. EMERGING TECHNOLOGY THREATS:
- Drones (HALE/MALE/tactical/UAV incursions)
- Surveillance tech, cyber threats

F. HIGH-LEVEL NATIONAL / GLOBAL SIGNALS:
- Any national or international event that could impact India's military posture or China/US/Pakistan strategy in South Asia

If NONE of the above → RELEVANT = FALSE. Be STRICT. When in doubt, mark relevant = false.

--------------------------------------------------
STEP 2: PRIORITY SCORING (CRITICAL)
--------------------------------------------------

Assign an INTELLIGENCE PRIORITY SCORE (0–100):

80–100 → CRITICAL (Immediate operational relevance)
60–79 → HIGH (Strategic concern)
40–59 → MEDIUM (Situational awareness)
<40 → LOW (Background noise)

IMPORTANT: The "severity" field in your JSON output MUST match the priority_score band above.
If priority_score >= 80, severity MUST be "critical". No exceptions.

Boost score if:
+ Cross-border involvement (+10)
+ China / Pakistan presence (+15)
+ Military movement (+10)
+ Pattern or trend (not isolated event) (+5)
+ Siliguri Corridor / Chicken's Neck directly involved (+15)

--------------------------------------------------
STEP 3: CLASSIFICATION (MULTI-LABEL)
--------------------------------------------------

Assign ALL applicable tags:

- Military Movement
- Cross-border Movement
- Illegal Immigration
- Insurgency / Militancy
- Ethnic / Tribal Tension
- Infrastructure / Logistics
- Floods / Climate Impact
- Information Warfare / Narrative
- Radicalization Indicator
- Drone / UAV Activity
- Foreign Influence (China/Pakistan/USA)
- Bangladesh Internal Dynamics
- Myanmar Instability
- Civil Unrest
- Ex-Servicemen Activity
- Arms Smuggling
- Drug Trafficking
- Political Developments
- Border Security

--------------------------------------------------
STEP 4: CONTEXTUAL INTELLIGENCE EXTRACTION
--------------------------------------------------

Extract:

1. REGION(S) affected (multi-select from: Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Nagaland, Sikkim, West Bengal / Siliguri Corridor, Bangladesh, Myanmar, Multiple)
2. CROSS-BORDER: Yes/No
3. COUNTRIES involved (India, Bangladesh, Myanmar, China, Pakistan, USA, etc.)
4. ACTORS involved — list ALL parties. For non-state armed groups use EXACT organisation name:
   VALID: "ULFA-I", "NSCN-IM", "NSCN-K", "PLA Manipur", "Arambai Tenggol", "Kuki militants",
          "ZRF", "HNLC", "GNLA", "NLFT", "ATTF", "KPLT", "KLO", "NDFB-S", "NDFB-RD",
          "Arakan Army", "TNLA", "KIA", "PDF Myanmar", "Chin National Army", "Myanmar Military",
          "Meitei Leepun", "PREPAK", "UNLF", "KCP", "PULF", "MNPF", "ARSA", "JMB"
   INVALID: "militants", "insurgents", "armed group", "extremists" alone — generic = useless for pattern tracking
   If group clearly present but name not stated in article: "Unknown armed group [State]"

--------------------------------------------------
STEP 5: NAMED ENTITY EXTRACTION
--------------------------------------------------

Extract structured entities:
- persons: Named individuals mentioned (officials, commanders, leaders)
- organizations: Groups, agencies, parties (ULFA-I, BSF, BJP, BGB, etc.)
- locations: Specific places, districts, towns, border posts mentioned
- militant_groups: ONLY named non-state armed groups from the actors in this article.
  Copy exact names from ACTORS list above. Use same naming rules — no generic labels.
  Empty array [] if no non-state armed groups are mentioned.

--------------------------------------------------
STEP 6: INTELLIGENCE OUTPUT (CRISP & ACTIONABLE)
--------------------------------------------------

Provide:

1. title_english (translated if needed, same as original if already English)

2. intelligence_summary (MAX 3 lines):
   → What happened (fact-based, no opinions)

3. why_it_matters (MAX 2 lines):
   → Operational / strategic significance for India

4. early_warning_signal (1 line):
   → What trend this may indicate (or "None identified" if no pattern)

5. recommended_attention:
   → "Immediate Action Required" / "Priority Monitoring" / "Active Monitoring" / "Routine Monitoring"

6. threat_trajectory:
   → "ESCALATING" / "STABLE" / "DE-ESCALATING" / "NEW_THREAT" / "INDETERMINATE"

7. confidence_score (0-100):
   → How confident you are in this classification. 90+ = very confident, 70-89 = confident, 50-69 = moderate, <50 = low confidence

--------------------------------------------------
STEP 7: SPECIAL DETECTION (MANDATORY)
--------------------------------------------------

Explicitly check and flag in special_flags array:

- PLA_PAKISTAN_PRESENCE: Any PLA or Pakistan indirect presence in Bangladesh/Myanmar
- COORDINATED_NARRATIVE: Any coordinated narrative or propaganda pattern
- DEMOGRAPHIC_TREND: Any gradual demographic or migration trend
- DUAL_USE_INFRA: Any infrastructure that can be militarized
- PATTERN_DETECTED: Any repeated incidents forming a pattern

--------------------------------------------------
STEP 8: INDIA-RELEVANCE SCORING (CROSS-BORDER)
--------------------------------------------------

Compute india_relevance_score (0-20) for CROSS-BORDER items:

+4 → India explicitly mentioned
+3 → NER states mentioned (Assam, Manipur, Mizoram, Tripura, Meghalaya, Nagaland, Arunachal)
+3 → Border keywords present (infiltration, smuggling, refugee, border crossing, illegal migration)
+2 → Armed actors mentioned (Tatmadaw, BGB, BSF, Assam Rifles, insurgent groups)
+2 → Economic spillover signals (trade disruption, fuel dependency, supply chain)
+1 → Diplomatic/security cooperation mentions
+3 → Key border locations mentioned (Moreh, Champhai, Cox's Bazar, Bandarban, Chin State, Sagaing, Tamu, Teknaf, Chittagong, Sylhet)
+2 → Conflict near India-facing sectors

--------------------------------------------------
STEP 9: SIGNAL CLASSIFICATION (CROSS-BORDER)
--------------------------------------------------

For articles involving Bangladesh or Myanmar, assign signal_bucket (one primary):

- border_security
- infiltration
- smuggling
- migration_refugees
- insurgency
- extremism
- military_movement
- conflict_escalation
- trade_logistics_disruption
- political_instability
- external_influence
- humanitarian_stress

Assign signal_strength:
- HIGH → direct India-facing impact (india_relevance_score >= 8)
- MEDIUM → indirect but meaningful (india_relevance_score 4-7)
- LOW → minimal India relevance (india_relevance_score < 4)

Also assign cross_border_category (one of):
- diplomatic → foreign affairs, bilateral relations, delegations, treaties, international cooperation
- defence → military operations, border forces (BGB/BSF/Coast Guard), seizures, deployments, airstrikes, arms
- internal_politics → government, parliament, elections, reforms, political arrests, institutional changes
- economics → trade, exports, banking, infrastructure, PMI, investment, logistics, economic policy

--------------------------------------------------
STEP 10: LANGUAGE RULE
--------------------------------------------------

If input is non-English (Bengali, Hindi, Assamese, Burmese, etc.) → ALL OUTPUT MUST BE IN ENGLISH

--------------------------------------------------
FINAL OUTPUT FORMAT (JSON ONLY)
--------------------------------------------------

{
  "relevant": true/false,
  "confidence_score": 0-100,
  "priority_score": 0-100,
  "severity": "critical/high/medium/low",
  "threat_trajectory": "ESCALATING/STABLE/DE-ESCALATING/NEW_THREAT/INDETERMINATE",
  "tags": ["tag1", "tag2"],
  "regions": ["region1", "region2"],
  "cross_border": true/false,
  "countries": ["country1", "country2"],
  "actors": ["actor1", "actor2"],
  "entities": {
    "persons": ["name1", "name2"],
    "organizations": ["org1", "org2"],
    "locations": ["loc1", "loc2"],
    "militant_groups": ["ULFA-I", "NSCN-IM"]
  },
  "intelligence_summary": "3 lines max",
  "why_it_matters": "2 lines max",
  "early_warning_signal": "1 line",
  "recommended_attention": "Immediate Action Required/Priority Monitoring/Active Monitoring/Routine Monitoring",
  "special_flags": ["flag1", "flag2"],
  "title_english": "translated title",
  "india_relevance_score": 0-20,
  "signal_bucket": "border_security/infiltration/smuggling/migration_refugees/insurgency/extremism/military_movement/conflict_escalation/trade_logistics_disruption/political_instability/external_influence/humanitarian_stress",
  "signal_strength": "HIGH/MEDIUM/LOW",
  "cross_border_category": "diplomatic/defence/internal_politics/economics"
}"""

BRIEF_PROMPT = """You are a senior military intelligence analyst. Generate a structured Daily Intelligence Brief for India's North Eastern Region (NER) AND bordering countries (Bangladesh, Myanmar) based on the following intelligence items.

The brief must include:
1. key_developments: List of 6-10 bullet points of the most important developments across NER, Bangladesh, and Myanmar
2. state_highlights: Object with region names as keys (Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar) and 1-2 line highlights for each affected region
3. cross_border_insights: Summary of cross-border activities and foreign power involvement (China/Pakistan/USA) in the region (3-4 lines)
4. analyst_summary: Professional analyst-style summary paragraph (5-6 lines) covering overall security posture of NER AND strategic developments in Bangladesh/Myanmar

Respond ONLY in valid JSON:
{
  "key_developments": ["...", "..."],
  "state_highlights": {"Assam": "...", "Bangladesh": "...", "Myanmar": "..."},
  "cross_border_insights": "...",
  "analyst_summary": "..."
}"""


async def classify_and_analyze_article(article, source_hint: str = "") -> dict:
    """Classify and analyze a news article using Gemini 2.5 Flash with enhanced military intelligence prompt.
    Dynamically injects analyst feedback bias when available.

    Accepts two calling conventions for backward-compatibility:
      classify_and_analyze_article(article_dict)        — preferred
      classify_and_analyze_article(text_str, src_name)  — legacy (fetchers pass raw text)
    """
    if isinstance(article, str):
        # Legacy calling pattern: (raw_text, source_name)
        # Used by telegram_fetcher, youtube_fetcher, twitter_fetcher, etc.
        title = source_hint or ""
        content = article
    else:
        title = article.get("title", "")
        content = article.get("raw_content", "") or article.get("description", "") or title

    article_text = f"Title: {title}\nContent: {content[:2000]}"

    try:
        from feedback_bias import get_feedback_bias_context

        # Build system prompt — prepend feedback bias if available.
        # Gemini uses OpenAI-compat format: system is a message, not a separate param.
        # No cache_control blocks needed (Gemini is cheap enough without caching).
        bias_context = await get_feedback_bias_context()
        system_text = CLASSIFICATION_PROMPT
        if bias_context:
            system_text = system_text + "\n\n" + bias_context

        client = get_client()
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,  # bumped: Gemini 2.5 Flash thinking uses tokens before JSON
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": f"Analyze this article:\n\n{article_text}"},
            ],
            extra_body={"include_reasoning": False},  # disable thinking — saves tokens + cost
        )

        # Track token usage and cost
        try:
            from usage_tracker import track_usage_generic
            usage = response.usage
            if usage:
                await track_usage_generic(
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    model=MODEL,
                )
        except Exception as e:
            logger.warning(f"track_usage (classify) failed: {e}")

        # Parse JSON from response
        response_text = response.choices[0].message.content or ""
        # Try to extract JSON from the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            analysis = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")

        # Extract data from new enhanced format
        display_title = analysis.get("title_english", title) or title
        priority_score = analysis.get("priority_score", 30)
        
        # Severity always derived from priority_score — never trust AI's severity
        # field directly, because the AI frequently outputs severity="high" even
        # when it sets priority_score=100, creating inconsistent classifications.
        # priority_score is the authoritative numeric measure; severity is just
        # its categorical label.
        if priority_score >= 80:
            severity = "critical"
        elif priority_score >= 60:
            severity = "high"
        elif priority_score >= 40:
            severity = "medium"
        else:
            severity = "low"
        
        # Get primary region from regions array — normalise to canonical map names
        _REGION_ALIASES = {
            "west bengal / siliguri corridor": "West Bengal",
            "west bengal/siliguri corridor": "West Bengal",
            "siliguri corridor": "West Bengal",
            "multiple": "",
        }
        _CANONICAL_REGIONS = {
            "assam", "meghalaya", "mizoram", "manipur", "arunachal pradesh",
            "tripura", "nagaland", "sikkim", "west bengal", "bangladesh", "myanmar",
        }
        def _normalise_region(r):
            r_low = (r or "").strip().lower()
            if r_low in _REGION_ALIASES:
                return _REGION_ALIASES[r_low]
            if r_low in _CANONICAL_REGIONS:
                return r.strip()
            # Partial match — e.g. "Nagaland (Dimapur)" → "Nagaland"
            for canon in _CANONICAL_REGIONS:
                if canon in r_low:
                    return canon.title()
            return r.strip()
        regions = [_normalise_region(r) for r in analysis.get("regions", []) if r and r.lower() != "multiple"]
        primary_region = regions[0] if regions else ""
        
        # Get tags - use as multi-label classification
        tags = analysis.get("tags", [])
        threat_category = tags[0] if tags else "General News"
        
        result = {
            "title": display_title,
            "original_title": title if display_title != title else None,
            "source": article.get("source", "Unknown"),
            "source_url": article.get("source_url", ""),
            "published_at": article.get("published_at", ""),
            "raw_content": content[:5000],
            
            # Enhanced intelligence fields
            "priority_score": priority_score,
            "confidence_score": analysis.get("confidence_score", 70),
            "threat_trajectory": analysis.get("threat_trajectory", "INDETERMINATE"),
            "tags": tags,
            "regions": regions,
            "actors": analysis.get("actors", []),
            "special_flags": analysis.get("special_flags", []),
            "early_warning_signal": analysis.get("early_warning_signal", ""),
            
            # Named Entity Extraction
            "entities": analysis.get("entities", {"persons": [], "organizations": [], "locations": []}),
            
            # Intelligence analysis
            "ai_summary": analysis.get("intelligence_summary", ""),
            "why_it_matters": analysis.get("why_it_matters", ""),
            "potential_impact": analysis.get("early_warning_signal", ""),
            "attention_level": analysis.get("recommended_attention", "Routine Monitoring"),
            
            # Backward compatible fields
            "state": primary_region,
            "threat_category": threat_category,
            "severity": severity,
            "is_cross_border": analysis.get("cross_border", False),
            "countries_involved": analysis.get("countries", []),

            # Cross-border intelligence fields
            "india_relevance_score": analysis.get("india_relevance_score", 0),
            "signal_bucket": analysis.get("signal_bucket", ""),
            "signal_strength": analysis.get("signal_strength", ""),
            "cross_border_category": analysis.get("cross_border_category", ""),

            "is_relevant": analysis.get("relevant", True),
            "processed": True
        }
        return result

    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        # Re-raise so _classify_with_retry_v2 can retry with back-off.
        # Callers that need a fallback (fetch_and_process_news) get None after
        # all retries are exhausted, and handle it via _make_raw_doc.
        raise


async def generate_daily_brief_ai(items: list, date: str) -> dict:
    """Generate a daily intelligence brief using AI"""
    import uuid
    from datetime import datetime, timezone

    items_summary = "\n".join([
        f"- [{item.get('severity', 'medium').upper()}] [{item.get('state', 'NER')}] {item.get('title', '')}: {item.get('ai_summary', '')}"
        for item in items[:30]
    ])

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=1500,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": BRIEF_PROMPT},
                {
                    "role": "user",
                    "content": f"Generate a Daily Intelligence Brief for {date} based on these intelligence items:\n\n{items_summary}",
                },
            ],
        )

        try:
            from usage_tracker import track_usage_generic
            usage = response.usage
            if usage:
                await track_usage_generic(
                    input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                    model=MODEL,
                )
        except Exception as e:
            logger.warning(f"track_usage (brief) failed: {e}")

        response_text = response.choices[0].message.content or ""
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            brief_data = json.loads(response_text[json_start:json_end])
        else:
            raise ValueError("No JSON in response")

        return {
            "id": str(uuid.uuid4()),
            "date": date,
            "key_developments": brief_data.get("key_developments", []),
            "state_highlights": brief_data.get("state_highlights", {}),
            "cross_border_insights": brief_data.get("cross_border_insights", ""),
            "analyst_summary": brief_data.get("analyst_summary", ""),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"AI brief generation failed: {e}")
        raise
