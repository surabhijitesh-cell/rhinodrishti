"""
Test suite for Manual Intelligence Uploads - Add to Feed feature (Iteration 33)
Tests the new POST /api/add-to-feed endpoint and related functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAddToFeedEndpoint:
    """Tests for POST /api/add-to-feed endpoint"""
    
    def test_add_to_feed_with_user_title(self):
        """Test adding URL to feed with user-provided title (scraping may fail)"""
        unique_url = f"https://example.com/test-article-{int(time.time())}"
        payload = {
            "url": unique_url,
            "title": "TEST_Manual Add Article",
            "severity": "high",
            "priority_score": 75,
            "threat_category": "Border Incursion",
            "state": "Manipur",
            "ai_summary": "Test summary for manual add",
            "is_cross_border": True,
            "tags": ["test", "manual"]
        }
        
        response = requests.post(f"{BASE_URL}/api/add-to-feed", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "item_id" in data
        assert data["title"] == "TEST_Manual Add Article"
        assert data["severity"] == "high"
        assert data["priority_score"] == 75
        assert data["message"] == "Article added to intelligence feed"
    
    def test_add_to_feed_duplicate_url_returns_409(self):
        """Test that adding duplicate URL returns 409 Conflict"""
        # This URL was already added during development
        duplicate_url = "https://www.ndtv.com/india-news"
        payload = {
            "url": duplicate_url,
            "title": "Duplicate Test",
            "severity": "medium",
            "priority_score": 50
        }
        
        response = requests.post(f"{BASE_URL}/api/add-to-feed", json=payload)
        assert response.status_code == 409, f"Expected 409 for duplicate, got {response.status_code}"
        
        data = response.json()
        assert "already exists" in data.get("detail", "").lower()
    
    def test_add_to_feed_invalid_url_returns_400(self):
        """Test that invalid URL returns 400"""
        payload = {
            "url": "not-a-valid-url",
            "title": "Test",
            "severity": "medium"
        }
        
        response = requests.post(f"{BASE_URL}/api/add-to-feed", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid URL, got {response.status_code}"
    
    def test_add_to_feed_severity_validation(self):
        """Test that invalid severity defaults to medium"""
        unique_url = f"https://example.com/severity-test-{int(time.time())}"
        payload = {
            "url": unique_url,
            "title": "TEST_Severity Validation",
            "severity": "invalid_severity",
            "priority_score": 50
        }
        
        response = requests.post(f"{BASE_URL}/api/add-to-feed", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["severity"] == "medium"  # Should default to medium
    
    def test_add_to_feed_priority_score_clamping(self):
        """Test that priority score is clamped to 0-100"""
        unique_url = f"https://example.com/priority-test-{int(time.time())}"
        payload = {
            "url": unique_url,
            "title": "TEST_Priority Clamping",
            "severity": "high",
            "priority_score": 150  # Should be clamped to 100
        }
        
        response = requests.post(f"{BASE_URL}/api/add-to-feed", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["priority_score"] == 100  # Clamped to max


class TestAddedItemsInFeed:
    """Tests to verify added items appear in intelligence feed"""
    
    def test_added_item_appears_in_intelligence_feed(self):
        """Test that manually added items appear in /api/intelligence"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=50")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        # Look for items with "Manual Upload" source
        manual_items = [i for i in items if i.get("source") == "Manual Upload"]
        assert len(manual_items) > 0, "No manually uploaded items found in feed"
        
        # Verify structure of manual items
        for item in manual_items:
            assert "id" in item
            assert "title" in item
            assert "severity" in item
            assert "source_url" in item
            assert item["source"] == "Manual Upload"
    
    def test_added_item_has_correct_fields(self):
        """Test that added items have all required fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=50")
        assert response.status_code == 200
        
        data = response.json()
        items = data.get("items", [])
        
        # Find our test item
        test_items = [i for i in items if "TEST_" in i.get("title", "")]
        
        if test_items:
            item = test_items[0]
            # Verify all expected fields
            assert "id" in item
            assert "title" in item
            assert "source" in item
            assert "source_url" in item
            assert "severity" in item
            assert "priority_score" in item
            assert "threat_category" in item
            assert "state" in item
            assert "processed" in item
            assert item["processed"] == True


class TestAnalyzeURLEndpoint:
    """Tests for POST /api/analyze-url endpoint (existing functionality)"""
    
    def test_analyze_url_returns_document_id(self):
        """Test that analyze-url returns a document ID for tracking"""
        payload = {
            "url": "https://www.bbc.com/news",
            "analysis_query": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/analyze-url", json=payload)
        # May fail if URL is blocked, but should return proper error
        if response.status_code == 200:
            data = response.json()
            assert "document_id" in data
            assert "filename" in data
        else:
            # URL fetch failed - acceptable
            assert response.status_code == 400
    
    def test_analyze_url_invalid_url(self):
        """Test that invalid URL returns 400"""
        payload = {
            "url": "not-a-url",
            "analysis_query": ""
        }
        
        response = requests.post(f"{BASE_URL}/api/analyze-url", json=payload)
        assert response.status_code == 400


class TestUploadedDocuments:
    """Tests for uploaded documents endpoints"""
    
    def test_get_uploaded_documents(self):
        """Test GET /api/uploaded-documents returns list"""
        response = requests.get(f"{BASE_URL}/api/uploaded-documents")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        assert "count" in data
        assert isinstance(data["documents"], list)


class TestRegressionKeywordEngine:
    """Regression tests for Keyword Engine"""
    
    def test_keywords_endpoint(self):
        """Test GET /api/keywords returns keywords"""
        response = requests.get(f"{BASE_URL}/api/keywords")
        assert response.status_code == 200
        
        data = response.json()
        assert "keywords" in data
        assert isinstance(data["keywords"], list)


class TestRegressionSettings:
    """Regression tests for Settings endpoints"""
    
    def test_get_bias_settings(self):
        """Test GET /api/settings/bias returns current settings"""
        response = requests.get(f"{BASE_URL}/api/settings/bias")
        assert response.status_code == 200
        
        data = response.json()
        assert "bias_window" in data
        assert "bias_influence" in data
    
    def test_get_retention_settings(self):
        """Test GET /api/settings/retention returns current settings"""
        response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert response.status_code == 200


class TestAuthLogin:
    """Test authentication"""
    
    def test_admin_login(self):
        """Test admin login works"""
        payload = {
            "username": "admin",
            "password": "Admin@2026!"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
