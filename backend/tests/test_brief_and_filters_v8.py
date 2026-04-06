"""
Test Suite for Iteration 8: Daily Brief Enhancements & Intelligence Feed Filters
Tests:
1. Daily Brief - No twitter_highlights field
2. Daily Brief - Contains pattern_insights array
3. Daily Brief - Contains included_item_ids for cross-brief dedup
4. POST /api/generate-brief - Triggers brief regeneration
5. Intelligence Feed - min_priority filter
6. Intelligence Feed - sort_by priority_score
7. Intelligence Feed - sort_order asc/desc
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDailyBriefEnhancements:
    """Tests for Daily Brief new features: no twitter, pattern insights, dedup tracking"""
    
    def test_daily_brief_no_twitter_highlights(self):
        """Daily brief should NOT contain twitter_highlights field"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "twitter_highlights" not in data, "twitter_highlights field should NOT exist in brief"
        print("PASS: Daily brief does not contain twitter_highlights")
    
    def test_daily_brief_has_pattern_insights(self):
        """Daily brief should contain pattern_insights array"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        assert "pattern_insights" in data, "pattern_insights field should exist"
        assert isinstance(data["pattern_insights"], list), "pattern_insights should be a list"
        print(f"PASS: Daily brief has pattern_insights array with {len(data['pattern_insights'])} items")
    
    def test_daily_brief_pattern_insights_structure(self):
        """Pattern insights should have required fields including escalation_risk"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        patterns = data.get("pattern_insights", [])
        
        if len(patterns) > 0:
            p = patterns[0]
            # Check required fields
            assert "region" in p, "Pattern should have region"
            assert "escalation_risk" in p, "Pattern should have escalation_risk"
            assert "event_count" in p, "Pattern should have event_count"
            
            # Validate escalation_risk values
            valid_risks = ["CRITICAL", "HIGH", "MODERATE", "LOW"]
            assert p["escalation_risk"] in valid_risks, f"Invalid escalation_risk: {p['escalation_risk']}"
            print(f"PASS: Pattern insight has valid structure with escalation_risk={p['escalation_risk']}")
        else:
            print("SKIP: No pattern insights to validate structure")
    
    def test_daily_brief_has_included_item_ids(self):
        """Daily brief should contain included_item_ids for cross-brief dedup tracking"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        assert "included_item_ids" in data, "included_item_ids field should exist"
        assert isinstance(data["included_item_ids"], list), "included_item_ids should be a list"
        print(f"PASS: Daily brief has included_item_ids array with {len(data['included_item_ids'])} IDs")
    
    def test_generate_brief_endpoint(self):
        """POST /api/generate-brief should trigger brief regeneration"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "date" in data, "Response should have date"
        assert "Brief generation started" in data["message"], f"Unexpected message: {data['message']}"
        print(f"PASS: Generate brief endpoint works, date={data['date']}")


class TestIntelligenceFeedFilters:
    """Tests for Intelligence Feed priority filter and sorting"""
    
    def test_min_priority_filter_60(self):
        """Filter with min_priority=60 should return only items with priority >= 60"""
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=60&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        # All items should have priority_score >= 60
        for item in items:
            priority = item.get("priority_score", 0)
            assert priority >= 60, f"Item has priority {priority}, expected >= 60"
        
        print(f"PASS: min_priority=60 filter works, {len(items)} items returned, all >= 60")
    
    def test_min_priority_filter_80(self):
        """Filter with min_priority=80 should return only items with priority >= 80"""
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=80&limit=50")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        total = data.get("total", 0)
        
        # All items should have priority_score >= 80
        for item in items:
            priority = item.get("priority_score", 0)
            assert priority >= 80, f"Item has priority {priority}, expected >= 80"
        
        print(f"PASS: min_priority=80 filter works, total={total}, {len(items)} items returned")
    
    def test_sort_by_priority_score_desc(self):
        """Sort by priority_score descending should return highest priority first"""
        response = requests.get(f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=desc&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        if len(items) >= 2:
            scores = [item.get("priority_score", 0) for item in items]
            # Check descending order
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i+1], f"Not descending: {scores[i]} < {scores[i+1]}"
            print(f"PASS: sort_by=priority_score desc works, scores: {scores[:5]}")
        else:
            print("SKIP: Not enough items to verify sorting")
    
    def test_sort_by_priority_score_asc(self):
        """Sort by priority_score ascending should return lowest priority first"""
        response = requests.get(f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=asc&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        if len(items) >= 2:
            scores = [item.get("priority_score", 0) for item in items]
            # Check ascending order
            for i in range(len(scores) - 1):
                assert scores[i] <= scores[i+1], f"Not ascending: {scores[i]} > {scores[i+1]}"
            print(f"PASS: sort_by=priority_score asc works, scores: {scores[:5]}")
        else:
            print("SKIP: Not enough items to verify sorting")
    
    def test_combined_filter_and_sort(self):
        """Combine min_priority filter with priority_score sorting"""
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=60&sort_by=priority_score&sort_order=desc&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        # All items should have priority >= 60 AND be sorted descending
        scores = []
        for item in items:
            priority = item.get("priority_score", 0)
            assert priority >= 60, f"Item has priority {priority}, expected >= 60"
            scores.append(priority)
        
        # Check descending order
        if len(scores) >= 2:
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i+1], f"Not descending: {scores[i]} < {scores[i+1]}"
        
        print(f"PASS: Combined filter+sort works, {len(items)} items, all >= 60, sorted desc")
    
    def test_sort_by_published_at_default(self):
        """Default sort should be by published_at"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        if len(items) >= 2:
            dates = [item.get("published_at", "") for item in items]
            # Check descending order (newest first)
            for i in range(len(dates) - 1):
                assert dates[i] >= dates[i+1], f"Not descending by date: {dates[i]} < {dates[i+1]}"
            print(f"PASS: Default sort by published_at desc works")
        else:
            print("SKIP: Not enough items to verify sorting")


class TestBriefDataIntegrity:
    """Tests for brief data integrity and structure"""
    
    def test_brief_has_key_developments(self):
        """Brief should have key_developments array"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        assert "key_developments" in data, "key_developments should exist"
        assert isinstance(data["key_developments"], list), "key_developments should be a list"
        print(f"PASS: Brief has {len(data['key_developments'])} key developments")
    
    def test_brief_has_analyst_summary(self):
        """Brief should have analyst_summary"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        assert "analyst_summary" in data, "analyst_summary should exist"
        print(f"PASS: Brief has analyst_summary")
    
    def test_brief_date_format(self):
        """Brief date should be in YYYY-MM-DD format"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        
        data = response.json()
        date = data.get("date", "")
        assert len(date) == 10, f"Date should be 10 chars, got {len(date)}"
        assert date[4] == "-" and date[7] == "-", f"Date format should be YYYY-MM-DD, got {date}"
        print(f"PASS: Brief date format is correct: {date}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
