"""
Test Training Relevance Tagging & Activity Log - Iteration 19
Tests:
- URL relevance tagging (1-6 integer) on add-url endpoint
- Activity log endpoint with entries, summary, and ai_impact
- Activity log records url_added, file_uploaded events
- Queue items show relevance field
- Existing endpoints still work
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestURLRelevanceTagging:
    """Tests for URL relevance tagging feature (1-6 scale)"""
    
    # ============================================================
    # POST /api/training/add-url with relevance field
    # ============================================================
    def test_add_url_with_relevance_1(self):
        """Add URL with relevance=1 (lowest)"""
        unique_url = f"https://relevance-test-1-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 1
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "id" in data
        assert data.get("relevance") == 1, f"Expected relevance=1, got {data.get('relevance')}"
        print(f"✓ Add URL with relevance=1 success: {data['id']}")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_add_url_with_relevance_6(self):
        """Add URL with relevance=6 (highest)"""
        unique_url = f"https://relevance-test-6-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 6
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("relevance") == 6, f"Expected relevance=6, got {data.get('relevance')}"
        print(f"✓ Add URL with relevance=6 success")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_add_url_with_relevance_3(self):
        """Add URL with relevance=3 (middle value)"""
        unique_url = f"https://relevance-test-3-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 3
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("relevance") == 3
        print(f"✓ Add URL with relevance=3 success")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_add_url_without_relevance(self):
        """Add URL without relevance (optional field)"""
        unique_url = f"https://no-relevance-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("relevance") is None, f"Expected relevance=None, got {data.get('relevance')}"
        print(f"✓ Add URL without relevance success (relevance=None)")
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{data['id']}")
    
    def test_add_url_relevance_0_rejected(self):
        """Relevance=0 should be rejected (must be 1-6)"""
        unique_url = f"https://invalid-rel-0-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 0
        })
        assert response.status_code == 400, f"Expected 400 for relevance=0, got {response.status_code}"
        assert "1-6" in response.json().get("detail", "")
        print("✓ Relevance=0 rejected with 400")
    
    def test_add_url_relevance_7_rejected(self):
        """Relevance=7 should be rejected (must be 1-6)"""
        unique_url = f"https://invalid-rel-7-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 7
        })
        assert response.status_code == 400, f"Expected 400 for relevance=7, got {response.status_code}"
        assert "1-6" in response.json().get("detail", "")
        print("✓ Relevance=7 rejected with 400")
    
    def test_add_url_relevance_string_rejected(self):
        """Relevance='abc' should be rejected (must be integer)"""
        unique_url = f"https://invalid-rel-str-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": "abc"
        })
        assert response.status_code == 400, f"Expected 400 for relevance='abc', got {response.status_code}"
        print("✓ Relevance='abc' rejected with 400")
    
    def test_add_url_relevance_float_rejected(self):
        """Relevance=3.5 should be rejected (must be integer)"""
        unique_url = f"https://invalid-rel-float-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 3.5
        })
        assert response.status_code == 400, f"Expected 400 for relevance=3.5, got {response.status_code}"
        print("✓ Relevance=3.5 rejected with 400")


class TestQueueRelevanceDisplay:
    """Tests for relevance field in training queue"""
    
    def test_queue_shows_relevance_on_items(self):
        """Queue items should show relevance field when set"""
        # Add item with relevance
        unique_url = f"https://queue-rel-test-{uuid.uuid4().hex[:8]}.com/article"
        add_res = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 4
        })
        assert add_res.status_code == 200
        item_id = add_res.json()["id"]
        
        # Get queue and find our item
        queue_res = requests.get(f"{BASE_URL}/api/training/queue")
        assert queue_res.status_code == 200
        items = queue_res.json().get("items", [])
        
        our_item = next((i for i in items if i["id"] == item_id), None)
        assert our_item is not None, "Item not found in queue"
        assert our_item.get("relevance") == 4, f"Expected relevance=4, got {our_item.get('relevance')}"
        print(f"✓ Queue item shows relevance=4")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
    
    def test_queue_shows_null_relevance_when_not_set(self):
        """Queue items should show relevance=null when not set"""
        unique_url = f"https://queue-no-rel-{uuid.uuid4().hex[:8]}.com/article"
        add_res = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url
        })
        assert add_res.status_code == 200
        item_id = add_res.json()["id"]
        
        queue_res = requests.get(f"{BASE_URL}/api/training/queue")
        items = queue_res.json().get("items", [])
        our_item = next((i for i in items if i["id"] == item_id), None)
        assert our_item is not None
        assert our_item.get("relevance") is None
        print(f"✓ Queue item shows relevance=null when not set")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")


class TestActivityLog:
    """Tests for Training Activity Log endpoint"""
    
    # ============================================================
    # GET /api/training/activity-log
    # ============================================================
    def test_activity_log_returns_entries(self):
        """Activity log should return entries array"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "entries" in data, "Response missing 'entries' field"
        assert isinstance(data["entries"], list), "entries should be a list"
        print(f"✓ Activity log returns {len(data['entries'])} entries")
    
    def test_activity_log_returns_summary(self):
        """Activity log should return summary stats"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200
        data = response.json()
        
        assert "summary" in data, "Response missing 'summary' field"
        summary = data["summary"]
        
        # Check required summary fields
        assert "total_feedback_ratings" in summary, "summary missing total_feedback_ratings"
        assert "recent_feedback_7d" in summary, "summary missing recent_feedback_7d"
        assert "total_items_trained" in summary, "summary missing total_items_trained"
        assert "training_errors" in summary, "summary missing training_errors"
        assert "items_with_relevance_tag" in summary, "summary missing items_with_relevance_tag"
        
        print(f"✓ Activity log summary: feedback={summary['total_feedback_ratings']}, trained={summary['total_items_trained']}, relevance_tagged={summary['items_with_relevance_tag']}")
    
    def test_activity_log_returns_ai_impact(self):
        """Activity log should return ai_impact data"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200
        data = response.json()
        
        assert "ai_impact" in data, "Response missing 'ai_impact' field"
        ai_impact = data["ai_impact"]
        
        # Check required ai_impact fields
        assert "regions_learned" in ai_impact, "ai_impact missing regions_learned"
        assert "actors_learned" in ai_impact, "ai_impact missing actors_learned"
        assert "keywords_learned" in ai_impact, "ai_impact missing keywords_learned"
        assert "total_successful" in ai_impact, "ai_impact missing total_successful"
        
        print(f"✓ Activity log ai_impact: total_successful={ai_impact['total_successful']}, regions={len(ai_impact['regions_learned'])}, actors={len(ai_impact['actors_learned'])}")
    
    def test_activity_log_records_url_added_event(self):
        """Adding a URL should create url_added activity entry"""
        # Add a URL with relevance
        unique_url = f"https://activity-url-test-{uuid.uuid4().hex[:8]}.com/article"
        add_res = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": unique_url,
            "relevance": 5
        })
        assert add_res.status_code == 200
        item_id = add_res.json()["id"]
        
        # Check activity log for the entry
        log_res = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert log_res.status_code == 200
        entries = log_res.json().get("entries", [])
        
        # Find our entry (should be recent, at the top)
        url_entries = [e for e in entries if e.get("type") == "url_added" and unique_url[:30] in e.get("description", "")]
        assert len(url_entries) > 0, f"No url_added entry found for {unique_url[:30]}"
        
        entry = url_entries[0]
        assert entry.get("item_id") == item_id, f"Entry item_id mismatch"
        assert entry.get("relevance_tag") == 5, f"Expected relevance_tag=5, got {entry.get('relevance_tag')}"
        print(f"✓ Activity log recorded url_added event with relevance_tag=5")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
    
    def test_activity_log_records_file_uploaded_event(self):
        """Uploading a file should create file_uploaded activity entry"""
        # Upload a file
        content = b"Test content for activity log testing."
        files = {"file": (f"activity_test_{uuid.uuid4().hex[:8]}.txt", content, "text/plain")}
        upload_res = requests.post(f"{BASE_URL}/api/training/upload-file", files=files)
        assert upload_res.status_code == 200
        item_id = upload_res.json()["id"]
        filename = upload_res.json()["filename"]
        
        # Check activity log for the entry
        log_res = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert log_res.status_code == 200
        entries = log_res.json().get("entries", [])
        
        # Find our entry
        file_entries = [e for e in entries if e.get("type") == "file_uploaded" and filename[:20] in e.get("description", "")]
        assert len(file_entries) > 0, f"No file_uploaded entry found for {filename}"
        
        entry = file_entries[0]
        assert entry.get("item_id") == item_id
        assert entry.get("relevance_tag") is None  # Files don't have relevance tag
        print(f"✓ Activity log recorded file_uploaded event")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
    
    def test_activity_log_entry_structure(self):
        """Activity log entries should have required fields"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200
        entries = response.json().get("entries", [])
        
        if len(entries) > 0:
            entry = entries[0]
            assert "id" in entry, "Entry missing 'id'"
            assert "type" in entry, "Entry missing 'type'"
            assert "description" in entry, "Entry missing 'description'"
            assert "timestamp" in entry, "Entry missing 'timestamp'"
            assert entry["type"] in ["url_added", "file_uploaded", "training_run"], f"Unknown entry type: {entry['type']}"
            print(f"✓ Activity log entry structure valid: type={entry['type']}")
        else:
            print("⚠ No entries to validate structure (empty log)")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after new features"""
    
    def test_feedback_submit_still_works(self):
        """POST /api/feedback should still work"""
        # Get an intelligence item
        items_res = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if items_res.status_code != 200 or not items_res.json().get("items"):
            pytest.skip("No intelligence items available")
        
        item_id = items_res.json()["items"][0]["id"]
        device_id = f"test_existing_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": item_id,
            "device_id": device_id,
            "rating": 4
        })
        assert response.status_code == 200
        assert response.json()["rating"] == 4
        print("✓ POST /api/feedback still works")
    
    def test_feedback_stats_still_works(self):
        """GET /api/feedback/stats should still work"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_feedback" in data
        assert "global_avg_rating" in data
        print(f"✓ GET /api/feedback/stats still works: total={data['total_feedback']}")
    
    def test_training_queue_still_works(self):
        """GET /api/training/queue should still work"""
        response = requests.get(f"{BASE_URL}/api/training/queue")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ GET /api/training/queue still works: {data['total']} items")
    
    def test_training_insights_still_works(self):
        """GET /api/training/insights should still work"""
        response = requests.get(f"{BASE_URL}/api/training/insights")
        assert response.status_code == 200
        data = response.json()
        assert "has_data" in data
        assert "positive_signals" in data
        print(f"✓ GET /api/training/insights still works: has_data={data['has_data']}")
    
    def test_training_progress_still_works(self):
        """GET /api/training/progress should still work"""
        response = requests.get(f"{BASE_URL}/api/training/progress")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert "total" in data
        print(f"✓ GET /api/training/progress still works: running={data['running']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
