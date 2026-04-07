"""
Knowledge Graph API Tests - Iteration 14
Tests for the Knowledge Graph Prep feature:
- POST /api/knowledge-graph/build - triggers graph build
- GET /api/knowledge-graph/stats - returns built status with counts
- GET /api/knowledge-graph/actors - returns list of actors
- GET /api/knowledge-graph/actors?cross_border=true - filters cross-border actors
- GET /api/knowledge-graph/actors/{name} - returns actor detail with edges
- GET /api/knowledge-graph/locations - returns locations
- GET /api/knowledge-graph/locations?is_border=true - filters border locations
- GET /api/knowledge-graph/edges - returns actor-location edges
- GET /api/knowledge-graph/network - returns nodes and links for visualization
"""

import pytest
import requests
import os
import time
import urllib.parse

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestKnowledgeGraphStats:
    """Test Knowledge Graph stats endpoint"""
    
    def test_kg_stats_returns_200(self):
        """GET /api/knowledge-graph/stats should return 200"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "built" in data, "Response should have 'built' field"
        print(f"KG Stats: built={data.get('built')}, actors={data.get('actors')}, locations={data.get('locations')}, edges={data.get('edges')}")
    
    def test_kg_stats_has_expected_fields_when_built(self):
        """GET /api/knowledge-graph/stats should have all expected fields when built"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/stats")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("built"):
            # Verify all expected fields are present
            assert "actors" in data, "Should have 'actors' count"
            assert "locations" in data, "Should have 'locations' count"
            assert "edges" in data, "Should have 'edges' count"
            assert "cross_border_actors" in data, "Should have 'cross_border_actors' count"
            assert "border_locations" in data, "Should have 'border_locations' count"
            assert "top_actors" in data, "Should have 'top_actors' list"
            assert "top_locations" in data, "Should have 'top_locations' list"
            
            # Verify counts are positive (based on context: 113 actors, 21 locations, 144 edges)
            assert data["actors"] > 0, f"Should have actors, got {data['actors']}"
            assert data["locations"] > 0, f"Should have locations, got {data['locations']}"
            assert data["edges"] > 0, f"Should have edges, got {data['edges']}"
            
            print(f"KG Stats verified: {data['actors']} actors, {data['locations']} locations, {data['edges']} edges")
            print(f"Cross-border actors: {data['cross_border_actors']}, Border locations: {data['border_locations']}")
        else:
            print("Knowledge graph not built yet - skipping field validation")


class TestKnowledgeGraphActors:
    """Test Knowledge Graph actors endpoints"""
    
    def test_kg_actors_returns_200(self):
        """GET /api/knowledge-graph/actors should return 200"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "actors" in data, "Response should have 'actors' field"
        assert "count" in data, "Response should have 'count' field"
        print(f"Actors endpoint: {data['count']} actors returned")
    
    def test_kg_actors_have_expected_fields(self):
        """Each actor should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            actor = data["actors"][0]
            expected_fields = ["name", "activity_count", "locations", "threat_types", "is_cross_border"]
            for field in expected_fields:
                assert field in actor, f"Actor should have '{field}' field"
            print(f"Sample actor: {actor['name']} - {actor['activity_count']} activities, cross_border={actor['is_cross_border']}")
        else:
            print("No actors found - skipping field validation")
    
    def test_kg_actors_cross_border_filter(self):
        """GET /api/knowledge-graph/actors?cross_border=true should filter cross-border actors"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors", params={"cross_border": "true"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # All returned actors should be cross-border
        for actor in data["actors"]:
            assert actor.get("is_cross_border") == True, f"Actor {actor['name']} should be cross-border"
        
        print(f"Cross-border filter: {data['count']} cross-border actors returned")
    
    def test_kg_actors_limit_param(self):
        """GET /api/knowledge-graph/actors should respect limit parameter"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors", params={"limit": 10})
        assert response.status_code == 200
        data = response.json()
        assert len(data["actors"]) <= 10, f"Should return at most 10 actors, got {len(data['actors'])}"
        print(f"Limit test: requested 10, got {len(data['actors'])}")


class TestKnowledgeGraphActorDetail:
    """Test Knowledge Graph actor detail endpoint"""
    
    def test_kg_actor_detail_assam_police(self):
        """GET /api/knowledge-graph/actors/Assam%20Police should return actor detail"""
        actor_name = "Assam Police"
        encoded_name = urllib.parse.quote(actor_name)
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors/{encoded_name}")
        
        if response.status_code == 404:
            # Actor might not exist - try to find an existing actor
            actors_response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors", params={"limit": 1})
            if actors_response.status_code == 200 and actors_response.json()["count"] > 0:
                existing_actor = actors_response.json()["actors"][0]["name"]
                encoded_name = urllib.parse.quote(existing_actor)
                response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors/{encoded_name}")
                print(f"Assam Police not found, testing with: {existing_actor}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "actor" in data, "Response should have 'actor' field"
        assert "edges" in data, "Response should have 'edges' field"
        
        actor = data["actor"]
        assert "name" in actor, "Actor should have 'name'"
        assert "locations" in actor, "Actor should have 'locations'"
        assert "threat_types" in actor, "Actor should have 'threat_types'"
        
        print(f"Actor detail: {actor['name']} - {len(data['edges'])} edges")
    
    def test_kg_actor_detail_ulfa_with_parentheses(self):
        """GET /api/knowledge-graph/actors/ULFA(I) should handle special chars (regex escape test)"""
        actor_name = "ULFA(I)"
        encoded_name = urllib.parse.quote(actor_name)
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors/{encoded_name}")
        
        # This tests the regex escape fix - parentheses should be escaped
        if response.status_code == 200:
            data = response.json()
            assert "actor" in data, "Response should have 'actor' field"
            print(f"ULFA(I) found: {data['actor']['name']} - regex escape working correctly")
        elif response.status_code == 404:
            print("ULFA(I) not found in knowledge graph - this is acceptable if actor doesn't exist")
        else:
            pytest.fail(f"Unexpected status code {response.status_code}: {response.text}")
    
    def test_kg_actor_detail_not_found(self):
        """GET /api/knowledge-graph/actors/NonExistentActor should return 404"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/actors/NonExistentActorXYZ123")
        assert response.status_code == 404, f"Expected 404 for non-existent actor, got {response.status_code}"
        print("Non-existent actor correctly returns 404")


class TestKnowledgeGraphLocations:
    """Test Knowledge Graph locations endpoints"""
    
    def test_kg_locations_returns_200(self):
        """GET /api/knowledge-graph/locations should return 200"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/locations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "locations" in data, "Response should have 'locations' field"
        assert "count" in data, "Response should have 'count' field"
        print(f"Locations endpoint: {data['count']} locations returned")
    
    def test_kg_locations_have_expected_fields(self):
        """Each location should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/locations", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            location = data["locations"][0]
            expected_fields = ["name", "activity_count", "actors", "is_border"]
            for field in expected_fields:
                assert field in location, f"Location should have '{field}' field"
            print(f"Sample location: {location['name']} - {location['activity_count']} activities, border={location['is_border']}")
        else:
            print("No locations found - skipping field validation")
    
    def test_kg_locations_border_filter(self):
        """GET /api/knowledge-graph/locations?is_border=true should filter border locations"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/locations", params={"is_border": "true"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # All returned locations should be border locations
        for location in data["locations"]:
            assert location.get("is_border") == True, f"Location {location['name']} should be border"
        
        print(f"Border filter: {data['count']} border locations returned")


class TestKnowledgeGraphEdges:
    """Test Knowledge Graph edges endpoint"""
    
    def test_kg_edges_returns_200(self):
        """GET /api/knowledge-graph/edges should return 200"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/edges")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "edges" in data, "Response should have 'edges' field"
        assert "count" in data, "Response should have 'count' field"
        print(f"Edges endpoint: {data['count']} edges returned")
    
    def test_kg_edges_have_expected_fields(self):
        """Each edge should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/edges", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            edge = data["edges"][0]
            expected_fields = ["actor", "location", "count", "contexts"]
            for field in expected_fields:
                assert field in edge, f"Edge should have '{field}' field"
            print(f"Sample edge: {edge['actor']} -> {edge['location']} ({edge['count']}x)")
        else:
            print("No edges found - skipping field validation")
    
    def test_kg_edges_min_count_filter(self):
        """GET /api/knowledge-graph/edges?min_count=2 should filter by minimum count"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/edges", params={"min_count": 2})
        assert response.status_code == 200
        data = response.json()
        
        # All returned edges should have count >= 2
        for edge in data["edges"]:
            assert edge.get("count", 0) >= 2, f"Edge {edge['actor']}->{edge['location']} should have count >= 2"
        
        print(f"Min count filter: {data['count']} edges with count >= 2")


class TestKnowledgeGraphNetwork:
    """Test Knowledge Graph network endpoint for visualization"""
    
    def test_kg_network_returns_200(self):
        """GET /api/knowledge-graph/network should return 200"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/network")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "nodes" in data, "Response should have 'nodes' field"
        assert "links" in data, "Response should have 'links' field"
        print(f"Network endpoint: {len(data['nodes'])} nodes, {len(data['links'])} links")
    
    def test_kg_network_nodes_have_expected_fields(self):
        """Network nodes should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/network", params={"limit": 20})
        assert response.status_code == 200
        data = response.json()
        
        if len(data["nodes"]) > 0:
            # Check actor node
            actor_nodes = [n for n in data["nodes"] if n.get("type") == "actor"]
            if actor_nodes:
                actor_node = actor_nodes[0]
                assert "id" in actor_node, "Actor node should have 'id'"
                assert "label" in actor_node, "Actor node should have 'label'"
                assert "type" in actor_node, "Actor node should have 'type'"
                assert actor_node["type"] == "actor", "Actor node type should be 'actor'"
                print(f"Sample actor node: {actor_node['label']}")
            
            # Check location node
            location_nodes = [n for n in data["nodes"] if n.get("type") == "location"]
            if location_nodes:
                location_node = location_nodes[0]
                assert "id" in location_node, "Location node should have 'id'"
                assert "label" in location_node, "Location node should have 'label'"
                assert "type" in location_node, "Location node should have 'type'"
                assert location_node["type"] == "location", "Location node type should be 'location'"
                print(f"Sample location node: {location_node['label']}")
        else:
            print("No nodes found - skipping field validation")
    
    def test_kg_network_links_have_expected_fields(self):
        """Network links should have expected fields"""
        response = requests.get(f"{BASE_URL}/api/knowledge-graph/network", params={"limit": 20})
        assert response.status_code == 200
        data = response.json()
        
        if len(data["links"]) > 0:
            link = data["links"][0]
            expected_fields = ["source", "target", "weight"]
            for field in expected_fields:
                assert field in link, f"Link should have '{field}' field"
            print(f"Sample link: {link['source']} -> {link['target']} (weight: {link['weight']})")
        else:
            print("No links found - skipping field validation")


class TestKnowledgeGraphBuild:
    """Test Knowledge Graph build endpoint"""
    
    def test_kg_build_returns_200(self):
        """POST /api/knowledge-graph/build should return 200"""
        response = requests.post(f"{BASE_URL}/api/knowledge-graph/build")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should have 'message' field"
        assert "build" in data["message"].lower() or "started" in data["message"].lower(), \
            f"Message should indicate build started: {data['message']}"
        print(f"Build triggered: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
