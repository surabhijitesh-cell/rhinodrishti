"""
Test suite for refactored router modules (v16)
Tests all endpoints after server.py was split into modular routers:
- intelligence.py: dashboard stats, intelligence CRUD, alerts, semantic search
- settings.py: retention settings
- briefs.py: daily brief, PDF generation, weekly trends
- pipeline.py: fetch, scrape, analyze, pipeline status
- documents.py: document upload and management
- knowledge_graph_routes.py: knowledge graph endpoints
- keywords_routes.py: keyword engine endpoints
- sources.py: RSS sources, twitter, handbook
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRootEndpoint:
    """Test root health check endpoint"""
    
    def test_root_health_check(self):
        """GET /api/ - root health check"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Rhino Drishti" in data["message"]
        print("✓ Root health check passed")


class TestDashboardStats:
    """Test dashboard statistics endpoint"""
    
    def test_dashboard_stats(self):
        """GET /api/dashboard/stats - returns total_items, critical_count, trend data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_items" in data
        assert "critical_count" in data
        assert "high_count" in data
        assert "medium_count" in data
        assert "low_count" in data
        assert "state_distribution" in data
        assert "threat_distribution" in data
        assert "recent_critical" in data
        assert "trend_7d" in data
        assert "retention_days" in data
        
        # Verify data types
        assert isinstance(data["total_items"], int)
        assert isinstance(data["critical_count"], int)
        assert isinstance(data["state_distribution"], dict)
        assert isinstance(data["trend_7d"], list)
        
        print(f"✓ Dashboard stats: {data['total_items']} items, {data['critical_count']} critical")


class TestIntelligenceEndpoints:
    """Test intelligence feed endpoints"""
    
    def test_intelligence_list(self):
        """GET /api/intelligence - paginated list with filters"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "pages" in data
        
        assert len(data["items"]) <= 5
        print(f"✓ Intelligence list: {data['total']} total items")
    
    def test_intelligence_filter_by_severity(self):
        """GET /api/intelligence - filter by severity"""
        response = requests.get(f"{BASE_URL}/api/intelligence?severity=high&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["items"]:
            assert item["severity"] == "high"
        print(f"✓ Intelligence filter by severity: {len(data['items'])} high items")
    
    def test_intelligence_filter_by_state(self):
        """GET /api/intelligence - filter by state"""
        response = requests.get(f"{BASE_URL}/api/intelligence?state=Manipur&limit=5")
        assert response.status_code == 200
        data = response.json()
        
        for item in data["items"]:
            assert item["state"] == "Manipur"
        print(f"✓ Intelligence filter by state: {len(data['items'])} Manipur items")
    
    def test_intelligence_item_detail(self):
        """GET /api/intelligence/{item_id} - single item detail"""
        # First get an item ID
        list_response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        
        if items:
            item_id = items[0]["id"]
            response = requests.get(f"{BASE_URL}/api/intelligence/{item_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == item_id
            print(f"✓ Intelligence item detail: {data['title'][:50]}...")
        else:
            pytest.skip("No intelligence items available")
    
    def test_intelligence_item_not_found(self):
        """GET /api/intelligence/{item_id} - 404 for non-existent item"""
        response = requests.get(f"{BASE_URL}/api/intelligence/non-existent-id-12345")
        assert response.status_code == 404
        print("✓ Intelligence item not found returns 404")


class TestAlertsEndpoints:
    """Test alerts endpoints"""
    
    def test_alerts_list(self):
        """GET /api/alerts - critical/high alerts list"""
        response = requests.get(f"{BASE_URL}/api/alerts")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "count" in data
        
        for alert in data["alerts"]:
            assert alert["severity"] in ["critical", "high"]
        print(f"✓ Alerts list: {data['count']} alerts")
    
    def test_unacknowledged_alerts(self):
        """GET /api/alerts/unacknowledged - unacknowledged alerts"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        assert response.status_code == 200
        data = response.json()
        
        assert "alerts" in data
        assert "count" in data
        print(f"✓ Unacknowledged alerts: {data['count']} alerts")


class TestPatternsEndpoint:
    """Test patterns endpoint"""
    
    def test_patterns_list(self):
        """GET /api/patterns - pattern list"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        assert response.status_code == 200
        data = response.json()
        
        assert "patterns" in data
        assert "count" in data
        print(f"✓ Patterns list: {data['count']} patterns")


class TestSemanticSearch:
    """Test semantic search endpoint"""
    
    def test_semantic_search(self):
        """POST /api/intelligence/semantic-search - semantic search endpoint"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/semantic-search",
            json={"query": "border security", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "count" in data
        assert "query" in data
        print(f"✓ Semantic search: {data['count']} results for 'border security'")
    
    def test_semantic_search_short_query(self):
        """POST /api/intelligence/semantic-search - rejects short query"""
        response = requests.post(
            f"{BASE_URL}/api/intelligence/semantic-search",
            json={"query": "ab", "limit": 5}
        )
        assert response.status_code == 400
        print("✓ Semantic search rejects short query")


class TestSettingsEndpoints:
    """Test settings endpoints"""
    
    def test_get_retention_setting(self):
        """GET /api/settings/retention - get retention days"""
        response = requests.get(f"{BASE_URL}/api/settings/retention")
        assert response.status_code == 200
        data = response.json()
        
        assert "retention_days" in data
        assert isinstance(data["retention_days"], int)
        assert 1 <= data["retention_days"] <= 365
        print(f"✓ Retention setting: {data['retention_days']} days")
    
    def test_update_retention_setting(self):
        """PUT /api/settings/retention - update retention days"""
        # Get current value
        get_response = requests.get(f"{BASE_URL}/api/settings/retention")
        original_days = get_response.json()["retention_days"]
        
        # Update to new value
        response = requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": 30}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["retention_days"] == 30
        
        # Restore original value
        requests.put(
            f"{BASE_URL}/api/settings/retention",
            json={"retention_days": original_days}
        )
        print("✓ Retention setting update works")


class TestBriefsEndpoints:
    """Test daily brief endpoints"""
    
    def test_get_daily_brief(self):
        """GET /api/daily-brief - get daily brief"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "key_developments" in data
        print(f"✓ Daily brief: {data['date']} with {len(data.get('key_developments', []))} developments")
    
    def test_generate_brief(self):
        """POST /api/generate-brief - trigger brief generation"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "date" in data
        print(f"✓ Brief generation triggered for {data['date']}")
    
    def test_weekly_trends(self):
        """GET /api/weekly-trends - trend data"""
        response = requests.get(f"{BASE_URL}/api/weekly-trends")
        assert response.status_code == 200
        data = response.json()
        
        assert "daily_severity" in data
        assert "category_stats" in data
        assert "state_stats" in data
        print(f"✓ Weekly trends: {len(data['daily_severity'])} days of data")


class TestPipelineEndpoints:
    """Test pipeline endpoints"""
    
    def test_pipeline_status(self):
        """GET /api/pipeline/status - pipeline health"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_items" in data
        assert "ai_processed" in data
        assert "pending_retry" in data
        assert "processing_rate" in data
        assert "rss_sources" in data
        print(f"✓ Pipeline status: {data['total_items']} items, {data['processing_rate']} processed")
    
    def test_scan_status(self):
        """GET /api/scan-status - scan progress"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        assert response.status_code == 200
        data = response.json()
        
        assert "is_scanning" in data
        assert "progress" in data
        print(f"✓ Scan status: scanning={data['is_scanning']}, progress={data['progress']}%")


class TestKnowledgeGraphEndpoints:
    """Test knowledge graph endpoints"""
    
    def test_kg_stats(self):
        """GET /api/knowledge-graph/stats - KG stats"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "actors" in data
        assert "locations" in data
        assert "edges" in data
        print(f"✓ KG stats: {data['actors']} actors, {data['locations']} locations, {data['edges']} edges")
    
    def test_kg_actors(self):
        """GET /api/knowledge-graph/actors - list actors"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert "actors" in data
        assert "count" in data
        print(f"✓ KG actors: {data['count']} actors returned")
    
    def test_kg_network(self):
        """GET /api/knowledge-graph/network - network graph data"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/network?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "nodes" in data
        assert "links" in data
        assert "actor_count" in data
        assert "location_count" in data
        print(f"✓ KG network: {data['actor_count']} actors, {data['location_count']} locations")


class TestKeywordsEndpoints:
    """Test keyword engine endpoints"""
    
    def test_keywords_list(self):
        """GET /api/keywords - keyword list"""
        response = requests.get(f"{BASE_URL}/api/keywords?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert "keywords" in data
        assert "count" in data
        assert "type_breakdown" in data
        print(f"✓ Keywords: {data['count']} keywords")
    
    def test_keywords_filter_by_type(self):
        """GET /api/keywords - filter by type"""
        response = requests.get(f"{BASE_URL}/api/keywords?type=primary&limit=10")
        assert response.status_code == 200
        data = response.json()
        
        for kw in data["keywords"]:
            assert kw["type"] == "primary"
        print(f"✓ Keywords filter by type: {data['count']} primary keywords")


class TestSourcesEndpoints:
    """Test sources endpoints"""
    
    def test_sources_list(self):
        """GET /api/sources - RSS sources"""
        response = requests.get(f"{BASE_URL}/api/sources")
        assert response.status_code == 200
        data = response.json()
        
        assert "sources" in data
        assert len(data["sources"]) > 0
        print(f"✓ Sources: {len(data['sources'])} RSS sources")
    
    def test_twitter_accounts(self):
        """GET /api/twitter-accounts - Twitter accounts"""
        response = requests.get(f"{BASE_URL}/api/twitter-accounts")
        assert response.status_code == 200
        data = response.json()
        
        assert "accounts" in data
        assert len(data["accounts"]) > 0
        print(f"✓ Twitter accounts: {len(data['accounts'])} accounts")
    
    def test_uploaded_documents(self):
        """GET /api/uploaded-documents - uploaded docs"""
        response = requests.get(f"{BASE_URL}/api/uploaded-documents")
        assert response.status_code == 200
        data = response.json()
        
        assert "documents" in data
        assert "count" in data
        print(f"✓ Uploaded documents: {data['count']} documents")
    
    def test_handbook(self):
        """GET /api/handbook - user handbook content"""
        response = requests.get(f"{BASE_URL}/api/handbook")
        assert response.status_code == 200
        data = response.json()
        
        assert "content" in data
        assert "Rhino Drishti" in data["content"]
        print(f"✓ Handbook: {len(data['content'])} characters")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
