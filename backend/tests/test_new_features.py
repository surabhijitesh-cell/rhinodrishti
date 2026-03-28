"""
Backend tests for Rhino Drishti new features:
- Dashboard stat cards navigation (clickable to filter by severity)
- RSS scan progress bar API (/api/scan-status)
- Daily Brief page (React error #31 fix)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://strategic-scan.preview.emergentagent.com')


class TestScanStatusAPI:
    """Tests for RSS scan status endpoint - used by scan progress bar"""
    
    def test_scan_status_endpoint_returns_200(self):
        """GET /api/scan-status should return 200"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/scan-status returns 200")
    
    def test_scan_status_has_required_fields(self):
        """Scan status should have all required fields for progress bar"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        required_fields = [
            "is_scanning",
            "progress",
            "total_sources",
            "sources_scanned",
            "last_scan_at",
            "last_scan_result"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"PASS: Scan status has all required fields: {required_fields}")
    
    def test_scan_status_progress_is_valid(self):
        """Progress should be between 0 and 100"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        progress = data.get("progress", 0)
        assert 0 <= progress <= 100, f"Progress {progress} out of valid range 0-100"
        print(f"PASS: Progress value {progress} is valid (0-100)")
    
    def test_scan_status_has_scan_log(self):
        """Scan status should have scan_log for showing scanned sources"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        assert "scan_log" in data, "Missing scan_log field"
        assert isinstance(data["scan_log"], list), "scan_log should be a list"
        print(f"PASS: scan_log present with {len(data['scan_log'])} entries")
    
    def test_scan_status_last_scan_result_structure(self):
        """Last scan result should have feeds_scanned, total_articles, new_relevant"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        last_result = data.get("last_scan_result")
        if last_result and not last_result.get("error"):
            expected_fields = ["feeds_scanned", "total_articles", "new_relevant"]
            for field in expected_fields:
                assert field in last_result, f"Missing field in last_scan_result: {field}"
            print(f"PASS: last_scan_result has proper structure: {expected_fields}")
        else:
            print("INFO: No last_scan_result or has error - skipping structure check")


class TestDashboardStatsAPI:
    """Tests for dashboard stats API - used by stat cards"""
    
    def test_dashboard_stats_returns_200(self):
        """GET /api/dashboard/stats should return 200"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/dashboard/stats returns 200")
    
    def test_dashboard_stats_has_severity_counts(self):
        """Dashboard stats should have counts for all severity levels"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        data = response.json()
        
        severity_fields = ["critical_count", "high_count", "medium_count", "low_count", "total_items"]
        for field in severity_fields:
            assert field in data, f"Missing severity count field: {field}"
            assert isinstance(data[field], int), f"{field} should be an integer"
        print(f"PASS: Dashboard stats has all severity counts: {severity_fields}")
    
    def test_dashboard_stats_counts_are_non_negative(self):
        """All counts should be non-negative"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        data = response.json()
        
        count_fields = ["critical_count", "high_count", "medium_count", "low_count", "total_items", "today_count"]
        for field in count_fields:
            if field in data:
                assert data[field] >= 0, f"{field} should be non-negative, got {data[field]}"
        print("PASS: All count fields are non-negative")


class TestIntelligenceFeedAPI:
    """Tests for intelligence feed API - used when clicking stat cards"""
    
    def test_intelligence_feed_returns_200(self):
        """GET /api/intelligence should return 200"""
        response = requests.get(f"{BASE_URL}/api/intelligence")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/intelligence returns 200")
    
    def test_intelligence_feed_filter_by_critical(self):
        """Filter by severity=critical should work"""
        response = requests.get(f"{BASE_URL}/api/intelligence?severity=critical")
        assert response.status_code == 200
        data = response.json()
        
        # All items should have severity=critical
        items = data.get("items", [])
        for item in items:
            assert item.get("severity") == "critical", f"Item has wrong severity: {item.get('severity')}"
        print(f"PASS: Filter by severity=critical works, returned {len(items)} items")
    
    def test_intelligence_feed_filter_by_high(self):
        """Filter by severity=high should work"""
        response = requests.get(f"{BASE_URL}/api/intelligence?severity=high")
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            assert item.get("severity") == "high", f"Item has wrong severity: {item.get('severity')}"
        print(f"PASS: Filter by severity=high works, returned {len(items)} items")
    
    def test_intelligence_feed_filter_by_medium(self):
        """Filter by severity=medium should work"""
        response = requests.get(f"{BASE_URL}/api/intelligence?severity=medium")
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            assert item.get("severity") == "medium", f"Item has wrong severity: {item.get('severity')}"
        print(f"PASS: Filter by severity=medium works, returned {len(items)} items")
    
    def test_intelligence_feed_filter_by_low(self):
        """Filter by severity=low should work"""
        response = requests.get(f"{BASE_URL}/api/intelligence?severity=low")
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        for item in items:
            assert item.get("severity") == "low", f"Item has wrong severity: {item.get('severity')}"
        print(f"PASS: Filter by severity=low works, returned {len(items)} items")
    
    def test_intelligence_feed_no_filter_returns_all(self):
        """No filter should return all items"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        total = data.get("total", 0)
        assert total > 0, "Expected some items in the feed"
        print(f"PASS: No filter returns all items, total: {total}")


class TestDailyBriefAPI:
    """Tests for daily brief API - checking React error #31 fix"""
    
    def test_daily_brief_returns_200(self):
        """GET /api/daily-brief should return 200"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/daily-brief returns 200")
    
    def test_daily_brief_has_required_fields(self):
        """Daily brief should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        required_fields = ["date", "analyst_summary", "key_developments", "state_highlights"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"PASS: Daily brief has required fields: {required_fields}")
    
    def test_daily_brief_key_developments_are_serializable(self):
        """Key developments should be properly serializable (no React error #31)"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        key_devs = data.get("key_developments", [])
        for i, dev in enumerate(key_devs):
            # Each development should be either a string or a dict with string values
            if isinstance(dev, dict):
                for key, value in dev.items():
                    # Values should be strings, numbers, bools, or lists - not complex objects
                    assert isinstance(value, (str, int, float, bool, list, type(None))), \
                        f"key_developments[{i}].{key} has non-serializable type: {type(value)}"
            elif isinstance(dev, str):
                pass  # Strings are fine
            else:
                pytest.fail(f"key_developments[{i}] has unexpected type: {type(dev)}")
        print(f"PASS: All {len(key_devs)} key_developments are properly serializable")
    
    def test_daily_brief_state_highlights_are_strings(self):
        """State highlights values should be strings (no React error #31)"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        state_highlights = data.get("state_highlights", {})
        for state, highlight in state_highlights.items():
            assert isinstance(highlight, str), \
                f"state_highlights[{state}] should be string, got {type(highlight)}"
        print(f"PASS: All {len(state_highlights)} state_highlights are strings")
    
    def test_daily_brief_analyst_summary_is_string(self):
        """Analyst summary should be a string (no React error #31)"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        analyst_summary = data.get("analyst_summary")
        assert isinstance(analyst_summary, str), \
            f"analyst_summary should be string, got {type(analyst_summary)}"
        print("PASS: analyst_summary is a string")
    
    def test_daily_brief_cross_border_insights_is_string(self):
        """Cross border insights should be a string (no React error #31)"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        cross_border = data.get("cross_border_insights")
        if cross_border is not None:
            assert isinstance(cross_border, str), \
                f"cross_border_insights should be string, got {type(cross_border)}"
        print("PASS: cross_border_insights is a string or None")


class TestHealthAndBasicAPIs:
    """Basic health check tests"""
    
    def test_root_api_returns_200(self):
        """GET /api/ should return 200"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/ returns 200")
    
    def test_alerts_api_returns_200(self):
        """GET /api/alerts should return 200"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/alerts returns 200")
    
    def test_sources_api_returns_200(self):
        """GET /api/sources should return 200"""
        response = requests.get(f"{BASE_URL}/api/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/sources returns 200")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
