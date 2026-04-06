import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# STAGE 1: HARD FILTER (Rule-based noise rejection)
# ============================================================

# Hard reject keywords - if title/content contains these, reject immediately
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

# Hard accept keywords - if present, always accept (security/strategic signals)
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

# Geographic relevance - accept if mentions these regions
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
    
    - Immediately reject pure entertainment/sports/lifestyle
    - Immediately accept security/strategic signals
    - Accept if geographically relevant
    - Reject if none of the above
    """
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or article.get("description", "") or "").lower()
    source_region = (article.get("region", "") or "").lower()
    text = f"{title} {content[:500]}"
    
    # RULE 1: If from Bangladesh/Myanmar specific feeds, always accept
    if source_region in ("bangladesh", "myanmar"):
        return True, "source_region_relevant"
    
    # RULE 2: Hard reject - entertainment/sports/lifestyle
    for kw in HARD_REJECT_KEYWORDS:
        if kw in title:  # Only check title for hard reject (more precise)
            return False, f"hard_reject:{kw}"
    
    # RULE 3: Hard accept - security/strategic signals
    for kw in HARD_ACCEPT_KEYWORDS:
        if kw in text:
            return True, f"hard_accept:{kw}"
    
    # RULE 4: Geographic relevance
    for geo in GEO_RELEVANT:
        if geo in text:
            return True, f"geo_relevant:{geo}"
    
    # RULE 5: If from national/international source with no relevance signals, reject
    if source_region in ("india", "international"):
        return False, "no_relevance_signal"
    
    # RULE 6: Regional NER sources - accept by default (they're subscribed for a reason)
    if source_region == "ner":
        return True, "ner_source"
    
    # Default: reject
    return False, "no_match"


# ============================================================
# LANGUAGE DETECTION (Pre-processing)
# ============================================================

def detect_language(text: str) -> str:
    """Detect language of text using character analysis"""
    if not text:
        return "en"
    
    # Check for Bengali/Bangla script (Unicode range U+0980-U+09FF)
    bengali_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    # Check for Devanagari (Hindi) script (Unicode range U+0900-U+097F)
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    # Check for Assamese (uses Bengali script with some extras)
    # Assamese specific chars: ৰ (U+09F0), ৱ (U+09F1)
    assamese_chars = len(re.findall(r'[\u09F0\u09F1]', text))
    
    total_chars = len(text)
    if total_chars == 0:
        return "en"
    
    # If more than 20% non-Latin characters
    non_latin_ratio = (bengali_chars + hindi_chars) / total_chars
    
    if assamese_chars > 0 and bengali_chars > total_chars * 0.15:
        return "as"  # Assamese
    elif bengali_chars > total_chars * 0.15:
        return "bn"  # Bengali
    elif hindi_chars > total_chars * 0.15:
        return "hi"  # Hindi
    
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
        
        # Simple confidence: check if output looks like English
        english_ratio = len(re.findall(r'[a-zA-Z]', translated)) / max(len(translated), 1)
        confidence = min(100, int(english_ratio * 120))
        
        # Retry if confidence is too low
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
