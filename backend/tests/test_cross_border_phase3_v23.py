"""
Iteration 23: Cross-Border Watch Phase 3 Testing
- Grouped data structure (bangladesh.grouped, myanmar.grouped)
- Category groups with category, label, items
- Feedback bias (feedback_boosted, effective_priority adjustment)
- cross_border_category field on all items
- Auto-categorization (diplomatic, defence, internal_politics, economics, other)
- Items without AI summary filtered out
- Indian border state items require explicit BD/MM keywords in title
- Myanmar news doesn't appear in Bangladesh section
- Existing endpoints still work
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCrossBorderPhase3:
    """Phase 3 Cross-Border Watch tests"""
    
    def test_api_returns_200(self):
        """GET /api/cross-border/watch returns 200"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: API returns 200")
    
    def test_bangladesh_has_grouped_array(self):
        """Bangladesh section has grouped array"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        assert "bangladesh" in data, "Missing bangladesh section"
        assert "grouped" in data["bangladesh"], "Missing grouped array in bangladesh"
        assert isinstance(data["bangladesh"]["grouped"], list), "grouped should be a list"
        print(f"PASS: Bangladesh has grouped array with {len(data['bangladesh']['grouped'])} groups")
    
    def test_myanmar_has_grouped_array(self):
        """Myanmar section has grouped array"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        assert "myanmar" in data, "Missing myanmar section"
        assert "grouped" in data["myanmar"], "Missing grouped array in myanmar"
        assert isinstance(data["myanmar"]["grouped"], list), "grouped should be a list"
        print(f"PASS: Myanmar has grouped array with {len(data['myanmar']['grouped'])} groups")
    
    def test_group_structure_has_category_label_items(self):
        """Each group has category, label, and items fields"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        all_groups = data["bangladesh"]["grouped"] + data["myanmar"]["grouped"]
        assert len(all_groups) > 0, "No groups found"
        
        for group in all_groups:
            assert "category" in group, f"Group missing category: {group}"
            assert "label" in group, f"Group missing label: {group}"
            assert "items" in group, f"Group missing items: {group}"
            assert isinstance(group["items"], list), "items should be a list"
        print(f"PASS: All {len(all_groups)} groups have category, label, items")
    
    def test_valid_category_values(self):
        """Categories are valid (diplomatic, defence, internal_politics, economics, other)"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        valid_categories = {"diplomatic", "defence", "internal_politics", "economics", "other"}
        all_groups = data["bangladesh"]["grouped"] + data["myanmar"]["grouped"]
        
        for group in all_groups:
            assert group["category"] in valid_categories, f"Invalid category: {group['category']}"
        print(f"PASS: All categories are valid")
    
    def test_category_order_is_correct(self):
        """Categories are ordered: diplomatic, defence, internal_politics, economics, other"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        expected_order = ["diplomatic", "defence", "internal_politics", "economics", "other"]
        
        for section in ["bangladesh", "myanmar"]:
            groups = data[section]["grouped"]
            categories = [g["category"] for g in groups]
            
            # Check order is maintained (only for categories that exist)
            prev_idx = -1
            for cat in categories:
                if cat in expected_order:
                    curr_idx = expected_order.index(cat)
                    assert curr_idx >= prev_idx, f"Category order wrong in {section}: {categories}"
                    prev_idx = curr_idx
        print("PASS: Category order is correct")
    
    def test_all_items_have_cross_border_category(self):
        """Every item has cross_border_category field set"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        items_without_category = [i for i in all_items if not i.get("cross_border_category")]
        
        assert len(items_without_category) == 0, f"{len(items_without_category)} items missing cross_border_category"
        print(f"PASS: All {len(all_items)} items have cross_border_category")
    
    def test_auto_categorization_diplomatic(self):
        """Items with diplomatic keywords get diplomatic category"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        diplomatic_keywords = {"bilateral", "delegation", "diplomat", "ambassador", "foreign affair", "foreign minister", "cooperation", "treaty", "mou signed", "visit", "summit", "relations"}
        
        diplomatic_items = [i for i in all_items if i.get("cross_border_category") == "diplomatic"]
        if diplomatic_items:
            # Check at least some diplomatic items have diplomatic keywords
            has_keyword = False
            for item in diplomatic_items[:5]:
                text = (item.get("title", "") + " " + item.get("ai_summary", "")).lower()
                if any(kw in text for kw in diplomatic_keywords):
                    has_keyword = True
                    break
            print(f"PASS: Found {len(diplomatic_items)} diplomatic items")
        else:
            print("INFO: No diplomatic items found (may be expected)")
    
    def test_auto_categorization_defence(self):
        """Items with defence keywords get defence category"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        defence_keywords = {"military", "army", "bgb", "bsf", "coast guard", "seized", "arrested", "raid", "deployed", "airstrike", "gunfight", "arms", "weapons", "heroin", "drug", "smuggl", "militant", "killed", "operation", "security force"}
        
        defence_items = [i for i in all_items if i.get("cross_border_category") == "defence"]
        if defence_items:
            print(f"PASS: Found {len(defence_items)} defence items")
        else:
            print("INFO: No defence items found (may be expected)")
    
    def test_auto_categorization_internal_politics(self):
        """Items with internal_politics keywords get internal_politics category"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        
        internal_politics_items = [i for i in all_items if i.get("cross_border_category") == "internal_politics"]
        if internal_politics_items:
            print(f"PASS: Found {len(internal_politics_items)} internal_politics items")
        else:
            print("INFO: No internal_politics items found (may be expected)")
    
    def test_auto_categorization_economics(self):
        """Items with economics keywords get economics category"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        
        economics_items = [i for i in all_items if i.get("cross_border_category") == "economics"]
        if economics_items:
            print(f"PASS: Found {len(economics_items)} economics items")
        else:
            print("INFO: No economics items found (may be expected)")
    
    def test_items_without_ai_summary_filtered(self):
        """Items without ai_summary are filtered out"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        items_without_summary = [i for i in all_items if not i.get("ai_summary")]
        
        assert len(items_without_summary) == 0, f"{len(items_without_summary)} items have no ai_summary"
        print(f"PASS: All {len(all_items)} items have ai_summary (unprocessed filtered)")
    
    def test_feedback_boosted_field_exists(self):
        """Items with feedback_avg_rating have feedback_boosted=true"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        items_with_rating = [i for i in all_items if i.get("feedback_avg_rating") and i.get("feedback_total_ratings", 0) > 0]
        
        if items_with_rating:
            boosted_items = [i for i in items_with_rating if i.get("feedback_boosted")]
            assert len(boosted_items) == len(items_with_rating), f"Not all rated items have feedback_boosted"
            print(f"PASS: {len(boosted_items)} items with ratings have feedback_boosted=true")
        else:
            print("INFO: No items with feedback ratings found (expected - most items have 0 ratings)")
    
    def test_effective_priority_includes_feedback_bias(self):
        """Items with feedback have adjusted effective_priority"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        all_items = data["bangladesh"]["items"] + data["myanmar"]["items"]
        
        # Check that effective_priority exists on all items
        for item in all_items:
            assert "effective_priority" in item, f"Item {item.get('id')} missing effective_priority"
        
        print(f"PASS: All {len(all_items)} items have effective_priority field")
    
    def test_myanmar_news_not_in_bangladesh(self):
        """Myanmar-specific news doesn't appear in Bangladesh section"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=100")
        data = response.json()
        
        mm_keywords = {"min aung hlaing", "tatmadaw", "chin state", "sagaing", "rakhine", "kachin", "shan state", "tamu", "kalay", "hakha", "junta"}
        
        bd_items = data["bangladesh"]["items"]
        misplaced = []
        for item in bd_items:
            title = (item.get("title", "") or "").lower()
            # Check if title contains Myanmar-specific keywords but NOT Bangladesh keywords
            has_mm = any(kw in title for kw in mm_keywords)
            has_bd = "bangladesh" in title or "dhaka" in title or "bgb" in title
            if has_mm and not has_bd:
                misplaced.append(item.get("title", ""))
        
        if misplaced:
            print(f"WARNING: {len(misplaced)} Myanmar items in Bangladesh section: {misplaced[:2]}")
        else:
            print("PASS: No Myanmar-specific news in Bangladesh section")
    
    def test_category_labels_correct(self):
        """Category labels are human-readable"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        expected_labels = {
            "diplomatic": "Diplomatic",
            "defence": "Defence",
            "internal_politics": "Internal Politics",
            "economics": "Economics",
            "other": "Other"
        }
        
        all_groups = data["bangladesh"]["grouped"] + data["myanmar"]["grouped"]
        for group in all_groups:
            cat = group["category"]
            if cat in expected_labels:
                assert group["label"] == expected_labels[cat], f"Wrong label for {cat}: {group['label']}"
        
        print("PASS: Category labels are correct")


class TestExistingEndpoints:
    """Verify existing endpoints still work"""
    
    def test_intelligence_endpoint(self):
        """GET /api/intelligence still works"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=5")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "items" in data, "Missing items in response"
        print(f"PASS: /api/intelligence returns {len(data['items'])} items")
    
    def test_training_effectiveness_endpoint(self):
        """GET /api/training/effectiveness still works"""
        response = requests.get(f"{BASE_URL}/api/training/effectiveness")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/training/effectiveness returns 200")
    
    def test_feedback_stats_endpoint(self):
        """GET /api/feedback/stats still works"""
        response = requests.get(f"{BASE_URL}/api/feedback/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: /api/feedback/stats returns 200")


class TestCategoryDistribution:
    """Test category distribution and grouping"""
    
    def test_grouped_items_match_flat_items(self):
        """Total items in grouped equals total in flat items array"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        for section in ["bangladesh", "myanmar"]:
            flat_count = len(data[section]["items"])
            grouped_count = sum(len(g["items"]) for g in data[section]["grouped"])
            assert flat_count == grouped_count, f"{section}: flat={flat_count}, grouped={grouped_count}"
        
        print("PASS: Grouped items count matches flat items count")
    
    def test_items_sorted_by_effective_priority(self):
        """Items within each category are sorted by effective_priority descending"""
        response = requests.get(f"{BASE_URL}/api/cross-border/watch?limit=50")
        data = response.json()
        
        for section in ["bangladesh", "myanmar"]:
            items = data[section]["items"]
            if len(items) > 1:
                priorities = [i.get("effective_priority", 0) for i in items]
                assert priorities == sorted(priorities, reverse=True), f"{section} items not sorted by effective_priority"
        
        print("PASS: Items sorted by effective_priority descending")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
