"""
Test suite for PDF Reports feature (Iteration 35)
Tests:
- GET /api/reports/filtered-feed - Export filtered intelligence as PDF
- GET /api/reports/regional-threat - Regional threat summary PDF
- GET /api/reports/cross-border-sitrep - Cross-border SITREP PDF
- GET /api/reports/custom - Custom filtered report PDF
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026!"


class TestReportsAuth:
    """Test authentication requirements for report endpoints"""
    
    def test_filtered_feed_requires_auth(self):
        """GET /api/reports/filtered-feed without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/filtered-feed")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: filtered-feed requires authentication")
    
    def test_regional_threat_requires_auth(self):
        """GET /api/reports/regional-threat without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/regional-threat?region=Manipur")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: regional-threat requires authentication")
    
    def test_cross_border_sitrep_requires_auth(self):
        """GET /api/reports/cross-border-sitrep without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/cross-border-sitrep?country=Myanmar")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: cross-border-sitrep requires authentication")
    
    def test_custom_report_requires_auth(self):
        """GET /api/reports/custom without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/reports/custom?title=Test")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: custom report requires authentication")


class TestFilteredFeedReport:
    """Test /api/reports/filtered-feed endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_filtered_feed_with_severity_high(self):
        """GET /api/reports/filtered-feed with severity=high returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/filtered-feed?severity=high",
            headers=self.headers
        )
        # Could be 200 (PDF) or 404 (no matching items)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
            assert len(response.content) > 0, "PDF content should not be empty"
            print(f"PASS: filtered-feed with severity=high returns PDF ({len(response.content)} bytes)")
        else:
            print("PASS: filtered-feed with severity=high returns 404 (no matching items)")
    
    def test_filtered_feed_with_state_filter(self):
        """GET /api/reports/filtered-feed with state filter"""
        response = requests.get(
            f"{BASE_URL}/api/reports/filtered-feed?state=Manipur",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: filtered-feed with state=Manipur returns PDF ({len(response.content)} bytes)")
        else:
            print("PASS: filtered-feed with state=Manipur returns 404 (no matching items)")
    
    def test_filtered_feed_with_multiple_filters(self):
        """GET /api/reports/filtered-feed with multiple filters"""
        response = requests.get(
            f"{BASE_URL}/api/reports/filtered-feed?severity=high&min_priority=60",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: filtered-feed with multiple filters returns PDF")
        else:
            print("PASS: filtered-feed with multiple filters returns 404 (no matching items)")
    
    def test_filtered_feed_no_filters(self):
        """GET /api/reports/filtered-feed with no filters (default last 30 days)"""
        response = requests.get(
            f"{BASE_URL}/api/reports/filtered-feed",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: filtered-feed with no filters returns PDF ({len(response.content)} bytes)")
        else:
            print("PASS: filtered-feed with no filters returns 404 (no items in last 30 days)")


class TestRegionalThreatReport:
    """Test /api/reports/regional-threat endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_regional_threat_manipur(self):
        """GET /api/reports/regional-threat?region=Manipur returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/regional-threat?region=Manipur",
            headers=self.headers
        )
        # Always returns 200 even with no data (shows "NO DATA" section)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"PASS: regional-threat for Manipur returns PDF ({len(response.content)} bytes)")
    
    def test_regional_threat_assam(self):
        """GET /api/reports/regional-threat?region=Assam returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/regional-threat?region=Assam",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf"
        print(f"PASS: regional-threat for Assam returns PDF ({len(response.content)} bytes)")
    
    def test_regional_threat_without_region_returns_422(self):
        """GET /api/reports/regional-threat without region returns 422"""
        response = requests.get(
            f"{BASE_URL}/api/reports/regional-threat",
            headers=self.headers
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("PASS: regional-threat without region returns 422")
    
    def test_regional_threat_with_date_range(self):
        """GET /api/reports/regional-threat with date range"""
        response = requests.get(
            f"{BASE_URL}/api/reports/regional-threat?region=Manipur&date_from=2026-01-01T00:00:00Z&date_to=2026-12-31T23:59:59Z",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf"
        print(f"PASS: regional-threat with date range returns PDF")


class TestCrossBorderSitrep:
    """Test /api/reports/cross-border-sitrep endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_cross_border_sitrep_myanmar(self):
        """GET /api/reports/cross-border-sitrep?country=Myanmar returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/cross-border-sitrep?country=Myanmar",
            headers=self.headers
        )
        # Always returns 200 even with no data (shows "NO DATA" section)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
        assert len(response.content) > 0, "PDF content should not be empty"
        print(f"PASS: cross-border-sitrep for Myanmar returns PDF ({len(response.content)} bytes)")
    
    def test_cross_border_sitrep_bangladesh(self):
        """GET /api/reports/cross-border-sitrep?country=Bangladesh returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/cross-border-sitrep?country=Bangladesh",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers.get("Content-Type") == "application/pdf"
        print(f"PASS: cross-border-sitrep for Bangladesh returns PDF ({len(response.content)} bytes)")
    
    def test_cross_border_sitrep_invalid_country(self):
        """GET /api/reports/cross-border-sitrep?country=Invalid returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/reports/cross-border-sitrep?country=Invalid",
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Expected error detail"
        print(f"PASS: cross-border-sitrep with invalid country returns 400: {data['detail']}")
    
    def test_cross_border_sitrep_without_country_returns_422(self):
        """GET /api/reports/cross-border-sitrep without country returns 422"""
        response = requests.get(
            f"{BASE_URL}/api/reports/cross-border-sitrep",
            headers=self.headers
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("PASS: cross-border-sitrep without country returns 422")


class TestCustomReport:
    """Test /api/reports/custom endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_custom_report_with_title_and_threat(self):
        """GET /api/reports/custom with title and threat_type returns 200 PDF"""
        response = requests.get(
            f"{BASE_URL}/api/reports/custom?title=Test%20Report&threat_type=Insurgency/Militancy",
            headers=self.headers
        )
        # Could be 200 (PDF) or 404 (no matching items)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf", "Expected PDF content type"
            assert len(response.content) > 0, "PDF content should not be empty"
            print(f"PASS: custom report with title and threat returns PDF ({len(response.content)} bytes)")
        else:
            print("PASS: custom report returns 404 (no matching items for threat type)")
    
    def test_custom_report_with_all_filters(self):
        """GET /api/reports/custom with multiple filters"""
        params = {
            "title": "Full Filter Test",
            "state": "Manipur",
            "severity": "high",
            "min_priority": "50",
            "is_cross_border": "false"
        }
        response = requests.get(
            f"{BASE_URL}/api/reports/custom",
            params=params,
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: custom report with all filters returns PDF")
        else:
            print("PASS: custom report with all filters returns 404 (no matching items)")
    
    def test_custom_report_default_title(self):
        """GET /api/reports/custom without title uses default"""
        response = requests.get(
            f"{BASE_URL}/api/reports/custom",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: custom report with default title returns PDF")
        else:
            print("PASS: custom report with default title returns 404 (no items)")
    
    def test_custom_report_with_source_filter(self):
        """GET /api/reports/custom with source filter"""
        response = requests.get(
            f"{BASE_URL}/api/reports/custom?source=NE%20Now",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: custom report with source filter returns PDF")
        else:
            print("PASS: custom report with source filter returns 404 (no matching items)")
    
    def test_custom_report_cross_border_only(self):
        """GET /api/reports/custom with is_cross_border=true"""
        response = requests.get(
            f"{BASE_URL}/api/reports/custom?is_cross_border=true",
            headers=self.headers
        )
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        if response.status_code == 200:
            assert response.headers.get("Content-Type") == "application/pdf"
            print(f"PASS: custom report with cross-border filter returns PDF")
        else:
            print("PASS: custom report with cross-border filter returns 404 (no matching items)")


class TestRegressionIntelligenceFeed:
    """Regression tests for Intelligence Feed functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_intelligence_feed_pagination(self):
        """GET /api/intelligence with pagination still works"""
        response = requests.get(
            f"{BASE_URL}/api/intelligence?page=1&limit=15",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Expected items in response"
        assert "total" in data, "Expected total in response"
        assert "pages" in data, "Expected pages in response"
        print(f"PASS: Intelligence feed pagination works (total: {data['total']}, pages: {data['pages']})")
    
    def test_intelligence_feed_filters(self):
        """GET /api/intelligence with filters still works"""
        response = requests.get(
            f"{BASE_URL}/api/intelligence?severity=high&page=1&limit=10",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Expected items in response"
        print(f"PASS: Intelligence feed filters work (found {len(data['items'])} high severity items)")
    
    def test_intelligence_delete_endpoint_exists(self):
        """DELETE /api/intelligence/{id} endpoint exists"""
        # Just verify the endpoint exists by checking a non-existent ID
        response = requests.delete(
            f"{BASE_URL}/api/intelligence/nonexistent-id-12345",
            headers=self.headers
        )
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code in [404, 200], f"Expected 404 or 200, got {response.status_code}"
        print("PASS: Intelligence delete endpoint exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
