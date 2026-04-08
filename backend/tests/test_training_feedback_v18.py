"""
Test Training Pipeline & Feedback System - Iteration 18
Tests:
- Training pipeline: add-url, upload-file, queue, delete, run, progress, insights
- Feedback: submit, batch, stats, training-profile
- Settings: feedback max limit with pill buttons
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTrainingPipeline:
    """Training pipeline endpoint tests"""
    
    # ============================================================
    # POST /api/training/add-url
    # ============================================================
    def test_add_url_success(self):
        """Add a valid URL to training queue"""
        unique_url = f"https://example.com/test-article-{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": unique_url})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert "message" in data
        assert data["source"] == "example.com"
        print(f"✓ Add URL success: {data['id']}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_add_url_duplicate_rejected(self):
        """Duplicate URL should return 409"""
        unique_url = f"https://duplicate-test-{uuid.uuid4().hex[:8]}.com/article"
        # First add
        res1 = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": unique_url})
        assert res1.status_code == 200
        item_id = res1.json()["id"]
        
        # Second add - should fail
        res2 = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": unique_url})
        assert res2.status_code == 409, f"Expected 409 for duplicate, got {res2.status_code}"
        assert "already" in res2.json().get("detail", "").lower()
        print("✓ Duplicate URL rejected with 409")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
    
    def test_add_url_invalid_rejected(self):
        """Invalid URL should return 400"""
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": "not-a-url"})
        assert response.status_code == 400
        print("✓ Invalid URL rejected with 400")
    
    def test_add_url_empty_rejected(self):
        """Empty URL should return 400"""
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": ""})
        assert response.status_code == 400
        print("✓ Empty URL rejected with 400")
    
    # ============================================================
    # POST /api/training/upload-file
    # ============================================================
    def test_upload_txt_file(self):
        """Upload a TXT file to training queue"""
        content = b"This is test content for training pipeline testing."
        files = {"file": ("test_document.txt", content, "text/plain")}
        response = requests.post(f"{BASE_URL}/api/training/upload-file", files=files)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["filename"] == "test_document.txt"
        assert data["chars_extracted"] > 0
        print(f"✓ TXT file upload success: {data['chars_extracted']} chars extracted")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_upload_unsupported_file_rejected(self):
        """Unsupported file type should return 400"""
        content = b"<html><body>test</body></html>"
        files = {"file": ("test.html", content, "text/html")}
        response = requests.post(f"{BASE_URL}/api/training/upload-file", files=files)
        assert response.status_code == 400
        assert "Supported" in response.json().get("detail", "")
        print("✓ Unsupported file type rejected with 400")
    
    # ============================================================
    # GET /api/training/queue
    # ============================================================
    def test_get_training_queue(self):
        """Get training queue with status counts"""
        response = requests.get(f"{BASE_URL}/api/training/queue")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "pending" in data
        assert "ready" in data
        assert "processed" in data
        assert isinstance(data["items"], list)
        print(f"✓ Training queue: {data['total']} items (pending={data['pending']}, ready={data['ready']}, processed={data['processed']})")
    
    # ============================================================
    # DELETE /api/training/queue/{id}
    # ============================================================
    def test_delete_training_item(self):
        """Delete item from training queue"""
        # First add an item
        unique_url = f"https://delete-test-{uuid.uuid4().hex[:8]}.com/article"
        add_res = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": unique_url})
        assert add_res.status_code == 200
        item_id = add_res.json()["id"]
        
        # Delete it
        del_res = requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
        assert del_res.status_code == 200
        assert "removed" in del_res.json().get("message", "").lower()
        print("✓ Training item deleted successfully")
    
    def test_delete_nonexistent_item(self):
        """Delete non-existent item should return 404"""
        response = requests.delete(f"{BASE_URL}/api/training/queue/nonexistent-id-12345")
        assert response.status_code == 404
        print("✓ Delete non-existent item returns 404")
    
    # ============================================================
    # POST /api/training/run
    # ============================================================
    def test_training_run_no_pending(self):
        """Training run with no pending items should return 400"""
        # First ensure queue is empty of pending items
        queue_res = requests.get(f"{BASE_URL}/api/training/queue")
        pending_count = queue_res.json().get("pending", 0) + queue_res.json().get("ready", 0)
        
        if pending_count == 0:
            response = requests.post(f"{BASE_URL}/api/training/run")
            assert response.status_code == 400
            assert "no pending" in response.json().get("detail", "").lower()
            print("✓ Training run with no pending items returns 400")
        else:
            print(f"⚠ Skipping test - {pending_count} pending items in queue")
    
    # ============================================================
    # GET /api/training/progress
    # ============================================================
    def test_get_training_progress(self):
        """Get training progress status"""
        response = requests.get(f"{BASE_URL}/api/training/progress")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "total" in data
        assert "current" in data
        assert "completed" in data
        assert "errors" in data
        print(f"✓ Training progress: running={data['running']}, {data['completed']}/{data['total']} completed")
    
    # ============================================================
    # GET /api/training/insights
    # ============================================================
    def test_get_training_insights(self):
        """Get aggregated training insights"""
        response = requests.get(f"{BASE_URL}/api/training/insights")
        assert response.status_code == 200
        data = response.json()
        assert "has_data" in data
        assert "positive_signals" in data
        assert "priority_regions" in data
        assert "key_actors" in data
        print(f"✓ Training insights: has_data={data['has_data']}, items_processed={data.get('items_processed', 0)}")


class TestFeedbackSystem:
    """Feedback endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get a valid intelligence item ID for testing"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if response.status_code == 200 and response.json().get("items"):
            self.test_item_id = response.json()["items"][0]["id"]
        else:
            self.test_item_id = None
    
    # ============================================================
    # POST /api/feedback
    # ============================================================
    def test_submit_feedback_success(self):
        """Submit a rating for an intelligence item"""
        if not self.test_item_id:
            pytest.skip("No intelligence items available")
        
        device_id = f"test_device_{uuid.uuid4().hex[:8]}"
        response = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.test_item_id,
            "device_id": device_id,
            "rating": 5
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["rating"] == 5
        assert data["action"] in ["created", "updated"]
        print(f"✓ Feedback submitted: action={data['action']}, rating={data['rating']}")
    
    def test_submit_feedback_update_existing(self):
        """Update existing rating (same device_id)"""
        if not self.test_item_id:
            pytest.skip("No intelligence items available")
        
        device_id = f"test_device_update_{uuid.uuid4().hex[:8]}"
        
        # First submission
        res1 = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.test_item_id,
            "device_id": device_id,
            "rating": 3
        })
        assert res1.status_code == 200
        assert res1.json()["action"] == "created"
        
        # Update
        res2 = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.test_item_id,
            "device_id": device_id,
            "rating": 5
        })
        assert res2.status_code == 200
        assert res2.json()["action"] == "updated"
        assert res2.json()["rating"] == 5
        print("✓ Feedback update works correctly")
    
    def test_submit_feedback_invalid_rating(self):
        """Invalid rating values should return 400"""
        if not self.test_item_id:
            pytest.skip("No intelligence items available")
        
        # Rating < 1
        res1 = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.test_item_id,
            "device_id": "test_device",
            "rating": 0
        })
        assert res1.status_code == 400
        
        # Rating > 6
        res2 = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": self.test_item_id,
            "device_id": "test_device",
            "rating": 7
        })
        assert res2.status_code == 400
        print("✓ Invalid ratings rejected with 400")
    
    def test_submit_feedback_missing_fields(self):
        """Missing required fields should return 400"""
        # Missing intelligence_id
        res1 = requests.post(f"{BASE_URL}/api/feedback", json={
            "device_id": "test",
            "rating": 5
        })
        assert res1.status_code == 400
        
        # Missing device_id
        res2 = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": "test",
            "rating": 5
        })
        assert res2.status_code == 400
        print("✓ Missing fields rejected with 400")
    
    def test_submit_feedback_nonexistent_item(self):
        """Feedback for non-existent item should return 404"""
        response = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": "nonexistent-item-12345",
            "device_id": "test_device",
            "rating": 5
        })
        assert response.status_code == 404
        print("✓ Non-existent item returns 404")
    
    # ============================================================
    # POST /api/feedback/batch
    # ============================================================
    def test_batch_feedback(self):
        """Batch fetch feedback for multiple items"""
        # Get some item IDs
        items_res = requests.get(f"{BASE_URL}/api/intelligence?limit=3")
        if items_res.status_code != 200 or not items_res.json().get("items"):
            pytest.skip("No intelligence items available")
        
        item_ids = [i["id"] for i in items_res.json()["items"]]
        
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json={
            "item_ids": item_ids,
            "device_id": "test_device"
        })
        assert response.status_code == 200
        data = response.json()
        assert "feedback" in data
        assert isinstance(data["feedback"], dict)
        
        # Check structure for each item
        for item_id in item_ids:
            if item_id in data["feedback"]:
                fb = data["feedback"][item_id]
                assert "total_ratings" in fb
                assert "avg_rating" in fb
                assert "limit_reached" in fb
                assert "max_limit" in fb
        print(f"✓ Batch feedback returned for {len(data['feedback'])} items")
    
    def test_batch_feedback_empty_rejected(self):
        """Empty item_ids should return 400"""
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json={
            "item_ids": [],
            "device_id": "test"
        })
        assert response.status_code == 400
        print("✓ Empty batch rejected with 400")
    
    def test_batch_feedback_too_many_rejected(self):
        """More than 50 item_ids should return 400"""
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json={
            "item_ids": [f"item_{i}" for i in range(51)],
            "device_id": "test"
        })
        assert response.status_code == 400
        print("✓ Batch > 50 items rejected with 400")
    
    # ============================================================
    # GET /api/feedback/stats
    # ============================================================
    def test_get_feedback_stats(self):
        """Get global feedback statistics"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_feedback" in data
        assert "unique_items_rated" in data
        assert "unique_devices" in data
        assert "global_avg_rating" in data
        assert "distribution" in data
        assert "max_feedback_per_item" in data
        print(f"✓ Feedback stats: total={data['total_feedback']}, avg={data['global_avg_rating']}")
    
    # ============================================================
    # GET /api/feedback/training-profile
    # ============================================================
    def test_get_training_profile(self):
        """Get analyst training profile"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        data = response.json()
        assert "total_feedback" in data
        assert "unique_items_rated" in data
        assert "confidence_level" in data
        assert "positive_weights" in data
        assert "negative_weights" in data
        print(f"✓ Training profile: confidence={data['confidence_level']}, total={data['total_feedback']}")


class TestFeedbackSettings:
    """Feedback settings endpoint tests"""
    
    # ============================================================
    # GET /api/settings/feedback
    # ============================================================
    def test_get_feedback_settings(self):
        """Get max feedback per item setting"""
        response = requests.get(f"{BASE_URL}/api/settings/feedback")
        assert response.status_code == 200
        data = response.json()
        assert "max_feedback_per_item" in data
        assert isinstance(data["max_feedback_per_item"], int)
        print(f"✓ Feedback settings: max_feedback_per_item={data['max_feedback_per_item']}")
    
    # ============================================================
    # PUT /api/settings/feedback
    # ============================================================
    def test_update_feedback_settings(self):
        """Update max feedback per item setting"""
        # Get current value
        get_res = requests.get(f"{BASE_URL}/api/settings/feedback")
        original_value = get_res.json()["max_feedback_per_item"]
        
        # Update to new value
        new_value = 30
        response = requests.put(f"{BASE_URL}/api/settings/feedback", json={
            "max_feedback_per_item": new_value
        })
        assert response.status_code == 200
        assert response.json()["max_feedback_per_item"] == new_value
        
        # Verify change
        verify_res = requests.get(f"{BASE_URL}/api/settings/feedback")
        assert verify_res.json()["max_feedback_per_item"] == new_value
        
        # Restore original
        requests.put(f"{BASE_URL}/api/settings/feedback", json={
            "max_feedback_per_item": original_value
        })
        print(f"✓ Feedback settings updated: {original_value} -> {new_value} -> {original_value}")
    
    def test_update_feedback_settings_invalid_values(self):
        """Invalid values should return 400"""
        # Value < 1
        res1 = requests.put(f"{BASE_URL}/api/settings/feedback", json={
            "max_feedback_per_item": 0
        })
        assert res1.status_code == 400
        
        # Value > 500
        res2 = requests.put(f"{BASE_URL}/api/settings/feedback", json={
            "max_feedback_per_item": 501
        })
        assert res2.status_code == 400
        
        # Non-integer
        res3 = requests.put(f"{BASE_URL}/api/settings/feedback", json={
            "max_feedback_per_item": "twenty"
        })
        assert res3.status_code == 400
        print("✓ Invalid feedback settings rejected with 400")


class TestRouteOrdering:
    """Verify static routes work (come before dynamic {id} route)"""
    
    def test_feedback_stats_route(self):
        """GET /api/feedback/stats should work (not match /{id})"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        assert "total_feedback" in response.json()
        print("✓ /feedback/stats route works correctly")
    
    def test_feedback_training_profile_route(self):
        """GET /api/feedback/training-profile should work"""
        response = requests.get(f"{BASE_URL}/api/feedback/training-profile")
        assert response.status_code == 200
        assert "confidence_level" in response.json()
        print("✓ /feedback/training-profile route works correctly")
    
    def test_feedback_batch_route(self):
        """POST /api/feedback/batch should work"""
        response = requests.post(f"{BASE_URL}/api/feedback/batch", json={
            "item_ids": ["test-id"],
            "device_id": "test"
        })
        # Should return 200 (even if items don't exist, it returns empty feedback)
        assert response.status_code == 200
        print("✓ /feedback/batch route works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
