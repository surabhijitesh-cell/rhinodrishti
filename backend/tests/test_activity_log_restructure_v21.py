"""
Iteration 21: Test Activity Log Restructure
- GET /api/training/activity-log returns paginated results with entries, total, page, page_size, total_pages
- Activity log only contains training_session and feedback_session entries (no url_added or file_uploaded)
- POST /api/training/add-url no longer creates activity log entries
- POST /api/feedback triggers feedback session aggregation after 5+ ratings from same device
- Feedback session entry has correct structure
- Existing endpoints still work
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestActivityLogPagination:
    """Test GET /api/training/activity-log pagination"""
    
    def test_activity_log_returns_200(self):
        """Activity log endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/training/activity-log returns 200")
    
    def test_activity_log_has_pagination_fields(self):
        """Activity log response has required pagination fields"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        required_fields = ["entries", "total", "page", "page_size", "total_pages"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        assert isinstance(data["entries"], list), "entries should be a list"
        assert isinstance(data["total"], int), "total should be int"
        assert isinstance(data["page"], int), "page should be int"
        assert isinstance(data["page_size"], int), "page_size should be int"
        assert isinstance(data["total_pages"], int), "total_pages should be int"
        
        print(f"PASS: Activity log has pagination fields - total={data['total']}, page={data['page']}, total_pages={data['total_pages']}")
    
    def test_activity_log_page_parameter(self):
        """Activity log accepts page parameter"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log?page=1")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1, f"Expected page=1, got {data['page']}"
        print("PASS: GET /api/training/activity-log?page=1 works correctly")
    
    def test_activity_log_only_session_entries(self):
        """Activity log only contains training_session and feedback_session entries"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        valid_types = ["training_session", "feedback_session"]
        for entry in data["entries"]:
            assert entry.get("activity_type") in valid_types, \
                f"Invalid activity_type: {entry.get('activity_type')}. Expected one of {valid_types}"
        
        print(f"PASS: All {len(data['entries'])} entries are session-level (training_session or feedback_session)")


class TestAddUrlNoActivityLog:
    """Test that POST /api/training/add-url no longer creates activity log entries"""
    
    def test_add_url_no_activity_log_entry(self):
        """Adding URL should NOT create activity log entry"""
        # Get current activity log count
        before_response = requests.get(f"{BASE_URL}/api/training/activity-log")
        before_data = before_response.json()
        before_total = before_data["total"]
        
        # Add a URL
        test_url = f"https://example.com/test-no-log-{uuid.uuid4()}"
        add_response = requests.post(f"{BASE_URL}/api/training/add-url", json={"url": test_url})
        assert add_response.status_code == 200, f"Failed to add URL: {add_response.text}"
        
        # Check activity log count hasn't changed
        after_response = requests.get(f"{BASE_URL}/api/training/activity-log")
        after_data = after_response.json()
        after_total = after_data["total"]
        
        assert after_total == before_total, \
            f"Activity log count changed from {before_total} to {after_total} after adding URL"
        
        # Cleanup - delete the added URL
        item_id = add_response.json().get("id")
        if item_id:
            requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
        
        print("PASS: POST /api/training/add-url no longer creates activity log entries")


class TestFeedbackSessionAggregation:
    """Test feedback session aggregation after 5+ ratings from same device"""
    
    def test_feedback_session_creation_after_5_ratings(self):
        """Submitting 5+ ratings from same device triggers feedback session"""
        # Use a unique device ID for this test
        test_device_id = f"test-device-v21-{uuid.uuid4()}"
        
        # Get current activity log count
        before_response = requests.get(f"{BASE_URL}/api/training/activity-log")
        before_data = before_response.json()
        before_total = before_data["total"]
        
        # Get some intelligence items to rate
        intel_response = requests.get(f"{BASE_URL}/api/intelligence?limit=10")
        assert intel_response.status_code == 200, f"Failed to get intelligence items: {intel_response.text}"
        intel_data = intel_response.json()
        items = intel_data.get("items", [])
        
        if len(items) < 5:
            pytest.skip("Not enough intelligence items to test (need at least 5)")
        
        # Submit 5 ratings from the same device
        ratings_submitted = []
        for i, item in enumerate(items[:5]):
            rating = (i % 6) + 1  # Ratings 1-6
            response = requests.post(f"{BASE_URL}/api/feedback", json={
                "intelligence_id": item["id"],
                "device_id": test_device_id,
                "rating": rating
            })
            assert response.status_code == 200, f"Failed to submit rating: {response.text}"
            ratings_submitted.append(rating)
            print(f"  Submitted rating {rating} for item {i+1}")
        
        # Wait for background task to complete (async processing)
        print("  Waiting 6 seconds for background task...")
        time.sleep(6)
        
        # Check activity log for new feedback_session entry
        after_response = requests.get(f"{BASE_URL}/api/training/activity-log")
        after_data = after_response.json()
        after_total = after_data["total"]
        
        # Find the feedback session for our device
        feedback_sessions = [
            e for e in after_data["entries"] 
            if e.get("activity_type") == "feedback_session" and e.get("device_id") == test_device_id[-6:]
        ]
        
        assert len(feedback_sessions) > 0, \
            f"No feedback_session created for device {test_device_id[-6:]} after 5 ratings"
        
        session = feedback_sessions[0]
        print(f"PASS: Feedback session created after 5 ratings - device_id={session.get('device_id')}")
        
        return session
    
    def test_feedback_session_structure(self):
        """Feedback session entry has correct structure"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        # Find a feedback_session entry
        feedback_sessions = [e for e in data["entries"] if e.get("activity_type") == "feedback_session"]
        
        if not feedback_sessions:
            pytest.skip("No feedback_session entries found to test structure")
        
        session = feedback_sessions[0]
        
        # Check required fields
        required_fields = ["id", "activity_type", "timestamp", "device_id", "total_items", "volume", "impact_summary"]
        for field in required_fields:
            assert field in session, f"Missing field in feedback_session: {field}"
        
        # Validate field types
        assert session["activity_type"] == "feedback_session"
        assert isinstance(session["device_id"], str), "device_id should be string"
        assert isinstance(session["total_items"], int), "total_items should be int"
        assert isinstance(session["volume"], str), "volume should be string"
        assert isinstance(session["impact_summary"], str), "impact_summary should be string"
        
        print(f"PASS: Feedback session has correct structure - id={session['id']}, device_id={session['device_id']}")
    
    def test_feedback_session_volume_format(self):
        """Feedback session volume shows rating breakdown format"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        feedback_sessions = [e for e in data["entries"] if e.get("activity_type") == "feedback_session"]
        
        if not feedback_sessions:
            pytest.skip("No feedback_session entries found to test volume format")
        
        session = feedback_sessions[0]
        volume = session.get("volume", "")
        
        # Volume should be like "5 ratings (1x3, 2x4, 1x5, 1x6)"
        assert "ratings" in volume.lower() or "rating" in volume.lower(), \
            f"Volume should contain 'ratings': {volume}"
        
        print(f"PASS: Feedback session volume format correct: '{volume}'")
    
    def test_feedback_session_impact_summary_not_empty(self):
        """Feedback session impact_summary is AI-generated text (not empty)"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        feedback_sessions = [e for e in data["entries"] if e.get("activity_type") == "feedback_session"]
        
        if not feedback_sessions:
            pytest.skip("No feedback_session entries found to test impact_summary")
        
        session = feedback_sessions[0]
        impact = session.get("impact_summary", "")
        
        assert impact and len(impact) > 10, \
            f"impact_summary should be non-empty AI-generated text, got: '{impact}'"
        
        print(f"PASS: Feedback session impact_summary is AI-generated: '{impact[:100]}...'")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after restructure"""
    
    def test_training_effectiveness_endpoint(self):
        """GET /api/training/effectiveness still works"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "score" in data or "grade" in data, "Response should have score or grade"
        print(f"PASS: GET /api/training/effectiveness works - score={data.get('score')}, grade={data.get('grade')}")
    
    def test_training_queue_endpoint(self):
        """GET /api/training/queue still works"""
        response = requests.get(f"{BASE_URL}/api/training/queue")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Response should have items"
        print(f"PASS: GET /api/training/queue works - {len(data.get('items', []))} items")
    
    def test_feedback_stats_endpoint(self):
        """GET /api/feedback/stats still works"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "total_feedback" in data, "Response should have total_feedback"
        print(f"PASS: GET /api/feedback/stats works - total_feedback={data.get('total_feedback')}")
    
    def test_feedback_post_endpoint(self):
        """POST /api/feedback still works"""
        # Get an intelligence item
        intel_response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        if intel_response.status_code != 200:
            pytest.skip("Cannot get intelligence items")
        
        items = intel_response.json().get("items", [])
        if not items:
            pytest.skip("No intelligence items available")
        
        # Submit a rating
        test_device = f"test-existing-{uuid.uuid4()}"
        response = requests.post(f"{BASE_URL}/api/feedback", json={
            "intelligence_id": items[0]["id"],
            "device_id": test_device,
            "rating": 4
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should have message"
        print(f"PASS: POST /api/feedback works - {data.get('message')}")


class TestTrainingSessionEntry:
    """Test training_session entry structure (if any exist)"""
    
    def test_training_session_structure(self):
        """Training session entry has correct structure"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        data = response.json()
        
        training_sessions = [e for e in data["entries"] if e.get("activity_type") == "training_session"]
        
        if not training_sessions:
            pytest.skip("No training_session entries found to test structure")
        
        session = training_sessions[0]
        
        # Check required fields
        required_fields = ["id", "activity_type", "timestamp", "volume", "impact_summary"]
        for field in required_fields:
            assert field in session, f"Missing field in training_session: {field}"
        
        assert session["activity_type"] == "training_session"
        assert isinstance(session["volume"], str), "volume should be string"
        assert isinstance(session["impact_summary"], str), "impact_summary should be string"
        
        print(f"PASS: Training session has correct structure - id={session['id']}, volume={session['volume']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
