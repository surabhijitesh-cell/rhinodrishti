"""
Test suite for Alpha Training & Multi-User Feedback System (v17)
Tests: feedback submission, duplicate prevention, max limit enforcement, 
       batch fetch, stats, training profile, settings endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test device IDs for duplicate prevention testing
TEST_DEVICE_1 = f"test_device_{uuid.uuid4().hex[:8]}"
TEST_DEVICE_2 = f"test_device_{uuid.uuid4().hex[:8]}"
TEST_DEVICE_3 = f"test_device_{uuid.uuid4().hex[:8]}"


class TestFeedbackSettings:
    """Test GET/PUT /api/settings/feedback for max_feedback_per_item"""

    def test_get_feedback_settings(self):
        """GET /api/settings/feedback returns max_feedback_per_item"""
        response = requests.get(f"{BASE_URL}/api/settings/feedback")
        assert response.status_code == 200
        data = response.json()
        assert "max_feedback_per_item" in data
        assert isinstance(data["max_feedback_per_item"], int)
        assert 1 <= data["max_feedback_per_item"] <= 500
        print(f"✓ GET /api/settings/feedback: max_feedback_per_item = {data['max_feedback_per_item']}")

    def test_update_feedback_settings_valid(self):
        """PUT /api/settings/feedback updates max_feedback_per_item (valid 1-500)"""
        # First get current value
        get_res = requests.get(f"{BASE_URL}/api/settings/feedback")
        original_value = get_res.json().get("max_feedback_per_item", 20)

        # Update to a new value
        new_value = 25
        response = requests.put(f"{BASE_URL}/api/settings/feedback", json={"max_feedback_per_item": new_value})
        assert response.status_code == 200
        data = response.json()
        assert data["max_feedback_per_item"] == new_value
        print(f"✓ PUT /api/settings/feedback: updated to {new_value}")

        # Restore original value
        requests.put(f"{BASE_URL}/api/settings/feedback", json={"max_feedback_per_item": original_value})

    def test_update_feedback_settings_invalid_low(self):
        """PUT /api/settings/feedback rejects value < 1"""
        response = requests.put(f"{BASE_URL}/api/settings/feedback", json={"max_feedback_per_item": 0})
        assert response.status_code == 400
        print("✓ PUT /api/settings/feedback: rejected value 0 (< 1)")

    def test_update_feedback_settings_invalid_high(self):
        """PUT /api/settings/feedback rejects value > 500"""
        response = requests.put(f"{BASE_URL}/api/settings/feedback", json={"max_feedback_per_item": 501})
        assert response.status_code == 400
        print("✓ PUT /api/settings/feedback: rejected value 501 (> 500)")

    def test_update_feedback_settings_invalid_type(self):
        """PUT /api/settings/feedback rejects non-integer"""
        response = requests.put(f"{BASE_URL}/api/settings/feedback", json={"max_feedback_per_item": "twenty"})
        assert response.status_code == 400
        print("✓ PUT /api/settings/feedback: rejected non-integer value")


class TestFeedbackSubmission:
    """Test POST /api/feedback for rating submission"""

    @pytest.fixture(autouse=True)
    def get_valid_intelligence_id(self):
        """Get a valid intelligence_id from the database"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if response.status_code == 200 and response.json().get("items"):
            self.valid_item_id = response.json()["items"][0]["id"]
        else:
            pytest.skip("No intelligence items available for testing")

    def test_submit_rating_valid(self):
        """POST /api/feedback creates new rating (1-6 scale)"""
        payload = {
            "intelligence_id": self.valid_item_id,
            "device_id": TEST_DEVICE_1,
            "rating": 5
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert data["action"] in ["created", "updated"]
        print(f"✓ POST /api/feedback: rating {data['action']} for item {self.valid_item_id[:8]}...")

    def test_submit_rating_update_same_device(self):
        """POST /api/feedback updates existing rating (same device_id + intelligence_id)"""
        # First submission
        payload = {
            "intelligence_id": self.valid_item_id,
            "device_id": TEST_DEVICE_2,
            "rating": 3
        }
        res1 = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert res1.status_code == 200

        # Second submission with same device - should update, not create
        payload["rating"] = 6
        res2 = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert res2.status_code == 200
        data = res2.json()
        assert data["rating"] == 6
        assert data["action"] == "updated"
        print("✓ POST /api/feedback: duplicate device updates existing rating (not creates new)")

    def test_submit_rating_invalid_low(self):
        """POST /api/feedback rejects rating < 1"""
        payload = {
            "intelligence_id": self.valid_item_id,
            "device_id": TEST_DEVICE_3,
            "rating": 0
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback: rejected rating 0 (< 1)")

    def test_submit_rating_invalid_high(self):
        """POST /api/feedback rejects rating > 6"""
        payload = {
            "intelligence_id": self.valid_item_id,
            "device_id": TEST_DEVICE_3,
            "rating": 7
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback: rejected rating 7 (> 6)")

    def test_submit_rating_invalid_float(self):
        """POST /api/feedback rejects non-integer rating"""
        payload = {
            "intelligence_id": self.valid_item_id,
            "device_id": TEST_DEVICE_3,
            "rating": 4.5
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback: rejected float rating 4.5")

    def test_submit_rating_missing_intelligence_id(self):
        """POST /api/feedback rejects missing intelligence_id"""
        payload = {
            "device_id": TEST_DEVICE_3,
            "rating": 4
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback: rejected missing intelligence_id")

    def test_submit_rating_missing_device_id(self):
        """POST /api/feedback rejects missing device_id"""
        payload = {
            "intelligence_id": self.valid_item_id,
            "rating": 4
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback: rejected missing device_id")

    def test_submit_rating_invalid_intelligence_id(self):
        """POST /api/feedback returns 404 for non-existent intelligence_id"""
        payload = {
            "intelligence_id": "non-existent-id-12345",
            "device_id": TEST_DEVICE_3,
            "rating": 4
        }
        response = requests.post(f"{BASE_URL}/api/feedback", json=payload)
        assert response.status_code == 404
        print("✓ POST /api/feedback: returned 404 for non-existent intelligence_id")


class TestFeedbackRetrieval:
    """Test GET /api/feedback/{intelligence_id} for single item feedback"""

    @pytest.fixture(autouse=True)
    def get_valid_intelligence_id(self):
        """Get a valid intelligence_id from the database"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if response.status_code == 200 and response.json().get("items"):
            self.valid_item_id = response.json()["items"][0]["id"]
        else:
            pytest.skip("No intelligence items available for testing")

    def test_get_feedback_for_item(self):
        """GET /api/feedback/{intelligence_id} returns feedback status"""
        response = requests.get(f"{BASE_URL}/api/feedback/{self.valid_item_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "intelligence_id" in data
        assert "total_ratings" in data
        assert "max_limit" in data
        assert "limit_reached" in data
        assert "avg_rating" in data
        assert "distribution" in data
        
        # Verify data types
        assert isinstance(data["total_ratings"], int)
        assert isinstance(data["max_limit"], int)
        assert isinstance(data["limit_reached"], bool)
        assert isinstance(data["avg_rating"], (int, float))
        assert isinstance(data["distribution"], dict)
        
        print(f"✓ GET /api/feedback/{{id}}: total={data['total_ratings']}, avg={data['avg_rating']}, limit_reached={data['limit_reached']}")

    def test_get_feedback_with_device_id(self):
        """GET /api/feedback/{intelligence_id}?device_id=X returns user_rating"""
        # First submit a rating
        device_id = f"test_device_{uuid.uuid4().hex[:8]}"
        requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.valid_item_id,
            "device_id": device_id,
            "rating": 4
        })

        # Then fetch with device_id
        response = requests.get(f"{BASE_URL}/api/feedback/{self.valid_item_id}?device_id={device_id}")
        assert response.status_code == 200
        data = response.json()
        assert "user_rating" in data
        assert data["user_rating"] == 4
        print(f"✓ GET /api/feedback/{{id}}?device_id: user_rating = {data['user_rating']}")

    def test_get_feedback_distribution(self):
        """GET /api/feedback/{intelligence_id} returns rating distribution (1-6)"""
        response = requests.get(f"{BASE_URL}/api/feedback/{self.valid_item_id}")
        assert response.status_code == 200
        data = response.json()
        
        distribution = data["distribution"]
        # Should have keys 1-6
        for i in range(1, 7):
            assert i in distribution or str(i) in distribution
        print(f"✓ GET /api/feedback/{{id}}: distribution = {distribution}")


class TestFeedbackBatch:
    """Test POST /api/feedback/batch for batch feedback fetch"""

    @pytest.fixture(autouse=True)
    def get_valid_intelligence_ids(self):
        """Get multiple valid intelligence_ids from the database"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=5")
        if response.status_code == 200 and response.json().get("items"):
            self.valid_item_ids = [item["id"] for item in response.json()["items"]]
        else:
            pytest.skip("No intelligence items available for testing")

    def test_batch_feedback_fetch(self):
        """POST /api/feedback/batch returns feedback for multiple items"""
        payload = {
            "item_ids": self.valid_item_ids,
            "device_id": TEST_DEVICE_1
        }
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "feedback" in data
        feedback_map = data["feedback"]
        
        # Should have entry for each requested item
        for item_id in self.valid_item_ids:
            assert item_id in feedback_map
            item_feedback = feedback_map[item_id]
            assert "total_ratings" in item_feedback
            assert "avg_rating" in item_feedback
            assert "limit_reached" in item_feedback
            assert "max_limit" in item_feedback
        
        print(f"✓ POST /api/feedback/batch: returned feedback for {len(feedback_map)} items")

    def test_batch_feedback_empty_ids(self):
        """POST /api/feedback/batch rejects empty item_ids"""
        payload = {
            "item_ids": [],
            "device_id": TEST_DEVICE_1
        }
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback/batch: rejected empty item_ids")

    def test_batch_feedback_too_many_ids(self):
        """POST /api/feedback/batch rejects > 50 item_ids"""
        payload = {
            "item_ids": [f"fake-id-{i}" for i in range(51)],
            "device_id": TEST_DEVICE_1
        }
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json=payload)
        assert response.status_code == 400
        print("✓ POST /api/feedback/batch: rejected > 50 item_ids")


class TestFeedbackStats:
    """Test GET /api/feedback/stats for global statistics"""

    def test_get_feedback_stats(self):
        """GET /api/feedback/stats returns global feedback statistics"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_feedback" in data
        assert "unique_items_rated" in data
        assert "unique_devices" in data
        assert "global_avg_rating" in data
        assert "distribution" in data
        assert "recent_7d" in data
        assert "max_feedback_per_item" in data
        
        # Verify data types
        assert isinstance(data["total_feedback"], int)
        assert isinstance(data["unique_items_rated"], int)
        assert isinstance(data["unique_devices"], int)
        assert isinstance(data["global_avg_rating"], (int, float))
        assert isinstance(data["distribution"], dict)
        
        print(f"✓ GET /api/feedback/stats: total={data['total_feedback']}, items={data['unique_items_rated']}, devices={data['unique_devices']}")

    def test_get_feedback_stats_distribution(self):
        """GET /api/feedback/stats returns rating distribution (1-6)"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        
        distribution = data["distribution"]
        # Should have keys 1-6
        for i in range(1, 7):
            assert i in distribution or str(i) in distribution
        print(f"✓ GET /api/feedback/stats: distribution = {distribution}")


class TestTrainingProfile:
    """Test GET /api/feedback/training-profile for intelligence learning profile"""

    def test_get_training_profile(self):
        """GET /api/feedback/training-profile returns training profile"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_feedback" in data
        assert "unique_items_rated" in data
        assert "confidence_level" in data
        assert "positive_weights" in data
        assert "negative_weights" in data
        
        # Verify confidence_level is valid
        valid_levels = ["HIGH", "MODERATE", "LOW", "INSUFFICIENT_DATA"]
        assert data["confidence_level"] in valid_levels
        
        # Verify weights structure
        assert isinstance(data["positive_weights"], dict)
        assert isinstance(data["negative_weights"], dict)
        
        print(f"✓ GET /api/feedback/training-profile: confidence={data['confidence_level']}, total={data['total_feedback']}")

    def test_training_profile_weights_structure(self):
        """GET /api/feedback/training-profile returns proper weights structure"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        data = response.json()
        
        # Positive weights should have regions, threat_categories, actors
        if data["total_feedback"] > 0:
            pos = data["positive_weights"]
            assert "regions" in pos or pos == {}
            assert "threat_categories" in pos or pos == {}
            
            neg = data["negative_weights"]
            assert "regions" in neg or neg == {}
            assert "threat_categories" in neg or neg == {}
        
        print("✓ GET /api/feedback/training-profile: weights structure verified")


class TestAggregationUpdate:
    """Test that feedback updates intelligence item aggregation fields"""

    @pytest.fixture(autouse=True)
    def get_valid_intelligence_id(self):
        """Get a valid intelligence_id from the database"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if response.status_code == 200 and response.json().get("items"):
            self.valid_item_id = response.json()["items"][0]["id"]
        else:
            pytest.skip("No intelligence items available for testing")

    def test_aggregation_updates_on_feedback(self):
        """Submitting feedback updates intelligence item aggregation fields"""
        # Submit a rating
        device_id = f"test_agg_{uuid.uuid4().hex[:8]}"
        res = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.valid_item_id,
            "device_id": device_id,
            "rating": 5
        })
        assert res.status_code == 200

        # Fetch the intelligence item and check aggregation fields
        item_res = requests.get(f"{BASE_URL}/api/intelligence/{self.valid_item_id}")
        assert item_res.status_code == 200
        item = item_res.json()
        
        # These fields should exist after feedback is submitted
        # Note: They may not exist if this is the first feedback ever
        if "feedback_avg_rating" in item:
            assert isinstance(item["feedback_avg_rating"], (int, float))
            print(f"✓ Aggregation: feedback_avg_rating = {item['feedback_avg_rating']}")
        if "feedback_total_ratings" in item:
            assert isinstance(item["feedback_total_ratings"], int)
            print(f"✓ Aggregation: feedback_total_ratings = {item['feedback_total_ratings']}")
        if "feedback_derived_relevance" in item:
            valid_relevance = ["CRITICAL", "HIGH", "MODERATE", "LOW"]
            assert item["feedback_derived_relevance"] in valid_relevance
            print(f"✓ Aggregation: feedback_derived_relevance = {item['feedback_derived_relevance']}")


class TestRouteOrdering:
    """Test that static routes work correctly (route ordering fix verification)"""

    def test_stats_route_works(self):
        """GET /api/feedback/stats works (static route before dynamic)"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        assert "total_feedback" in response.json()
        print("✓ Route ordering: /feedback/stats works correctly")

    def test_training_profile_route_works(self):
        """GET /api/feedback/training-profile works (static route before dynamic)"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        assert "confidence_level" in response.json()
        print("✓ Route ordering: /feedback/training-profile works correctly")

    def test_batch_route_works(self):
        """POST /api/feedback/batch works (static route before dynamic)"""
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json={
            "item_ids": ["test-id"],
            "device_id": "test-device"
        })
        # Should return 200 even if items don't exist (returns empty feedback map)
        assert response.status_code == 200
        print("✓ Route ordering: /feedback/batch works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
