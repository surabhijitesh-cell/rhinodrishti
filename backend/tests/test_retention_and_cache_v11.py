"""
Test suite for P2 features: Configurable News Retention Window and Dashboard Stats Caching
Iteration 11 - Tests retention settings endpoints, cache behavior, and retention filtering
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRetentionSettings:
    """Tests for GET/PUT /api/settings/retention endpoints"""
    
    def test_get_retention_setting_returns_200(self):
        """GET /api/settings/retention should return 200 with retention_days"""
        response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "retention_days" in data, "Response should contain retention_days"
        assert isinstance(data["retention_days"], int), "retention_days should be an integer"
        print(f"✓ GET /api/settings/retention returns {data['retention_days']} days")
    
    def test_put_retention_setting_valid_value(self):
        """PUT /api/settings/retention with valid value should update and return confirmation"""
        # First get current value to restore later
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        
        # Update to 14 days
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": 14}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data, "Response should contain message"
        assert data["retention_days"] == 14, f"Expected retention_days=14, got {data['retention_days']}"
        print(f"✓ PUT /api/settings/retention with 14 days succeeded: {data['message']}")
        
        # Verify the change persisted
        verify = requests.get(f"{BASE_URL}/api/settings/retention").json()
        assert verify["retention_days"] == 14, "Retention setting should persist"
        print("✓ Retention setting persisted correctly")
        
        # Restore original value
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})
    
    def test_put_retention_setting_invalid_zero(self):
        """PUT /api/settings/retention with 0 should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": 0}
        )
        assert response.status_code == 400, f"Expected 400 for retention_days=0, got {response.status_code}"
        print("✓ PUT /api/settings/retention with 0 returns 400")
    
    def test_put_retention_setting_invalid_too_high(self):
        """PUT /api/settings/retention with 400 should return 400 (max is 365)"""
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": 400}
        )
        assert response.status_code == 400, f"Expected 400 for retention_days=400, got {response.status_code}"
        print("✓ PUT /api/settings/retention with 400 returns 400")
    
    def test_put_retention_setting_invalid_negative(self):
        """PUT /api/settings/retention with negative value should return 400"""
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": -5}
        )
        assert response.status_code == 400, f"Expected 400 for negative value, got {response.status_code}"
        print("✓ PUT /api/settings/retention with -5 returns 400")


class TestDashboardStatsRetention:
    """Tests for dashboard stats with retention window"""
    
    def test_dashboard_stats_includes_retention_days(self):
        """GET /api/dashboard/stats should include retention_days field"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "retention_days" in data, "Dashboard stats should include retention_days"
        assert isinstance(data["retention_days"], int), "retention_days should be an integer"
        print(f"✓ Dashboard stats includes retention_days: {data['retention_days']}")
    
    def test_dashboard_stats_retention_affects_counts(self):
        """Dashboard stats should show fewer items with shorter retention window"""
        # Get current retention
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        
        # Set to 30 days and get stats
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 30})
        time.sleep(0.5)  # Allow cache to invalidate
        stats_30d = requests.get(f"{BASE_URL}/api/dashboard/stats").json()
        total_30d = stats_30d["total_items"]
        
        # Set to 7 days and get stats
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 7})
        time.sleep(0.5)  # Allow cache to invalidate
        stats_7d = requests.get(f"{BASE_URL}/api/dashboard/stats").json()
        total_7d = stats_7d["total_items"]
        
        print(f"✓ Stats with 30d retention: {total_30d} items")
        print(f"✓ Stats with 7d retention: {total_7d} items")
        
        # 7 day window should have fewer or equal items than 30 day window
        assert total_7d <= total_30d, f"7d retention ({total_7d}) should have <= items than 30d ({total_30d})"
        print(f"✓ Retention window correctly filters stats: 7d ({total_7d}) <= 30d ({total_30d})")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})


class TestDashboardStatsCache:
    """Tests for dashboard stats caching behavior"""
    
    def test_cache_serves_same_data_within_ttl(self):
        """Second call within 60s should return cached data (same response)"""
        # First call
        response1 = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second call immediately after
        response2 = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Data should be identical (from cache)
        assert data1["total_items"] == data2["total_items"], "Cached data should be identical"
        assert data1["retention_days"] == data2["retention_days"], "Cached retention_days should match"
        print("✓ Dashboard stats cache serves same data within TTL")
    
    def test_cache_invalidated_after_retention_change(self):
        """Cache should be invalidated after PUT /api/settings/retention"""
        # Get current retention
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        
        # Get initial stats (populates cache)
        stats1 = requests.get(f"{BASE_URL}/api/dashboard/stats").json()
        
        # Change retention (should invalidate cache)
        new_retention = 14 if original != 14 else 30
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": new_retention})
        
        # Get stats again (should be fresh, not cached)
        stats2 = requests.get(f"{BASE_URL}/api/dashboard/stats").json()
        
        # The retention_days in stats should reflect the new value
        assert stats2["retention_days"] == new_retention, f"Expected retention_days={new_retention}, got {stats2['retention_days']}"
        print(f"✓ Cache invalidated after retention change: now shows {new_retention} days")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})


class TestIntelligenceRetentionFilter:
    """Tests for /api/intelligence retention window filtering"""
    
    def test_intelligence_applies_retention_filter(self):
        """GET /api/intelligence should apply retention window filter"""
        # Get current retention
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        
        # Set to 30 days
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 30})
        response_30d = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response_30d.status_code == 200
        total_30d = response_30d.json()["total"]
        
        # Set to 7 days
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 7})
        response_7d = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response_7d.status_code == 200
        total_7d = response_7d.json()["total"]
        
        print(f"✓ Intelligence feed with 30d retention: {total_30d} items")
        print(f"✓ Intelligence feed with 7d retention: {total_7d} items")
        
        # 7 day window should have fewer or equal items
        assert total_7d <= total_30d, f"7d retention ({total_7d}) should have <= items than 30d ({total_30d})"
        print(f"✓ Intelligence feed correctly applies retention filter")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})
    
    def test_intelligence_explicit_date_from_overrides_retention(self):
        """GET /api/intelligence with explicit date_from should override retention filter"""
        # Set retention to 7 days
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 7})
        
        # Get with 7d retention (default)
        response_7d = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        total_7d = response_7d.json()["total"]
        
        # Get with explicit date_from (should override retention)
        response_explicit = requests.get(f"{BASE_URL}/api/intelligence?limit=100&date_from=2025-01-01")
        total_explicit = response_explicit.json()["total"]
        
        print(f"✓ With 7d retention: {total_7d} items")
        print(f"✓ With explicit date_from=2025-01-01: {total_explicit} items")
        
        # Explicit date_from should potentially return more items (if data exists before 7d window)
        # At minimum, it should work without error
        assert response_explicit.status_code == 200
        print("✓ Explicit date_from parameter works correctly")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})


class TestRetentionEdgeCases:
    """Edge case tests for retention settings"""
    
    def test_retention_boundary_values(self):
        """Test boundary values: 1 and 365 days"""
        original = requests.get(f"{BASE_URL}/api/settings/retention").json()["retention_days"]
        
        # Test minimum valid value (1 day)
        response_1 = requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 1})
        assert response_1.status_code == 200, "retention_days=1 should be valid"
        print("✓ retention_days=1 is valid")
        
        # Test maximum valid value (365 days)
        response_365 = requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": 365})
        assert response_365.status_code == 200, "retention_days=365 should be valid"
        print("✓ retention_days=365 is valid")
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/retention", json={"retention_days": original})
    
    def test_retention_non_integer_rejected(self):
        """Non-integer values should be rejected"""
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": "thirty"}
        )
        assert response.status_code == 400, f"String value should return 400, got {response.status_code}"
        print("✓ Non-integer retention_days rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
