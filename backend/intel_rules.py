"""Shared meanings used by faultlines, trends and Cross-Border Watch."""
from intelligence_filter import has_keyword

NORTH_BENGAL_REGION = "West Bengal / Siliguri Corridor"
NORTH_BENGAL_TERMS = (
    "north bengal", "siliguri", "chicken's neck", "chickens neck", "bagdogra",
    "naxalbari", "jalpaiguri", "alipurduar", "cooch behar", "coochbehar",
    "koch bihar", "darjeeling", "kalimpong", "kurseong", "dooars", "duars",
    "terai", "malda", "uttar dinajpur", "dakshin dinajpur", "islampur",
    "changrabandha", "phulbari", "jaldhaka", "teesta",
)

CROSS_BORDER_COUNTRIES = ("Bangladesh", "Myanmar", "China", "Bhutan", "Nepal")


def concerns_north_bengal(item: dict) -> bool:
    """A West Bengal item counts only when it names North Bengal or the corridor."""
    entities = item.get("entities") or {}
    locations = entities.get("locations") if isinstance(entities, dict) else None
    text = " ".join([
        str(item.get("title") or ""), str(item.get("ai_summary") or ""),
        " ".join(str(x) for x in (locations or [])),
    ]).lower().replace("’", "'")
    return has_keyword(text, NORTH_BENGAL_TERMS)


def faultline_regions(item: dict) -> set:
    """Regions used to match an item to faultlines.

    The classifier stores "West Bengal"; North Bengal faultlines look for
    NORTH_BENGAL_REGION, so relevant West Bengal items get that region too.
    """
    regions = {r for r in (item.get("regions") or []) if isinstance(r, str)}
    if item.get("state"):
        regions.add(item["state"])
    if "West Bengal" in regions and concerns_north_bengal(item):
        regions.add(NORTH_BENGAL_REGION)
    return regions


def is_cross_border_item(item: dict) -> bool:
    countries = item.get("countries_involved") or []
    return bool(
        item.get("is_cross_border") is True
        or item.get("state") in CROSS_BORDER_COUNTRIES
        or set(countries) & set(CROSS_BORDER_COUNTRIES)
    )


def cross_border_query() -> dict:
    """The same rule as is_cross_border_item, for database queries."""
    return {"$or": [
        {"is_cross_border": True},
        {"state": {"$in": list(CROSS_BORDER_COUNTRIES)}},
        {"countries_involved": {"$in": list(CROSS_BORDER_COUNTRIES)}},
    ]}
