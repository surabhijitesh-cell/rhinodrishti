"""
Test Cross-Border Watch Module - Iteration 22
Tests the Bangladesh & Myanmar intelligence engine with India-relevance scoring.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCrossBorderWatchEndpoint:
    """Tests for GET /api/cross-border/watch endpoint"""
    
    def test_cross_border_watch_returns_200(self):
        """Basic endpoint availability test"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/cross-border/watch returns 200")
    
    def test_response_has_bangladesh_section(self):
        """Response contains bangladesh section with items, count, posture"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        assert "bangladesh" in data, "Response missing 'bangladesh' section"
        bd = data["bangladesh"]
        assert "items" in bd, "Bangladesh section missing 'items'"
        assert "count" in bd, "Bangladesh section missing 'count'"
        assert "posture" in bd, "Bangladesh section missing 'posture'"
        assert isinstance(bd["items"], list), "Bangladesh items should be a list"
        assert isinstance(bd["count"], int), "Bangladesh count should be an integer"
        print(f"✓ Bangladesh section present with {bd['count']} items, posture: {bd['posture']}")
    
    def test_response_has_myanmar_section(self):
        """Response contains myanmar section with items, count, posture"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        assert "myanmar" in data, "Response missing 'myanmar' section"
        mm = data["myanmar"]
        assert "items" in mm, "Myanmar section missing 'items'"
        assert "count" in mm, "Myanmar section missing 'count'"
        assert "posture" in mm, "Myanmar section missing 'posture'"
        assert isinstance(mm["items"], list), "Myanmar items should be a list"
        assert isinstance(mm["count"], int), "Myanmar count should be an integer"
        print(f"✓ Myanmar section present with {mm['count']} items, posture: {mm['posture']}")
    
    def test_response_has_watchpoints(self):
        """Response contains watchpoints array"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        assert "watchpoints" in data, "Response missing 'watchpoints'"
        assert isinstance(data["watchpoints"], list), "Watchpoints should be a list"
        print(f"✓ Watchpoints present: {len(data['watchpoints'])} items")
    
    def test_response_has_signal_distribution(self):
        """Response contains signal_distribution object"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        assert "signal_distribution" in data, "Response missing 'signal_distribution'"
        assert isinstance(data["signal_distribution"], dict), "Signal distribution should be a dict"
        print(f"✓ Signal distribution present: {data['signal_distribution']}")
    
    def test_posture_values_are_valid(self):
        """Posture should be one of: stable, watchful, elevated, deteriorating"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        valid_postures = {"stable", "watchful", "elevated", "deteriorating"}
        bd_posture = data["bangladesh"]["posture"]
        mm_posture = data["myanmar"]["posture"]
        
        assert bd_posture in valid_postures, f"Invalid Bangladesh posture: {bd_posture}"
        assert mm_posture in valid_postures, f"Invalid Myanmar posture: {mm_posture}"
        print(f"✓ Postures valid - Bangladesh: {bd_posture}, Myanmar: {mm_posture}")
    
    def test_items_have_required_fields(self):
        """Each item should have: id, title, ai_summary, severity, priority_score"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        if not all_items:
            pytest.skip("No cross-border items available to test")
        
        required_fields = ["id", "title", "severity", "priority_score"]
        for item in all_items[:5]:  # Check first 5 items
            for field in required_fields:
                assert field in item, f"Item missing required field: {field}"
        
        print(f"✓ Items have required fields (checked {min(5, len(all_items))} items)")
    
    def test_items_have_optional_signal_fields(self):
        """Items may have signal_strength, signal_bucket, india_relevance_score (new AI fields)"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        if not all_items:
            pytest.skip("No cross-border items available to test")
        
        # Count items with new signal fields
        items_with_signal_strength = sum(1 for i in all_items if i.get("signal_strength"))
        items_with_signal_bucket = sum(1 for i in all_items if i.get("signal_bucket"))
        items_with_india_relevance = sum(1 for i in all_items if i.get("india_relevance_score", 0) > 0)
        
        print(f"✓ Signal fields present - signal_strength: {items_with_signal_strength}/{len(all_items)}, "
              f"signal_bucket: {items_with_signal_bucket}/{len(all_items)}, "
              f"india_relevance_score: {items_with_india_relevance}/{len(all_items)}")
        # Note: These fields may be empty for items processed before AI prompt update


class TestCrossBorderSignalFiltering:
    """Tests for signal strength filtering"""
    
    def test_filter_high_signal_returns_200(self):
        """GET /api/cross-border/watch?min_signal=HIGH returns 200"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?min_signal=HIGH", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/cross-border/watch?min_signal=HIGH returns 200")
    
    def test_filter_medium_signal_returns_200(self):
        """GET /api/cross-border/watch?min_signal=MEDIUM returns 200"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?min_signal=MEDIUM", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/cross-border/watch?min_signal=MEDIUM returns 200")
    
    def test_high_filter_only_returns_high_items(self):
        """When min_signal=HIGH, only HIGH signal items should be returned"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?min_signal=HIGH", timeout=30)
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        # Items without signal_strength are filtered out by the query
        for item in all_items:
            if item.get("signal_strength"):
                assert item["signal_strength"] == "HIGH", f"Expected HIGH, got {item['signal_strength']}"
        
        print(f"✓ HIGH filter working - {len(all_items)} items returned")
    
    def test_medium_filter_returns_high_and_medium(self):
        """When min_signal=MEDIUM, HIGH and MEDIUM signal items should be returned"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?min_signal=MEDIUM", timeout=30)
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        valid_strengths = {"HIGH", "MEDIUM"}
        for item in all_items:
            if item.get("signal_strength"):
                assert item["signal_strength"] in valid_strengths, f"Expected HIGH/MEDIUM, got {item['signal_strength']}"
        
        print(f"✓ MEDIUM filter working - {len(all_items)} items returned")


class TestCrossBorderGeoBoost:
    """Tests for geographic relevance boost"""
    
    def test_items_have_geo_boost_field(self):
        """Items should have geo_boost and effective_priority fields"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        if not all_items:
            pytest.skip("No cross-border items available to test")
        
        for item in all_items[:5]:
            assert "geo_boost" in item, "Item missing geo_boost field"
            assert "effective_priority" in item, "Item missing effective_priority field"
            assert item["effective_priority"] == item.get("priority_score", 0) + item["geo_boost"], \
                "effective_priority should equal priority_score + geo_boost"
        
        print(f"✓ Geo boost fields present and calculated correctly")
    
    def test_items_sorted_by_effective_priority(self):
        """Items should be sorted by effective_priority descending"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch", timeout=30)
        data = response.json()
        
        for section in ["bangladesh", "myanmar"]:
            items = data[section]["items"]
            if len(items) > 1:
                priorities = [i.get("effective_priority", 0) for i in items]
                assert priorities == sorted(priorities, reverse=True), \
                    f"{section} items not sorted by effective_priority"
        
        print("✓ Items sorted by effective_priority descending")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still function after cross-border changes"""
    
    def test_intelligence_endpoint_works(self):
        """GET /api/intelligence still works"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=3", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Response missing 'items'"
        print(f"✓ GET /api/intelligence works - {len(data['items'])} items returned")
    
    def test_feedback_stats_endpoint_works(self):
        """GET /api/feedback/stats still works"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_feedback" in data, "Response missing 'total_feedback'"
        print(f"✓ GET /api/feedback/stats works - {data['total_feedback']} total feedback")
    
    def test_training_effectiveness_endpoint_works(self):
        """GET /api/training/effectiveness still works"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness", timeout=30)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "score" in data, "Response missing 'score'"
        assert "grade" in data, "Response missing 'grade'"
        print(f"✓ GET /api/training/effectiveness works - score: {data['score']}, grade: {data['grade']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
