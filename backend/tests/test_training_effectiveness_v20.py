"""
Test Training Effectiveness Score Feature - Iteration 20
Tests the new GET /api/training/effectiveness endpoint that computes alignment
between AI classifications (severity) and analyst feedback ratings.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTrainingEffectivenessEndpoint:
    """Tests for GET /api/training/effectiveness endpoint"""
    
    def test_effectiveness_endpoint_returns_200(self):
        """Verify the effectiveness endpoint is accessible and returns 200"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/training/effectiveness returns 200")
    
    def test_effectiveness_response_structure(self):
        """Verify response contains required fields: score, grade, sample_size, worst_misalignments, best_alignments, trend, delta_from_last"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "score" in data, "Response missing 'score' field"
        assert "grade" in data, "Response missing 'grade' field"
        assert "sample_size" in data, "Response missing 'sample_size' field"
        assert "worst_misalignments" in data, "Response missing 'worst_misalignments' field"
        assert "best_alignments" in data, "Response missing 'best_alignments' field"
        assert "trend" in data, "Response missing 'trend' field"
        assert "delta_from_last" in data, "Response missing 'delta_from_last' field"
        
        print(f"✓ Response structure valid with all required fields")
        print(f"  - score: {data['score']}")
        print(f"  - grade: {data['grade']}")
        print(f"  - sample_size: {data['sample_size']}")
    
    def test_effectiveness_score_range(self):
        """Verify score is either null (insufficient data) or 0-100"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        score = data.get("score")
        if score is not None:
            assert isinstance(score, (int, float)), f"Score should be numeric, got {type(score)}"
            assert 0 <= score <= 100, f"Score should be 0-100, got {score}"
            print(f"✓ Score {score} is within valid range 0-100")
        else:
            assert data.get("grade") == "INSUFFICIENT_DATA", "When score is null, grade should be INSUFFICIENT_DATA"
            print("✓ Score is null with INSUFFICIENT_DATA grade (no rated items)")
    
    def test_effectiveness_grade_mapping(self):
        """Verify grade mapping: >=80 EXCELLENT, >=65 GOOD, >=50 MODERATE, >=35 NEEDS_IMPROVEMENT, <35 POOR"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        score = data.get("score")
        grade = data.get("grade")
        
        valid_grades = ["EXCELLENT", "GOOD", "MODERATE", "NEEDS_IMPROVEMENT", "POOR", "INSUFFICIENT_DATA"]
        assert grade in valid_grades, f"Invalid grade: {grade}"
        
        if score is not None:
            if score >= 80:
                expected = "EXCELLENT"
            elif score >= 65:
                expected = "GOOD"
            elif score >= 50:
                expected = "MODERATE"
            elif score >= 35:
                expected = "NEEDS_IMPROVEMENT"
            else:
                expected = "POOR"
            assert grade == expected, f"Score {score} should have grade {expected}, got {grade}"
            print(f"✓ Grade mapping correct: score {score} -> {grade}")
        else:
            print(f"✓ Grade is {grade} (no score available)")
    
    def test_worst_misalignments_structure(self):
        """Verify worst_misalignments is a list with proper item structure"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        worst = data.get("worst_misalignments", [])
        assert isinstance(worst, list), "worst_misalignments should be a list"
        assert len(worst) <= 5, f"worst_misalignments should have max 5 items, got {len(worst)}"
        
        if worst:
            item = worst[0]
            required_fields = ["id", "title", "ai_severity", "ai_mapped", "analyst_avg", "ratings_count", "alignment"]
            for field in required_fields:
                assert field in item, f"Misalignment item missing '{field}' field"
            
            # Verify alignment is sorted (worst first = lowest alignment)
            alignments = [m["alignment"] for m in worst]
            assert alignments == sorted(alignments), "worst_misalignments should be sorted by alignment ascending"
            print(f"✓ worst_misalignments structure valid with {len(worst)} items, sorted correctly")
        else:
            print("✓ worst_misalignments is empty (no rated items)")
    
    def test_best_alignments_structure(self):
        """Verify best_alignments is a list with proper item structure"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        best = data.get("best_alignments", [])
        assert isinstance(best, list), "best_alignments should be a list"
        assert len(best) <= 5, f"best_alignments should have max 5 items, got {len(best)}"
        
        if best:
            item = best[0]
            required_fields = ["id", "title", "ai_severity", "ai_mapped", "analyst_avg", "ratings_count", "alignment"]
            for field in required_fields:
                assert field in item, f"Alignment item missing '{field}' field"
            
            # Verify alignment is sorted (best first = highest alignment)
            alignments = [m["alignment"] for m in best]
            assert alignments == sorted(alignments, reverse=True), "best_alignments should be sorted by alignment descending"
            print(f"✓ best_alignments structure valid with {len(best)} items, sorted correctly")
        else:
            print("✓ best_alignments is empty (no rated items)")
    
    def test_trend_structure(self):
        """Verify trend is a list of historical snapshots"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        trend = data.get("trend", [])
        assert isinstance(trend, list), "trend should be a list"
        
        if trend:
            snapshot = trend[0]
            assert "score" in snapshot, "Trend snapshot missing 'score'"
            assert "sample_size" in snapshot, "Trend snapshot missing 'sample_size'"
            assert "timestamp" in snapshot, "Trend snapshot missing 'timestamp'"
            print(f"✓ trend structure valid with {len(trend)} historical snapshots")
        else:
            print("✓ trend is empty (no training runs completed since feature added)")
    
    def test_delta_from_last_value(self):
        """Verify delta_from_last is null or a numeric value"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        delta = data.get("delta_from_last")
        if delta is not None:
            assert isinstance(delta, (int, float)), f"delta_from_last should be numeric, got {type(delta)}"
            print(f"✓ delta_from_last is {delta}")
        else:
            print("✓ delta_from_last is null (no previous snapshot to compare)")
    
    def test_alignment_item_fields_valid(self):
        """Verify alignment items have valid field values"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("worst_misalignments", []) + data.get("best_alignments", [])
        
        for item in all_items:
            # ai_severity should be a string (critical, high, medium, low, unknown)
            assert isinstance(item.get("ai_severity"), str), "ai_severity should be string"
            
            # ai_mapped should be numeric (the mapped score)
            assert isinstance(item.get("ai_mapped"), (int, float)), "ai_mapped should be numeric"
            
            # analyst_avg should be numeric (1-6 range)
            analyst_avg = item.get("analyst_avg")
            assert isinstance(analyst_avg, (int, float)), "analyst_avg should be numeric"
            
            # alignment should be 0-1 range
            alignment = item.get("alignment")
            assert isinstance(alignment, (int, float)), "alignment should be numeric"
            assert 0 <= alignment <= 1, f"alignment should be 0-1, got {alignment}"
            
            # ratings_count should be positive integer
            ratings_count = item.get("ratings_count")
            assert isinstance(ratings_count, int), "ratings_count should be integer"
            assert ratings_count >= 1, "ratings_count should be >= 1"
        
        if all_items:
            print(f"✓ All {len(all_items)} alignment items have valid field values")
        else:
            print("✓ No alignment items to validate (no rated items)")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after adding effectiveness feature"""
    
    def test_training_add_url_with_relevance(self):
        """POST /api/training/add-url with relevance still works"""
        test_url = f"https://test-effectiveness-{uuid.uuid4().hex[:8]}.com/article"
        response = requests.post(f"{BASE_URL}/api/training/add-url", json={
            "url": test_url,
            "relevance": 5
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("relevance") == 5
        
        # Cleanup
        item_id = data.get("id")
        if item_id:
            requests.delete(f"{BASE_URL}/api/training/queue/{item_id}")
        
        print("✓ POST /api/training/add-url with relevance still works")
    
    def test_training_activity_log(self):
        """GET /api/training/activity-log still works"""
        response = requests.get(f"{BASE_URL}/api/training/activity-log")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "entries" in data
        assert "summary" in data
        assert "ai_impact" in data
        print("✓ GET /api/training/activity-log still works")
    
    def test_feedback_stats(self):
        """GET /api/feedback/stats still works"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/feedback/stats still works")
    
    def test_training_queue(self):
        """GET /api/training/queue still works"""
        response = requests.get(f"{BASE_URL}/api/training/queue")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        print("✓ GET /api/training/queue still works")


class TestSeverityMapping:
    """Test the SEVERITY_MAP values used in effectiveness calculation"""
    
    def test_severity_map_values_documented(self):
        """Document the expected severity mapping: critical=6, high=5, medium=3.5, low=2"""
        # This test documents the expected mapping based on the code
        # The actual mapping is: SEVERITY_MAP = {"critical": 6.0, "high": 5.0, "medium": 3.5, "low": 2.0}
        expected_map = {
            "critical": 6.0,
            "high": 5.0,
            "medium": 3.5,
            "low": 2.0
        }
        
        # We can verify this indirectly by checking alignment items
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get("worst_misalignments", []) + data.get("best_alignments", [])
        
        for item in all_items:
            sev = item.get("ai_severity", "").lower()
            mapped = item.get("ai_mapped")
            
            if sev in expected_map:
                assert mapped == expected_map[sev], f"Severity '{sev}' should map to {expected_map[sev]}, got {mapped}"
        
        print(f"✓ Severity mapping verified: critical=6, high=5, medium=3.5, low=2")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
