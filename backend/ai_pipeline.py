import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

CLASSIFICATION_PROMPT = """You are a SENIOR MILITARY INTELLIGENCE ANALYST specializing in:

- India's North Eastern Region (Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura)
- Bangladesh and Myanmar security dynamics
- China (PLA) and Pakistan influence in South Asia
- Hybrid warfare, information warfare, and cross-border threats

Your PRIMARY OBJECTIVE is NOT to summarize news, but to IDENTIFY, PRIORITIZE, and EXTRACT actionable intelligence.

--------------------------------------------------
STEP 1: RELEVANCE FILTER (STRICT)
--------------------------------------------------

Classify the article as RELEVANT = TRUE if it satisfies ANY of the following:

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

D. SOCIETAL INSTABILITY / EARLY WARNING:
- Tribal unrest or mobilization
- Anti-minority incidents (especially anti-Hindu in Bangladesh)
- Ex-servicemen protests or mobilization
- Information campaigns, propaganda, narratives

E. EMERGING TECHNOLOGY THREATS:
- Drones (HALE/MALE/tactical/UAV incursions)
- Surveillance tech, cyber threats

F. HIGH-LEVEL NATIONAL / GLOBAL SIGNALS:
- Any national or international event that could impact:
  - India's military posture
  - China/US/Pakistan strategy in South Asia

If NONE of the above → RELEVANT = FALSE

--------------------------------------------------
STEP 2: PRIORITY SCORING (CRITICAL)
--------------------------------------------------

Assign an INTELLIGENCE PRIORITY SCORE (0–100):

80–100 → CRITICAL (Immediate operational relevance)
60–79 → HIGH (Strategic concern)
40–59 → MEDIUM (Situational awareness)
<40 → LOW (Background noise)

Boost score if:
+ Cross-border involvement (+10)
+ China / Pakistan presence (+15)
+ Military movement (+10)
+ Pattern or trend (not isolated event) (+5)

--------------------------------------------------
STEP 3: CLASSIFICATION (MULTI-LABEL)
--------------------------------------------------

Assign ALL applicable tags (not just one):

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

--------------------------------------------------
STEP 4: CONTEXTUAL INTELLIGENCE EXTRACTION
--------------------------------------------------

Extract:

1. REGION(S) affected (multi-select from: Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar, Multiple)
2. CROSS-BORDER: Yes/No
3. COUNTRIES involved (India, Bangladesh, Myanmar, China, Pakistan, USA, etc.)
4. ACTORS involved (Army, BSF, BGB, Assam Rifles, PLA, insurgent groups, tribes, political parties etc.)

--------------------------------------------------
STEP 5: INTELLIGENCE OUTPUT (CRISP & ACTIONABLE)
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

--------------------------------------------------
STEP 6: SPECIAL DETECTION (MANDATORY)
--------------------------------------------------

Explicitly check and flag in special_flags array:

- PLA_PAKISTAN_PRESENCE: Any PLA or Pakistan indirect presence in Bangladesh/Myanmar
- COORDINATED_NARRATIVE: Any coordinated narrative or propaganda pattern
- DEMOGRAPHIC_TREND: Any gradual demographic or migration trend
- DUAL_USE_INFRA: Any infrastructure that can be militarized
- PATTERN_DETECTED: Any repeated incidents forming a pattern

--------------------------------------------------
STEP 7: LANGUAGE RULE
--------------------------------------------------

If input is non-English (Bengali, Hindi, Assamese, etc.) → ALL OUTPUT MUST BE IN ENGLISH

--------------------------------------------------
FINAL OUTPUT FORMAT (JSON ONLY)
--------------------------------------------------

{
  "relevant": true/false,
  "priority_score": 0-100,
  "severity": "critical/high/medium/low",
  "tags": ["tag1", "tag2"],
  "regions": ["region1", "region2"],
  "cross_border": true/false,
  "countries": ["country1", "country2"],
  "actors": ["actor1", "actor2"],
  "intelligence_summary": "3 lines max",
  "why_it_matters": "2 lines max",
  "early_warning_signal": "1 line",
  "recommended_attention": "Immediate Action Required/Priority Monitoring/Active Monitoring/Routine Monitoring",
  "special_flags": ["flag1", "flag2"],
  "title_english": "translated title"
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


async def classify_and_analyze_article(article: dict) -> dict:
    """Classify and analyze a news article using Claude Haiku 4.5 with enhanced military intelligence prompt"""
    title = article.get("title", "")
    content = article.get("raw_content", "") or article.get("description", "") or title

    article_text = f"Title: {title}\nContent: {content[:2000]}"

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"classify-{article.get('id', 'unknown')}",
            system_message=CLASSIFICATION_PROMPT
        ).with_model("anthropic", "claude-haiku-4-5-20251001")

        user_message = UserMessage(text=f"Analyze this article:\n\n{article_text}")
        response = await chat.send_message(user_message)

        # Parse JSON from response
        response_text = str(response)
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
        
        # Determine severity from priority_score if not directly provided
        severity = analysis.get("severity", "")
        if not severity or severity not in ["critical", "high", "medium", "low"]:
            if priority_score >= 80:
                severity = "critical"
            elif priority_score >= 60:
                severity = "high"
            elif priority_score >= 40:
                severity = "medium"
            else:
                severity = "low"
        
        # Get primary region from regions array
        regions = analysis.get("regions", [])
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
            
            # New enhanced intelligence fields
            "priority_score": priority_score,
            "tags": tags,
            "regions": regions,
            "actors": analysis.get("actors", []),
            "special_flags": analysis.get("special_flags", []),
            "early_warning_signal": analysis.get("early_warning_signal", ""),
            
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
            
            "is_relevant": analysis.get("relevant", True),
            "processed": True
        }
        return result

    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        # Return article with basic classification
        return {
            "title": title,
            "source": article.get("source", "Unknown"),
            "source_url": article.get("source_url", ""),
            "published_at": article.get("published_at", ""),
            "raw_content": content[:5000],
            "ai_summary": content[:200],
            "why_it_matters": "Requires manual review.",
            "potential_impact": "Assessment pending.",
            "attention_level": "Monitor",
            "state": "",
            "threat_category": "",
            "severity": "low",
            "is_cross_border": False,
            "countries_involved": [],
            "is_relevant": True,
            "processed": False,
            "tags": ["unprocessed"]
        }


async def generate_daily_brief_ai(items: list, date: str) -> dict:
    """Generate a daily intelligence brief using AI"""
    import uuid
    from datetime import datetime, timezone

    items_summary = "\n".join([
        f"- [{item.get('severity', 'medium').upper()}] [{item.get('state', 'NER')}] {item.get('title', '')}: {item.get('ai_summary', '')}"
        for item in items[:30]
    ])

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"brief-{date}",
            system_message=BRIEF_PROMPT
        ).with_model("anthropic", "claude-haiku-4-5-20251001")

        user_message = UserMessage(
            text=f"Generate a Daily Intelligence Brief for {date} based on these intelligence items:\n\n{items_summary}"
        )
        response = await chat.send_message(user_message)

        response_text = str(response)
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
