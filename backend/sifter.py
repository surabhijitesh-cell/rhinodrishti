"""
Level 1 "Sifter" Agent — Lightweight pre-filter for high-priority intelligence triggers.

Quickly identifies items requiring deep Level 2 analysis vs routine classification.
Designed to be FAST with zero LLM calls — pure rule-based pattern matching.
"""
import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# HIGH-PRIORITY TRIGGER CATEGORIES
# ============================================================

BORDER_INSTABILITY_TRIGGERS = [
    'drone', 'uav', 'unmanned aerial', 'quadcopter',
    'border firing', 'border breach', 'border violation', 'infiltration',
    'bsf firing', 'bgb firing', 'border skirmish',
    'mizoram border', 'myanmar border', 'manipur border', 'arunachal border',
    'moreh', 'champhai', 'zokhawthar', 'dawki', 'sutarkandi',
    'border fence', 'fence cutting', 'border patrol', 'border alert',
    'fencing breach', 'cross-border firing', 'unprovoked firing',
    'loc violation', 'ceasefire violation',
]

INFRASTRUCTURE_TRIGGERS = [
    'radar installation', 'radar station', 'surveillance radar',
    'rail line', 'railway', 'rail project', 'railway bridge',
    'airstrip', 'airfield', 'air base', 'helipad',
    'road construction', 'highway', 'border road', 'bro ',
    'bridge construction', 'river bridge', 'brahmaputra bridge',
    'strategic tunnel', 'tunnel project',
    'telecom tower', 'signal station', 'communication relay',
]

REFUGEE_MOVEMENT_TRIGGERS = [
    'refugee', 'displaced', 'exodus', 'mass migration',
    'rohingya', 'rohingya influx', 'refugee camp',
    'illegal crossing', 'illegal immigrant', 'push back',
    'deportation', 'detention camp', 'foreigner tribunal',
    'border crossing', 'influx', 'undocumented migrant',
    'nrc ', 'national register', 'citizenship',
]

MILITARY_TRIGGERS = [
    'military deployment', 'troop movement', 'army movement',
    'assam rifles', 'crpf deployment', 'bsf alert',
    'afspa', 'operation launch', 'combing operation',
    'encounter', 'gunfight', 'ambush', 'exchange of fire',
    'ied ', 'improvised explosive', 'bomb blast', 'grenade attack',
    'arms recovery', 'arms cache', 'weapons seizure',
    'ceasefire', 'surrender', 'militant arrest',
    'pla ', 'tatmadaw', 'chinese military', 'pakistan isi',
]

INSURGENCY_TRIGGERS = [
    'ulfa', 'nscn', 'hnlc', 'nlft', 'pla ', 'knf',
    'corcom', 'meitei', 'kuki', 'naga', 'bodo',
    'insurgent', 'militant', 'separatist', 'extremist',
    'underground group', 'banned outfit', 'proscribed',
    'ethnic clash', 'tribal conflict', 'communal violence',
    'curfew', 'internet shutdown', 'bandh',
]

CHINA_PAKISTAN_TRIGGERS = [
    'china', 'chinese', 'beijing', 'pla ', 'lac ',
    'pakistan', 'isi ', 'rawalpindi',
    'belt and road', 'bri ', 'cpec',
    'south china sea', 'quad',
    'dalai lama', 'tibet', 'arunachal claim',
]

# Combine all triggers for fast lookup
ALL_TRIGGERS = {
    'border_instability': BORDER_INSTABILITY_TRIGGERS,
    'infrastructure': INFRASTRUCTURE_TRIGGERS,
    'refugee_movement': REFUGEE_MOVEMENT_TRIGGERS,
    'military_activity': MILITARY_TRIGGERS,
    'insurgency': INSURGENCY_TRIGGERS,
    'china_pakistan': CHINA_PAKISTAN_TRIGGERS,
}


def sift_article(article: dict) -> dict:
    """
    Level 1 Sifter: Fast rule-based pre-filter.
    
    Returns:
        {
            "level": 2 (deep analysis) or 1 (routine),
            "triggers": ["border_instability", ...],
            "matched_keywords": ["drone", "mizoram border", ...],
            "boost_score": int (added to priority_score)
        }
    """
    title = (article.get("title", "") or "").lower()
    content = (article.get("raw_content", "") or article.get("description", "") or "").lower()[:1000]
    source = (article.get("source", "") or "").lower()
    text = f"{title} {content}"
    
    triggers_found = []
    matched_keywords = []
    boost = 0
    
    for category, keywords in ALL_TRIGGERS.items():
        for kw in keywords:
            if kw in text:
                if category not in triggers_found:
                    triggers_found.append(category)
                if kw not in matched_keywords:
                    matched_keywords.append(kw)
    
    # Calculate boost score
    if 'china_pakistan' in triggers_found:
        boost += 15
    if 'military_activity' in triggers_found:
        boost += 10
    if 'border_instability' in triggers_found:
        boost += 12
    if 'refugee_movement' in triggers_found:
        boost += 8
    if 'insurgency' in triggers_found:
        boost += 10
    if 'infrastructure' in triggers_found:
        boost += 5
    
    # Multiple trigger categories = higher priority
    if len(triggers_found) >= 3:
        boost += 10
    elif len(triggers_found) >= 2:
        boost += 5
    
    # Grassroots source boost
    grassroots = ['ukhrul times', 'morung express', 'sangai express', 'northeast now',
                  'eastern mirror', 'nagaland post', 'shillong times', 'imphal free press']
    if any(g in source for g in grassroots):
        boost += 3
    
    level = 2 if triggers_found else 1
    
    if triggers_found:
        logger.info(f"Sifter L2: {title[:50]} — triggers={triggers_found}")
    
    return {
        "level": level,
        "triggers": triggers_found,
        "matched_keywords": matched_keywords[:10],
        "boost_score": boost,
    }
