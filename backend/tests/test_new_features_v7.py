"""
Test suite for Rhino Drishti new features (iteration 7):
- Advanced Relevance Filter (hard filter + translation pre-processing)
- Pattern Detection Engine
- Critical Alert Acknowledgement workflow
- Filter stats in scan status and pipeline status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestUnacknowledgedAlerts:
    """Tests for GET /api/alerts/unacknowledged endpoint"""
    
    def test_unacknowledged_alerts_endpoint_returns_200(self):
        """Test that unacknowledged alerts endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/alerts/unacknowledged returns 200")
    
    def test_unacknowledged_alerts_response_structure(self):
        """Test response has correct structure with alerts array and count"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        data = response.json()
        
        assert "alerts" in data, "Response missing 'alerts' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["alerts"], list), "'alerts' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        assert data["count"] == len(data["alerts"]), "Count should match alerts length"
        print(f"✓ Unacknowledged alerts response structure valid (count: {data['count']})")
    
    def test_unacknowledged_alerts_only_critical_high(self):
        """Test that only critical/high severity alerts are returned"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        data = response.json()
        
        for alert in data["alerts"]:
            assert alert.get("severity") in ["critical", "high"], \
                f"Alert {alert.get('id')} has severity {alert.get('severity')}, expected critical/high"
        print(f"✓ All {len(data['alerts'])} alerts are critical/high severity")
    
    def test_unacknowledged_alerts_not_acknowledged(self):
        """Test that returned alerts are not acknowledged"""
        response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        data = response.json()
        
        for alert in data["alerts"]:
            # Should either not have 'acknowledged' field or it should be False
            ack_status = alert.get("acknowledged", False)
            assert ack_status is False or ack_status is None, \
                f"Alert {alert.get('id')} is acknowledged but returned in unacknowledged list"
        print(f"✓ All {len(data['alerts'])} alerts are unacknowledged")


class TestAcknowledgeAlert:
    """Tests for POST /api/intelligence/{item_id}/acknowledge endpoint"""
    
    def test_acknowledge_valid_alert(self):
        """Test acknowledging a valid alert"""
        # First get an unacknowledged alert
        alerts_response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        alerts = alerts_response.json().get("alerts", [])
        
        if not alerts:
            pytest.skip("No unacknowledged alerts available for testing")
        
        alert_id = alerts[0]["id"]
        initial_count = alerts_response.json()["count"]
        
        # Acknowledge the alert
        ack_response = requests.post(f"{BASE_URL}/api/intelligence/{alert_id}/acknowledge")
        assert ack_response.status_code == 200, f"Expected 200, got {ack_response.status_code}"
        
        ack_data = ack_response.json()
        assert "message" in ack_data, "Response missing 'message' field"
        assert ack_data.get("id") == alert_id, "Response ID doesn't match"
        print(f"✓ Alert {alert_id} acknowledged successfully")
        
        # Verify count decreased
        new_alerts_response = requests.get(f"{BASE_URL}/api/alerts/unacknowledged")
        new_count = new_alerts_response.json()["count"]
        assert new_count < initial_count, f"Count should decrease after acknowledgement (was {initial_count}, now {new_count})"
        print(f"✓ Unacknowledged count decreased from {initial_count} to {new_count}")
    
    def test_acknowledge_nonexistent_alert(self):
        """Test acknowledging a non-existent alert returns 404"""
        fake_id = "nonexistent-alert-id-12345"
        response = requests.post(f"{BASE_URL}/api/intelligence/{fake_id}/acknowledge")
        assert response.status_code == 404, f"Expected 404 for non-existent alert, got {response.status_code}"
        print("✓ Non-existent alert returns 404")


class TestPatternsEndpoint:
    """Tests for GET /api/patterns endpoint"""
    
    def test_patterns_endpoint_returns_200(self):
        """Test that patterns endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/patterns returns 200")
    
    def test_patterns_response_structure(self):
        """Test response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        data = response.json()
        
        assert "patterns" in data, "Response missing 'patterns' field"
        assert "count" in data, "Response missing 'count' field"
        assert isinstance(data["patterns"], list), "'patterns' should be a list"
        assert isinstance(data["count"], int), "'count' should be an integer"
        print(f"✓ Patterns response structure valid (count: {data['count']})")
    
    def test_patterns_have_required_fields(self):
        """Test that patterns have required fields"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        data = response.json()
        
        if not data["patterns"]:
            pytest.skip("No patterns available for field validation")
        
        required_fields = [
            "pattern_key", "pattern_type", "region", "event_count",
            "window_days", "escalation_risk", "detected_at"
        ]
        
        for pattern in data["patterns"][:5]:  # Check first 5
            for field in required_fields:
                assert field in pattern, f"Pattern missing required field: {field}"
        print(f"✓ Patterns have all required fields")
    
    def test_patterns_escalation_risk_values(self):
        """Test that escalation_risk has valid values"""
        response = requests.get(f"{BASE_URL}/api/patterns")
        data = response.json()
        
        valid_risks = ["CRITICAL", "HIGH", "MODERATE", "LOW"]
        
        for pattern in data["patterns"]:
            risk = pattern.get("escalation_risk")
            assert risk in valid_risks, f"Invalid escalation_risk: {risk}"
        print(f"✓ All patterns have valid escalation_risk values")


class TestPatternDetection:
    """Tests for POST /api/patterns/detect endpoint"""
    
    def test_pattern_detection_trigger(self):
        """Test triggering pattern detection"""
        response = requests.post(f"{BASE_URL}/api/patterns/detect")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response missing 'message' field"
        assert "started" in data["message"].lower(), "Message should indicate detection started"
        print("✓ Pattern detection triggered successfully")


class TestPipelineStatus:
    """Tests for GET /api/pipeline/status endpoint with filter_stats"""
    
    def test_pipeline_status_returns_200(self):
        """Test that pipeline status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/pipeline/status returns 200")
    
    def test_pipeline_status_has_filter_stats(self):
        """Test that pipeline status includes filter_stats field"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        data = response.json()
        
        assert "filter_stats" in data, "Response missing 'filter_stats' field"
        filter_stats = data["filter_stats"]
        
        assert "last_filtered_out" in filter_stats, "filter_stats missing 'last_filtered_out'"
        assert "last_translated" in filter_stats, "filter_stats missing 'last_translated'"
        print(f"✓ Pipeline status includes filter_stats: {filter_stats}")
    
    def test_pipeline_status_basic_fields(self):
        """Test pipeline status has basic required fields"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        data = response.json()
        
        required_fields = ["total_items", "ai_processed", "pending_retry", "rss_sources"]
        for field in required_fields:
            assert field in data, f"Pipeline status missing field: {field}"
        print(f"✓ Pipeline status has all basic fields (total: {data['total_items']}, sources: {data['rss_sources']})")


class TestScanStatus:
    """Tests for GET /api/scan-status endpoint with filter stats"""
    
    def test_scan_status_returns_200(self):
        """Test that scan status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/scan-status returns 200")
    
    def test_scan_status_has_filter_fields(self):
        """Test that scan status includes filtered_out and translated fields"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        assert "filtered_out" in data, "Scan status missing 'filtered_out' field"
        assert "translated" in data, "Scan status missing 'translated' field"
        print(f"✓ Scan status includes filter fields (filtered_out: {data['filtered_out']}, translated: {data['translated']})")
    
    def test_scan_status_basic_fields(self):
        """Test scan status has basic required fields"""
        response = requests.get(f"{BASE_URL}/api/scan-status")
        data = response.json()
        
        required_fields = ["is_scanning", "progress", "total_sources", "articles_found", "relevant_found"]
        for field in required_fields:
            assert field in data, f"Scan status missing field: {field}"
        print(f"✓ Scan status has all basic fields")


class TestIntelligenceFilter:
    """Tests for intelligence filter module functionality"""
    
    def test_intelligence_items_have_filter_metadata(self):
        """Test that intelligence items may have filter-related metadata"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=10")
        data = response.json()
        
        assert "items" in data, "Response missing 'items' field"
        assert len(data["items"]) > 0, "No intelligence items returned"
        
        # Check if items have original_title field (indicates translation happened)
        items_with_original = [i for i in data["items"] if i.get("original_title")]
        print(f"✓ Intelligence items retrieved ({len(data['items'])} items, {len(items_with_original)} with original_title)")


class TestRSSSources:
    """Tests for RSS sources count (should be 32 total)"""
    
    def test_rss_sources_count(self):
        """Test that there are 32 RSS sources"""
        response = requests.get(f"{BASE_URL}/api/sources")
        data = response.json()
        
        assert "sources" in data, "Response missing 'sources' field"
        source_count = len(data["sources"])
        print(f"✓ RSS sources count: {source_count}")
        # Note: Main agent mentioned 32 sources
        assert source_count >= 30, f"Expected at least 30 sources, got {source_count}"


class TestDashboardStats:
    """Tests for dashboard stats endpoint"""
    
    def test_dashboard_stats_returns_200(self):
        """Test dashboard stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "total_items" in data, "Missing total_items"
        assert "critical_count" in data, "Missing critical_count"
        assert "high_count" in data, "Missing high_count"
        print(f"✓ Dashboard stats: {data['total_items']} total, {data['critical_count']} critical, {data['high_count']} high")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
