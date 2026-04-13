"""
Test P1 Features - Dashboard Priority Filter & Sort + RSS Sources Expansion
Iteration 30 - Tests for:
1. GET /api/intelligence with min_priority filter
2. GET /api/intelligence with sort_by=priority_score
3. RSS sources count verification (72 total, 12 new national sources)
4. Regression: Login, bias-profile endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Authentication regression tests"""
    
    def test_login_success(self):
        """Test login with valid admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in response"
        assert data.get("user", {}).get("username") == "admin"
        return data["token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestIntelligenceFilters:
    """Test intelligence endpoint filter and sort parameters"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_intelligence_default(self, auth_token):
        """Test default intelligence endpoint returns items"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/intelligence", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"Default query returned {len(data['items'])} items, total: {data['total']}")
    
    def test_intelligence_min_priority_80(self, auth_token):
        """Test min_priority=80 filter returns only high priority items"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=80", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "items" in data
        
        # Verify all returned items have priority_score >= 80
        for item in data["items"]:
            priority = item.get("priority_score", 0)
            assert priority >= 80, f"Item {item.get('id')} has priority {priority} < 80"
        
        print(f"min_priority=80 returned {len(data['items'])} items (all with priority >= 80)")
    
    def test_intelligence_min_priority_60(self, auth_token):
        """Test min_priority=60 filter returns items with priority >= 60"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=60", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        for item in data["items"]:
            priority = item.get("priority_score", 0)
            assert priority >= 60, f"Item {item.get('id')} has priority {priority} < 60"
        
        print(f"min_priority=60 returned {len(data['items'])} items")
    
    def test_intelligence_min_priority_40(self, auth_token):
        """Test min_priority=40 filter returns items with priority >= 40"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=40", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        for item in data["items"]:
            priority = item.get("priority_score", 0)
            assert priority >= 40, f"Item {item.get('id')} has priority {priority} < 40"
        
        print(f"min_priority=40 returned {len(data['items'])} items")
    
    def test_intelligence_sort_by_priority_desc(self, auth_token):
        """Test sort_by=priority_score&sort_order=desc returns items sorted by priority descending"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=desc&limit=20",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        items = data["items"]
        
        if len(items) > 1:
            # Verify items are sorted by priority_score descending
            priorities = [item.get("priority_score", 0) for item in items]
            for i in range(len(priorities) - 1):
                assert priorities[i] >= priorities[i+1], \
                    f"Items not sorted descending: {priorities[i]} < {priorities[i+1]}"
            print(f"Sort by priority desc: priorities = {priorities[:5]}...")
        else:
            print("Not enough items to verify sorting")
    
    def test_intelligence_sort_by_priority_asc(self, auth_token):
        """Test sort_by=priority_score&sort_order=asc returns items sorted ascending"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=asc&limit=20",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        items = data["items"]
        
        if len(items) > 1:
            priorities = [item.get("priority_score", 0) for item in items]
            for i in range(len(priorities) - 1):
                assert priorities[i] <= priorities[i+1], \
                    f"Items not sorted ascending: {priorities[i]} > {priorities[i+1]}"
            print(f"Sort by priority asc: priorities = {priorities[:5]}...")
    
    def test_intelligence_sort_by_published_at(self, auth_token):
        """Test default sort_by=published_at returns items sorted by date"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/intelligence?sort_by=published_at&sort_order=desc&limit=20",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        items = data["items"]
        
        if len(items) > 1:
            dates = [item.get("published_at", "") for item in items]
            for i in range(len(dates) - 1):
                assert dates[i] >= dates[i+1], \
                    f"Items not sorted by date descending: {dates[i]} < {dates[i+1]}"
            print(f"Sort by published_at desc: first date = {dates[0]}")
    
    def test_intelligence_combined_filter_and_sort(self, auth_token):
        """Test combining min_priority filter with sort_by priority"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/intelligence?min_priority=60&sort_by=priority_score&sort_order=desc&limit=10",
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        items = data["items"]
        
        # Verify filter
        for item in items:
            assert item.get("priority_score", 0) >= 60
        
        # Verify sort
        if len(items) > 1:
            priorities = [item.get("priority_score", 0) for item in items]
            for i in range(len(priorities) - 1):
                assert priorities[i] >= priorities[i+1]
        
        print(f"Combined filter+sort returned {len(items)} items")


class TestRSSSources:
    """Test RSS sources expansion"""
    
    def test_rss_sources_count(self):
        """Verify RSS_SOURCES has 72 total sources"""
        import sys
        sys.path.insert(0, '/app/backend')
        from rss_fetcher import RSS_SOURCES
        
        assert len(RSS_SOURCES) == 72, f"Expected 72 RSS sources, got {len(RSS_SOURCES)}"
        print(f"RSS_SOURCES count: {len(RSS_SOURCES)}")
    
    def test_new_national_sources_present(self):
        """Verify 12 new national Indian sources are present"""
        import sys
        sys.path.insert(0, '/app/backend')
        from rss_fetcher import RSS_SOURCES
        
        expected_new_sources = [
            "India Today",
            "Hindustan Times",
            "Deccan Herald",
            "The Wire",
            "Scroll.in",
            "The Print",
            "The Quint",
            "Mint - Defence",
            "Economic Times - Defence",
            "Firstpost",
            "The Indian Express - India",
            "The Tribune India"
        ]
        
        source_names = [s["name"] for s in RSS_SOURCES]
        
        for expected in expected_new_sources:
            assert expected in source_names, f"Missing new source: {expected}"
            print(f"Found new source: {expected}")
        
        print(f"All 12 new national sources verified")
    
    def test_national_sources_have_correct_category(self):
        """Verify new national sources have category='national' and region='India'"""
        import sys
        sys.path.insert(0, '/app/backend')
        from rss_fetcher import RSS_SOURCES
        
        new_national_names = [
            "India Today", "Hindustan Times", "Deccan Herald", "The Wire",
            "Scroll.in", "The Print", "The Quint", "Mint - Defence",
            "Economic Times - Defence", "Firstpost", "The Indian Express - India",
            "The Tribune India"
        ]
        
        for source in RSS_SOURCES:
            if source["name"] in new_national_names:
                assert source["category"] == "national", \
                    f"{source['name']} has wrong category: {source['category']}"
                assert source["region"] == "India", \
                    f"{source['name']} has wrong region: {source['region']}"
        
        print("All new national sources have correct category and region")


class TestRegressionBiasProfile:
    """Regression test for bias profile endpoint (P2 feature)"""
    
    @pytest.fixture
    def auth_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "Admin@2026!"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")
    
    def test_bias_profile_endpoint(self, auth_token):
        """Verify bias-profile endpoint still returns active data"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/feedback/bias-profile", headers=headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "status" in data, "Missing status field"
        assert data["status"] in ["active", "inactive", "insufficient_data"]
        
        if data["status"] == "active":
            assert "upweight_regions" in data
            assert "upweight_threats" in data
            print(f"Bias profile active with {data.get('total_ratings', 0)} ratings")
        else:
            print(f"Bias profile status: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
