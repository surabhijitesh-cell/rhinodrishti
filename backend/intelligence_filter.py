import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================
# STAGE 1: HARD FILTER (Rule-based noise rejection)
# ============================================================

# Keywords that need WORD BOUNDARY matching (short/ambiguous terms)
# These use regex \b...\b to avoid matching inside other words
REJECT_WORD_BOUNDARY = [
    r'\bipl\b', r'\bodi\b', r'\bt20\b', r'\bicc\b', r'\bisl\b',
    r'\bf1\b', r'\blbw\b',
]

# Keywords that use simple substring matching (long enough to be unambiguous)
REJECT_SUBSTRING = [
    # Cricket
    'cricket', 'cricketer', 'bcci', 'test match', 'wicket', 'batsman',
    'bowler', 'batting average', 'bowling figures', 'innings defeat',
    'world cup cricket', 'indian premier league',
    # IPL teams (full names only)
    'mumbai indians', 'chennai super kings', 'royal challengers bengaluru',
    'royal challengers bangalore', 'kolkata knight riders',
    'sunrisers hyderabad', 'rajasthan royals', 'delhi capitals',
    'punjab kings', 'lucknow super giants', 'gujarat titans',
    # Football
    'premier league', 'la liga', 'champions league', 'goalkeeper',
    'midfielder', 'striker', 'chelsea', 'real madrid',
    'arsenal', 'liverpool fc', 'tottenham', 'serie a football',
    'fc barcelona', 'barcelona fc',
    # Other Sports
    'tennis', 'wimbledon', 'olympics', 'badminton championship',
    'kabaddi', 'hockey league', 'pro kabaddi', 'asian games medal',
    'commonwealth games', 'formula 1', 'grand prix', 'boxing match',
    'wrestling championship',
    # Entertainment
    'bollywood', 'tollywood', 'kollywood', 'movie review', 'box office',
    'film review', 'celebrity gossip', 'trailer launch', 'ott release',
    'bigg boss', 'reality show', 'tv serial', 'web series review',
    # Lifestyle
    'recipe', 'fashion week', 'beauty tips', 'skincare routine',
    'makeup tutorial', 'horoscope', 'astrology', 'zodiac',
    'lottery result', 'lottery winner', 'teer result',
    'wedding ceremony', 'divorce settlement', 'dating app',
    # Education spam
    'upsc coaching', 'coaching institute', 'admission open',
    # General irrelevant
    'game show', 'quiz show', 'crossword puzzle', 'sudoku',
    'stock market tip', 'mutual fund', 'crypto price', 'bitcoin price',
]

HARD_ACCEPT_KEYWORDS = [
    # Military/Security
    'military', 'army', 'navy', 'air force', 'defence', 'defense', 'weapon', 'ammunition',
    'missile', 'artillery', 'tank', 'warship', 'fighter jet', 'helicopter gunship',
    'bsf', 'crpf', 'assam rifles', 'itbp', 'ssb', 'nsg', 'marcos', 'para sf',
    'bgb', 'border guard', 'tatmadaw',
    # Insurgency/Conflict
    'insurgent', 'militant', 'separatist', 'ulfa', 'nscn', 'hnlc', 'nlft',
    'ambush', 'encounter', 'gunfight', 'firing', 'ied', 'bomb blast', 'grenade',
    'ceasefire', 'surrender', 'arms cache', 'arms recovery', 'explosives recovered',
    # Border/Cross-border
    'border', 'infiltration', 'cross-border', 'smuggling', 'trafficking', 'narcotics',
    'illegal immigration', 'deportation', 'rohingya', 'refugee',
    # Strategic
    'nuclear', 'submarine', 'aircraft carrier', 'radar', 'surveillance', 'drone', 'uav',
    'cyber attack', 'espionage', 'intelligence agency', 'diplomatic', 'sanctions',
    # NER specific
    'northeast india', 'north east india', 'manipur', 'assam', 'meghalaya',
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

# Pre-compile word-boundary patterns for efficiency
_COMPILED_WB_PATTERNS = [re.compile(p, re.IGNORECASE) for p in REJECT_WORD_BOUNDARY]


def _check_reject(text: str) -> str:
    """Check if text matches any reject pattern. Returns matched keyword or empty string."""
    text_lower = text.lower()
    # Substring matches (long, unambiguous keywords)
    for kw in REJECT_SUBSTRING:
        if kw in text_lower:
            return kw
    # Word-boundary matches (short, ambiguous keywords)
    for pattern in _COMPILED_WB_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return ""


def hard_filter(article: dict) -> tuple:
    """
    STAGE 1: Rule-based hard filter.
    Returns: (pass: bool, reason: str)
    
    REJECT runs on BOTH title AND content, and runs FIRST before any accept logic.
    This ensures sports/entertainment/lifestyle never leaks through regardless of source.
    """
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or article.get("description", "") or "").lower()
    source_region = (article.get("region", "") or "").lower()
    text = f"{title} {content[:500]}"

    # RULE 1: Hard reject on title OR content — runs FIRST, no exceptions
    reject_match = _check_reject(title)
    if reject_match:
        return False, f"hard_reject_title:{reject_match}"
    reject_match = _check_reject(content[:800])
    if reject_match:
        return False, f"hard_reject_content:{reject_match}"

    # RULE 2: Bangladesh/Myanmar feeds always accepted (after reject check)
    if source_region in ("bangladesh", "myanmar"):
        return True, "source_region_relevant"

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

    # RULE 6: NER sources accepted by default (only after passing reject check)
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
