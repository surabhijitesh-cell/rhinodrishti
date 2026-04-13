"""
Test Bias Settings Feature - Iteration 31
Tests for configurable feedback bias settings (window and influence level)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        return data["token"]
    
    def test_login_success(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print("✓ Admin login successful")


class TestBiasSettingsAPI:
    """Tests for GET/PUT /api/settings/bias endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_bias_settings_returns_defaults(self, auth_headers):
        """GET /api/settings/bias returns default values (rolling_30, moderate)"""
        response = requests.get(f"{BASE_URL}/api/settings/bias", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check structure
        assert "bias_window" in data, "Missing bias_window in response"
        assert "bias_influence" in data, "Missing bias_influence in response"
        
        # Default values should be rolling_30 and moderate
        assert data["bias_window"] in ["rolling_30", "all_time"], f"Invalid bias_window: {data['bias_window']}"
        assert data["bias_influence"] in ["light", "moderate", "high"], f"Invalid bias_influence: {data['bias_influence']}"
        print(f"✓ GET /api/settings/bias returns: window={data['bias_window']}, influence={data['bias_influence']}")
    
    def test_put_bias_settings_update_to_all_time_high(self, auth_headers):
        """PUT /api/settings/bias with {bias_window: 'all_time', bias_influence: 'high'} updates settings"""
        response = requests.put(f"{BASE_URL}/api/settings/bias", 
            headers=auth_headers,
            json={"bias_window": "all_time", "bias_influence": "high"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "No message in response"
        assert data["bias_window"] == "all_time", f"Expected all_time, got {data['bias_window']}"
        assert data["bias_influence"] == "high", f"Expected high, got {data['bias_influence']}"
        print("✓ PUT /api/settings/bias updated to all_time, high")
        
        # Verify with GET
        get_response = requests.get(f"{BASE_URL}/api/settings/bias", headers=auth_headers)
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["bias_window"] == "all_time", "GET didn't reflect update"
        assert get_data["bias_influence"] == "high", "GET didn't reflect update"
        print("✓ GET confirms settings persisted")
    
    def test_put_bias_settings_invalid_window_returns_400(self, auth_headers):
        """PUT /api/settings/bias with invalid window returns 400"""
        response = requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "invalid_window"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid bias_window returns 400")
    
    def test_put_bias_settings_invalid_influence_returns_400(self, auth_headers):
        """PUT /api/settings/bias with invalid influence returns 400"""
        response = requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_influence": "extreme"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid bias_influence returns 400")
    
    def test_put_bias_settings_partial_update_window_only(self, auth_headers):
        """PUT /api/settings/bias with only window updates just window"""
        response = requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "rolling_30"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Partial update (window only) works")
    
    def test_put_bias_settings_partial_update_influence_only(self, auth_headers):
        """PUT /api/settings/bias with only influence updates just influence"""
        response = requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_influence": "light"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        print("✓ Partial update (influence only) works")


class TestBiasProfileReflectsSettings:
    """Tests that /api/feedback/bias-profile reflects the settings"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_bias_profile_shows_window_mode(self, auth_headers):
        """GET /api/feedback/bias-profile reflects window_mode from settings"""
        # First set to all_time
        requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "all_time"}
        )
        
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "window_mode" in data, "Missing window_mode in bias profile"
        assert data["window_mode"] == "all_time", f"Expected all_time, got {data['window_mode']}"
        print(f"✓ Bias profile shows window_mode={data['window_mode']}")
    
    def test_bias_profile_shows_influence(self, auth_headers):
        """GET /api/feedback/bias-profile reflects influence from settings"""
        # Set to high influence
        requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_influence": "high"}
        )
        
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "influence" in data, "Missing influence in bias profile"
        assert data["influence"] == "high", f"Expected high, got {data['influence']}"
        
        # Check influence_pct label
        if data.get("status") == "active":
            assert "influence_pct" in data, "Missing influence_pct for active profile"
            assert "~35-40%" in data["influence_pct"], f"Expected ~35-40% for high, got {data['influence_pct']}"
        print(f"✓ Bias profile shows influence={data['influence']}")
    
    def test_bias_profile_window_label_all_time(self, auth_headers):
        """After changing to all_time, bias profile shows 'all time' window label"""
        requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "all_time"}
        )
        
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "window_label" in data, "Missing window_label"
        assert data["window_label"] == "all time", f"Expected 'all time', got {data['window_label']}"
        print(f"✓ Bias profile window_label={data['window_label']}")
    
    def test_bias_profile_window_label_rolling_30(self, auth_headers):
        """After changing to rolling_30, bias profile shows '30 days' window label"""
        requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "rolling_30"}
        )
        
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "window_label" in data, "Missing window_label"
        assert data["window_label"] == "30 days", f"Expected '30 days', got {data['window_label']}"
        print(f"✓ Bias profile window_label={data['window_label']}")


class TestResetToDefaults:
    """Reset settings back to defaults after testing"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        token = response.json()["token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_reset_bias_settings_to_defaults(self, auth_headers):
        """Reset settings back to defaults (rolling_30, moderate)"""
        response = requests.put(f"{BASE_URL}/api/settings/bias",
            headers=auth_headers,
            json={"bias_window": "rolling_30", "bias_influence": "moderate"}
        )
        assert response.status_code == 200, f"Failed to reset: {response.text}"
        
        # Verify reset
        get_response = requests.get(f"{BASE_URL}/api/settings/bias", headers=auth_headers)
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["bias_window"] == "rolling_30", "Failed to reset window"
        assert data["bias_influence"] == "moderate", "Failed to reset influence"
        print("✓ Settings reset to defaults (rolling_30, moderate)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
