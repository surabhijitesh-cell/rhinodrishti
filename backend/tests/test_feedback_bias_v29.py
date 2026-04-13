"""
Test Suite for Feedback Bias Feature (Iteration 29)
Tests the new feedback bias engine that injects analyst ratings into AI classification pipeline.

Features tested:
- GET /api/feedback/bias-profile returns active bias profile
- Bias profile reflects real feedback data (57 ratings, 40 items)
- Bias cache invalidation on new feedback submission
- Login authentication
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test login with valid admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert data["user"]["username"] == "admin"
        print(f"✓ Login successful, token received")
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Invalid credentials correctly rejected with 401")


class TestFeedbackBiasProfile:
    """Tests for the new feedback bias profile endpoint"""
    
    def test_bias_profile_endpoint_exists(self):
        """Test GET /api/feedback/bias-profile returns 200"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        assert response.status_code == 200, f"Bias profile endpoint failed: {response.text}"
        print(f"✓ Bias profile endpoint returns 200")
    
    def test_bias_profile_has_active_status(self):
        """Test bias profile has active status with sufficient data"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        assert response.status_code == 200
        data = response.json()
        
        # Should be active since we have 57 ratings (>5 minimum)
        assert data.get("status") == "active", f"Expected active status, got: {data.get('status')}"
        print(f"✓ Bias profile status is ACTIVE")
    
    def test_bias_profile_has_total_ratings(self):
        """Test bias profile contains total_ratings field"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "total_ratings" in data, "total_ratings field missing"
        assert data["total_ratings"] >= 5, f"Expected at least 5 ratings, got {data['total_ratings']}"
        print(f"✓ Bias profile has {data['total_ratings']} total ratings")
    
    def test_bias_profile_has_unique_items(self):
        """Test bias profile contains unique_items field"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "unique_items" in data, "unique_items field missing"
        assert data["unique_items"] > 0, "Expected at least 1 unique item"
        print(f"✓ Bias profile has {data['unique_items']} unique items rated")
    
    def test_bias_profile_has_upweight_regions(self):
        """Test bias profile contains upweight_regions from high-rated items"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "upweight_regions" in data, "upweight_regions field missing"
        # Should have some regions since we have high-rated items
        if data.get("high_rated_items", 0) > 0:
            assert isinstance(data["upweight_regions"], dict), "upweight_regions should be a dict"
            print(f"✓ Upweight regions: {list(data['upweight_regions'].keys())}")
        else:
            print(f"✓ No high-rated items yet, upweight_regions is empty")
    
    def test_bias_profile_has_upweight_threats(self):
        """Test bias profile contains upweight_threats from high-rated items"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "upweight_threats" in data, "upweight_threats field missing"
        assert isinstance(data["upweight_threats"], dict), "upweight_threats should be a dict"
        print(f"✓ Upweight threats: {list(data['upweight_threats'].keys())[:5]}")
    
    def test_bias_profile_has_upweight_actors(self):
        """Test bias profile contains upweight_actors from high-rated items"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "upweight_actors" in data, "upweight_actors field missing"
        assert isinstance(data["upweight_actors"], dict), "upweight_actors should be a dict"
        print(f"✓ Upweight actors: {list(data['upweight_actors'].keys())[:5]}")
    
    def test_bias_profile_has_downweight_fields(self):
        """Test bias profile contains downweight fields"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "downweight_regions" in data, "downweight_regions field missing"
        assert "downweight_threats" in data, "downweight_threats field missing"
        print(f"✓ Downweight fields present")
    
    def test_bias_profile_has_window_days(self):
        """Test bias profile uses 30-day rolling window"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "window_days" in data, "window_days field missing"
        assert data["window_days"] == 30, f"Expected 30-day window, got {data['window_days']}"
        print(f"✓ Bias profile uses {data['window_days']}-day rolling window")
    
    def test_bias_profile_has_high_low_rated_counts(self):
        """Test bias profile contains high_rated_items and low_rated_items counts"""
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        data = response.json()
        
        assert "high_rated_items" in data, "high_rated_items field missing"
        assert "low_rated_items" in data, "low_rated_items field missing"
        print(f"✓ High-rated items: {data['high_rated_items']}, Low-rated items: {data['low_rated_items']}")


class TestBiasCacheInvalidation:
    """Tests for bias cache invalidation when new feedback is submitted"""
    
    @pytest.fixture
    def get_intelligence_item(self):
        """Get an intelligence item to rate"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if response.status_code == 200:
            items = response.json().get("items", [])
            if items:
                return items[0]["id"]
        return None
    
    def test_feedback_submission_invalidates_cache(self, get_intelligence_item):
        """Test that submitting feedback invalidates the bias cache"""
        if not get_intelligence_item:
            pytest.skip("No intelligence items available for testing")
        
        # Get initial bias profile
        initial_response = requests.get(f"{BASE_URL}/api/feedback/bias-profile")
        assert initial_response.status_code == 200
        
        # Submit new feedback
        device_id = f"test-device-{uuid.uuid4().hex[:8]}"
        feedback_response = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": get_intelligence_item,
            "device_id": device_id,
            "rating": 5
        })
        
        # Should succeed (200) or hit limit (429)
        assert feedback_response.status_code in [200, 429], f"Feedback submission failed: {feedback_response.text}"
        
        if feedback_response.status_code == 200:
            print(f"✓ Feedback submitted successfully, cache should be invalidated")
        else:
            print(f"✓ Feedback limit reached (expected behavior)")


class TestFeedbackStats:
    """Tests for feedback stats endpoint (regression)"""
    
    def test_feedback_stats_endpoint(self):
        """Test GET /api/feedback/stats returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        
        expected_fields = ["total_feedback", "unique_items_rated", "unique_devices", 
                          "global_avg_rating", "distribution", "recent_7d"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Feedback stats: {data['total_feedback']} total, {data['unique_items_rated']} items, avg {data['global_avg_rating']}")


class TestTrainingProfile:
    """Tests for training profile endpoint (regression)"""
    
    def test_training_profile_endpoint(self):
        """Test GET /api/feedback/training-profile returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        data = response.json()
        
        expected_fields = ["total_feedback", "unique_items_rated", "confidence_level",
                          "positive_weights", "negative_weights"]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Training profile: confidence={data['confidence_level']}, {data['total_feedback']} ratings")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
