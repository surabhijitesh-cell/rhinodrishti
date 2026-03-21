import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

CLASSIFICATION_PROMPT = """You are a military intelligence analyst specializing in India's North Eastern Region (NER) and bordering countries (Bangladesh, Myanmar).

Your areas of interest are:
- 6 NER States: Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura
- Bangladesh (internal politics, military, economy, foreign relations)
- Myanmar (internal conflict, military junta, ethnic armed organizations)

IMPORTANT: Be INCLUSIVE in relevance assessment. ANY news from NER states or Bangladesh/Myanmar should be marked relevant.

CRITICAL: If the article is in Bengali, Assamese, Hindi, or any other non-English language, you MUST TRANSLATE all your responses (ai_summary, why_it_matters, potential_impact, title_english) to ENGLISH. All output must be in English only.

SPECIAL EMPHASIS: Flag any news indicating involvement of China, Pakistan, or USA in Bangladesh or Myanmar. These are HIGH PRIORITY items.

Analyze the following news article and determine:

1. Is this article relevant to monitoring? (true/false)
   - For NER: ANY news from these states is relevant (politics, economy, crime, development, social issues)
   - For Bangladesh/Myanmar: ALL news is relevant
   - China/Pakistan/USA involvement is ALWAYS relevant and HIGH/CRITICAL
   - Default to TRUE if article mentions any NER state, Bangladesh, or Myanmar
2. Primary threat category (choose ONE):
   - Insurgency
   - Cross-border Movement
   - Illegal Immigration
   - Drug Trafficking
   - Arms Smuggling
   - Ethnic Conflicts
   - Cyber Threats
   - Strategic Infrastructure
   - Political Developments
   - Foreign Power Influence
   - Military Operations
   - Economic/Trade
   - General News (for non-security news from the region)
3. Severity level: low, medium, high, or critical
   - Mark as HIGH or CRITICAL if China/Pakistan/USA involvement is detected
4. Region primarily affected (choose ONE): Assam, Meghalaya, Mizoram, Manipur, Arunachal Pradesh, Tripura, Bangladesh, Myanmar, or "Multiple"
5. Is this a cross-border issue? (true/false)
6. Countries involved (Bangladesh, Myanmar, China, Pakistan, USA, Bhutan, India, or empty list)
7. Concise intelligence summary IN ENGLISH (3-4 lines) - translate if source is non-English
8. Why it matters IN ENGLISH (security/strategic implications from India's perspective, 2-3 lines)
9. Potential future impact IN ENGLISH (1-2 lines)
10. Recommended attention level (Immediate Action Required, Priority Monitoring, Active Monitoring, Monitor)
11. title_english: English translation of the title (same as original if already English)

Respond ONLY in valid JSON format:
{
  "is_relevant": true/false,
  "threat_category": "...",
  "severity": "...",
  "state": "...",
  "is_cross_border": true/false,
  "countries_involved": [],
  "ai_summary": "...",
  "why_it_matters": "...",
  "potential_impact": "...",
  "attention_level": "...",
  "title_english": "..."
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
    """Classify and analyze a news article using Claude Haiku 4.5"""
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

        # Merge with original article data
        # Use translated title if provided, otherwise use original
        display_title = analysis.get("title_english", title) or title
        
        result = {
            "title": display_title,
            "original_title": title if display_title != title else None,
            "source": article.get("source", "Unknown"),
            "source_url": article.get("source_url", ""),
            "published_at": article.get("published_at", ""),
            "raw_content": content[:5000],
            "ai_summary": analysis.get("ai_summary", ""),
            "why_it_matters": analysis.get("why_it_matters", ""),
            "potential_impact": analysis.get("potential_impact", ""),
            "attention_level": analysis.get("attention_level", "Monitor"),
            "state": analysis.get("state", ""),
            "threat_category": analysis.get("threat_category", ""),
            "severity": analysis.get("severity", "medium"),
            "is_cross_border": analysis.get("is_cross_border", False),
            "countries_involved": analysis.get("countries_involved", []),
            "is_relevant": analysis.get("is_relevant", True),
            "processed": True,
            "tags": []
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
