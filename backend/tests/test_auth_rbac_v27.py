"""
Test Suite for JWT Authentication and RBAC - Iteration 27
Tests: Login, /auth/me, User CRUD, Role-based access, Regression on existing endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@2026!"


class TestAuthLogin:
    """Authentication login endpoint tests"""
    
    def test_login_with_valid_username(self):
        """POST /api/auth/login with valid admin credentials returns token and user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user object"
        assert isinstance(data["token"], str) and len(data["token"]) > 0
        
        user = data["user"]
        assert user["username"] == ADMIN_USERNAME
        assert user["role"] == "admin"
        assert "id" in user
        assert "email" in user
        assert "password_hash" not in user, "password_hash should not be in response"
    
    def test_login_with_email_as_username(self):
        """POST /api/auth/login accepts email in username field ($or operator)"""
        # First get the admin email
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        admin_email = login_resp.json()["user"]["email"]
        
        # Now login with email
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": admin_email,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login with email failed: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert data["user"]["username"] == ADMIN_USERNAME
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "nonexistent",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        assert "detail" in response.json()
    
    def test_login_wrong_password(self):
        """POST /api/auth/login with wrong password returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401


class TestAuthMe:
    """GET /auth/me endpoint tests"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    def test_get_me_with_valid_token(self, admin_token):
        """GET /api/auth/me with valid Bearer token returns user info"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert data["username"] == ADMIN_USERNAME
        assert data["role"] == "admin"
        assert "id" in data
        assert "is_active" in data
        assert "password_hash" not in data, "password_hash should not be exposed"
    
    def test_get_me_without_token(self):
        """GET /api/auth/me without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        assert "detail" in response.json()
    
    def test_get_me_with_invalid_token(self):
        """GET /api/auth/me with invalid token returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers={
            "Authorization": "Bearer invalid_token_here"
        })
        assert response.status_code == 401


class TestUserManagement:
    """User CRUD endpoints (admin only)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return response.json()["token"]
    
    @pytest.fixture
    def admin_headers(self, admin_token):
        """Headers with admin auth"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    def test_list_users_as_admin(self, admin_headers):
        """GET /api/users requires admin role and returns users list"""
        response = requests.get(f"{BASE_URL}/api/users", headers=admin_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "users" in data
        assert isinstance(data["users"], list)
        assert len(data["users"]) >= 1  # At least admin user
        
        # Verify no password_hash in response
        for user in data["users"]:
            assert "password_hash" not in user
    
    def test_list_users_without_auth(self):
        """GET /api/users without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/users")
        assert response.status_code == 401
    
    def test_create_user_as_admin(self, admin_headers):
        """POST /api/users creates new user with hashed password (admin only)"""
        unique_id = str(uuid.uuid4())[:8]
        new_user = {
            "username": f"TEST_user_{unique_id}",
            "email": f"test_{unique_id}@example.com",
            "password": "TestPass123!",
            "name": "Test User",
            "role": "analyst"
        }
        
        response = requests.post(f"{BASE_URL}/api/users", json=new_user, headers=admin_headers)
        assert response.status_code == 200, f"Create user failed: {response.text}"
        
        data = response.json()
        assert data["username"] == new_user["username"]
        assert data["email"] == new_user["email"]
        assert data["role"] == "analyst"
        assert "id" in data
        assert "password_hash" not in data
        
        # Verify user can login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": new_user["username"],
            "password": new_user["password"]
        })
        assert login_resp.status_code == 200, "Created user should be able to login"
        
        # Cleanup - delete the test user
        user_id = data["id"]
        requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
    
    def test_create_user_duplicate_username(self, admin_headers):
        """POST /api/users with duplicate username returns 409"""
        response = requests.post(f"{BASE_URL}/api/users", json={
            "username": ADMIN_USERNAME,  # Already exists
            "password": "TestPass123!",
            "role": "viewer"
        }, headers=admin_headers)
        assert response.status_code == 409
    
    def test_create_user_short_password(self, admin_headers):
        """POST /api/users with password < 8 chars returns 400"""
        response = requests.post(f"{BASE_URL}/api/users", json={
            "username": f"TEST_short_{uuid.uuid4().hex[:6]}",
            "password": "short",
            "role": "viewer"
        }, headers=admin_headers)
        assert response.status_code == 400
    
    def test_update_user_as_admin(self, admin_headers):
        """PUT /api/users/{id} updates user fields (admin only)"""
        # Create a test user first
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/users", json={
            "username": f"TEST_update_{unique_id}",
            "password": "TestPass123!",
            "role": "viewer"
        }, headers=admin_headers)
        user_id = create_resp.json()["id"]
        
        # Update the user
        update_resp = requests.put(f"{BASE_URL}/api/users/{user_id}", json={
            "name": "Updated Name",
            "role": "analyst"
        }, headers=admin_headers)
        assert update_resp.status_code == 200
        
        data = update_resp.json()
        assert data["name"] == "Updated Name"
        assert data["role"] == "analyst"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
    
    def test_reset_password_as_admin(self, admin_headers):
        """PUT /api/users/{id}/password resets password (admin only)"""
        # Create a test user
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/users", json={
            "username": f"TEST_reset_{unique_id}",
            "password": "OldPass123!",
            "role": "viewer"
        }, headers=admin_headers)
        user_id = create_resp.json()["id"]
        username = create_resp.json()["username"]
        
        # Reset password
        new_password = "NewPass456!"
        reset_resp = requests.put(f"{BASE_URL}/api/users/{user_id}/password", json={
            "new_password": new_password
        }, headers=admin_headers)
        assert reset_resp.status_code == 200
        
        # Verify old password no longer works
        old_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": "OldPass123!"
        })
        assert old_login.status_code == 401
        
        # Verify new password works
        new_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": new_password
        })
        assert new_login.status_code == 200
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
    
    def test_delete_user_as_admin(self, admin_headers):
        """DELETE /api/users/{id} deletes user (admin only)"""
        # Create a test user
        unique_id = str(uuid.uuid4())[:8]
        create_resp = requests.post(f"{BASE_URL}/api/users", json={
            "username": f"TEST_delete_{unique_id}",
            "password": "TestPass123!",
            "role": "viewer"
        }, headers=admin_headers)
        user_id = create_resp.json()["id"]
        
        # Delete the user
        delete_resp = requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
        assert delete_resp.status_code == 200
        
        # Verify user no longer in list
        list_resp = requests.get(f"{BASE_URL}/api/users", headers=admin_headers)
        user_ids = [u["id"] for u in list_resp.json()["users"]]
        assert user_id not in user_ids
    
    def test_admin_cannot_delete_self(self, admin_headers):
        """DELETE /api/users/{id} prevents self-deletion"""
        # Get admin user ID
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
        admin_id = me_resp.json()["id"]
        
        # Try to delete self
        delete_resp = requests.delete(f"{BASE_URL}/api/users/{admin_id}", headers=admin_headers)
        assert delete_resp.status_code == 400
        assert "Cannot delete your own account" in delete_resp.json()["detail"]


class TestRegressionExistingEndpoints:
    """Regression tests - existing endpoints should still work without auth"""
    
    def test_intelligence_endpoint(self):
        """GET /api/intelligence still works (not protected)"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)
    
    def test_cross_border_watch_endpoint(self):
        """GET /api/cross-border/watch still works (not protected)"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        assert "bangladesh" in data or "myanmar" in data
    
    def test_daily_brief_endpoint(self):
        """GET /api/daily-brief still works (not protected)"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
    
    def test_dashboard_stats_endpoint(self):
        """GET /api/dashboard/stats still works (not protected)"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_items" in data or "critical_count" in data


class TestRoleBasedAccess:
    """Test RBAC - non-admin users cannot access admin endpoints"""
    
    @pytest.fixture
    def admin_headers(self):
        """Get admin headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        return {"Authorization": f"Bearer {response.json()['token']}"}
    
    @pytest.fixture
    def viewer_user(self, admin_headers):
        """Create a viewer user and return credentials"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "username": f"TEST_viewer_{unique_id}",
            "password": "ViewerPass123!",
            "role": "viewer"
        }
        create_resp = requests.post(f"{BASE_URL}/api/users", json=user_data, headers=admin_headers)
        user_id = create_resp.json()["id"]
        
        yield {**user_data, "id": user_id}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=admin_headers)
    
    def test_viewer_cannot_list_users(self, viewer_user):
        """Viewer role cannot access GET /api/users"""
        # Login as viewer
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": viewer_user["username"],
            "password": viewer_user["password"]
        })
        viewer_token = login_resp.json()["token"]
        
        # Try to list users
        response = requests.get(f"{BASE_URL}/api/users", headers={
            "Authorization": f"Bearer {viewer_token}"
        })
        assert response.status_code == 403, f"Viewer should get 403, got {response.status_code}"
    
    def test_viewer_cannot_create_users(self, viewer_user):
        """Viewer role cannot access POST /api/users"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": viewer_user["username"],
            "password": viewer_user["password"]
        })
        viewer_token = login_resp.json()["token"]
        
        response = requests.post(f"{BASE_URL}/api/users", json={
            "username": "should_fail",
            "password": "TestPass123!",
            "role": "viewer"
        }, headers={"Authorization": f"Bearer {viewer_token}"})
        assert response.status_code == 403


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
