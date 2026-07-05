"""
test_periodic_report_v36.py — periodic report upgrade (custom-agent format,
month-on-month comparison, trendline, per-PAOI map, RAS restructure,
NER LoC priority surfacing, Commander's Attention Required).

Pure-function tests — no Mongo connection or LLM calls needed
(motor is lazy; shared.py only needs backend/.env to import).

Run:  cd backend && python -m pytest tests/test_periodic_report_v36.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from paoi_brief import article_matches_pull, select_top_events_for_paoi
from brief_visuals import (
    draw_paoi_map, draw_paoi_trendline, geocode_item, geocode_points,
)
from priority_areas_seed import PRIORITY_AREAS, RAS_PARENT_GROUP
from periodic_report_config import ATTENTION_CONFIG, RAS_LOCATIONS, LOC_PRIORITY_KEYWORDS
from routers.brief_monthly import _detect_attention_items, _category_covered_by_paoi


def _art(title, summary="", **kw):
    return {"title": title, "ai_summary": summary, **kw}


# ── RAS Sub-PAOI location-based filtering ─────────────────────────────────────

class TestRASLocationFiltering:
    def _ras_pull(self):
        pa = next(p for p in PRIORITY_AREAS if p["id"] == "P5_ras_locations")
        kp = pa["keyword_pull"]
        return ([k.lower() for k in kp["keywords"]],
                [k.lower() for k in kp["exclude_keywords"]])

    def test_matches_designated_location(self):
        kws, excl = self._ras_pull()
        assert article_matches_pull(
            _art("Suspicious movement reported near Misamari army station"), kws, excl)

    def test_matches_any_threat_category_at_location(self):
        kws, excl = self._ras_pull()
        assert article_matches_pull(
            _art("Drug seizure in Panitola", "Police recovered narcotics"), kws, excl)

    def test_excludes_highway_stories(self):
        kws, excl = self._ras_pull()
        assert not article_matches_pull(
            _art("Landslide blocks national highway near Jorhat"), kws, excl)

    def test_excludes_railway_stories(self):
        kws, excl = self._ras_pull()
        assert not article_matches_pull(
            _art("Rail line disruption at Jorhat station", "railway track damaged"), kws, excl)

    def test_ignores_unlisted_locations(self):
        kws, excl = self._ras_pull()
        assert not article_matches_pull(
            _art("Protest in Dimapur town center"), kws, excl)

    def test_ras_paois_share_parent_group(self):
        groups = {p["id"]: p.get("parent_group") for p in PRIORITY_AREAS}
        assert groups["P4_meghalaya_internal_security"] == RAS_PARENT_GROUP
        assert groups["P5_ras_locations"] == RAS_PARENT_GROUP
        assert not groups["P3_ner_lines_of_communication"]

    def test_all_seven_locations_covered(self):
        for loc in ["Narangi", "Jorhat", "Misamari", "Likabali",
                    "Panitola", "Masimpur", "Shillong"]:
            assert loc in RAS_LOCATIONS


# ── NER LoC highway/rail priority surfacing ───────────────────────────────────

class TestLoCPrioritySurfacing:
    def test_priority_keyword_boost_surfaces_low_volume_item(self):
        pa = {"geography": ["Assam"], "watch_geography": [],
              "priority_keywords": LOC_PRIORITY_KEYWORDS}
        low_priority_nh = _art(
            "Minor protest disrupts traffic on NH-27 near Nagaon",
            severity="medium", priority_score=30, state="Assam",
            published_at="2026-06-20",
        )
        high_generic = _art(
            "Major flood situation in Assam",
            severity="high", priority_score=85, state="Assam",
            published_at="2026-06-20",
        )
        top = select_top_events_for_paoi(
            [high_generic, low_priority_nh], pa, n=1, period_end="2026-06-30")
        assert top[0]["title"].startswith("Minor protest disrupts traffic on NH-27")

    def test_no_boost_without_priority_keywords(self):
        pa = {"geography": ["Assam"], "watch_geography": []}
        low = _art("Minor protest on NH-27", severity="medium",
                   priority_score=30, state="Assam", published_at="2026-06-20")
        high = _art("Major flood in Assam", severity="high",
                    priority_score=85, state="Assam", published_at="2026-06-20")
        top = select_top_events_for_paoi([high, low], pa, n=1, period_end="2026-06-30")
        assert top[0]["title"] == "Major flood in Assam"

    def test_p3_seed_carries_priority_keywords(self):
        p3 = next(p for p in PRIORITY_AREAS if p["id"] == "P3_ner_lines_of_communication")
        assert "NH-27" in p3["priority_keywords"]
        assert any("Railway" in k or "railway" in k for k in p3["priority_keywords"])


# ── Map marker generation (current vs previous period) ────────────────────────

class TestMapMarkers:
    def test_geocode_prefers_entity_location(self):
        item = {"entities": {"locations": ["Jorhat"]}, "district": "Kamrup",
                "state": "Assam"}
        (lat, lon), label = geocode_item(item)
        assert label == "Jorhat"
        assert abs(lat - 26.747) < 0.01

    def test_geocode_falls_back_to_district_then_state(self):
        item = {"entities": {}, "district": "Churachandpur", "state": "Manipur"}
        (_, _), label = geocode_item(item)
        assert label == "Churachandpur"
        item2 = {"entities": {}, "district": "", "state": "Manipur"}
        (_, _), label2 = geocode_item(item2)
        assert label2 == "Manipur"

    def test_geocode_points_reports_unresolved(self):
        pts, unresolved = geocode_points([
            {"title": "located", "severity": "critical",
             "entities": {"locations": ["Shillong"]}},
            {"title": "nowhere", "severity": "high", "entities": {}},
        ])
        assert len(pts) == 1 and pts[0]["label"] == "Shillong"
        assert len(unresolved) == 1

    def test_draw_map_renders_both_period_layers(self):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        cur = [{"lat": 26.144, "lon": 91.736, "label": "Guwahati",
                "severity": "critical", "title": "x"}]
        prev = [{"lat": 25.574, "lon": 91.882, "label": "Shillong",
                 "severity": "high", "title": "y"}]
        y_after = draw_paoi_map(pdf, cur, prev, 10, 20, unresolved=["z"])
        assert y_after > 20 + 82  # frame + legend + footnote consumed space
        assert bytes(pdf.output())  # renders to valid PDF


# ── Trendline trigger (3+ periods) ────────────────────────────────────────────

class TestTrendline:
    def _series(self, n):
        return [{"label": f"P{i}", "score": 40 + i * 5, "level": "MONITOR"}
                for i in range(n)]

    def test_no_chart_below_two_points(self):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        assert draw_paoi_trendline(pdf, self._series(1), 10, 20) == 20

    def test_chart_renders_at_three_plus(self):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        y_after = draw_paoi_trendline(pdf, self._series(3), 10, 20)
        assert y_after > 20
        assert bytes(pdf.output())

    def test_none_scores_skipped(self):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        series = [{"label": "a", "score": None, "level": ""}] * 3
        assert draw_paoi_trendline(pdf, series, 10, 20) == 20


# ── Commander's Attention Required anomaly detection ──────────────────────────

class TestAttentionRequired:
    def _stats(self, stability=None, cats=None):
        return {"stability": stability or [], "top_categories": cats or []}

    def test_faultline_shift_flagged_at_threshold(self):
        thr = ATTENTION_CONFIG["faultline_delta_threshold"]
        other = {"rising": [{"name": "Test fault", "state": "Manipur",
                             "last": 80, "delta": thr, "level": "CRITICAL"}],
                 "declining": []}
        items = _detect_attention_items(self._stats(), None, [], other)
        assert len(items) == 1
        assert items[0]["type"] == "faultline_shift"
        assert str(int(thr)) in items[0]["numbers"] or f"{thr:+.0f}" in items[0]["numbers"]

    def test_faultline_shift_below_threshold_ignored(self):
        thr = ATTENTION_CONFIG["faultline_delta_threshold"]
        other = {"rising": [{"name": "Small fault", "state": "", "last": 50,
                             "delta": thr - 1, "level": "MONITOR"}], "declining": []}
        assert _detect_attention_items(self._stats(), None, [], other) == []

    def test_stability_swing_flagged(self):
        thr = ATTENTION_CONFIG["stability_delta_threshold"]
        stats = self._stats(stability=[{"state": "Tripura", "score": 40, "level": "MONITOR"}])
        prev = self._stats(stability=[{"state": "Tripura", "score": 40 + thr, "level": "STABLE"}])
        items = _detect_attention_items(stats, prev, [], {"rising": [], "declining": []})
        assert len(items) == 1
        assert items[0]["type"] == "stability_shift"
        assert "Tripura" in items[0]["headline"]

    def test_category_spike_flagged_and_paoi_covered_excluded(self):
        cfg_ratio = ATTENTION_CONFIG["category_spike_ratio"]
        min_cnt = ATTENTION_CONFIG["category_spike_min_count"]
        spike = max(min_cnt, int(10 * cfg_ratio) + 1)
        stats = self._stats(cats=[["Cyber Threats", spike], ["Border Tension", spike]])
        baselines = [[["Cyber Threats", 10], ["Border Tension", 10]]]
        items = _detect_attention_items(stats, None, baselines,
                                        {"rising": [], "declining": []})
        types = [(i["type"], i["headline"]) for i in items]
        assert any("Cyber Threats" in h for _, h in types)
        # "Border Tension" overlaps the "India-Bangladesh Border" PAOI name → excluded
        assert not any("Border Tension" in h for _, h in types)

    def test_max_items_cap(self):
        thr = ATTENTION_CONFIG["faultline_delta_threshold"]
        other = {"rising": [
            {"name": f"F{i}", "state": "", "last": 80, "delta": thr + i, "level": "CRITICAL"}
            for i in range(8)
        ], "declining": []}
        items = _detect_attention_items(self._stats(), None, [], other)
        assert len(items) <= ATTENTION_CONFIG["max_items"]

    def test_deterministic_no_llm_fields(self):
        other = {"rising": [{"name": "F", "state": "", "last": 80,
                             "delta": 30, "level": "CRITICAL"}], "declining": []}
        item = _detect_attention_items(self._stats(), None, [], other)[0]
        assert set(item.keys()) == {"type", "headline", "significance", "numbers"}

    def test_category_covered_by_paoi_word_overlap(self):
        assert _category_covered_by_paoi("Border Tension")
        assert not _category_covered_by_paoi("Cyber Threats")


# ── PAOI month-on-month diffing (via full render) ─────────────────────────────

class TestPeriodComparisonRender:
    def _brief(self):
        return {
            "year": 2026, "month": 6, "status": "ready",
            "generated_at": "2026-07-01T00:00:00",
            "stats": {"total": 10, "sev_counts": {}, "cross_border_count": 0,
                      "stability": [], "states": {}, "top_actors": [],
                      "top_locations": [], "top_categories": [], "daily_severity": []},
            "executive_summary": "x", "state_sections": {},
            "mitigation_playbook": {}, "scenarios": [],
            "cross_border_analysis": {}, "faultline_analysis": {"available": False},
            "attention_required": [
                {"type": "stability_shift", "headline": "Tripura swing",
                 "significance": "sig", "numbers": "71 -> 47"}],
            "paoi_analysis": {
                "available": True,
                "commander_dashboard": [],
                "paois": [{
                    "id": "P1_india_bangladesh_border", "rank": 1,
                    "name": "India-Bangladesh Border", "parent_group": "",
                    "faultline_movement": {"level": "CRITICAL", "delta": -4.6,
                                           "last": 78.0, "n_faultlines": 1,
                                           "dominant": None, "per_faultline": []},
                    "keyword_hits": {"n_articles": 1, "top_articles": []},
                }],
                "synthesis": {"tier": "rich", "per_paoi": {
                    "P1_india_bangladesh_border": {
                        "situation_overview": "Overview [CONFIRMED].",
                        "critical_developments": [],
                        "overall_assessment": "Assessment [ASSESSED].",
                        "risk_trajectory": "STABLE",
                        "actionable_recommendations": [],
                        "next_period_watch": [],
                    }}, "overall": {}},
                "map_points": {},
            },
        }

    def test_prev_period_diff_appears_in_pdf(self):
        from routers.brief_monthly import _render_pdf
        prev_brief = {
            "year": 2026, "month": 5, "stats": {"stability": [], "sev_counts": {}},
            "executive_summary": "",
            "paoi_analysis": {"commander_dashboard": [
                {"id": "P1_india_bangladesh_border", "score": 82.6, "level": "ELEVATED"},
            ]},
        }
        pdf_bytes = _render_pdf(self._brief(), prev_brief=prev_brief)
        import io
        from PyPDF2 import PdfReader
        text = " ".join(pg.extract_text() for pg in PdfReader(io.BytesIO(pdf_bytes)).pages)
        assert "PERIOD COMPARISON" in text
        assert "ELEVATED (83)" in text          # previous level + score
        assert "CRITICAL (78)" in text          # current level + score
        assert "FL delta -4.6" in text
        assert "COMMANDER'S ATTENTION REQUIRED" in text
        # amended ordering: attention section comes AFTER the deep dives
        assert text.index("PRIORITY AREA DEEP DIVES") < text.index("COMMANDER'S ATTENTION REQUIRED")

    def test_render_without_history_or_prev(self):
        from routers.brief_monthly import _render_pdf
        assert bytes(_render_pdf(self._brief()))


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
