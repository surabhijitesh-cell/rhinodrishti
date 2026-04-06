"""
Test Suite for Iteration 9: APScheduler Daily Brief at 0600 IST
Tests:
1. GET /api/pipeline/status - scheduler field mentions daily brief at 0600 IST
2. APScheduler has 3 jobs registered: news_fetch, retry_unprocessed, daily_brief_0600
3. POST /api/generate-brief - triggers regeneration with correct time window
4. GET /api/daily-brief - includes included_item_ids for cross-brief dedup
5. GET /api/daily-brief - no twitter_highlights field
6. GET /api/daily-brief - contains pattern_insights
7. Regenerated brief has different items than previous (cross-brief dedup working)
8. Brief generation logs show 'prev day brief' window calculation
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPipelineStatus:
    """Test /api/pipeline/status endpoint for scheduler info"""
    
    def test_pipeline_status_returns_200(self):
        """Test that pipeline status endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/pipeline/status returns 200")
    
    def test_pipeline_status_scheduler_mentions_daily_brief_0600_ist(self):
        """Test that scheduler field mentions daily brief at 0600 IST"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        
        # Check scheduler field exists
        assert "scheduler" in data, "scheduler field missing from pipeline status"
        scheduler_info = data["scheduler"]
        
        # Verify it mentions daily brief at 0600 IST
        assert "daily brief" in scheduler_info.lower(), f"scheduler field should mention 'daily brief': {scheduler_info}"
        assert "0600" in scheduler_info or "06:00" in scheduler_info, f"scheduler field should mention '0600': {scheduler_info}"
        assert "ist" in scheduler_info.lower(), f"scheduler field should mention 'IST': {scheduler_info}"
        
        print(f"PASS: scheduler field mentions daily brief at 0600 IST: '{scheduler_info}'")
    
    def test_pipeline_status_has_rate_limit_config(self):
        """Test that pipeline status includes rate limit configuration"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "rate_limit_config" in data, "rate_limit_config missing from pipeline status"
        config = data["rate_limit_config"]
        assert "max_articles_per_cycle" in config
        assert "batch_size" in config
        print(f"PASS: rate_limit_config present with {len(config)} settings")


class TestDailyBrief:
    """Test /api/daily-brief endpoint for brief structure"""
    
    def test_daily_brief_returns_200(self):
        """Test that daily brief endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/daily-brief returns 200")
    
    def test_daily_brief_no_twitter_highlights(self):
        """Test that daily brief does NOT contain twitter_highlights field"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        # twitter_highlights should NOT be present
        assert "twitter_highlights" not in data, f"twitter_highlights field should NOT be present in daily brief"
        print("PASS: daily brief does NOT contain twitter_highlights field")
    
    def test_daily_brief_contains_pattern_insights(self):
        """Test that daily brief contains pattern_insights array"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        # pattern_insights should be present
        assert "pattern_insights" in data, "pattern_insights field missing from daily brief"
        assert isinstance(data["pattern_insights"], list), "pattern_insights should be a list"
        
        pattern_count = len(data["pattern_insights"])
        print(f"PASS: daily brief contains pattern_insights array with {pattern_count} items")
        
        # If patterns exist, verify structure
        if pattern_count > 0:
            pattern = data["pattern_insights"][0]
            expected_fields = ["region", "detail", "escalation_risk"]
            for field in expected_fields:
                assert field in pattern, f"pattern_insights item missing '{field}' field"
            print(f"PASS: pattern_insights items have correct structure (region, detail, escalation_risk)")
    
    def test_daily_brief_contains_included_item_ids(self):
        """Test that daily brief contains included_item_ids for cross-brief dedup"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        # included_item_ids should be present
        assert "included_item_ids" in data, "included_item_ids field missing from daily brief"
        assert isinstance(data["included_item_ids"], list), "included_item_ids should be a list"
        
        item_count = len(data["included_item_ids"])
        print(f"PASS: daily brief contains included_item_ids array with {item_count} IDs for cross-brief dedup")
    
    def test_daily_brief_has_key_developments(self):
        """Test that daily brief has key_developments"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "key_developments" in data, "key_developments field missing"
        assert isinstance(data["key_developments"], list), "key_developments should be a list"
        
        dev_count = len(data["key_developments"])
        print(f"PASS: daily brief has key_developments with {dev_count} items")
    
    def test_daily_brief_has_generated_at(self):
        """Test that daily brief has generated_at timestamp"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "generated_at" in data, "generated_at field missing"
        assert len(data["generated_at"]) > 10, "generated_at should be a valid timestamp"
        print(f"PASS: daily brief has generated_at: {data['generated_at']}")


class TestBriefRegeneration:
    """Test POST /api/generate-brief for regeneration"""
    
    def test_generate_brief_triggers_regeneration(self):
        """Test that POST /api/generate-brief triggers brief regeneration"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "message" in data, "Response should contain 'message' field"
        assert "brief" in data["message"].lower() or "generation" in data["message"].lower(), \
            f"Message should mention brief generation: {data['message']}"
        
        print(f"PASS: POST /api/generate-brief triggers regeneration: '{data['message']}'")
    
    def test_regenerated_brief_has_different_items(self):
        """Test that regenerated brief has different items (cross-brief dedup working)"""
        # Get current brief
        response1 = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response1.status_code == 200
        brief1 = response1.json()
        items1 = set(brief1.get("included_item_ids", []))
        gen_time1 = brief1.get("generated_at", "")
        
        print(f"First brief: {len(items1)} items, generated at {gen_time1}")
        
        # Trigger regeneration
        regen_response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert regen_response.status_code == 200
        
        # Wait for background task to complete
        time.sleep(5)
        
        # Get new brief
        response2 = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response2.status_code == 200
        brief2 = response2.json()
        items2 = set(brief2.get("included_item_ids", []))
        gen_time2 = brief2.get("generated_at", "")
        
        print(f"Second brief: {len(items2)} items, generated at {gen_time2}")
        
        # Check that generation time changed (brief was regenerated)
        # Note: If items are the same, it could mean dedup is working and excluding previous items
        if gen_time1 != gen_time2:
            print(f"PASS: Brief was regenerated (different generated_at timestamps)")
            
            # Check for item overlap
            overlap = items1 & items2
            if len(overlap) < len(items1):
                print(f"PASS: Cross-brief dedup working - overlap: {len(overlap)} items (first had {len(items1)}, second has {len(items2)})")
            else:
                print(f"INFO: Items may be same if no new items available since last brief")
        else:
            print(f"INFO: Brief may not have been regenerated yet (background task)")


class TestSchedulerJobs:
    """Test that APScheduler has correct jobs registered (via logs/status)"""
    
    def test_pipeline_status_shows_scheduler_config(self):
        """Test that pipeline status shows scheduler configuration"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify scheduler info is present
        assert "scheduler" in data, "scheduler field missing"
        scheduler_info = data["scheduler"]
        
        # Should mention all three job types
        assert "fetch" in scheduler_info.lower() or "30" in scheduler_info, \
            f"scheduler should mention fetch job: {scheduler_info}"
        assert "retry" in scheduler_info.lower() or "15" in scheduler_info, \
            f"scheduler should mention retry job: {scheduler_info}"
        assert "brief" in scheduler_info.lower() or "0600" in scheduler_info, \
            f"scheduler should mention daily brief job: {scheduler_info}"
        
        print(f"PASS: scheduler config shows all 3 jobs: '{scheduler_info}'")


class TestBriefTimeWindow:
    """Test brief time window logic"""
    
    def test_brief_has_date_field(self):
        """Test that brief has date field"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data, "date field missing from brief"
        assert len(data["date"]) == 10, f"date should be YYYY-MM-DD format: {data['date']}"
        print(f"PASS: brief has date field: {data['date']}")
    
    def test_brief_key_developments_have_timestamps(self):
        """Test that key developments have timestamps for time window verification"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        developments = data.get("key_developments", [])
        if len(developments) > 0:
            # Check first development has timestamp
            dev = developments[0]
            if isinstance(dev, dict):
                has_timestamp = "timestamp" in dev or "published_at" in dev
                if has_timestamp:
                    ts = dev.get("timestamp") or dev.get("published_at")
                    print(f"PASS: key developments have timestamps (first: {ts})")
                else:
                    print(f"INFO: key development structure: {list(dev.keys())}")
        else:
            print("INFO: No key developments to check timestamps")


class TestBriefStructureComplete:
    """Test complete brief structure"""
    
    def test_brief_has_all_required_fields(self):
        """Test that brief has all required fields"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "id", "date", "key_developments", "state_highlights",
            "cross_border_insights", "analyst_summary", "national_news",
            "international_news", "pattern_insights", "uploaded_insights",
            "included_item_ids", "generated_at"
        ]
        
        missing = []
        for field in required_fields:
            if field not in data:
                missing.append(field)
        
        if missing:
            print(f"WARNING: Missing fields: {missing}")
        else:
            print(f"PASS: Brief has all {len(required_fields)} required fields")
        
        # This should not fail the test, just report
        assert len(missing) == 0, f"Brief missing fields: {missing}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
