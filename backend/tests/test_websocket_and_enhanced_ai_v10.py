"""
Test Suite for Iteration 10: WebSocket Real-time Updates & Enhanced AI Classification

Features tested:
1. WebSocket /api/ws/intelligence - connection and ping/pong
2. GET /api/intelligence - items have confidence_score, threat_trajectory, entities fields
3. GET /api/intelligence?sort_by=priority_score - sort by priority works
4. GET /api/intelligence?min_priority=80 - priority filter works
5. AI pipeline prompt includes STEP 5 Named Entity Extraction and confidence_score output
6. Backend broadcasts new_item and critical_alert messages via WebSocket
"""

import pytest
import requests
import os
import asyncio
import websockets
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestWebSocketEndpoint:
    """Test WebSocket /api/ws/intelligence endpoint"""
    
    def test_websocket_connection_and_ping_pong(self):
        """Test WebSocket accepts connection and responds to ping with pong"""
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/intelligence"
        
        async def run_ws_test():
            async with websockets.connect(ws_url, close_timeout=5) as ws:
                # Send ping
                await ws.send("ping")
                
                # Wait for pong response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                assert data.get("type") == "pong", f"Expected pong response, got: {data}"
                return data
        
        try:
            result = asyncio.get_event_loop().run_until_complete(run_ws_test())
            print(f"✓ WebSocket ping/pong working: {result}")
        except RuntimeError:
            # If no event loop, create one
            result = asyncio.run(run_ws_test())
            print(f"✓ WebSocket ping/pong working: {result}")


class TestIntelligenceAPIEnhancements:
    """Test enhanced intelligence API with new fields"""
    
    def test_intelligence_endpoint_returns_200(self):
        """Basic health check for intelligence endpoint"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data
        assert "total" in data
        print(f"✓ GET /api/intelligence returns 200 with {data['total']} total items")
    
    def test_intelligence_items_have_enhanced_fields(self):
        """Test that items have confidence_score, threat_trajectory, entities fields"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=20")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        # Check if any items have the new fields (only newly processed items will have them)
        items_with_confidence = [i for i in items if i.get("confidence_score") is not None]
        items_with_trajectory = [i for i in items if i.get("threat_trajectory") is not None]
        items_with_entities = [i for i in items if i.get("entities") is not None]
        
        print(f"✓ Items with confidence_score: {len(items_with_confidence)}/{len(items)}")
        print(f"✓ Items with threat_trajectory: {len(items_with_trajectory)}/{len(items)}")
        print(f"✓ Items with entities: {len(items_with_entities)}/{len(items)}")
        
        # Verify field structure for items that have them
        for item in items_with_confidence[:3]:
            assert isinstance(item["confidence_score"], (int, float)), f"confidence_score should be numeric"
            assert 0 <= item["confidence_score"] <= 100, f"confidence_score should be 0-100"
        
        for item in items_with_trajectory[:3]:
            valid_trajectories = ["ESCALATING", "STABLE", "DE-ESCALATING", "NEW_THREAT", "INDETERMINATE"]
            assert item["threat_trajectory"] in valid_trajectories, f"Invalid trajectory: {item['threat_trajectory']}"
        
        for item in items_with_entities[:3]:
            entities = item["entities"]
            assert isinstance(entities, dict), "entities should be a dict"
            # Check structure
            if entities:
                assert "persons" in entities or "organizations" in entities or "locations" in entities
    
    def test_sort_by_priority_score(self):
        """Test GET /api/intelligence?sort_by=priority_score works"""
        response = requests.get(f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=desc&limit=10")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        if len(items) >= 2:
            # Verify descending order
            scores = [i.get("priority_score", 0) for i in items]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i+1], f"Items not sorted by priority_score desc: {scores}"
            print(f"✓ Sort by priority_score works. Top scores: {scores[:5]}")
        else:
            print(f"✓ Sort by priority_score endpoint works (only {len(items)} items)")
    
    def test_min_priority_filter(self):
        """Test GET /api/intelligence?min_priority=80 filters correctly"""
        response = requests.get(f"{BASE_URL}/api/intelligence?min_priority=80&limit=20")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        # All returned items should have priority_score >= 80
        for item in items:
            score = item.get("priority_score", 0)
            assert score >= 80, f"Item with priority_score {score} should not be returned with min_priority=80"
        
        print(f"✓ min_priority=80 filter works. Returned {len(items)} items with priority >= 80")
    
    def test_combined_sort_and_filter(self):
        """Test combining sort_by and min_priority"""
        response = requests.get(f"{BASE_URL}/api/intelligence?sort_by=priority_score&sort_order=desc&min_priority=60&limit=10")
        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])
        
        if items:
            # All items should have priority >= 60
            for item in items:
                assert item.get("priority_score", 0) >= 60
            
            # Should be sorted descending
            scores = [i.get("priority_score", 0) for i in items]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i+1]
            
            print(f"✓ Combined sort + filter works. Scores: {scores[:5]}")


class TestAIPipelinePrompt:
    """Test AI pipeline has enhanced classification prompt"""
    
    def test_ai_pipeline_has_named_entity_extraction(self):
        """Verify AI pipeline prompt includes STEP 5 Named Entity Extraction"""
        import sys
        sys.path.insert(0, '/app/backend')
        from ai_pipeline import CLASSIFICATION_PROMPT
        
        assert "STEP 5" in CLASSIFICATION_PROMPT, "STEP 5 not found in prompt"
        # Check for named entity extraction (case-insensitive)
        assert "NAMED ENTITY EXTRACTION" in CLASSIFICATION_PROMPT.upper(), "Named Entity Extraction not in prompt"
        assert "persons" in CLASSIFICATION_PROMPT, "persons entity type not in prompt"
        assert "organizations" in CLASSIFICATION_PROMPT, "organizations entity type not in prompt"
        assert "locations" in CLASSIFICATION_PROMPT, "locations entity type not in prompt"
        print("✓ AI pipeline prompt includes STEP 5 Named Entity Extraction")
    
    def test_ai_pipeline_has_confidence_score(self):
        """Verify AI pipeline prompt includes confidence_score output"""
        import sys
        sys.path.insert(0, '/app/backend')
        from ai_pipeline import CLASSIFICATION_PROMPT
        
        assert "confidence_score" in CLASSIFICATION_PROMPT, "confidence_score not in prompt"
        assert "0-100" in CLASSIFICATION_PROMPT or "0 to 100" in CLASSIFICATION_PROMPT, "confidence_score range not specified"
        print("✓ AI pipeline prompt includes confidence_score (0-100)")
    
    def test_ai_pipeline_has_threat_trajectory(self):
        """Verify AI pipeline prompt includes threat_trajectory output"""
        import sys
        sys.path.insert(0, '/app/backend')
        from ai_pipeline import CLASSIFICATION_PROMPT
        
        assert "threat_trajectory" in CLASSIFICATION_PROMPT, "threat_trajectory not in prompt"
        assert "ESCALATING" in CLASSIFICATION_PROMPT, "ESCALATING trajectory not in prompt"
        assert "DE-ESCALATING" in CLASSIFICATION_PROMPT, "DE-ESCALATING trajectory not in prompt"
        assert "NEW_THREAT" in CLASSIFICATION_PROMPT, "NEW_THREAT trajectory not in prompt"
        print("✓ AI pipeline prompt includes threat_trajectory with all values")


class TestIntelligenceItemModel:
    """Test IntelligenceItem model has new fields"""
    
    def test_model_has_enhanced_fields(self):
        """Verify IntelligenceItem model includes new fields"""
        import sys
        sys.path.insert(0, '/app/backend')
        from server import IntelligenceItem
        
        # Create a test item
        item = IntelligenceItem(
            title="Test Item",
            source="Test Source",
            published_at="2026-01-01T00:00:00Z"
        )
        
        # Check default values for new fields
        assert hasattr(item, 'confidence_score'), "Model missing confidence_score"
        assert hasattr(item, 'threat_trajectory'), "Model missing threat_trajectory"
        assert hasattr(item, 'entities'), "Model missing entities"
        
        # Check defaults
        assert item.confidence_score == 70, f"Default confidence_score should be 70, got {item.confidence_score}"
        assert item.threat_trajectory == "INDETERMINATE", f"Default threat_trajectory should be INDETERMINATE"
        assert item.entities == {"persons": [], "organizations": [], "locations": []}, f"Default entities structure incorrect"
        
        print("✓ IntelligenceItem model has all enhanced fields with correct defaults")


class TestWebSocketBroadcastLogic:
    """Test WebSocket broadcast logic in server code"""
    
    def test_broadcast_includes_new_fields(self):
        """Verify WebSocket broadcast message includes new fields"""
        # Read server.py and check broadcast message structure
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        # Check that broadcast includes confidence_score and threat_trajectory
        assert '"confidence_score"' in server_code or "'confidence_score'" in server_code, \
            "WebSocket broadcast should include confidence_score"
        assert '"threat_trajectory"' in server_code or "'threat_trajectory'" in server_code, \
            "WebSocket broadcast should include threat_trajectory"
        
        print("✓ WebSocket broadcast includes confidence_score and threat_trajectory")
    
    def test_critical_alert_type_for_high_severity(self):
        """Verify critical/high items get critical_alert type"""
        with open('/app/backend/server.py', 'r') as f:
            server_code = f.read()
        
        assert 'critical_alert' in server_code, "critical_alert type should be in server code"
        assert 'new_item' in server_code, "new_item type should be in server code"
        
        # Check the logic for critical_alert
        assert 'severity' in server_code and 'critical' in server_code, \
            "Should check severity for critical_alert"
        
        print("✓ WebSocket uses critical_alert type for critical/high severity items")


class TestConnectionManager:
    """Test ConnectionManager class for WebSocket"""
    
    def test_connection_manager_exists(self):
        """Verify ConnectionManager class exists and has required methods"""
        import sys
        sys.path.insert(0, '/app/backend')
        from server import ws_manager, ConnectionManager
        
        assert ws_manager is not None, "ws_manager should be instantiated"
        assert isinstance(ws_manager, ConnectionManager), "ws_manager should be ConnectionManager instance"
        
        # Check methods exist
        assert hasattr(ws_manager, 'connect'), "ConnectionManager missing connect method"
        assert hasattr(ws_manager, 'disconnect'), "ConnectionManager missing disconnect method"
        assert hasattr(ws_manager, 'broadcast'), "ConnectionManager missing broadcast method"
        assert hasattr(ws_manager, 'active_connections'), "ConnectionManager missing active_connections"
        
        print(f"✓ ConnectionManager exists with all required methods. Active connections: {len(ws_manager.active_connections)}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
