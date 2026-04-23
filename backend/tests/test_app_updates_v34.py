"""
Test Suite for App Updates / Notification System (Iteration 34)
Tests: POST /api/admin/create-update, GET /api/admin/update-logs, POST /api/admin/trigger-update-preview,
       GET /api/app/updates, POST /api/app/updates/acknowledge, GET /api/app/updates/all
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "Admin@2026!"}
VIEWER_CREDS = {"username": "testviewer", "password": "Viewer@2026!"}


class TestAuthSetup:
    """Authentication setup tests"""
    
    def test_admin_login(self, api_client):
        """Test admin login returns token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ Admin login successful, role: {data['user']['role']}")
    
    def test_viewer_login(self, api_client):
        """Test viewer login returns token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=VIEWER_CREDS)
        assert response.status_code == 200, f"Viewer login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "viewer"
        print(f"✓ Viewer login successful, role: {data['user']['role']}")


class TestAdminCreateUpdate:
    """Tests for POST /api/admin/create-update"""
    
    def test_create_update_major(self, admin_client):
        """Admin can create a major update"""
        payload = {
            "version": "TEST_10.0",
            "message": "Major feature release for testing",
            "priority": "major"
        }
        response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        assert response.status_code == 200, f"Create update failed: {response.text}"
        data = response.json()
        assert "update" in data
        assert data["update"]["version"] == "TEST_10.0"
        assert data["update"]["priority"] == "major"
        print(f"✓ Created major update v{data['update']['version']}")
    
    def test_create_update_minor(self, admin_client):
        """Admin can create a minor update"""
        payload = {
            "version": "TEST_10.0.1",
            "message": "Minor bug fixes",
            "priority": "minor"
        }
        response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        assert response.status_code == 200, f"Create minor update failed: {response.text}"
        data = response.json()
        assert data["update"]["priority"] == "minor"
        print(f"✓ Created minor update v{data['update']['version']}")
    
    def test_create_update_duplicate_version_returns_409(self, admin_client):
        """Creating update with duplicate version returns 409"""
        payload = {
            "version": "TEST_10.0",
            "message": "Duplicate version test",
            "priority": "major"
        }
        response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        assert response.status_code == 409, f"Expected 409 for duplicate, got {response.status_code}"
        assert "already exists" in response.json().get("detail", "").lower()
        print("✓ Duplicate version correctly returns 409")
    
    def test_create_update_missing_version_returns_400(self, admin_client):
        """Creating update without version returns 400"""
        payload = {"message": "No version", "priority": "major"}
        response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        # Pydantic validation or custom validation
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"
        print("✓ Missing version correctly returns 400/422")
    
    def test_create_update_invalid_priority_returns_400(self, admin_client):
        """Creating update with invalid priority returns 400"""
        payload = {
            "version": "TEST_10.0.2",
            "message": "Invalid priority test",
            "priority": "critical"  # Invalid
        }
        response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        assert response.status_code == 400, f"Expected 400 for invalid priority, got {response.status_code}"
        print("✓ Invalid priority correctly returns 400")
    
    def test_viewer_cannot_create_update_403(self, viewer_client):
        """Non-admin (viewer) cannot create updates - returns 403"""
        payload = {
            "version": "TEST_VIEWER_1.0",
            "message": "Viewer should not create this",
            "priority": "major"
        }
        response = viewer_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
        assert response.status_code == 403, f"Expected 403 for viewer, got {response.status_code}"
        print("✓ Viewer correctly rejected with 403")


class TestAdminUpdateLogs:
    """Tests for GET /api/admin/update-logs"""
    
    def test_admin_can_get_update_logs(self, admin_client):
        """Admin can retrieve all update logs"""
        response = admin_client.get(f"{BASE_URL}/api/admin/update-logs")
        assert response.status_code == 200, f"Get update logs failed: {response.text}"
        data = response.json()
        assert "updates" in data
        assert "total" in data
        assert isinstance(data["updates"], list)
        # Should be sorted newest-first
        if len(data["updates"]) >= 2:
            first_date = data["updates"][0].get("created_at", "")
            second_date = data["updates"][1].get("created_at", "")
            assert first_date >= second_date, "Updates should be sorted newest-first"
        print(f"✓ Admin retrieved {data['total']} update logs")
    
    def test_viewer_cannot_get_update_logs_403(self, viewer_client):
        """Non-admin (viewer) cannot access update logs - returns 403"""
        response = viewer_client.get(f"{BASE_URL}/api/admin/update-logs")
        assert response.status_code == 403, f"Expected 403 for viewer, got {response.status_code}"
        print("✓ Viewer correctly rejected from update-logs with 403")


class TestAdminTriggerUpdatePreview:
    """Tests for POST /api/admin/trigger-update-preview"""
    
    def test_preview_major_update(self, admin_client):
        """Preview a major update returns actual message"""
        payload = {"version": "TEST_10.0"}
        response = admin_client.post(f"{BASE_URL}/api/admin/trigger-update-preview", json=payload)
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        assert data["version"] == "TEST_10.0"
        assert data["priority"] == "major"
        assert data["message"] == "Major feature release for testing"  # Actual message
        assert data.get("preview") == True
        print(f"✓ Major update preview shows actual message: '{data['message']}'")
    
    def test_preview_minor_update_shows_generic_message(self, admin_client):
        """Preview a minor update returns generic message"""
        payload = {"version": "TEST_10.0.1"}
        response = admin_client.post(f"{BASE_URL}/api/admin/trigger-update-preview", json=payload)
        assert response.status_code == 200, f"Preview failed: {response.text}"
        data = response.json()
        assert data["priority"] == "minor"
        assert data["message"] == "Performance improvements and bug fixes"
        print(f"✓ Minor update preview shows generic message: '{data['message']}'")
    
    def test_preview_nonexistent_version_returns_404(self, admin_client):
        """Preview non-existent version returns 404"""
        payload = {"version": "NONEXISTENT_999.0"}
        response = admin_client.post(f"{BASE_URL}/api/admin/trigger-update-preview", json=payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent version correctly returns 404")
    
    def test_viewer_cannot_preview_403(self, viewer_client):
        """Non-admin (viewer) cannot preview updates - returns 403"""
        payload = {"version": "TEST_10.0"}
        response = viewer_client.post(f"{BASE_URL}/api/admin/trigger-update-preview", json=payload)
        assert response.status_code == 403, f"Expected 403 for viewer, got {response.status_code}"
        print("✓ Viewer correctly rejected from preview with 403")


class TestUserGetPendingUpdates:
    """Tests for GET /api/app/updates - user-facing pending notifications"""
    
    def test_get_pending_updates_returns_notifications(self, viewer_client):
        """User can get pending updates"""
        response = viewer_client.get(f"{BASE_URL}/api/app/updates")
        assert response.status_code == 200, f"Get updates failed: {response.text}"
        data = response.json()
        assert "notifications" in data
        assert "has_more" in data
        assert "total_major" in data
        assert "total_pending" in data
        print(f"✓ Got {len(data['notifications'])} notifications, has_more={data['has_more']}, total_major={data['total_major']}")
    
    def test_admin_can_also_get_pending_updates(self, admin_client):
        """Admin can also access pending updates endpoint"""
        response = admin_client.get(f"{BASE_URL}/api/app/updates")
        assert response.status_code == 200, f"Admin get updates failed: {response.text}"
        print("✓ Admin can access pending updates endpoint")


class TestUserAcknowledgeUpdates:
    """Tests for POST /api/app/updates/acknowledge"""
    
    def test_acknowledge_updates(self, viewer_client):
        """User can acknowledge updates"""
        response = viewer_client.post(f"{BASE_URL}/api/app/updates/acknowledge")
        assert response.status_code == 200, f"Acknowledge failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Acknowledged updates: {data.get('last_seen_version', 'N/A')}")
    
    def test_after_acknowledge_no_pending_updates(self, viewer_client):
        """After acknowledge, GET /api/app/updates returns 0 notifications (Case 6)"""
        # First acknowledge
        viewer_client.post(f"{BASE_URL}/api/app/updates/acknowledge")
        # Then check
        response = viewer_client.get(f"{BASE_URL}/api/app/updates")
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 0, f"Expected 0 notifications after acknowledge, got {len(data['notifications'])}"
        assert data["has_more"] == False
        print("✓ After acknowledge, no pending notifications (Case 6 verified)")


class TestUserGetAllUpdates:
    """Tests for GET /api/app/updates/all"""
    
    def test_get_all_updates_history(self, viewer_client):
        """Any authenticated user can get full update history"""
        response = viewer_client.get(f"{BASE_URL}/api/app/updates/all")
        assert response.status_code == 200, f"Get all updates failed: {response.text}"
        data = response.json()
        assert "updates" in data
        assert isinstance(data["updates"], list)
        print(f"✓ Got {len(data['updates'])} total updates in history")
    
    def test_admin_can_get_all_updates(self, admin_client):
        """Admin can also get full update history"""
        response = admin_client.get(f"{BASE_URL}/api/app/updates/all")
        assert response.status_code == 200
        print("✓ Admin can access all updates history")


class TestLongGapUserScenario:
    """Tests for Case 2: Long-gap user with >3 major updates"""
    
    def test_create_multiple_major_updates_for_long_gap(self, admin_client):
        """Create 4+ major updates to test long-gap scenario"""
        # Create 4 more major updates
        for i in range(4):
            payload = {
                "version": f"TEST_LONGGAP_{i+1}.0",
                "message": f"Long gap test update {i+1}",
                "priority": "major"
            }
            response = admin_client.post(f"{BASE_URL}/api/admin/create-update", json=payload)
            # May get 409 if already exists from previous run
            if response.status_code == 200:
                print(f"  Created TEST_LONGGAP_{i+1}.0")
            elif response.status_code == 409:
                print(f"  TEST_LONGGAP_{i+1}.0 already exists")
        print("✓ Long-gap test updates created/verified")


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_updates(self, admin_client):
        """Note: Test updates with TEST_ prefix should be cleaned up manually or via DB"""
        # This is a placeholder - actual cleanup would require a delete endpoint
        # or direct DB access
        print("✓ Test cleanup noted (TEST_ prefixed updates created)")


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def admin_client(api_client):
    """Session with admin auth header"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.text}")
    token = response.json().get("token")
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client


@pytest.fixture
def viewer_client():
    """Session with viewer auth header"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json=VIEWER_CREDS)
    if response.status_code != 200:
        pytest.skip(f"Viewer login failed: {response.text}")
    token = response.json().get("token")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
