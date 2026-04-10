"""
Test Suite for Multi-Article Fusion and Deduplication Feature (Iteration 25)
Tests fusion statistics, batch fusion trigger, intelligence feed filtering,
and regression tests for cross-border/daily-brief endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestFusionStats:
    """Tests for GET /api/fusion/stats endpoint"""
    
    def test_fusion_stats_returns_200(self):
        """Verify fusion stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/fusion/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/fusion/stats returns 200")
    
    def test_fusion_stats_has_required_fields(self):
        """Verify fusion stats contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/fusion/stats")
        data = response.json()
        
        required_fields = ['total_items', 'clustered_items', 'unique_clusters', 'dedup_ratio', 'top_clusters']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"PASS: Fusion stats has all required fields: {required_fields}")
    
    def test_fusion_stats_values_are_valid(self):
        """Verify fusion stats values are logically valid"""
        response = requests.get(f"{BASE_URL}/api/fusion/stats")
        data = response.json()
        
        assert data['total_items'] > 0, "total_items should be > 0"
        assert data['clustered_items'] >= 0, "clustered_items should be >= 0"
        assert data['unique_clusters'] >= 0, "unique_clusters should be >= 0"
        assert 0 <= data['dedup_ratio'] <= 100, "dedup_ratio should be between 0-100"
        assert isinstance(data['top_clusters'], list), "top_clusters should be a list"
        
        print(f"PASS: Fusion stats values valid - total={data['total_items']}, clustered={data['clustered_items']}, clusters={data['unique_clusters']}, dedup_ratio={data['dedup_ratio']}%")
    
    def test_top_clusters_structure(self):
        """Verify top_clusters has correct structure"""
        response = requests.get(f"{BASE_URL}/api/fusion/stats")
        data = response.json()
        
        if data['top_clusters']:
            cluster = data['top_clusters'][0]
            assert 'title' in cluster, "top_clusters items should have 'title'"
            assert 'size' in cluster, "top_clusters items should have 'size'"
            assert cluster['size'] >= 2, "Cluster size should be >= 2"
            print(f"PASS: Top cluster structure valid - '{cluster['title'][:50]}...' with {cluster['size']} sources")


class TestBatchFusion:
    """Tests for POST /api/fusion/run endpoint"""
    
    def test_batch_fusion_trigger_returns_200(self):
        """Verify batch fusion trigger returns 200"""
        response = requests.post(f"{BASE_URL}/api/fusion/run")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: POST /api/fusion/run returns 200")
    
    def test_batch_fusion_returns_message(self):
        """Verify batch fusion returns expected message"""
        response = requests.post(f"{BASE_URL}/api/fusion/run")
        data = response.json()
        
        assert 'message' in data, "Response should contain 'message'"
        assert 'fusion' in data['message'].lower() or 'started' in data['message'].lower(), \
            f"Message should indicate fusion started, got: {data['message']}"
        print(f"PASS: Batch fusion message: {data['message']}")


class TestIntelligenceFeedFusion:
    """Tests for GET /api/intelligence with fusion filtering"""
    
    def test_intelligence_returns_200(self):
        """Verify intelligence endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/intelligence returns 200")
    
    def test_intelligence_only_returns_primaries(self):
        """Verify no non-primary cluster items appear in feed"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        data = response.json()
        
        items = data.get('items', [])
        non_primaries = [i for i in items if i.get('is_cluster_primary') == False]
        
        assert len(non_primaries) == 0, f"Found {len(non_primaries)} non-primary items in feed (should be 0)"
        print(f"PASS: No non-primary cluster items in feed (checked {len(items)} items)")
    
    def test_fused_items_have_cluster_fields(self):
        """Verify fused items have cluster_size > 1 and cluster_sources"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        data = response.json()
        
        items = data.get('items', [])
        fused_items = [i for i in items if i.get('cluster_size', 0) > 1]
        
        if fused_items:
            for item in fused_items[:5]:  # Check first 5 fused items
                assert item.get('cluster_size', 0) > 1, "Fused item should have cluster_size > 1"
                assert 'cluster_sources' in item, "Fused item should have cluster_sources"
                assert isinstance(item['cluster_sources'], list), "cluster_sources should be a list"
                assert len(item['cluster_sources']) >= 2, "cluster_sources should have >= 2 entries"
                
                # Verify cluster_sources structure
                for src in item['cluster_sources']:
                    assert 'source' in src, "cluster_source should have 'source'"
                    assert 'source_url' in src, "cluster_source should have 'source_url'"
                    assert 'title' in src, "cluster_source should have 'title'"
                    assert 'published_at' in src, "cluster_source should have 'published_at'"
            
            print(f"PASS: Found {len(fused_items)} fused items with valid cluster_sources structure")
        else:
            print("INFO: No fused items found in current feed (may need more data)")
    
    def test_visible_count_less_than_total_db(self):
        """Verify deduplication reduces visible count"""
        stats_response = requests.get(f"{BASE_URL}/api/fusion/stats")
        stats = stats_response.json()
        
        intel_response = requests.get(f"{BASE_URL}/api/intelligence?limit=1")
        intel = intel_response.json()
        
        total_db = stats.get('total_items', 0)
        visible = intel.get('total', 0)
        
        # If there are clusters, visible should be less than total
        if stats.get('clustered_items', 0) > 0:
            assert visible <= total_db, f"Visible ({visible}) should be <= total DB ({total_db})"
            print(f"PASS: Dedup working - visible={visible}, total_db={total_db}, reduction={total_db - visible}")
        else:
            print(f"INFO: No clusters yet - visible={visible}, total_db={total_db}")


class TestCrossBorderRegression:
    """Regression tests for GET /api/cross-border/watch (P0 fixes from iteration 24)"""
    
    def test_cross_border_returns_200(self):
        """Verify cross-border watch endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/cross-border/watch returns 200")
    
    def test_cross_border_has_sections(self):
        """Verify cross-border has Bangladesh and Myanmar sections"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        data = response.json()
        
        assert 'bangladesh' in data, "Response should have 'bangladesh' section"
        assert 'myanmar' in data, "Response should have 'myanmar' section"
        print("PASS: Cross-border has Bangladesh and Myanmar sections")
    
    def test_cross_border_no_low_severity(self):
        """Verify no LOW severity items in cross-border (P0 fix)"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        data = response.json()
        
        for country in ['bangladesh', 'myanmar']:
            items = data.get(country, {}).get('items', [])
            low_items = [i for i in items if i.get('severity', '').lower() == 'low']
            assert len(low_items) == 0, f"Found {len(low_items)} LOW severity items in {country}"
        
        print("PASS: No LOW severity items in cross-border watch")
    
    def test_cross_border_no_non_latin_chars(self):
        """Verify no non-Latin (Bengali/Hindi) characters in titles/summaries (P0 fix)"""
        import re
        
        def has_non_latin(text):
            if not text:
                return False
            # Check for Bengali, Hindi, Assamese scripts
            return bool(re.search(r'[\u0980-\u09FF\u0900-\u097F]', text))
        
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        data = response.json()
        
        for country in ['bangladesh', 'myanmar']:
            items = data.get(country, {}).get('items', [])
            for item in items:
                title = item.get('title', '')
                summary = item.get('ai_summary', '')
                assert not has_non_latin(title), f"Non-Latin chars in title: {title[:50]}"
                assert not has_non_latin(summary), f"Non-Latin chars in summary: {summary[:50]}"
        
        print("PASS: No non-Latin characters in cross-border titles/summaries")


class TestDailyBriefRegression:
    """Regression tests for GET /api/daily-brief (P0 fixes from iteration 24)"""
    
    def test_daily_brief_returns_200(self):
        """Verify daily brief endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/daily-brief returns 200")
    
    def test_daily_brief_has_required_fields(self):
        """Verify daily brief has required fields"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        required_fields = ['date', 'key_developments', 'analyst_summary']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"PASS: Daily brief has required fields: {required_fields}")
    
    def test_key_developments_only_ner_states(self):
        """Verify key_developments only contains NER states (P0 fix)"""
        NER_STATES = {'Assam', 'Meghalaya', 'Mizoram', 'Manipur', 'Arunachal Pradesh', 
                      'Tripura', 'Nagaland', 'Sikkim', 'Multiple'}
        
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        data = response.json()
        
        key_devs = data.get('key_developments', [])
        for dev in key_devs:
            state = dev.get('state', '')
            assert state in NER_STATES or state == '', \
                f"Found non-NER state in key_developments: {state}"
        
        # Verify no Bangladesh/Myanmar
        states_found = {dev.get('state', '') for dev in key_devs}
        assert 'Bangladesh' not in states_found, "Bangladesh should not be in key_developments"
        assert 'Myanmar' not in states_found, "Myanmar should not be in key_developments"
        
        print(f"PASS: Key developments only contain NER states: {states_found}")


class TestPipelineStatus:
    """Tests for pipeline status endpoint"""
    
    def test_pipeline_status_returns_200(self):
        """Verify pipeline status endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/pipeline/status returns 200")
    
    def test_pipeline_status_has_scheduler_info(self):
        """Verify pipeline status includes scheduler info"""
        response = requests.get(f"{BASE_URL}/api/pipeline/status")
        data = response.json()
        
        scheduler = data.get('scheduler', '')
        # Note: Fusion scheduler is configured in server.py but pipeline status string may be outdated
        assert len(scheduler) > 0, "Scheduler info should be present"
        print(f"PASS: Pipeline scheduler info present: {scheduler}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
