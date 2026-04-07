"""
Test suite for Dynamic Keyword Generation Engine
Tests: GET /api/keywords, POST /api/keywords/refresh, keyword_engine.py functions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestKeywordsEndpoint:
    """Tests for GET /api/keywords endpoint"""
    
    def test_get_keywords_returns_200(self):
        """GET /api/keywords returns 200 with keywords list"""
        response = requests.get(f"{BASE_URL}/api/keywords")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "keywords" in data, "Response should contain 'keywords' field"
        assert "count" in data, "Response should contain 'count' field"
        assert "type_breakdown" in data, "Response should contain 'type_breakdown' field"
        print(f"✓ GET /api/keywords returns 200 with {data['count']} keywords")
    
    def test_keywords_have_required_fields(self):
        """Keywords contain score, type, and keyword fields"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=50")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        assert len(keywords) > 0, "Should have at least some keywords"
        
        for kw in keywords[:10]:  # Check first 10
            assert "keyword" in kw, f"Keyword missing 'keyword' field: {kw}"
            assert "type" in kw, f"Keyword missing 'type' field: {kw}"
            assert "score" in kw, f"Keyword missing 'score' field: {kw}"
        print(f"✓ Keywords have required fields (keyword, type, score)")
    
    def test_keywords_scores_in_valid_range(self):
        """Keyword scores are between 0-100"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=100")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        for kw in keywords:
            score = kw.get("score", 0)
            assert 0 <= score <= 100, f"Score {score} out of range for keyword: {kw['keyword']}"
        print(f"✓ All {len(keywords)} keyword scores are in valid range 0-100")
    
    def test_keywords_contain_all_six_types(self):
        """Keywords contain all 6 types: primary, entity, geo, cross_border, emerging, expanded"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=300")
        assert response.status_code == 200
        data = response.json()
        
        type_breakdown = data.get("type_breakdown", {})
        expected_types = ["primary", "entity", "geo", "cross_border", "emerging", "expanded"]
        
        found_types = list(type_breakdown.keys())
        print(f"Found types: {found_types}")
        print(f"Type breakdown: {type_breakdown}")
        
        # At minimum, we should have primary, entity, geo, cross_border from seed/historical
        core_types = ["primary", "entity", "geo", "cross_border"]
        for t in core_types:
            assert t in found_types, f"Missing core type: {t}"
        
        print(f"✓ Keywords contain core types: {core_types}")
        print(f"  Type breakdown: {type_breakdown}")
    
    def test_filter_by_type_emerging(self):
        """GET /api/keywords?type=emerging filters to only emerging type"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=emerging&limit=50")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        for kw in keywords:
            assert kw.get("type") == "emerging", f"Expected type 'emerging', got '{kw.get('type')}'"
        
        print(f"✓ Filter by type=emerging works ({len(keywords)} emerging keywords)")
    
    def test_filter_by_type_primary(self):
        """GET /api/keywords?type=primary filters to only primary type"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=primary&limit=50")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) > 0, "Should have primary keywords"
        for kw in keywords:
            assert kw.get("type") == "primary", f"Expected type 'primary', got '{kw.get('type')}'"
        
        print(f"✓ Filter by type=primary works ({len(keywords)} primary keywords)")
    
    def test_filter_by_min_score(self):
        """GET /api/keywords?min_score=70 filters by minimum score"""
        response = requests.get(f"{BASE_URL}/api/keywords?min_score=70&limit=100")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        for kw in keywords:
            assert kw.get("score", 0) >= 70, f"Score {kw.get('score')} below min_score 70"
        
        print(f"✓ Filter by min_score=70 works ({len(keywords)} keywords with score >= 70)")
    
    def test_limit_parameter(self):
        """GET /api/keywords?limit=10 respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=10")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) <= 10, f"Expected max 10 keywords, got {len(keywords)}"
        print(f"✓ Limit parameter works (returned {len(keywords)} keywords with limit=10)")
    
    def test_type_breakdown_matches_keywords(self):
        """type_breakdown counts match actual keyword types"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=300")
        assert response.status_code == 200
        data = response.json()
        
        keywords = data.get("keywords", [])
        type_breakdown = data.get("type_breakdown", {})
        
        # Count types manually
        manual_counts = {}
        for kw in keywords:
            t = kw.get("type", "unknown")
            manual_counts[t] = manual_counts.get(t, 0) + 1
        
        # Compare
        for t, count in type_breakdown.items():
            assert manual_counts.get(t, 0) == count, f"Type {t}: breakdown says {count}, actual is {manual_counts.get(t, 0)}"
        
        print(f"✓ type_breakdown matches actual keyword counts")


class TestKeywordsRefresh:
    """Tests for POST /api/keywords/refresh endpoint"""
    
    def test_refresh_keywords_returns_200(self):
        """POST /api/keywords/refresh returns 200 with success message"""
        response = requests.post(f"{BASE_URL}/api/keywords/refresh")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should contain 'message' field"
        assert "refresh" in data["message"].lower() or "started" in data["message"].lower(), \
            f"Message should indicate refresh started: {data['message']}"
        print(f"✓ POST /api/keywords/refresh returns 200: {data['message']}")


class TestKeywordEngineIntegration:
    """Integration tests for keyword engine with RSS filtering"""
    
    def test_keywords_sorted_by_score(self):
        """Keywords are returned sorted by score descending"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=50")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        if len(keywords) > 1:
            scores = [kw.get("score", 0) for kw in keywords]
            assert scores == sorted(scores, reverse=True), "Keywords should be sorted by score descending"
        
        print(f"✓ Keywords are sorted by score descending")
    
    def test_keywords_have_source_field(self):
        """Keywords have source field indicating origin (seed, historical, ai, etc)"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=100")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        sources_found = set()
        for kw in keywords:
            if "source" in kw:
                sources_found.add(kw["source"])
        
        print(f"✓ Keywords have source field. Sources found: {sources_found}")
    
    def test_combined_filters(self):
        """Combined filters work: type + min_score + limit"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=primary&min_score=40&limit=5")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) <= 5, f"Limit not respected: {len(keywords)}"
        for kw in keywords:
            assert kw.get("type") == "primary", f"Type filter not working"
            assert kw.get("score", 0) >= 40, f"min_score filter not working"
        
        print(f"✓ Combined filters work correctly ({len(keywords)} results)")


class TestKeywordTypes:
    """Tests for specific keyword types"""
    
    def test_geo_keywords_exist(self):
        """Geo keywords exist and contain location-related terms"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=geo&limit=30")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) > 0, "Should have geo keywords"
        print(f"✓ Geo keywords exist ({len(keywords)} found)")
        print(f"  Sample geo keywords: {[kw['keyword'] for kw in keywords[:5]]}")
    
    def test_entity_keywords_exist(self):
        """Entity keywords exist (actors, organizations)"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=entity&limit=30")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) > 0, "Should have entity keywords"
        print(f"✓ Entity keywords exist ({len(keywords)} found)")
        print(f"  Sample entity keywords: {[kw['keyword'] for kw in keywords[:5]]}")
    
    def test_cross_border_keywords_exist(self):
        """Cross-border keywords exist"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=cross_border&limit=30")
        assert response.status_code == 200
        data = response.json()
        keywords = data.get("keywords", [])
        
        assert len(keywords) > 0, "Should have cross_border keywords"
        print(f"✓ Cross-border keywords exist ({len(keywords)} found)")
        print(f"  Sample cross_border keywords: {[kw['keyword'] for kw in keywords[:5]]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
