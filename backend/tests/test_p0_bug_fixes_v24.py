"""
Iteration 24: P0 Bug Fixes Testing
Bug 1: Cross-Border Watch - LOW severity and non-Latin (Bengali/Hindi) items should be filtered out
Bug 2: Daily Brief PDF - NER Key Developments should only contain NER states (no Bangladesh, Myanmar, empty)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# NER states that should appear in key_developments
NER_STATES_ALLOWED = ["Assam", "Meghalaya", "Mizoram", "Manipur", "Arunachal Pradesh", "Tripura", "Nagaland", "Sikkim", "Multiple"]

# States that should NOT appear in key_developments
EXCLUDED_STATES = ["Bangladesh", "Myanmar", ""]


def has_non_latin_chars(text: str) -> bool:
    """Check if text contains Bengali, Hindi, Assamese, or other Indic scripts."""
    if not text:
        return False
    for char in text:
        code = ord(char)
        # Devanagari (Hindi), Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada, Malayalam
        if (0x0900 <= code <= 0x097F) or \
           (0x0980 <= code <= 0x09FF) or \
           (0x0A00 <= code <= 0x0A7F) or \
           (0x0A80 <= code <= 0x0AFF) or \
           (0x0B00 <= code <= 0x0B7F) or \
           (0x0B80 <= code <= 0x0BFF) or \
           (0x0C00 <= code <= 0x0C7F) or \
           (0x0C80 <= code <= 0x0CFF) or \
           (0x0D00 <= code <= 0x0D7F):
            return True
    return False


class TestCrossBorderBugFixes:
    """Test Bug 1: Cross-Border Watch should filter LOW severity and non-Latin items"""
    
    def test_cross_border_endpoint_returns_200(self):
        """Verify endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Cross-border endpoint returns 200")
    
    def test_no_low_severity_items_in_bangladesh(self):
        """Bug Fix: No items should have severity=low in Bangladesh section"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        bangladesh_items = data.get("bangladesh", {}).get("items", [])
        low_severity_items = [
            item for item in bangladesh_items 
            if (item.get("severity") or "").lower() == "low"
        ]
        
        assert len(low_severity_items) == 0, f"Found {len(low_severity_items)} LOW severity items in Bangladesh: {[i.get('title', '')[:50] for i in low_severity_items]}"
        print(f"✓ No LOW severity items in Bangladesh section ({len(bangladesh_items)} items checked)")
    
    def test_no_low_severity_items_in_myanmar(self):
        """Bug Fix: No items should have severity=low in Myanmar section"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        myanmar_items = data.get("myanmar", {}).get("items", [])
        low_severity_items = [
            item for item in myanmar_items 
            if (item.get("severity") or "").lower() == "low"
        ]
        
        assert len(low_severity_items) == 0, f"Found {len(low_severity_items)} LOW severity items in Myanmar: {[i.get('title', '')[:50] for i in low_severity_items]}"
        print(f"✓ No LOW severity items in Myanmar section ({len(myanmar_items)} items checked)")
    
    def test_no_non_latin_titles_in_bangladesh(self):
        """Bug Fix: No items should have Bengali/Hindi/Assamese characters in title"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        bangladesh_items = data.get("bangladesh", {}).get("items", [])
        non_latin_items = [
            item for item in bangladesh_items 
            if has_non_latin_chars(item.get("title", ""))
        ]
        
        assert len(non_latin_items) == 0, f"Found {len(non_latin_items)} items with non-Latin titles in Bangladesh: {[i.get('title', '')[:50] for i in non_latin_items]}"
        print(f"✓ No non-Latin titles in Bangladesh section ({len(bangladesh_items)} items checked)")
    
    def test_no_non_latin_titles_in_myanmar(self):
        """Bug Fix: No items should have Bengali/Hindi/Assamese characters in title"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        myanmar_items = data.get("myanmar", {}).get("items", [])
        non_latin_items = [
            item for item in myanmar_items 
            if has_non_latin_chars(item.get("title", ""))
        ]
        
        assert len(non_latin_items) == 0, f"Found {len(non_latin_items)} items with non-Latin titles in Myanmar: {[i.get('title', '')[:50] for i in non_latin_items]}"
        print(f"✓ No non-Latin titles in Myanmar section ({len(myanmar_items)} items checked)")
    
    def test_no_non_latin_summaries_in_bangladesh(self):
        """Bug Fix: No items should have Bengali/Hindi/Assamese characters in ai_summary"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        bangladesh_items = data.get("bangladesh", {}).get("items", [])
        non_latin_items = [
            item for item in bangladesh_items 
            if has_non_latin_chars(item.get("ai_summary", ""))
        ]
        
        assert len(non_latin_items) == 0, f"Found {len(non_latin_items)} items with non-Latin summaries in Bangladesh"
        print(f"✓ No non-Latin summaries in Bangladesh section ({len(bangladesh_items)} items checked)")
    
    def test_no_non_latin_summaries_in_myanmar(self):
        """Bug Fix: No items should have Bengali/Hindi/Assamese characters in ai_summary"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        myanmar_items = data.get("myanmar", {}).get("items", [])
        non_latin_items = [
            item for item in myanmar_items 
            if has_non_latin_chars(item.get("ai_summary", ""))
        ]
        
        assert len(non_latin_items) == 0, f"Found {len(non_latin_items)} items with non-Latin summaries in Myanmar"
        print(f"✓ No non-Latin summaries in Myanmar section ({len(myanmar_items)} items checked)")
    
    def test_items_have_cross_border_category(self):
        """Verify items have cross_border_category field"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        valid_categories = ["diplomatic", "defence", "internal_politics", "economics", "other"]
        
        all_items = data.get("bangladesh", {}).get("items", []) + data.get("myanmar", {}).get("items", [])
        items_without_category = [
            item for item in all_items 
            if item.get("cross_border_category") not in valid_categories
        ]
        
        assert len(items_without_category) == 0, f"Found {len(items_without_category)} items without valid cross_border_category"
        print(f"✓ All {len(all_items)} items have valid cross_border_category")
    
    def test_bangladesh_myanmar_sections_exist(self):
        """Verify response has both Bangladesh and Myanmar sections"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        assert "bangladesh" in data, "Missing 'bangladesh' section in response"
        assert "myanmar" in data, "Missing 'myanmar' section in response"
        assert "items" in data["bangladesh"], "Missing 'items' in bangladesh section"
        assert "items" in data["myanmar"], "Missing 'items' in myanmar section"
        print(f"✓ Both Bangladesh ({data['bangladesh'].get('count', 0)} items) and Myanmar ({data['myanmar'].get('count', 0)} items) sections exist")


class TestDailyBriefBugFixes:
    """Test Bug 2: Daily Brief NER Key Developments should only contain NER states"""
    
    def test_generate_brief_endpoint(self):
        """Verify brief generation endpoint works"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "message" in data, "Missing 'message' in response"
        print(f"✓ Generate brief endpoint works: {data.get('message')}")
    
    def test_daily_brief_endpoint_returns_200(self):
        """Verify daily brief endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Daily brief endpoint returns 200")
    
    def test_key_developments_only_ner_states(self):
        """Bug Fix: key_developments should only contain items with NER states"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        key_developments = data.get("key_developments", [])
        
        invalid_state_items = []
        for dev in key_developments:
            if isinstance(dev, dict):
                state = dev.get("state", "")
                # Check if state is in allowed NER states
                if state and state not in NER_STATES_ALLOWED:
                    invalid_state_items.append({
                        "title": dev.get("title", "")[:60],
                        "state": state
                    })
        
        assert len(invalid_state_items) == 0, f"Found {len(invalid_state_items)} items with non-NER states in key_developments: {invalid_state_items}"
        print(f"✓ All key_developments ({len(key_developments)} items) have valid NER states")
    
    def test_no_bangladesh_in_key_developments(self):
        """Bug Fix: No Bangladesh items in key_developments"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        key_developments = data.get("key_developments", [])
        
        bangladesh_items = [
            dev for dev in key_developments 
            if isinstance(dev, dict) and dev.get("state") == "Bangladesh"
        ]
        
        assert len(bangladesh_items) == 0, f"Found {len(bangladesh_items)} Bangladesh items in key_developments: {[i.get('title', '')[:50] for i in bangladesh_items]}"
        print(f"✓ No Bangladesh items in key_developments")
    
    def test_no_myanmar_in_key_developments(self):
        """Bug Fix: No Myanmar items in key_developments"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        key_developments = data.get("key_developments", [])
        
        myanmar_items = [
            dev for dev in key_developments 
            if isinstance(dev, dict) and dev.get("state") == "Myanmar"
        ]
        
        assert len(myanmar_items) == 0, f"Found {len(myanmar_items)} Myanmar items in key_developments: {[i.get('title', '')[:50] for i in myanmar_items]}"
        print(f"✓ No Myanmar items in key_developments")
    
    def test_no_empty_state_in_key_developments(self):
        """Bug Fix: No items with empty state in key_developments"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        key_developments = data.get("key_developments", [])
        
        empty_state_items = [
            dev for dev in key_developments 
            if isinstance(dev, dict) and (dev.get("state") == "" or dev.get("state") is None)
        ]
        
        # Note: Empty state might be acceptable for string-type developments
        dict_devs = [d for d in key_developments if isinstance(d, dict)]
        if dict_devs:
            assert len(empty_state_items) == 0, f"Found {len(empty_state_items)} items with empty state in key_developments"
        print(f"✓ No empty state items in key_developments (checked {len(dict_devs)} dict items)")
    
    def test_daily_brief_pdf_download(self):
        """Verify PDF downloads successfully with correct headers"""
        response = requests.get(f"{BASE_URL}/api/daily-brief/pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check Content-Type header
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got {content_type}"
        
        # Check Content-Disposition header
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in Content-Disposition, got {content_disposition}"
        assert "Rhino_Drishti_Brief" in content_disposition, f"Expected Rhino_Drishti_Brief in filename, got {content_disposition}"
        
        # Check PDF content starts with PDF magic bytes
        assert response.content[:4] == b'%PDF', "Response content is not a valid PDF"
        
        print(f"✓ PDF download successful: {len(response.content)} bytes, Content-Type: {content_type}")
    
    def test_key_developments_states_distribution(self):
        """Report distribution of states in key_developments for verification"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        key_developments = data.get("key_developments", [])
        
        state_counts = {}
        for dev in key_developments:
            if isinstance(dev, dict):
                state = dev.get("state", "UNKNOWN")
                state_counts[state] = state_counts.get(state, 0) + 1
        
        print(f"✓ Key developments state distribution: {state_counts}")
        
        # Verify all states are in allowed list
        for state in state_counts.keys():
            if state != "UNKNOWN":
                assert state in NER_STATES_ALLOWED, f"Unexpected state '{state}' in key_developments"


class TestCrossBorderResponseStructure:
    """Additional tests for Cross-Border response structure"""
    
    def test_grouped_structure_exists(self):
        """Verify grouped array exists in response"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        assert "grouped" in data.get("bangladesh", {}), "Missing 'grouped' in bangladesh section"
        assert "grouped" in data.get("myanmar", {}), "Missing 'grouped' in myanmar section"
        print("✓ Grouped structure exists in both sections")
    
    def test_posture_fields_exist(self):
        """Verify posture fields exist"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        assert "posture" in data.get("bangladesh", {}), "Missing 'posture' in bangladesh section"
        assert "posture" in data.get("myanmar", {}), "Missing 'posture' in myanmar section"
        
        valid_postures = ["stable", "watchful", "elevated", "deteriorating"]
        assert data["bangladesh"]["posture"] in valid_postures, f"Invalid posture: {data['bangladesh']['posture']}"
        assert data["myanmar"]["posture"] in valid_postures, f"Invalid posture: {data['myanmar']['posture']}"
        
        print(f"✓ Postures: Bangladesh={data['bangladesh']['posture']}, Myanmar={data['myanmar']['posture']}")
    
    def test_watchpoints_exist(self):
        """Verify watchpoints field exists"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch")
        assert response.status_code == 200
        data = response.json()
        
        assert "watchpoints" in data, "Missing 'watchpoints' in response"
        assert isinstance(data["watchpoints"], list), "watchpoints should be a list"
        print(f"✓ Watchpoints: {len(data['watchpoints'])} items")


class TestDailyBriefStructure:
    """Additional tests for Daily Brief structure"""
    
    def test_brief_has_required_fields(self):
        """Verify brief has all required fields"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["date", "key_developments", "analyst_summary"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ Brief has all required fields: {required_fields}")
    
    def test_brief_has_optional_sections(self):
        """Verify brief has optional sections"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200
        data = response.json()
        
        optional_fields = ["national_news", "international_news", "pattern_insights", "state_highlights"]
        present_fields = [f for f in optional_fields if f in data]
        
        print(f"✓ Brief has optional sections: {present_fields}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
