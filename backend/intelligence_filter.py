import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================
# STAGE 1: HARD FILTER (Rule-based noise rejection)
# ============================================================

HARD_REJECT_KEYWORDS = [
    # Sports
    'cricket', 'cricketer', 'ipl', 'bcci', 'odi', 't20', 'test match', 'wicket', 'batsman', 'bowler',
    'football', 'fifa', 'premier league', 'la liga', 'champions league', 'goalkeeper', 'midfielder',
    'striker', 'chelsea', 'manchester', 'barcelona', 'real madrid', 'tennis', 'wimbledon', 'olympics',
    'badminton', 'kabaddi', 'hockey league', 'isl ', 'pro kabaddi',
    # Entertainment
    'bollywood', 'tollywood', 'kollywood', 'hollywood', 'movie review', 'box office', 'film review',
    'celebrity', 'actress', 'actor', 'singer', 'album', 'music video', 'trailer launch', 'ott release',
    'bigg boss', 'reality show', 'tv serial', 'web series',
    # Lifestyle
    'recipe', 'cooking', 'fashion week', 'beauty tips', 'skincare', 'haircare', 'makeup tutorial',
    'horoscope', 'astrology', 'zodiac', 'lottery result', 'lottery winner',
    'wedding ceremony', 'divorce settlement', 'dating app',
    # General irrelevant
    'game show', 'quiz show', 'crossword', 'sudoku', 'weather forecast today',
    'stock market tip', 'mutual fund', 'crypto price', 'bitcoin price',
]

HARD_ACCEPT_KEYWORDS = [
    # Military/Security
    'military', 'army', 'navy', 'air force', 'defence', 'defense', 'weapon', 'ammunition',
    'missile', 'artillery', 'tank', 'warship', 'fighter jet', 'helicopter gunship',
    'bsf', 'crpf', 'assam rifles', 'itbp', 'ssb', 'nsg', 'marcos', 'para sf',
    'bgb', 'border guard', 'tatmadaw', 'pla ',
    # Insurgency/Conflict
    'insurgent', 'militant', 'separatist', 'ulfa', 'nscn', 'pla', 'hnlc', 'nlft',
    'ambush', 'encounter', 'gunfight', 'firing', 'ied', 'bomb blast', 'grenade',
    'rpg', 'ceasefire', 'surrender', 'arms cache', 'arms recovery',
    # Border/Cross-border
    'border', 'infiltration', 'cross-border', 'smuggling', 'trafficking', 'narcotics',
    'illegal immigration', 'deportation', 'rohingya', 'refugee',
    # Strategic
    'nuclear', 'submarine', 'aircraft carrier', 'radar', 'surveillance', 'drone', 'uav',
    'cyber attack', 'espionage', 'intelligence', 'diplomatic', 'sanctions',
    # NER specific
    'northeast india', 'north east india', 'ner ', 'manipur', 'assam', 'meghalaya',
    'mizoram', 'tripura', 'arunachal', 'nagaland',
]

GEO_RELEVANT = [
    'assam', 'meghalaya', 'mizoram', 'manipur', 'arunachal', 'tripura', 'nagaland', 'sikkim',
    'northeast india', 'guwahati', 'imphal', 'shillong', 'itanagar', 'agartala', 'aizawl',
    'dimapur', 'kohima', 'tinsukia', 'dibrugarh', 'silchar', 'tezpur', 'kokrajhar',
    'churachandpur', 'moreh', 'dawki', 'tawang', 'changlang',
    'bangladesh', 'dhaka', 'chittagong', 'sylhet', 'myanmar', 'naypyidaw', 'rakhine',
    'chin state', 'sagaing', 'kachin',
]


def hard_filter(article: dict) -> tuple:
    """
    STAGE 1: Rule-based hard filter.
    Returns: (pass: bool, reason: str)
    """
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or article.get("description", "") or "").lower()
    source_region = (article.get("region", "") or "").lower()
    text = f"{title} {content[:500]}"

    # RULE 1: Bangladesh/Myanmar feeds always accepted
    if source_region in ("bangladesh", "myanmar"):
        return True, "source_region_relevant"

    # RULE 2: Hard reject on title
    for kw in HARD_REJECT_KEYWORDS:
        if kw in title:
            return False, f"hard_reject:{kw}"

    # RULE 3: Hard accept on security signals
    for kw in HARD_ACCEPT_KEYWORDS:
        if kw in text:
            return True, f"hard_accept:{kw}"

    # RULE 4: Geographic relevance
    for geo in GEO_RELEVANT:
        if geo in text:
            return True, f"geo_relevant:{geo}"

    # RULE 5: National/international with no signals -> reject
    if source_region in ("india", "international"):
        return False, "no_relevance_signal"

    # RULE 6: NER sources accepted by default
    if source_region in ("ner", "ner "):
        return True, "ner_source"

    return False, "no_match"


# ============================================================
# LANGUAGE DETECTION
# ============================================================

def detect_language(text: str) -> str:
    """Detect language via character analysis."""
    if not text:
        return "en"
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    assamese_chars = len(re.findall(r'[\u09F0\u09F1]', text))
    total_chars = len(text)
    if total_chars == 0:
        return "en"
    if assamese_chars > 0 and bengali_chars > total_chars * 0.15:
        return "as"
    elif bengali_chars > total_chars * 0.15:
        return "bn"
    elif hindi_chars > total_chars * 0.15:
        return "hi"
    return "en"


async def translate_to_english(text: str, source_lang: str, emergent_key: str) -> tuple:
    """
    Translate non-English text to English using Claude.
    Returns: (translated_text, confidence_score 0-100)
    """
    if source_lang == "en" or not text or len(text.strip()) < 10:
        return text, 100

    lang_names = {"bn": "Bengali", "hi": "Hindi", "as": "Assamese"}
    lang_name = lang_names.get(source_lang, "Unknown")

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"translate-{hash(text[:50])}",
            system_message=f"You are a precise translator. Translate the following {lang_name} text to English. "
                          f"Preserve all proper nouns, place names, organization names, and military terms. "
                          f"Return ONLY the translation, nothing else. If text is already English, return as-is."
        ).with_model("anthropic", "claude-haiku-4-5-20251001")

        response = await chat.send_message(UserMessage(text=text[:3000]))
        translated = str(response).strip()

        english_ratio = len(re.findall(r'[a-zA-Z]', translated)) / max(len(translated), 1)
        confidence = min(100, int(english_ratio * 120))

        if confidence < 50:
            logger.warning(f"Low translation confidence ({confidence}), retrying...")
            response2 = await chat.send_message(UserMessage(
                text=f"Please translate this {lang_name} text to clear English. Output ONLY the English translation:\n\n{text[:2000]}"
            ))
            translated = str(response2).strip()
            english_ratio = len(re.findall(r'[a-zA-Z]', translated)) / max(len(translated), 1)
            confidence = min(100, int(english_ratio * 120))

        return translated, confidence

    except Exception as e:
        logger.error(f"Translation failed for {lang_name}: {e}")
        return text, 0


# ============================================================
# FULL FILTER PIPELINE
# ============================================================

async def run_filter_pipeline(article: dict, emergent_key: str) -> dict:
    """
    Run the complete 2-stage filter pipeline on an article.
    
    Returns dict with:
      - passed: bool
      - reason: str
      - language: str
      - translated_title: str (if translated)
      - translated_content: str (if translated)
    """
    result = {
        "passed": False,
        "reason": "",
        "language": "en",
        "translated_title": None,
        "translated_content": None,
    }

    # Stage 1: Hard filter
    passed, reason = hard_filter(article)
    result["reason"] = reason

    if not passed:
        result["passed"] = False
        return result

    result["passed"] = True

    # Language detection & translation (pre-process before AI)
    title = article.get("title", "") or ""
    content = article.get("raw_content", "") or article.get("description", "") or ""
    combined = f"{title} {content[:200]}"
    lang = detect_language(combined)
    result["language"] = lang

    if lang != "en" and emergent_key:
        # Translate title
        translated_title, t_conf = await translate_to_english(title, lang, emergent_key)
        if t_conf >= 40:
            result["translated_title"] = translated_title

        # Translate content snippet for AI classification
        translated_content, c_conf = await translate_to_english(content[:2000], lang, emergent_key)
        if c_conf >= 40:
            result["translated_content"] = translated_content

    return result
