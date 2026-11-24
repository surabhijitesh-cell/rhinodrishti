"""Army image: incidents that affect how the public sees the Army are relevant
even with no security angle (Rohit, Nov 2026). Negative stories in the AOR
reach High; positive stories are kept but at a lower level."""
from intelligence_filter import has_keyword

ARMY_IMAGE_TAG = "Army Image"
# The commander's area of responsibility (fixed by decision, not a setting).
AOR_PLACES = ("jorhat", "narangi", "narengi", "shillong")

ARMY_TERMS = ("army", "jawan", "jawans", "soldier", "soldiers", "military", "armed forces",
              "assam rifles", "cantonment", "army vehicle", "army truck", "army officer", "defence personnel")
CIVIL_TERMS = ("police", "traffic", "challan", "villagers", "locals", "residents", "protest", "viral",
               "video", "accident", "court", "land", "dispute", "scuffle", "assault", "misbehave",
               "harass", "complaint", "fir", "students", "civilian", "civilians", "public", "driver")

NEGATIVE_AOR_FLOOR = 60      # High
NEGATIVE_NER_FLOOR = 40      # Medium
POSITIVE_CEILING = 55        # never above Medium
POSITIVE_AOR_FLOOR = 40      # Medium in the AOR


def mentions_army_and_civilians(text: str) -> bool:
    t = (text or "").lower()
    return has_keyword(t, ARMY_TERMS) and has_keyword(t, CIVIL_TERMS)


def in_aor(text: str) -> bool:
    return has_keyword((text or "").lower(), AOR_PLACES)


def apply_army_image(score: int, army_image, text: str) -> tuple:
    """(score, is_army_image) after the Army-image floors and ceiling."""
    kind = (army_image or "").strip().lower() if isinstance(army_image, str) else ""
    if kind not in ("negative", "positive"):
        return score, False
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = 30
    aor = in_aor(text)
    if kind == "negative":
        score = max(score, NEGATIVE_AOR_FLOOR if aor else NEGATIVE_NER_FLOOR)
    else:
        score = min(score, POSITIVE_CEILING)
        if aor:
            score = max(score, POSITIVE_AOR_FLOOR)
    return score, True
