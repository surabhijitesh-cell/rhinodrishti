import re
import logging
from datetime import datetime, timezone

from llm_client import get_client, MODEL

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
    # ============================================================
    # A. INSURGENCY / MILITANCY
    # ============================================================
    'insurgent', 'insurgency', 'militant', 'militancy', 'separatist', 'rebel', 'extremist',
    'ulfa', 'nscn', 'pla', 'prepak', 'unlf', 'kcp', 'hnlc', 'gnla', 'ndfb', 'klo',
    'nlft', 'kuki militant', 'meitei armed', 'cadre', 'underground outfit',
    'ambush', 'encounter', 'gunfight', 'firing', 'ied', 'landmine', 'bomb blast',
    'grenade', 'explosive recovered', 'arms cache', 'arms recovery',
    'ceasefire', 'surrender', 'recruitment drive', 'extortion', 'abduct', 'kidnap',
    'terror', 'terrorist', 'terror attack', 'sleeper cell',

    # ============================================================
    # B. MILITARY / SECURITY FORCES
    # ============================================================
    'military', 'army', 'navy', 'air force', 'defence', 'defense', 'weapon', 'ammunition',
    'missile', 'artillery', 'tank', 'warship', 'fighter jet', 'helicopter gunship',
    'bsf', 'crpf', 'assam rifles', 'itbp', 'ssb', 'nsg', 'marcos', 'para sf', 'cobra',
    'bgb', 'border guard bangladesh', 'tatmadaw', 'myanmar army', 'pla army',
    'security forces', 'paramilitary', 'special forces',

    # ============================================================
    # C. BORDER / CROSS-BORDER
    # ============================================================
    'border', 'infiltration', 'cross-border', 'smuggling', 'trafficking', 'narcotics',
    'drug bust', 'heroin', 'yaba', 'methamphetamine', 'opium', 'poppy cultivation',
    'arms haul', 'weapon seizure', 'illegal immigration', 'illegal immigrant',
    'deportation', 'rohingya', 'refugee', 'fencing', 'border outpost',
    'chinese incursion', 'lac', 'doklam', 'tawang sector', 'bum la',
    'chin state', 'kachin', 'arakan', 'pdf myanmar', 'junta',

    # ============================================================
    # D. COMMUNAL / ETHNIC TENSION
    # ============================================================
    'communal', 'communal tension', 'riot', 'mob lynch', 'lynching', 'curfew',
    'section 144', 'prohibitory order', 'ethnic clash', 'tribal clash',
    'kuki', 'meitei', 'naga', 'bodo', 'karbi', 'dimasa', 'hmar', 'zomi',
    # Meghalaya ethnic communities (previously missing — critical for local coverage)
    'khasi', 'garo', 'jaintia', 'hajong', 'koch', 'biate', 'pnar', 'war tribe',
    'rabha', 'boro kachari',
    'inter-community', 'land dispute', 'ilp', 'inner line permit', 'caa', 'nrc',
    'illegal settler', 'mob attack',
    # Meghalaya-specific social unrest triggers
    'murder in meghalaya', 'killing in meghalaya', 'shillong unrest',
    'meghalaya bandh', 'meghalaya protest', 'shillong violence',
    'local vs non-local', 'settler issue meghalaya', 'indigenous meghalaya',

    # ============================================================
    # E. POLITICAL UNREST
    # ============================================================
    'protest', 'bandh', 'hartal', 'blockade', 'agitation', 'rally',
    'gherao', 'dharna', 'self-immolation', 'sit-in', 'stone pelting',
    'lathi charge', 'tear gas', 'police firing', 'election violence',
    'booth capture', 'no-confidence', 'defection', 'coalition crisis',
    'governor rule', "president's rule",

    # ============================================================
    # F. NATURAL DISASTERS
    # ============================================================
    'earthquake', 'tremor', 'seismic', 'landslide', 'landslip', 'mudslide',
    'flood', 'flash flood', 'deluge', 'inundation', 'inundated', 'cloudburst',
    'cyclone', 'storm surge', 'hailstorm', 'thunderstorm', 'lightning strike',
    'avalanche', 'glacial lake', 'glof', 'glacial lake outburst',
    'river breach', 'embankment breach', 'erosion', 'displacement',
    'relief camp', 'evacuation', 'disaster',

    # ============================================================
    # G. EXTREME WEATHER
    # ============================================================
    'heatwave', 'cold wave', 'drought', 'monsoon failure', 'excess rain',
    'deficit rain', 'snowfall heavy', 'hailstorm', 'squall', 'depression weather',
    'low pressure', 'imd warning', 'red alert', 'orange alert',
    "nor'wester", 'kalbaisakhi', 'extreme weather',

    # ============================================================
    # H. INFRASTRUCTURE IMPACT
    # ============================================================
    'bridge collapse', 'road cave', 'tunnel collapse', 'highway block',
    'nh-37', 'nh-44', 'nh-2', 'national highway block',
    'railway derail', 'train derail', 'track damage', 'station closed',
    'airport closure', 'flight cancel', 'power outage', 'blackout',
    'grid failure', 'water supply', 'pipeline burst',
    'internet shutdown', 'mobile network down', 'tower attack',
    'dam release', 'hydroelectric', 'subansiri dam', 'tipaimukh',
    'siliguri corridor', "chicken's neck",

    # ============================================================
    # I. FINANCIAL / ECONOMIC
    # ============================================================
    'gst evasion', 'revenue loss', 'budget cut', 'bank fraud', 'scam crore',
    'ponzi', 'chit fund', 'npa', 'loan default', 'msme crisis',
    'industrial shutdown', 'factory close', 'mass layoff',
    'oil refinery', 'numaligarh', 'digboi', 'tea garden', 'tea industry',
    'plantation crisis', 'gi tag', 'export ban', 'fuel price hike',
    'illegal mining', 'coal mining', 'sand mafia', 'stone quarry',

    # ============================================================
    # J. HEALTH / BIOSECURITY
    # ============================================================
    'outbreak', 'epidemic', 'pandemic', 'h5n1', 'bird flu', 'swine flu',
    'encephalitis', 'malaria outbreak', 'dengue', 'cholera', 'measles',
    'african swine fever', 'asf outbreak', 'foot and mouth', 'anthrax',
    'zoonotic', 'quarantine', 'hospital overflow', 'health emergency',

    # ============================================================
    # K. CYBER / INFO OPS
    # ============================================================
    'cyber attack', 'cyberattack', 'ransomware', 'data breach', 'phishing',
    'deepfake', 'disinformation', 'fake news', 'propaganda', 'misinformation',
    'social media ban', 'vpn ban', 'dark web', 'crypto fraud', 'cyber espionage',
    'espionage', 'intelligence agency',

    # ============================================================
    # L. WILDLIFE / ENVIRONMENT (NER-specific security)
    # ============================================================
    'poaching', 'rhino poach', 'tiger poach', 'elephant poach',
    'man-animal conflict', 'illegal logging', 'timber smuggling',
    'kaziranga', 'manas national', 'namdapha', 'dampa sanctuary',
    'oil spill', 'gas leak', 'baghjan', 'river dolphin',

    # ============================================================
    # M. CHINA / GEOPOLITICAL
    # ============================================================
    'china', 'pla china', 'beijing', 'xi jinping', 'tibet', 'lhasa',
    'cpec', 'bri belt road', 'arunachal claim', 'zangnan', 'galwan',
    'pangong', 'g20', 'quad', 'act east', 'kaladan', 'trilateral highway',
    'bangladesh pm', 'hasina', 'yunus', 'myanmar coup', 'min aung hlaing',
    'asean', 'bimstec',

    # ============================================================
    # N. STRATEGIC / GENERAL SECURITY
    # ============================================================
    'nuclear', 'submarine', 'aircraft carrier', 'radar', 'surveillance',
    'drone', 'uav', 'diplomatic', 'sanctions', 'treaty',

    # ============================================================
    # O. NER GEOGRAPHIC (broad accept)
    # ============================================================
    'northeast india', 'north east india', 'north-east india',
    'manipur', 'assam', 'meghalaya', 'mizoram', 'tripura',
    'arunachal', 'nagaland', 'sikkim', 'west bengal',
]

GEO_RELEVANT = [
    # NER states
    'assam', 'meghalaya', 'mizoram', 'manipur', 'arunachal', 'tripura',
    'nagaland', 'sikkim', 'west bengal',
    'northeast india', 'north east india', 'north-east india', 'ner ',
    # NER cities
    'guwahati', 'imphal', 'shillong', 'itanagar', 'agartala', 'aizawl', 'gangtok',
    'dispur', 'dimapur', 'kohima', 'tinsukia', 'dibrugarh', 'silchar', 'tezpur',
    'kokrajhar', 'jorhat', 'churachandpur', 'moreh', 'dawki', 'tawang', 'changlang',
    'tura', 'cherrapunji', 'lunglei', 'champhai',
    # West Bengal / Siliguri corridor
    'siliguri', 'jalpaiguri', 'cooch behar', 'alipurduar', 'darjeeling',
    'kalimpong', 'kurseong', "chicken's neck", 'siliguri corridor', 'terai',
    # Bhutan
    'bhutan', 'thimphu', 'phuentsholing',
    # Bangladesh
    'bangladesh', 'dhaka', 'chittagong', 'sylhet', "cox's bazar", 'rangpur',
    # Myanmar
    'myanmar', 'naypyidaw', 'yangon', 'mandalay', 'rakhine', 'sittwe',
    'chin state', 'sagaing', 'kachin',
    # Tibet/China border zones
    'tibet', 'lhasa',
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

    # RULE 5: NER sources accepted by default (only after passing reject check)
    if source_region in ("ner", "ner "):
        return True, "ner_source"

    # RULE 6: National/international with no signals -> reject
    if source_region in ("india", "international"):
        return False, "no_relevance_signal"

    # RULE 7: Unknown/empty region (bulk backlog items without region metadata).
    # Fail-open: pass to Stage 1 Gemini which can judge relevance semantically.
    # Only pure-reject items (sports/entertainment) are already dead at RULE 1.
    if not source_region:
        return True, "no_region_failopen"

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


async def translate_to_english(text: str, source_lang: str, emergent_key: str = "") -> tuple:
    """
    Translate non-English text to English using Claude.
    Returns: (translated_text, confidence_score 0-100)
    Note: emergent_key parameter kept for backward compatibility but is no longer used.
    """
    if source_lang == "en" or not text or len(text.strip()) < 10:
        return text, 100

    lang_names = {"bn": "Bengali", "hi": "Hindi", "as": "Assamese"}
    lang_name = lang_names.get(source_lang, "Unknown")
    system_prompt = (
        f"You are a precise translator. Translate the following {lang_name} text to English. "
        f"Preserve all proper nouns, place names, organization names, and military terms. "
        f"Return ONLY the translation, nothing else. If text is already English, return as-is."
    )

    try:
        client = get_client()
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": text[:3000]}],
        )
        translated = response.content[0].text.strip()

        english_ratio = len(re.findall(r'[a-zA-Z]', translated)) / max(len(translated), 1)
        confidence = min(100, int(english_ratio * 120))

        if confidence < 50:
            logger.warning(f"Low translation confidence ({confidence}), retrying...")
            response2 = await client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": text[:3000]},
                    {"role": "assistant", "content": translated},
                    {
                        "role": "user",
                        "content": f"Please translate this {lang_name} text to clear English. Output ONLY the English translation:\n\n{text[:2000]}",
                    },
                ],
            )
            translated = response2.content[0].text.strip()
            english_ratio = len(re.findall(r'[a-zA-Z]', translated)) / max(len(translated), 1)
            confidence = min(100, int(english_ratio * 120))

        return translated, confidence

    except Exception as e:
        logger.error(f"Translation failed for {lang_name}: {e}")
        return text, 0


# ============================================================
# FULL FILTER PIPELINE
# ============================================================

async def run_filter_pipeline(article: dict, emergent_key: str = "") -> dict:
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
