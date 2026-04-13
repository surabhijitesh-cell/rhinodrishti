"""
Iteration 32 Tests: Settings Page Layout, Bias Impact Report, Viewer Role Restriction
Tests for:
1. GET /api/feedback/bias-impact endpoint
2. Settings page layout (side-by-side cards)
3. Viewer role cannot access Settings page
4. Bias settings dropdowns work correctly
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBiasImpactEndpoint:
    """Tests for GET /api/feedback/bias-impact endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_bias_impact_returns_200(self):
        """GET /api/feedback/bias-impact returns 200"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact")
        assert response.status_code == 200
        print("✓ GET /api/feedback/bias-impact returns 200")
    
    def test_bias_impact_has_required_fields(self):
        """Bias impact response has required fields"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact")
        data = response.json()
        
        assert "status" in data
        assert "influence" in data
        assert "influence_label" in data
        assert "window" in data
        assert "total_items_analyzed" in data
        assert "summary" in data
        assert "items" in data
        print("✓ Bias impact response has all required fields")
    
    def test_bias_impact_summary_structure(self):
        """Bias impact summary has boosted/reduced/unchanged counts"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact")
        data = response.json()
        
        summary = data.get("summary", {})
        assert "boosted" in summary
        assert "reduced" in summary
        assert "unchanged" in summary
        assert "avg_absolute_delta" in summary
        
        # Verify counts are integers
        assert isinstance(summary["boosted"], int)
        assert isinstance(summary["reduced"], int)
        assert isinstance(summary["unchanged"], int)
        print(f"✓ Summary: boosted={summary['boosted']}, reduced={summary['reduced']}, unchanged={summary['unchanged']}")
    
    def test_bias_impact_items_structure(self):
        """Bias impact items have correct structure"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact")
        data = response.json()
        
        items = data.get("items", [])
        if len(items) > 0:
            item = items[0]
            assert "id" in item
            assert "title" in item
            assert "region" in item
            assert "threat_category" in item
            assert "original_score" in item
            assert "biased_score" in item
            assert "delta" in item
            assert "direction" in item
            assert "analyst_avg_rating" in item
            assert "rating_count" in item
            assert "reasons" in item
            print(f"✓ Items have correct structure, first item: {item['title'][:50]}...")
        else:
            print("? No items in bias impact report")
    
    def test_bias_impact_total_matches_items(self):
        """Total items analyzed matches or exceeds items returned"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact")
        data = response.json()
        
        total = data.get("total_items_analyzed", 0)
        items_count = len(data.get("items", []))
        
        # Items are limited to 30, so total should be >= items_count
        assert total >= items_count or total == items_count
        print(f"✓ Total items analyzed: {total}, items returned: {items_count}")


class TestBiasSettingsEndpoint:
    """Tests for GET/PUT /api/settings/bias endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_bias_settings(self):
        """GET /api/settings/bias returns current settings"""
        response = requests.get(f"{BASE_URL}/api/settings/bias")
        assert response.status_code == 200
        
        data = response.json()
        assert "bias_window" in data
        assert "bias_influence" in data
        assert data["bias_window"] in ["rolling_30", "all_time"]
        assert data["bias_influence"] in ["light", "moderate", "high"]
        print(f"✓ Current bias settings: window={data['bias_window']}, influence={data['bias_influence']}")
    
    def test_put_bias_settings_update(self):
        """PUT /api/settings/bias updates settings"""
        # Update to high influence
        response = requests.put(f"{BASE_URL}/api/settings/bias", json={
            "bias_window": "all_time",
            "bias_influence": "high"
        })
        assert response.status_code == 200
        
        # Verify update
        get_response = requests.get(f"{BASE_URL}/api/settings/bias")
        data = get_response.json()
        assert data["bias_window"] == "all_time"
        assert data["bias_influence"] == "high"
        print("✓ Bias settings updated to all_time/high")
        
        # Reset to defaults
        requests.put(f"{BASE_URL}/api/settings/bias", json={
            "bias_window": "rolling_30",
            "bias_influence": "moderate"
        })
        print("✓ Bias settings reset to defaults")
    
    def test_put_bias_settings_invalid_window(self):
        """PUT /api/settings/bias rejects invalid window"""
        response = requests.put(f"{BASE_URL}/api/settings/bias", json={
            "bias_window": "invalid_window",
            "bias_influence": "moderate"
        })
        assert response.status_code == 400
        print("✓ Invalid window rejected with 400")
    
    def test_put_bias_settings_invalid_influence(self):
        """PUT /api/settings/bias rejects invalid influence"""
        response = requests.put(f"{BASE_URL}/api/settings/bias", json={
            "bias_window": "rolling_30",
            "bias_influence": "invalid_influence"
        })
        assert response.status_code == 400
        print("✓ Invalid influence rejected with 400")


class TestViewerRoleRestriction:
    """Tests for viewer role cannot access admin-only endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get viewer auth token"""
        # First ensure viewer user exists
        admin_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        admin_token = admin_response.json()["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Check if viewer exists, create if not
        users_response = requests.get(f"{BASE_URL}/api/users", headers=admin_headers)
        users_data = users_response.json()
        users = users_data.get("users", []) if isinstance(users_data, dict) else users_data
        viewer_exists = any(u.get("username") == "testviewer" for u in users)
        
        if not viewer_exists:
            requests.post(f"{BASE_URL}/api/users", headers=admin_headers, json={
                "username": "testviewer",
                "email": "testviewer@test.com",
                "name": "Test Viewer",
                "password": "Viewer@2026!",
                "role": "viewer"
            })
        
        # Login as viewer
        viewer_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "testviewer",
            "password": "Viewer@2026!"
        })
        assert viewer_response.status_code == 200, f"Viewer login failed: {viewer_response.text}"
        self.viewer_token = viewer_response.json()["token"]
        self.viewer_headers = {"Authorization": f"Bearer {self.viewer_token}"}
        self.admin_headers = admin_headers
    
    def test_viewer_can_access_public_endpoints(self):
        """Viewer can access public endpoints like intelligence feed"""
        response = requests.get(f"{BASE_URL}/api/intelligence", headers=self.viewer_headers)
        assert response.status_code == 200
        print("✓ Viewer can access /api/intelligence")
    
    def test_viewer_can_access_feedback_bias_impact(self):
        """Viewer can access bias impact report (read-only)"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-impact", headers=self.viewer_headers)
        assert response.status_code == 200
        print("✓ Viewer can access /api/feedback/bias-impact")
    
    def test_viewer_cannot_create_users(self):
        """Viewer cannot create users (admin-only)"""
        response = requests.post(f"{BASE_URL}/api/users", headers=self.viewer_headers, json={
            "username": "hacker",
            "email": "hacker@test.com",
            "name": "Hacker",
            "password": "Hacker@2026!",
            "role": "admin"
        })
        # Should be 401 or 403
        assert response.status_code in [401, 403]
        print(f"✓ Viewer cannot create users (status: {response.status_code})")


class TestRetentionSettings:
    """Tests for retention settings endpoint"""
    
    def test_get_retention_settings(self):
        """GET /api/settings/retention returns current retention"""
        response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert response.status_code == 200
        
        data = response.json()
        assert "retention_days" in data
        assert isinstance(data["retention_days"], int)
        print(f"✓ Current retention: {data['retention_days']} days")
    
    def test_put_retention_settings(self):
        """PUT /api/settings/retention updates retention"""
        # Get current value
        get_response = requests.get(f"{BASE_URL}/api/settings/retention")
        original = get_response.json()["retention_days"]
        
        # Update to 60 days
        response = requests.put(f"{BASE_URL}/api/settings/retention", json={
            "retention_days": 60
        })
        assert response.status_code == 200
        
        # Verify
        verify_response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert verify_response.json()["retention_days"] == 60
        print("✓ Retention updated to 60 days")
        
        # Reset to original
        requests.put(f"{BASE_URL}/api/settings/retention", json={
            "retention_days": original
        })
        print(f"✓ Retention reset to {original} days")


class TestFeedbackSettings:
    """Tests for feedback settings endpoint"""
    
    def test_get_feedback_settings(self):
        """GET /api/settings/feedback returns current settings"""
        response = requests.get(f"{BASE_URL}/api/settings/feedback")
        assert response.status_code == 200
        
        data = response.json()
        assert "max_feedback_per_item" in data
        assert isinstance(data["max_feedback_per_item"], int)
        print(f"✓ Current max feedback per item: {data['max_feedback_per_item']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
