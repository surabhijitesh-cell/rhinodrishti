"""Shared North Bengal and cross-border rules. Pure logic only."""
from intel_rules import (
    NORTH_BENGAL_REGION, cross_border_query, faultline_regions, is_cross_border_item,
)


def test_west_bengal_item_about_siliguri_reaches_north_bengal():
    item = {"state": "West Bengal", "title": "Army movement near Siliguri Corridor"}
    assert NORTH_BENGAL_REGION in faultline_regions(item)


def test_place_named_only_in_entities_counts():
    item = {"regions": ["West Bengal"], "entities": {"locations": ["Cooch Behar"]}}
    assert NORTH_BENGAL_REGION in faultline_regions(item)


def test_kolkata_story_does_not_reach_north_bengal():
    item = {"state": "West Bengal", "title": "Kolkata civic poll dispute"}
    assert NORTH_BENGAL_REGION not in faultline_regions(item)


def test_other_state_naming_siliguri_keeps_its_own_regions():
    item = {"state": "Assam", "title": "Bus from Guwahati to Siliguri"}
    assert faultline_regions(item) == {"Assam"}


def test_odd_stored_values_do_not_crash():
    assert faultline_regions({"regions": None, "entities": None, "state": None}) == set()


def test_cross_border_has_one_meaning():
    assert is_cross_border_item({"is_cross_border": True})
    assert is_cross_border_item({"state": "Myanmar"})
    assert is_cross_border_item({"countries_involved": ["India", "China"]})
    assert not is_cross_border_item({"state": "Assam", "countries_involved": ["India"]})
    assert len(cross_border_query()["$or"]) == 3
