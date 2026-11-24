"""Army-image stories: always relevant; negative ones in the AOR reach High. Pure logic."""
from army_image import apply_army_image, in_aor, mentions_army_and_civilians
from relevance_filter import is_regional_language  # noqa: F401  (module import check)

CHALLAN = "Assam army vehicle row: can traffic police challan military drivers? Incident near Narangi, Guwahati"


def test_negative_story_in_aor_is_at_least_high():
    assert apply_army_image(20, "negative", CHALLAN) == (60, True)
    assert apply_army_image(70, "negative", "Jorhat: villagers protest against army") == (70, True)


def test_negative_story_elsewhere_is_at_least_medium():
    assert apply_army_image(10, "negative", "Army truck accident in Kohima") == (40, True)


def test_positive_story_never_above_medium():
    assert apply_army_image(90, "positive", "Army rescues flood victims in Dhemaji") == (55, True)
    assert apply_army_image(20, "positive", "Army medical camp in Shillong") == (40, True)


def test_ordinary_story_untouched():
    assert apply_army_image(33, None, CHALLAN) == (33, False)
    assert apply_army_image(33, "null", CHALLAN) == (33, False)


def test_aor_and_army_civil_detection():
    assert in_aor("NARENGI cantonment") and not in_aor("Dibrugarh market")
    assert mentions_army_and_civilians(CHALLAN)
    assert not mentions_army_and_civilians("Army chief visits forward posts")


def test_army_civil_story_skips_the_similarity_filter(monkeypatch):
    import asyncio
    import relevance_filter as rf

    async def centroid(db):
        return [1.0]

    async def no_embed(text):
        raise AssertionError("should not be embedded")

    monkeypatch.setattr(rf, "_ensure_centroid", centroid)
    monkeypatch.setattr(rf, "generate_embedding", no_embed)
    res = asyncio.run(rf.is_semantically_relevant({"title": CHALLAN}, None))
    assert res["relevant"] is True and res["reason"] == "army_image"
