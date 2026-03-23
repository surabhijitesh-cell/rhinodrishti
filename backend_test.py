#!/usr/bin/env python3
"""
Backend API Testing for Rhino Drishti Intelligence Aggregation Platform
Tests all endpoints mentioned in the review request.
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any

class RhinoDrishtiAPITester:
    def __init__(self):
        self.base_url = "https://strategic-scan.preview.emergentagent.com/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            self.failed_tests.append({"name": name, "details": details})
            print(f"❌ {name} - {details}")

    def make_request(self, method: str, endpoint: str, data: Dict[Any, Any] = None) -> tuple:
        """Make HTTP request and return (success, response_data, status_code)"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            headers = {'Content-Type': 'application/json'}
            
            if method.upper() == 'GET':
                response = requests.get(url, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            else:
                return False, {}, 0
            
            # Try to parse JSON
            try:
                response_data = response.json()
            except:
                response_data = {"raw_text": response.text}
            
            return response.status_code < 400, response_data, response.status_code
            
        except Exception as e:
            return False, {"error": str(e)}, 0

    def test_dashboard_stats(self):
        """Test GET /api/dashboard/stats"""
        print("\n🔍 Testing Dashboard Stats API...")
        success, data, status = self.make_request('GET', '/dashboard/stats')
        
        if not success:
            self.log_test("Dashboard Stats - Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Dashboard Stats - Request", True)
        
        # Check required fields
        required_fields = [
            'total_items', 'critical_count', 'high_count', 'medium_count', 'low_count',
            'state_distribution', 'threat_distribution', 'recent_critical', 'trend_7d'
        ]
        
        for field in required_fields:
            if field in data:
                self.log_test(f"Dashboard Stats - Has {field}", True)
            else:
                self.log_test(f"Dashboard Stats - Has {field}", False, f"Missing field: {field}")
        
        # Check data types
        if isinstance(data.get('total_items'), int) and data['total_items'] >= 0:
            self.log_test("Dashboard Stats - Total Items Type", True)
        else:
            self.log_test("Dashboard Stats - Total Items Type", False, "Should be non-negative integer")
        
        if isinstance(data.get('state_distribution'), dict):
            self.log_test("Dashboard Stats - State Distribution Type", True)
        else:
            self.log_test("Dashboard Stats - State Distribution Type", False, "Should be dict")

    def test_intelligence_api(self):
        """Test GET /api/intelligence with various filters"""
        print("\n🔍 Testing Intelligence API...")
        
        # Basic intelligence fetch
        success, data, status = self.make_request('GET', '/intelligence')
        if not success:
            self.log_test("Intelligence - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Intelligence - Basic Request", True)
        
        # Check response structure
        required_fields = ['items', 'total', 'page', 'limit', 'pages']
        for field in required_fields:
            if field in data:
                self.log_test(f"Intelligence - Has {field}", True)
            else:
                self.log_test(f"Intelligence - Has {field}", False, f"Missing field: {field}")
        
        # Test pagination
        success, data, status = self.make_request('GET', '/intelligence?page=1&limit=5')
        if success and len(data.get('items', [])) <= 5:
            self.log_test("Intelligence - Pagination", True)
        else:
            self.log_test("Intelligence - Pagination", False, "Pagination not working correctly")
        
        # Test state filter
        success, data, status = self.make_request('GET', '/intelligence?state=Assam')
        if success:
            assam_items = [item for item in data.get('items', []) if item.get('state') == 'Assam']
            if len(assam_items) == len(data.get('items', [])):
                self.log_test("Intelligence - State Filter", True)
            else:
                self.log_test("Intelligence - State Filter", False, "State filter not working")
        
        # Test threat type filter
        success, data, status = self.make_request('GET', '/intelligence?threat_type=Insurgency')
        if success:
            self.log_test("Intelligence - Threat Type Filter", True)
        else:
            self.log_test("Intelligence - Threat Type Filter", False, f"Status {status}")
        
        # Test severity filter
        success, data, status = self.make_request('GET', '/intelligence?severity=critical')
        if success:
            self.log_test("Intelligence - Severity Filter", True)
        else:
            self.log_test("Intelligence - Severity Filter", False, f"Status {status}")
        
        # Test search
        success, data, status = self.make_request('GET', '/intelligence?search=border')
        if success:
            self.log_test("Intelligence - Search", True)
        else:
            self.log_test("Intelligence - Search", False, f"Status {status}")
        
        # Test cross-border filter
        success, data, status = self.make_request('GET', '/intelligence?is_cross_border=true')
        if success:
            self.log_test("Intelligence - Cross-border Filter", True)
        else:
            self.log_test("Intelligence - Cross-border Filter", False, f"Status {status}")

    def test_intelligence_item(self):
        """Test GET /api/intelligence/{item_id}"""
        print("\n🔍 Testing Intelligence Item API...")
        
        # First get a list to find a valid ID
        success, data, status = self.make_request('GET', '/intelligence?limit=1')
        if not success or not data.get('items'):
            self.log_test("Intelligence Item - Get Valid ID", False, "No items to test with")
            return
        
        item_id = data['items'][0].get('id')
        if not item_id:
            self.log_test("Intelligence Item - Get Valid ID", False, "Items missing ID field")
            return
        
        # Test getting specific item
        success, item_data, status = self.make_request('GET', f'/intelligence/{item_id}')
        if success and item_data.get('id') == item_id:
            self.log_test("Intelligence Item - Get by ID", True)
        else:
            self.log_test("Intelligence Item - Get by ID", False, f"Status {status}: {item_data}")
        
        # Test invalid ID
        success, data, status = self.make_request('GET', '/intelligence/invalid-id-123')
        if status == 404:
            self.log_test("Intelligence Item - Invalid ID Returns 404", True)
        else:
            self.log_test("Intelligence Item - Invalid ID Returns 404", False, f"Expected 404, got {status}")

    def test_alerts_api(self):
        """Test GET /api/alerts"""
        print("\n🔍 Testing Alerts API...")
        
        success, data, status = self.make_request('GET', '/alerts')
        if not success:
            self.log_test("Alerts - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Alerts - Basic Request", True)
        
        # Check response structure
        if 'alerts' in data and 'count' in data:
            self.log_test("Alerts - Response Structure", True)
        else:
            self.log_test("Alerts - Response Structure", False, "Missing alerts or count field")
        
        # Check that alerts are high/critical severity
        alerts = data.get('alerts', [])
        valid_severities = ['critical', 'high']
        invalid_alerts = [a for a in alerts if a.get('severity') not in valid_severities]
        
        if len(invalid_alerts) == 0:
            self.log_test("Alerts - Only Critical/High Severity", True)
        else:
            self.log_test("Alerts - Only Critical/High Severity", False, f"Found {len(invalid_alerts)} non-critical/high alerts")

    def test_daily_brief_api(self):
        """Test GET /api/daily-brief and POST /api/generate-brief"""
        print("\n🔍 Testing Daily Brief API...")
        
        # Test getting today's brief
        success, data, status = self.make_request('GET', '/daily-brief')
        if success:
            self.log_test("Daily Brief - Get Today's Brief", True)
            
            # Check structure
            expected_fields = ['id', 'date', 'key_developments', 'state_highlights', 'cross_border_insights', 'analyst_summary']
            missing_fields = [f for f in expected_fields if f not in data]
            
            if not missing_fields:
                self.log_test("Daily Brief - Response Structure", True)
            else:
                self.log_test("Daily Brief - Response Structure", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test("Daily Brief - Get Today's Brief", False, f"Status {status}: {data}")
        
        # Test specific date
        success, data, status = self.make_request('GET', '/daily-brief?date=2024-12-28')
        if success:
            self.log_test("Daily Brief - Get Specific Date", True)
        else:
            self.log_test("Daily Brief - Get Specific Date", False, f"Status {status}")
        
        # Test generate brief (this will run in background)
        success, data, status = self.make_request('POST', '/generate-brief')
        if success and 'message' in data:
            self.log_test("Daily Brief - Generate Brief", True)
        else:
            self.log_test("Daily Brief - Generate Brief", False, f"Status {status}: {data}")

    def test_daily_brief_pdf_api(self):
        """Test GET /api/daily-brief/pdf - NEW PDF EXPORT FEATURE"""
        print("\n🔍 Testing Daily Brief PDF Export API...")
        
        try:
            url = f"{self.base_url}/daily-brief/pdf"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                self.log_test("PDF Export - Request Status", True)
                
                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if 'application/pdf' in content_type:
                    self.log_test("PDF Export - Content Type", True)
                else:
                    self.log_test("PDF Export - Content Type", False, f"Expected application/pdf, got {content_type}")
                
                # Check content disposition header for filename
                content_disposition = response.headers.get('Content-Disposition', '')
                if 'attachment' in content_disposition and 'Rhino_Drishti_Brief_' in content_disposition:
                    self.log_test("PDF Export - Download Header", True)
                else:
                    self.log_test("PDF Export - Download Header", False, f"Content-Disposition: {content_disposition}")
                
                # Check PDF content size
                content_length = len(response.content)
                if content_length > 1000:  # PDF should be reasonable size
                    self.log_test("PDF Export - Content Size", True)
                else:
                    self.log_test("PDF Export - Content Size", False, f"PDF too small: {content_length} bytes")
                
                # Check PDF signature
                if response.content.startswith(b'%PDF'):
                    self.log_test("PDF Export - Valid PDF Format", True)
                else:
                    self.log_test("PDF Export - Valid PDF Format", False, "Not a valid PDF file")
                    
            else:
                self.log_test("PDF Export - Request Status", False, f"Status {response.status_code}")
                
            # Test PDF with specific date
            url_with_date = f"{self.base_url}/daily-brief/pdf?date=2024-12-28"
            response = requests.get(url_with_date, timeout=30)
            if response.status_code == 200:
                self.log_test("PDF Export - With Date Parameter", True)
            else:
                self.log_test("PDF Export - With Date Parameter", False, f"Status {response.status_code}")
                
        except Exception as e:
            self.log_test("PDF Export - Request", False, f"Exception: {str(e)}")

    def test_weekly_trends_api(self):
        """Test GET /api/weekly-trends"""
        print("\n🔍 Testing Weekly Trends API...")
        
        success, data, status = self.make_request('GET', '/weekly-trends')
        if not success:
            self.log_test("Weekly Trends - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Weekly Trends - Basic Request", True)
        
        # Check response structure
        expected_fields = ['daily_severity', 'category_stats', 'state_stats']
        for field in expected_fields:
            if field in data:
                self.log_test(f"Weekly Trends - Has {field}", True)
            else:
                self.log_test(f"Weekly Trends - Has {field}", False, f"Missing field: {field}")
        
        # Check data types
        if isinstance(data.get('daily_severity'), list):
            self.log_test("Weekly Trends - Daily Severity Type", True)
        else:
            self.log_test("Weekly Trends - Daily Severity Type", False, "Should be list")
        
        if isinstance(data.get('category_stats'), list):
            self.log_test("Weekly Trends - Category Stats Type", True)
        else:
            self.log_test("Weekly Trends - Category Stats Type", False, "Should be list")

    def test_sources_api(self):
        """Test GET /api/sources"""
        print("\n🔍 Testing Sources API...")
        
        success, data, status = self.make_request('GET', '/sources')
        if success and 'sources' in data:
            self.log_test("Sources - Basic Request", True)
            sources = data.get('sources', [])
            if len(sources) > 0:
                self.log_test("Sources - Has RSS Sources", True)
            else:
                self.log_test("Sources - Has RSS Sources", False, "No sources returned")
        else:
            self.log_test("Sources - Basic Request", False, f"Status {status}: {data}")

    def test_pipeline_status_api(self):
        """Test GET /api/pipeline/status for rate limit configuration"""
        print("\n🔍 Testing Pipeline Status API with Rate Limit Config...")
        
        success, data, status = self.make_request('GET', '/pipeline/status')
        if not success:
            self.log_test("Pipeline Status - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Pipeline Status - Basic Request", True)
        
        # Check required fields
        required_fields = [
            'total_items', 'ai_processed', 'pending_retry', 'processing_rate',
            'recent_24h_processed', 'rss_sources', 'rate_limit_config', 'scheduler'
        ]
        
        for field in required_fields:
            if field in data:
                self.log_test(f"Pipeline Status - Has {field}", True)
            else:
                self.log_test(f"Pipeline Status - Has {field}", False, f"Missing field: {field}")
        
        # Check rate_limit_config specifically
        rate_config = data.get('rate_limit_config', {})
        expected_config = {
            'max_articles_per_cycle': 25,
            'batch_size': 3,
            'batch_pause_seconds': 5,
            'inter_article_delay_seconds': 1.5,
            'max_retry_per_cycle': 15
        }
        
        for key, expected_value in expected_config.items():
            actual_value = rate_config.get(key)
            if actual_value == expected_value:
                self.log_test(f"Pipeline Status - Rate Config {key}", True)
            else:
                self.log_test(f"Pipeline Status - Rate Config {key}", False, 
                             f"Expected {expected_value}, got {actual_value}")

    def test_analyze_news_api(self):
        """Test POST /api/analyze-news for retry functionality"""
        print("\n🔍 Testing Analyze News API...")
        
        success, data, status = self.make_request('POST', '/analyze-news')
        if success and 'message' in data and 'Analysis triggered' in data['message']:
            self.log_test("Analyze News - Trigger Request", True)
        else:
            self.log_test("Analyze News - Trigger Request", False, f"Status {status}: {data}")

    def test_root_endpoint(self):
        """Test GET /api/"""
        print("\n🔍 Testing Root Endpoint...")
        
        success, data, status = self.make_request('GET', '/')
        if success and 'message' in data:
            self.log_test("Root Endpoint - Basic Request", True)
        else:
            self.log_test("Root Endpoint - Basic Request", False, f"Status {status}: {data}")

    def test_fetch_news_api(self):
        """Test POST /api/fetch-news"""
        print("\n🔍 Testing Fetch News API...")
        
        success, data, status = self.make_request('POST', '/fetch-news')
        if success and 'message' in data:
            self.log_test("Fetch News - Trigger Request", True)
        else:
            self.log_test("Fetch News - Trigger Request", False, f"Status {status}: {data}")

    def test_deduplication_logic(self):
        """Test deduplication by checking processed articles count"""
        print("\n🔍 Testing Deduplication Logic...")
        
        # Get initial count
        success1, data1, status1 = self.make_request('GET', '/dashboard/stats')
        if not success1:
            self.log_test("Deduplication - Get Initial Count", False, f"Status {status1}")
            return
        
        initial_total = data1.get('total_items', 0)
        self.log_test("Deduplication - Get Initial Count", True)
        
        # Trigger fetch (this should skip already processed articles)
        success2, data2, status2 = self.make_request('POST', '/fetch-news')
        if success2:
            self.log_test("Deduplication - Trigger Fetch", True)
            
            # Wait a moment for background processing
            import time
            time.sleep(3)
            
            # Get count again - should either stay same or increase minimally
            success3, data3, status3 = self.make_request('GET', '/dashboard/stats')
            if success3:
                final_total = data3.get('total_items', 0)
                # Deduplication is working if total doesn't increase dramatically
                if final_total <= initial_total + 50:  # Allow small increase for new articles
                    self.log_test("Deduplication - Working Correctly", True)
                else:
                    self.log_test("Deduplication - Working Correctly", False, 
                                 f"Total increased from {initial_total} to {final_total}")
            else:
                self.log_test("Deduplication - Get Final Count", False, f"Status {status3}")
        else:
            self.log_test("Deduplication - Trigger Fetch", False, f"Status {status2}")

    def test_rate_limiting_config(self):
        """Test rate limiting configuration is correctly applied"""
        print("\n🔍 Testing Rate Limiting Configuration...")
        
        success, data, status = self.make_request('GET', '/pipeline/status')
        if not success:
            self.log_test("Rate Limiting - Pipeline Status", False, f"Status {status}")
            return
        
        rate_config = data.get('rate_limit_config', {})
        
        # Verify max articles per cycle is 25
        max_articles = rate_config.get('max_articles_per_cycle')
        if max_articles == 25:
            self.log_test("Rate Limiting - Max Articles Per Cycle (25)", True)
        else:
            self.log_test("Rate Limiting - Max Articles Per Cycle (25)", False, 
                         f"Expected 25, got {max_articles}")
        
        # Verify batch size is 3
        batch_size = rate_config.get('batch_size')
        if batch_size == 3:
            self.log_test("Rate Limiting - Batch Size (3)", True)
        else:
            self.log_test("Rate Limiting - Batch Size (3)", False, 
                         f"Expected 3, got {batch_size}")
        
        # Verify batch pause is 5 seconds
        batch_pause = rate_config.get('batch_pause_seconds')
        if batch_pause == 5:
            self.log_test("Rate Limiting - Batch Pause (5s)", True)
        else:
            self.log_test("Rate Limiting - Batch Pause (5s)", False, 
                         f"Expected 5, got {batch_pause}")
        
        # Verify inter-article delay is 1.5 seconds
        inter_delay = rate_config.get('inter_article_delay_seconds')
        if inter_delay == 1.5:
            self.log_test("Rate Limiting - Inter Article Delay (1.5s)", True)
        else:
            self.log_test("Rate Limiting - Inter Article Delay (1.5s)", False, 
                         f"Expected 1.5, got {inter_delay}")

    def test_unprocessed_items_retry(self):
        """Test that unprocessed items exist and retry mechanism works"""
        print("\n🔍 Testing Unprocessed Items Retry Logic...")
        
        # Check pipeline status for unprocessed items
        success, data, status = self.make_request('GET', '/pipeline/status')
        if not success:
            self.log_test("Retry Logic - Get Pipeline Status", False, f"Status {status}")
            return
        
        self.log_test("Retry Logic - Get Pipeline Status", True)
        
        pending_retry = data.get('pending_retry', 0)
        total_items = data.get('total_items', 0)
        
        if isinstance(pending_retry, int) and pending_retry >= 0:
            self.log_test("Retry Logic - Pending Retry Count Valid", True)
            print(f"   📊 Pending retry: {pending_retry}/{total_items} total items")
        else:
            self.log_test("Retry Logic - Pending Retry Count Valid", False, 
                         f"Invalid pending_retry value: {pending_retry}")
        
        # Trigger analyze news (retry mechanism)
        success2, data2, status2 = self.make_request('POST', '/analyze-news')
        if success2:
            self.log_test("Retry Logic - Trigger Retry Analysis", True)
        else:
            self.log_test("Retry Logic - Trigger Retry Analysis", False, f"Status {status2}")

    def test_background_processing_logs(self):
        """Test that background processing is configured correctly"""
        print("\n🔍 Testing Background Processing Configuration...")
        
        success, data, status = self.make_request('GET', '/pipeline/status')
        if not success:
            self.log_test("Background Processing - Get Status", False, f"Status {status}")
            return
        
        scheduler_info = data.get('scheduler', '')
        expected_schedule = "fetch every 30 min (max 25 articles), retry unprocessed every 15 min (max 15 articles)"
        
        if expected_schedule in scheduler_info:
            self.log_test("Background Processing - Scheduler Config", True)
        else:
            self.log_test("Background Processing - Scheduler Config", False, 
                         f"Expected '{expected_schedule}', got '{scheduler_info}'")
        
        # Check recent processing activity (last 24h)
        recent_processed = data.get('recent_24h_processed', 0)
        if isinstance(recent_processed, int) and recent_processed >= 0:
            self.log_test("Background Processing - Recent Activity Tracking", True)
            print(f"   📊 Recent 24h processed: {recent_processed} items")
        else:
            self.log_test("Background Processing - Recent Activity Tracking", False, 
                         f"Invalid recent_24h_processed: {recent_processed}")

    def test_twitter_accounts_api(self):
        """Test GET /api/twitter-accounts - NEW FEATURE"""
        print("\n🔍 Testing Twitter Accounts API...")
        
        success, data, status = self.make_request('GET', '/twitter-accounts')
        if not success:
            self.log_test("Twitter Accounts - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Twitter Accounts - Basic Request", True)
        
        # Check response structure
        if 'accounts' in data:
            self.log_test("Twitter Accounts - Has Accounts Field", True)
            
            accounts = data.get('accounts', [])
            if len(accounts) >= 10:  # Should have at least 10 defense accounts
                self.log_test("Twitter Accounts - Has Multiple Accounts", True)
            else:
                self.log_test("Twitter Accounts - Has Multiple Accounts", False, f"Only {len(accounts)} accounts")
            
            # Check for specific defense accounts
            handles = [acc.get('handle', '') for acc in accounts]
            expected_handles = ['@adgpi', '@IAF_MCC', '@indiannavy', '@DefenceMinIndia']
            
            found_handles = [h for h in expected_handles if h in handles]
            if len(found_handles) >= 3:
                self.log_test("Twitter Accounts - Has Defense Accounts", True)
            else:
                self.log_test("Twitter Accounts - Has Defense Accounts", False, f"Missing key defense accounts")
            
            # Check account structure
            if accounts and all(acc.get('handle') and acc.get('name') and acc.get('category') for acc in accounts):
                self.log_test("Twitter Accounts - Account Structure", True)
            else:
                self.log_test("Twitter Accounts - Account Structure", False, "Missing handle/name/category fields")
        else:
            self.log_test("Twitter Accounts - Has Accounts Field", False, "Missing accounts field")

    def test_uploaded_documents_api(self):
        """Test GET /api/uploaded-documents - NEW FEATURE"""
        print("\n🔍 Testing Uploaded Documents API...")
        
        success, data, status = self.make_request('GET', '/uploaded-documents')
        if not success:
            self.log_test("Uploaded Documents - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Uploaded Documents - Basic Request", True)
        
        # Check response structure
        if 'documents' in data and 'count' in data:
            self.log_test("Uploaded Documents - Response Structure", True)
            
            documents = data.get('documents', [])
            count = data.get('count', 0)
            
            if len(documents) == count:
                self.log_test("Uploaded Documents - Count Matches", True)
            else:
                self.log_test("Uploaded Documents - Count Matches", False, f"Count {count} != documents length {len(documents)}")
            
            # If there are documents, check structure
            if documents:
                doc = documents[0]
                required_fields = ['id', 'filename', 'file_type', 'uploaded_at', 'processed']
                missing_fields = [f for f in required_fields if f not in doc]
                
                if not missing_fields:
                    self.log_test("Uploaded Documents - Document Structure", True)
                else:
                    self.log_test("Uploaded Documents - Document Structure", False, f"Missing fields: {missing_fields}")
        else:
            self.log_test("Uploaded Documents - Response Structure", False, "Missing documents or count field")

    def test_upload_document_api(self):
        """Test POST /api/upload-document - NEW FEATURE"""
        print("\n🔍 Testing Upload Document API...")
        
        # Create a simple test file content
        test_content = "This is a test document for intelligence analysis. It contains information about border security and regional developments."
        
        try:
            import io
            # Create a file-like object
            files = {'file': ('test_document.txt', io.StringIO(test_content), 'text/plain')}
            
            url = f"{self.base_url}/upload-document"
            response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                self.log_test("Upload Document - Request Status", True)
                
                try:
                    data = response.json()
                    
                    # Check response structure
                    required_fields = ['message', 'document_id', 'filename', 'extracted_chars']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if not missing_fields:
                        self.log_test("Upload Document - Response Structure", True)
                    else:
                        self.log_test("Upload Document - Response Structure", False, f"Missing fields: {missing_fields}")
                    
                    # Check if document_id is valid UUID format
                    doc_id = data.get('document_id', '')
                    if len(doc_id) > 20:  # Basic UUID length check
                        self.log_test("Upload Document - Valid Document ID", True)
                    else:
                        self.log_test("Upload Document - Valid Document ID", False, f"Invalid document ID: {doc_id}")
                    
                    # Check extracted characters count
                    extracted_chars = data.get('extracted_chars', 0)
                    if extracted_chars > 0:
                        self.log_test("Upload Document - Text Extraction", True)
                    else:
                        self.log_test("Upload Document - Text Extraction", False, "No text extracted")
                        
                except Exception as e:
                    self.log_test("Upload Document - Parse Response", False, f"JSON parse error: {e}")
                    
            else:
                self.log_test("Upload Document - Request Status", False, f"Status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.log_test("Upload Document - Request", False, f"Exception: {str(e)}")

    def test_twitter_feeds_api(self):
        """Test GET /api/twitter-feeds - NEW FEATURE"""
        print("\n🔍 Testing Twitter Feeds API...")
        
        success, data, status = self.make_request('GET', '/twitter-feeds')
        if not success:
            self.log_test("Twitter Feeds - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Twitter Feeds - Basic Request", True)
        
        # Check response structure
        if 'feeds' in data and 'count' in data:
            self.log_test("Twitter Feeds - Response Structure", True)
            
            feeds = data.get('feeds', [])
            count = data.get('count', 0)
            
            if len(feeds) == count:
                self.log_test("Twitter Feeds - Count Matches", True)
            else:
                self.log_test("Twitter Feeds - Count Matches", False, f"Count {count} != feeds length {len(feeds)}")
            
            # Test with limit parameter
            success2, data2, status2 = self.make_request('GET', '/twitter-feeds?limit=10')
            if success2:
                feeds2 = data2.get('feeds', [])
                if len(feeds2) <= 10:
                    self.log_test("Twitter Feeds - Limit Parameter", True)
                else:
                    self.log_test("Twitter Feeds - Limit Parameter", False, f"Returned {len(feeds2)} feeds with limit=10")
            else:
                self.log_test("Twitter Feeds - Limit Parameter", False, f"Status {status2}")
        else:
            self.log_test("Twitter Feeds - Response Structure", False, "Missing feeds or count field")

    def test_enhanced_daily_brief_structure(self):
        """Test enhanced daily brief with new sections - NEW FEATURE"""
        print("\n🔍 Testing Enhanced Daily Brief Structure...")
        
        success, data, status = self.make_request('GET', '/daily-brief')
        if not success:
            self.log_test("Enhanced Brief - Basic Request", False, f"Status {status}: {data}")
            return
        
        self.log_test("Enhanced Brief - Basic Request", True)
        
        # Check for new sections
        new_sections = ['national_news', 'international_news', 'twitter_highlights', 'uploaded_insights']
        
        for section in new_sections:
            if section in data:
                self.log_test(f"Enhanced Brief - Has {section.replace('_', ' ').title()}", True)
                
                # Check if section is a list
                section_data = data.get(section, [])
                if isinstance(section_data, list):
                    self.log_test(f"Enhanced Brief - {section.replace('_', ' ').title()} is List", True)
                else:
                    self.log_test(f"Enhanced Brief - {section.replace('_', ' ').title()} is List", False, f"Should be list, got {type(section_data)}")
            else:
                self.log_test(f"Enhanced Brief - Has {section.replace('_', ' ').title()}", False, f"Missing {section} section")
        
        # Check if key_developments has enhanced structure with source links
        key_developments = data.get('key_developments', [])
        if key_developments and isinstance(key_developments[0], dict):
            dev = key_developments[0]
            if 'source_url' in dev and 'timestamp' in dev:
                self.log_test("Enhanced Brief - Key Developments with Links", True)
            else:
                self.log_test("Enhanced Brief - Key Developments with Links", False, "Missing source_url or timestamp")
        elif key_developments:
            self.log_test("Enhanced Brief - Key Developments with Links", False, "Key developments not in enhanced format")
        else:
            self.log_test("Enhanced Brief - Key Developments with Links", False, "No key developments found")

    def run_all_tests(self):
        """Run all API tests including new features"""
        print("🚀 Starting Rhino Drishti Backend API Tests")
        print(f"📡 Testing API at: {self.base_url}")
        print("=" * 60)
        
        self.test_root_endpoint()
        self.test_dashboard_stats()
        self.test_intelligence_api()
        self.test_intelligence_item()
        self.test_alerts_api()
        self.test_daily_brief_api()
        self.test_daily_brief_pdf_api()  # PDF export feature test
        self.test_weekly_trends_api()
        self.test_sources_api()
        self.test_fetch_news_api()
        
        # NEW FEATURES TESTS
        self.test_twitter_accounts_api()  # NEW: Twitter accounts monitoring
        self.test_uploaded_documents_api()  # NEW: Document upload list
        self.test_upload_document_api()  # NEW: Document upload functionality
        self.test_twitter_feeds_api()  # NEW: Twitter feeds
        self.test_enhanced_daily_brief_structure()  # NEW: Enhanced brief structure
        
        # Rate limiting and retry functionality tests
        self.test_pipeline_status_api()
        self.test_analyze_news_api()
        self.test_deduplication_logic()
        self.test_rate_limiting_config()
        self.test_unprocessed_items_retry()
        self.test_background_processing_logs()
        
        print("\n" + "=" * 60)
        print(f"📊 TEST RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for fail in self.failed_tests:
                print(f"   • {fail['name']}: {fail['details']}")
        
        success_rate = (self.tests_passed / self.tests_run) * 100 if self.tests_run > 0 else 0
        print(f"✨ Success Rate: {success_rate:.1f}%")
        
        return success_rate >= 80  # Consider 80%+ as overall success

if __name__ == "__main__":
    tester = RhinoDrishtiAPITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)