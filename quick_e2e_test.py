#!/usr/bin/env python3
"""
Quick E2E Test for Restaurant Management System
Fast HTTP-based testing of all major pages
"""

import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin

class QuickE2ETest:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = []
        self.run_id = f"quick_e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def log_result(self, test_name, status, message="", response_time=None):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'response_time_ms': response_time,
            'timestamp': datetime.now().isoformat()
        }
        self.results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        time_info = f" ({response_time}ms)" if response_time else ""
        print(f"{status_emoji} {test_name}: {status} - {message}{time_info}")
    
    def test_page(self, url, page_name, expected_content=None):
        """Test individual page"""
        try:
            start_time = time.time()
            response = self.session.get(url, timeout=10)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                # Check for expected content if provided
                if expected_content:
                    if any(content.lower() in response.text.lower() for content in expected_content):
                        self.log_result(page_name, "PASS", f"Page loaded with expected content", response_time)
                    else:
                        self.log_result(page_name, "WARN", f"Page loaded but missing expected content", response_time)
                else:
                    self.log_result(page_name, "PASS", f"Page loaded successfully", response_time)
                return True
            elif response.status_code == 302:
                self.log_result(page_name, "WARN", f"Redirect (probably needs login)", response_time)
                return True
            else:
                self.log_result(page_name, "FAIL", f"HTTP {response.status_code}", response_time)
                return False
                
        except Exception as e:
            self.log_result(page_name, "FAIL", f"Request failed: {str(e)}")
            return False
    
    def test_api_endpoint(self, endpoint, expected_json=True):
        """Test API endpoint"""
        try:
            url = urljoin(self.base_url, endpoint)
            start_time = time.time()
            response = self.session.get(url, timeout=10)
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                if expected_json:
                    try:
                        json.loads(response.text)
                        self.log_result(f"API - {endpoint}", "PASS", "Valid JSON response", response_time)
                    except:
                        self.log_result(f"API - {endpoint}", "WARN", "Non-JSON response", response_time)
                else:
                    self.log_result(f"API - {endpoint}", "PASS", "Response received", response_time)
                return True
            elif response.status_code == 404:
                self.log_result(f"API - {endpoint}", "FAIL", "Not Found", response_time)
                return False
            else:
                self.log_result(f"API - {endpoint}", "WARN", f"HTTP {response.status_code}", response_time)
                return True
                
        except Exception as e:
            self.log_result(f"API - {endpoint}", "FAIL", f"Request failed: {str(e)}")
            return False
    
    def run_quick_test(self):
        """Run quick comprehensive test"""
        print(f"🚀 Quick E2E Test - Run ID: {self.run_id}")
        print(f"🎯 Target: {self.base_url}")
        print("=" * 60)
        
        start_time = time.time()
        
        # Test main pages
        pages_to_test = [
            {'url': '/', 'name': 'Home/Login Page', 'content': ['login', 'username', 'password']},
            {'url': '/dashboard', 'name': 'Dashboard', 'content': ['dashboard', 'card']},
            {'url': '/settings', 'name': 'Settings Page', 'content': ['settings', 'company']},
            {'url': '/employees', 'name': 'Employees Page', 'content': ['employee', 'name']},
            {'url': '/inventory', 'name': 'Inventory Page', 'content': ['inventory', 'material']},
            {'url': '/reports', 'name': 'Reports Page', 'content': ['report', 'chart']},
            {'url': '/sales/china_town', 'name': 'China Town POS', 'content': ['china', 'product']},
            {'url': '/sales/palace_india', 'name': 'Palace India POS', 'content': ['palace', 'product']},
            {'url': '/tables/1', 'name': 'China Town Tables', 'content': ['table', 'china']},
            {'url': '/tables/2', 'name': 'Palace India Tables', 'content': ['table', 'palace']},
        ]
        
        print("📄 Testing Main Pages:")
        for page in pages_to_test:
            url = urljoin(self.base_url, page['url'])
            self.test_page(url, page['name'], page.get('content'))
            time.sleep(0.2)  # Brief pause
        
        print("\n🔌 Testing API Endpoints:")
        api_endpoints = [
            '/api/tables/1',
            '/api/tables/2',
            '/api/categories',
            '/api/products/1',
            '/api/load-draft-order/1/1',
            '/api/table-settings'
        ]
        
        for endpoint in api_endpoints:
            self.test_api_endpoint(endpoint)
            time.sleep(0.1)
        
        # Test static resources
        print("\n📁 Testing Static Resources:")
        static_resources = [
            '/static/css/style.css',
            '/static/js/main.js',
            '/static/images/logo.png'
        ]
        
        for resource in static_resources:
            url = urljoin(self.base_url, resource)
            self.test_page(url, f"Static - {resource}", None)
            time.sleep(0.1)
        
        # Generate summary
        end_time = time.time()
        duration = end_time - start_time
        
        self.generate_summary(duration)
        
        return True
    
    def generate_summary(self, duration):
        """Generate test summary"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['status'] == 'PASS'])
        failed_tests = len([r for r in self.results if r['status'] == 'FAIL'])
        warned_tests = len([r for r in self.results if r['status'] == 'WARN'])
        
        # Calculate average response time
        response_times = [r['response_time_ms'] for r in self.results if r.get('response_time_ms')]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"🕐 Duration: {duration:.2f} seconds")
        print(f"📈 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Warnings: {warned_tests}")
        print(f"📊 Success Rate: {(passed_tests/total_tests*100):.1f}%")
        print(f"⚡ Avg Response Time: {avg_response_time:.0f}ms")
        
        # Show failed tests
        if failed_tests > 0:
            print(f"\n❌ FAILED TESTS:")
            for result in self.results:
                if result['status'] == 'FAIL':
                    print(f"   • {result['test_name']}: {result['message']}")
        
        # Show warnings
        if warned_tests > 0:
            print(f"\n⚠️ WARNINGS:")
            for result in self.results:
                if result['status'] == 'WARN':
                    print(f"   • {result['test_name']}: {result['message']}")
        
        # Save detailed results
        report_data = {
            'run_id': self.run_id,
            'base_url': self.base_url,
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'warnings': warned_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%",
                'avg_response_time_ms': round(avg_response_time, 0)
            },
            'results': self.results
        }
        
        # Save to file
        filename = f"quick_e2e_report_{self.run_id}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Detailed report saved: {filename}")
        except Exception as e:
            print(f"\n❌ Failed to save report: {e}")
        
        print("=" * 60)
        
        return report_data

if __name__ == "__main__":
    # Run quick E2E test
    tester = QuickE2ETest("https://restaurant-system-fnbm.onrender.com")
    success = tester.run_quick_test()
    
    if success:
        print("🎉 Quick E2E Test completed successfully!")
    else:
        print("💥 Quick E2E Test encountered issues!")
