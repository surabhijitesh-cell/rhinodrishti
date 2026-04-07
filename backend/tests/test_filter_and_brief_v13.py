"""
Test Suite for Bug Fixes - Iteration 13
========================================
Tests for:
1. Daily Brief generation endpoint (POST /api/generate-brief)
2. Hard filter rejecting sports/entertainment in BOTH title AND content
3. Hard filter NOT false-rejecting legitimate intelligence (e.g., 'PM Modi')
4. Intelligence feed should not contain sports/cricket/lottery items
"""

import pytest
import requests
import os
import sys
import time

# Add backend to path for direct filter testing
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://strategic-scan.preview.emergentagent.com').rstrip('/')


class TestDailyBriefGeneration:
    """Tests for Daily Brief generation endpoints"""
    
    def test_generate_brief_endpoint_exists(self):
        """POST /api/generate-brief should return 200 and trigger brief generation"""
        response = requests.post(f"{BASE_URL}/api/generate-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should contain 'message' field"
        assert "Brief generation started" in data["message"], f"Unexpected message: {data['message']}"
        assert "date" in data, "Response should contain 'date' field"
        print(f"✓ POST /api/generate-brief returns 200 with message: {data['message']}")
    
    def test_get_daily_brief_returns_data(self):
        """GET /api/daily-brief should return today's brief with key_developments and analyst_summary"""
        response = requests.get(f"{BASE_URL}/api/daily-brief")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "date" in data, "Brief should have 'date' field"
        assert "key_developments" in data, "Brief should have 'key_developments' field"
        assert "analyst_summary" in data, "Brief should have 'analyst_summary' field"
        
        # Verify data is present
        print(f"✓ GET /api/daily-brief returns brief for date: {data['date']}")
        print(f"  - key_developments count: {len(data.get('key_developments', []))}")
        print(f"  - analyst_summary length: {len(data.get('analyst_summary', ''))}")
        print(f"  - national_news count: {len(data.get('national_news', []))}")
        print(f"  - international_news count: {len(data.get('international_news', []))}")
    
    def test_daily_brief_pdf_returns_valid_pdf(self):
        """GET /api/daily-brief/pdf should return a valid PDF"""
        response = requests.get(f"{BASE_URL}/api/daily-brief/pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        assert 'application/pdf' in content_type, f"Expected PDF content type, got: {content_type}"
        
        # Check PDF magic bytes
        content = response.content
        assert content[:4] == b'%PDF', "Response should start with PDF magic bytes"
        assert len(content) > 1000, f"PDF seems too small: {len(content)} bytes"
        
        print(f"✓ GET /api/daily-brief/pdf returns valid PDF ({len(content)} bytes)")


class TestHardFilterRejectsSports:
    """Tests for hard filter rejecting sports/entertainment content"""
    
    def test_filter_rejects_ipl_cricket_in_title(self):
        """Hard filter should reject IPL cricket news in title"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "MI seek reset against RR Pandya fitness",
            "raw_content": "Mumbai Indians are looking to bounce back in their next match.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject IPL cricket news, but passed with reason: {reason}"
        assert "hard_reject" in reason.lower(), f"Reason should indicate hard reject: {reason}"
        print(f"✓ Filter rejects IPL cricket title with reason: {reason}")
    
    def test_filter_rejects_ipl_in_content(self):
        """Hard filter should reject IPL content even if title is clean"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Sports update from Mumbai",
            "raw_content": "INDIAN PREMIER LEAGUE match between Mumbai Indians and Chennai Super Kings was exciting.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject IPL in content, but passed with reason: {reason}"
        assert "hard_reject" in reason.lower(), f"Reason should indicate hard reject: {reason}"
        print(f"✓ Filter rejects IPL in content with reason: {reason}")
    
    def test_filter_rejects_lottery(self):
        """Hard filter should reject lottery news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Lottery results today",
            "raw_content": "Check the winning numbers for today's lottery draw.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject lottery news, but passed with reason: {reason}"
        print(f"✓ Filter rejects lottery news with reason: {reason}")
    
    def test_filter_rejects_bollywood(self):
        """Hard filter should reject Bollywood entertainment news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "New Bollywood movie release",
            "raw_content": "The latest Bollywood blockbuster is set to release this Friday.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject Bollywood news, but passed with reason: {reason}"
        print(f"✓ Filter rejects Bollywood news with reason: {reason}")
    
    def test_filter_rejects_cricket_in_content_only(self):
        """Hard filter should reject cricket even when only in content"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Weekend sports roundup",
            "raw_content": "The cricket match between India and Australia ended in a draw. The batsman scored a century.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject cricket in content, but passed with reason: {reason}"
        print(f"✓ Filter rejects cricket in content with reason: {reason}")


class TestHardFilterAcceptsLegitIntelligence:
    """Tests for hard filter accepting legitimate intelligence"""
    
    def test_filter_accepts_arms_recovery(self):
        """Hard filter should accept arms/explosives recovery news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Arms and Explosives Recovered in Manipur",
            "raw_content": "Security forces recovered a cache of arms and ammunition in Manipur.",
            "region": "ner"
        }
        passed, reason = hard_filter(article)
        assert passed, f"Should accept arms recovery news, but rejected with reason: {reason}"
        print(f"✓ Filter accepts arms recovery news with reason: {reason}")
    
    def test_filter_accepts_border_news(self):
        """Hard filter should accept border-related news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Cattle killing sparks tension along Assam-Nagaland border",
            "raw_content": "Tensions rose along the Assam-Nagaland border after cattle killing incident.",
            "region": "ner"
        }
        passed, reason = hard_filter(article)
        assert passed, f"Should accept border news, but rejected with reason: {reason}"
        print(f"✓ Filter accepts border news with reason: {reason}")
    
    def test_filter_does_not_false_reject_modi(self):
        """Hard filter should NOT false-reject 'PM Modi' (previously 'odi' matched inside Modi)"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "PM Modi visits Assam for development projects",
            "raw_content": "Prime Minister Narendra Modi inaugurated several development projects in Assam.",
            "region": "ner"
        }
        passed, reason = hard_filter(article)
        assert passed, f"Should NOT reject PM Modi news (false positive on 'odi'), but rejected with reason: {reason}"
        print(f"✓ Filter correctly accepts PM Modi news with reason: {reason}")
    
    def test_filter_accepts_military_operations(self):
        """Hard filter should accept military operations news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "Army conducts operations in Manipur",
            "raw_content": "The Indian Army conducted counter-insurgency operations in Manipur.",
            "region": "ner"
        }
        passed, reason = hard_filter(article)
        assert passed, f"Should accept military news, but rejected with reason: {reason}"
        print(f"✓ Filter accepts military operations news with reason: {reason}")
    
    def test_filter_accepts_insurgency_news(self):
        """Hard filter should accept insurgency-related news"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "ULFA militant surrenders in Assam",
            "raw_content": "A top ULFA militant surrendered before security forces in Assam.",
            "region": "ner"
        }
        passed, reason = hard_filter(article)
        assert passed, f"Should accept insurgency news, but rejected with reason: {reason}"
        print(f"✓ Filter accepts insurgency news with reason: {reason}")


class TestWordBoundaryMatching:
    """Tests for word-boundary matching of short keywords"""
    
    def test_ipl_word_boundary(self):
        """'ipl' should match as word boundary, not inside other words"""
        from intelligence_filter import hard_filter
        
        # Should reject standalone IPL
        article1 = {
            "title": "IPL 2024 schedule announced",
            "raw_content": "The IPL schedule has been released.",
            "region": "india"
        }
        passed1, reason1 = hard_filter(article1)
        assert not passed1, f"Should reject standalone IPL: {reason1}"
        print(f"✓ Rejects standalone 'IPL' with reason: {reason1}")
        
        # Should NOT reject 'multiple' (contains 'ipl' but not as word)
        article2 = {
            "title": "Multiple incidents reported in Manipur",
            "raw_content": "Security forces responded to multiple incidents.",
            "region": "ner"
        }
        passed2, reason2 = hard_filter(article2)
        assert passed2, f"Should NOT reject 'multiple' (false positive on 'ipl'): {reason2}"
        print(f"✓ Does NOT reject 'multiple' (no false positive on 'ipl'): {reason2}")
    
    def test_odi_word_boundary(self):
        """'odi' should match as word boundary, not inside 'Modi'"""
        from intelligence_filter import hard_filter
        
        # Should reject standalone ODI
        article1 = {
            "title": "India wins ODI series",
            "raw_content": "India won the ODI series against Australia.",
            "region": "india"
        }
        passed1, reason1 = hard_filter(article1)
        assert not passed1, f"Should reject standalone ODI: {reason1}"
        print(f"✓ Rejects standalone 'ODI' with reason: {reason1}")
        
        # Should NOT reject 'Modi'
        article2 = {
            "title": "Modi government announces new policy",
            "raw_content": "The Modi government has announced a new security policy.",
            "region": "india"
        }
        passed2, reason2 = hard_filter(article2)
        # This might still be rejected for 'no_relevance_signal' if no NER keywords
        # But should NOT be rejected for 'odi'
        if not passed2:
            assert "odi" not in reason2.lower() or "hard_reject" not in reason2.lower(), \
                f"Should NOT reject 'Modi' due to 'odi' match: {reason2}"
        print(f"✓ Does NOT false-reject 'Modi' due to 'odi': {reason2}")
    
    def test_t20_word_boundary(self):
        """'t20' should match as word boundary"""
        from intelligence_filter import hard_filter
        
        article = {
            "title": "T20 World Cup 2024",
            "raw_content": "The T20 World Cup is scheduled for next month.",
            "region": "india"
        }
        passed, reason = hard_filter(article)
        assert not passed, f"Should reject T20 cricket: {reason}"
        print(f"✓ Rejects 'T20' cricket with reason: {reason}")


class TestIntelligenceFeedNoSports:
    """Tests to verify intelligence feed doesn't contain sports/entertainment"""
    
    def test_intelligence_feed_no_cricket(self):
        """GET /api/intelligence should not return cricket-related items"""
        import re
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        # Use word boundary patterns for short keywords, substring for long ones
        cricket_patterns = {
            'cricket': re.compile(r'cricket', re.IGNORECASE),
            'ipl': re.compile(r'\bipl\b', re.IGNORECASE),  # word boundary
            'bcci': re.compile(r'\bbcci\b', re.IGNORECASE),
            'wicket': re.compile(r'wicket', re.IGNORECASE),
            'batsman': re.compile(r'batsman', re.IGNORECASE),
            'bowler': re.compile(r'bowler', re.IGNORECASE),
            'mumbai indians': re.compile(r'mumbai indians', re.IGNORECASE),
            'chennai super kings': re.compile(r'chennai super kings', re.IGNORECASE),
            'royal challengers': re.compile(r'royal challengers', re.IGNORECASE),
            'indian premier league': re.compile(r'indian premier league', re.IGNORECASE),
        }
        
        sports_items = []
        for item in data.get('items', []):
            title = (item.get('title', '') or '')
            content = (item.get('raw_content', '') or '')
            combined = f"{title} {content}"
            
            for kw, pattern in cricket_patterns.items():
                if pattern.search(combined):
                    sports_items.append({
                        'title': item.get('title', '')[:80],
                        'keyword': kw
                    })
                    break
        
        if sports_items:
            print(f"⚠ Found {len(sports_items)} cricket-related items in feed:")
            for item in sports_items[:5]:
                print(f"  - '{item['title']}' (matched: {item['keyword']})")
        else:
            print(f"✓ No cricket-related items found in {len(data.get('items', []))} items")
        
        # This is a soft assertion - we report but don't fail if some old items exist
        assert len(sports_items) == 0, f"Found {len(sports_items)} cricket items in feed"
    
    def test_intelligence_feed_no_lottery(self):
        """GET /api/intelligence should not return lottery-related items"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        lottery_keywords = ['lottery', 'teer result', 'lottery result', 'lottery winner']
        
        lottery_items = []
        for item in data.get('items', []):
            title = (item.get('title', '') or '').lower()
            content = (item.get('raw_content', '') or '').lower()
            
            for kw in lottery_keywords:
                if kw in title or kw in content:
                    lottery_items.append({
                        'title': item.get('title', '')[:80],
                        'keyword': kw
                    })
                    break
        
        if lottery_items:
            print(f"⚠ Found {len(lottery_items)} lottery-related items in feed:")
            for item in lottery_items[:5]:
                print(f"  - '{item['title']}' (matched: {item['keyword']})")
        else:
            print(f"✓ No lottery-related items found in {len(data.get('items', []))} items")
        
        assert len(lottery_items) == 0, f"Found {len(lottery_items)} lottery items in feed"
    
    def test_intelligence_feed_no_bollywood(self):
        """GET /api/intelligence should not return Bollywood-related items"""
        response = requests.get(f"{BASE_URL}/api/intelligence?limit=100")
        assert response.status_code == 200
        data = response.json()
        
        entertainment_keywords = ['bollywood', 'tollywood', 'movie review', 'box office', 
                                  'film review', 'celebrity gossip', 'bigg boss']
        
        entertainment_items = []
        for item in data.get('items', []):
            title = (item.get('title', '') or '').lower()
            content = (item.get('raw_content', '') or '').lower()
            
            for kw in entertainment_keywords:
                if kw in title or kw in content:
                    entertainment_items.append({
                        'title': item.get('title', '')[:80],
                        'keyword': kw
                    })
                    break
        
        if entertainment_items:
            print(f"⚠ Found {len(entertainment_items)} entertainment-related items in feed:")
            for item in entertainment_items[:5]:
                print(f"  - '{item['title']}' (matched: {item['keyword']})")
        else:
            print(f"✓ No entertainment-related items found in {len(data.get('items', []))} items")
        
        assert len(entertainment_items) == 0, f"Found {len(entertainment_items)} entertainment items in feed"


class TestDashboardStats:
    """Tests for dashboard stats endpoint"""
    
    def test_dashboard_stats_returns_data(self):
        """GET /api/dashboard/stats should return non-zero counts"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check required fields
        assert "total_items" in data, "Should have total_items"
        assert "critical_count" in data, "Should have critical_count"
        assert "high_count" in data, "Should have high_count"
        assert "state_distribution" in data, "Should have state_distribution"
        assert "threat_distribution" in data, "Should have threat_distribution"
        
        print(f"✓ Dashboard stats:")
        print(f"  - total_items: {data.get('total_items', 0)}")
        print(f"  - critical_count: {data.get('critical_count', 0)}")
        print(f"  - high_count: {data.get('high_count', 0)}")
        print(f"  - medium_count: {data.get('medium_count', 0)}")
        print(f"  - low_count: {data.get('low_count', 0)}")
        
        # Verify non-zero total
        assert data.get('total_items', 0) > 0, "Should have some intelligence items"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
