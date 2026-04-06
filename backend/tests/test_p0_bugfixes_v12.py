"""
Test P0 Bug Fixes - Iteration 12
================================
Tests for two critical P0 bugs that were fixed:
1. OpenAI Embeddings 401 error - fixed by using OPENAI_API_KEY instead of EMERGENT_LLM_KEY
2. Custom Daily Brief PDF 500 error - fixed by using explicit effective_w in fpdf2 calls

Also tests general API health and the features mentioned in the review request.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Rhino Drishti" in data["message"]
        print(f"✓ API root: {data['message']}")

    def test_pipeline_status(self):
        """Test pipeline status endpoint returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert "total_items" in data
        assert "ai_processed" in data
        assert "pending_retry" in data
        assert "processing_rate" in data
        assert "rss_sources" in data
        assert "scheduler" in data
        assert "rate_limit_config" in data
        
        print(f"✓ Pipeline status: {data['total_items']} total items, {data['ai_processed']} processed")
        print(f"  Scheduler: {data['scheduler']}")


class TestIntelligenceFeed:
    """Test intelligence feed endpoints"""
    
    def test_get_intelligence_returns_items(self):
        """Test GET /api/intelligence returns items with 30-day retention"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pages" in data
        
        # Should have items within 30-day retention window
        assert data["total"] > 0, "Expected items within retention window"
        assert len(data["items"]) > 0
        
        print(f"✓ Intelligence feed: {data['total']} total items, {len(data['items'])} returned")
    
    def test_intelligence_item_structure(self):
        """Test intelligence items have expected fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0
        item = data["items"][0]
        
        # Check required fields
        required_fields = ["id", "title", "source", "published_at", "severity", "state"]
        for field in required_fields:
            assert field in item, f"Missing field: {field}"
        
        print(f"✓ Item structure valid: {item['title'][:50]}...")


class TestDailyBrief:
    """Test daily brief endpoints"""
    
    def test_get_daily_brief(self):
        """Test GET /api/daily-brief returns today's brief"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "analyst_summary" in data
        assert "key_developments" in data
        
        # Verify content
        assert data["analyst_summary"], "Expected analyst_summary to have content"
        assert len(data["key_developments"]) > 0, "Expected key_developments"
        
        print(f"✓ Daily brief: date={data['date']}, {len(data['key_developments'])} key developments")
    
    def test_generate_brief_trigger(self):
        """Test POST /api/generate-brief triggers brief generation"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "date" in data
        assert "Brief generation started" in data["message"]
        
        print(f"✓ Brief generation triggered for {data['date']}")


class TestP0BugFix_CustomPDF:
    """Test P0 Bug Fix: Custom Daily Brief PDF 500 error
    
    Bug: fpdf2 cell(0,...) caused 'Not enough horizontal space' error
    Fix: Changed to use explicit effective_w calculations
    """
    
    def test_custom_brief_pdf_returns_200(self):
        """Test POST /api/intelligence/custom-brief returns 200 with PDF"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/custom-brief",
            json={"hours": 720, "title": "Test Brief"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        assert response.headers.get("content-type") == "application/pdf"
        
        # Verify PDF content
        content = response.content
        assert len(content) > 1000, "PDF should have substantial content"
        assert content[:4] == b'%PDF', "Response should be valid PDF"
        
        print(f"✓ Custom PDF generated: {len(content)} bytes")
    
    def test_custom_brief_pdf_with_filters(self):
        """Test custom brief with region filter"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/custom-brief",
            json={"hours": 720, "title": "Assam Brief", "region": "Assam"},
            headers={"Content-Type": "application/json"}
        )
        
        # May return 404 if no items match, or 200 with PDF
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            assert response.headers.get("content-type") == "application/pdf"
            print(f"✓ Custom PDF with filter: {len(response.content)} bytes")
        else:
            print("✓ Custom PDF with filter: No items match (404 expected)")
    
    def test_daily_brief_pdf_download(self):
        """Test GET /api/daily-brief/pdf returns PDF"""
        response = requests.get(f"{BASE_URL}/api/daily-brief/pdf")
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/pdf"
        
        content = response.content
        assert len(content) > 1000
        assert content[:4] == b'%PDF'
        
        print(f"✓ Daily brief PDF: {len(content)} bytes")


class TestP0BugFix_Embeddings:
    """Test P0 Bug Fix: OpenAI Embeddings 401 error
    
    Bug: embedding_service.py was using EMERGENT_LLM_KEY instead of OPENAI_API_KEY
    Fix: Changed to use OPENAI_API_KEY environment variable
    
    Note: User's OpenAI key has insufficient quota (429 error) so actual embedding
    generation will fail, but the endpoint should not crash with 401/500.
    """
    
    def test_embeddings_backfill_returns_200(self):
        """Test POST /api/embeddings/backfill returns 200 (not 401/500)"""
        response = requests.post(f"{BASE_URL}/api/embeddings/backfill")
        
        # Should return 200 with message, not 401 (auth error) or 500 (crash)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "backfill" in data["message"].lower()
        
        print(f"✓ Embeddings backfill: {data['message']}")
    
    def test_semantic_search_returns_200(self):
        """Test POST /api/intelligence/semantic-search returns 200 with empty results"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/semantic-search",
            json={"query": "border security", "limit": 5},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 200, not 401/500
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert "query" in data
        
        # Results will be empty since no embeddings exist (expected)
        print(f"✓ Semantic search: {data['count']} results for '{data['query']}'")
    
    def test_semantic_search_validation(self):
        """Test semantic search validates query length"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/semantic-search",
            json={"query": "ab", "limit": 5},  # Too short
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 400 for query too short
        assert response.status_code == 400
        print("✓ Semantic search validation: rejects short queries")


class TestRetentionSettings:
    """Test retention settings endpoint"""
    
    def test_get_retention_setting(self):
        """Test GET /api/settings/retention returns current setting"""
        response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert response.status_code == 200
        data = response.json()
        
        assert "retention_days" in data
        assert isinstance(data["retention_days"], int)
        assert 1 <= data["retention_days"] <= 365
        
        print(f"✓ Retention setting: {data['retention_days']} days")


class TestAlerts:
    """Test alerts endpoints"""
    
    def test_get_alerts(self):
        """Test GET /api/alerts returns critical/high alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "count" in data
        
        print(f"✓ Alerts: {data['count']} critical/high alerts")
    
    def test_get_unacknowledged_alerts(self):
        """Test GET /api/alerts/unacknowledged"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "count" in data
        
        print(f"✓ Unacknowledged alerts: {data['count']}")


class TestDashboardStats:
    """Test dashboard stats endpoint"""
    
    def test_dashboard_stats(self):
        """Test GET /api/dashboard/stats returns all expected fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        expected_fields = [
            "total_items", "today_count", "critical_count", "high_count",
            "medium_count", "low_count", "state_distribution", "threat_distribution",
            "recent_critical", "retention_days"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"✓ Dashboard stats: {data['total_items']} items, {data['critical_count']} critical")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
