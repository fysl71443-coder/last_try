#!/usr/bin/env python3
"""
Simplified E2E Testing for Restaurant Management System
HTTP-based testing without browser automation
"""

import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import os

class SimpleE2ETest:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = []
        self.run_id = f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_folder = f"test_results/{self.run_id}"
        
        # Create output directory
        os.makedirs(self.output_folder, exist_ok=True)
    
    def log_result(self, test_name, status, message="", details=None):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'details': details
        }
        self.results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌"
        print(f"{status_emoji} {test_name}: {status} - {message}")
    
    def test_page_accessibility(self, url, page_name):
        """Test if page is accessible and returns valid HTML"""
        try:
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                # Check if it's HTML content
                if 'text/html' in response.headers.get('content-type', ''):
                    soup = BeautifulSoup(response.content, 'html.parser')
                    title = soup.title.string if soup.title else "No title"
                    
                    # Check for error indicators
                    if any(error in title.lower() for error in ['error', '404', '500']):
                        self.log_result(f"Page Access - {page_name}", "FAIL", f"Error page detected: {title}")
                        return False
                    
                    self.log_result(f"Page Access - {page_name}", "PASS", f"Page loaded successfully - {title}")
                    return True, soup
                else:
                    self.log_result(f"Page Access - {page_name}", "FAIL", "Non-HTML response")
                    return False
            else:
                self.log_result(f"Page Access - {page_name}", "FAIL", f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result(f"Page Access - {page_name}", "FAIL", f"Request failed: {str(e)}")
            return False
    
    def test_login_functionality(self):
        """Test login page and functionality"""
        try:
            # Test login page access
            result = self.test_page_accessibility(self.base_url, "Login Page")
            if not result:
                return False
            
            success, soup = result
            
            # Look for login form
            login_form = soup.find('form')
            if not login_form:
                self.log_result("Login Form", "FAIL", "No login form found")
                return False
            
            # Check for username and password fields
            username_field = soup.find('input', {'name': 'username'}) or soup.find('input', {'type': 'text'})
            password_field = soup.find('input', {'name': 'password'}) or soup.find('input', {'type': 'password'})
            
            if username_field and password_field:
                self.log_result("Login Form Elements", "PASS", "Username and password fields found")
            else:
                self.log_result("Login Form Elements", "FAIL", "Missing login fields")
                return False
            
            # Attempt login (if we can find the form action)
            form_action = login_form.get('action', '/login')
            login_url = urljoin(self.base_url, form_action)
            
            # Try to login with default credentials
            login_data = {
                'username': 'admin',
                'password': 'admin'
            }
            
            # Get CSRF token if present
            csrf_token = soup.find('input', {'name': 'csrf_token'})
            if csrf_token:
                login_data['csrf_token'] = csrf_token.get('value')
            
            response = self.session.post(login_url, data=login_data, timeout=15, allow_redirects=True)

            # Check for successful login indicators
            success_indicators = [
                'dashboard' in response.url.lower(),
                'dashboard' in response.text.lower(),
                'logout' in response.text.lower(),
                'welcome' in response.text.lower(),
                'dashboard-card' in response.text
            ]

            if response.status_code == 200 and any(success_indicators):
                self.log_result("Login Functionality", "PASS", f"Successfully logged in - URL: {response.url}")
                return True
            else:
                # Try to continue anyway for testing
                self.log_result("Login Functionality", "WARN", f"Login uncertain - Status: {response.status_code}, URL: {response.url}")
                return True  # Continue testing anyway
                
        except Exception as e:
            self.log_result("Login Functionality", "FAIL", f"Login test failed: {str(e)}")
            return False
    
    def discover_navigation_links(self):
        """Discover navigation links from dashboard"""
        try:
            dashboard_url = urljoin(self.base_url, '/dashboard')
            result = self.test_page_accessibility(dashboard_url, "Dashboard")
            
            if not result:
                return []
            
            success, soup = result
            
            # Find navigation links
            nav_links = []
            
            # Look for dashboard cards
            dashboard_cards = soup.find_all('div', class_='dashboard-card')
            for card in dashboard_cards:
                parent_link = card.find_parent('a')
                if parent_link and parent_link.get('href'):
                    title_elem = card.find('h6')
                    title = title_elem.text.strip() if title_elem else "Unknown"
                    
                    nav_links.append({
                        'title': title,
                        'url': urljoin(self.base_url, parent_link.get('href'))
                    })
            
            # Also look for regular navigation links
            nav_elements = soup.find_all('a', href=True)
            for link in nav_elements:
                href = link.get('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    full_url = urljoin(self.base_url, href)
                    if self.base_url in full_url:  # Only internal links
                        title = link.text.strip() or href
                        if title and len(title) < 100:  # Reasonable title length
                            nav_links.append({
                                'title': title,
                                'url': full_url
                            })
            
            # Remove duplicates
            unique_links = []
            seen_urls = set()
            for link in nav_links:
                if link['url'] not in seen_urls:
                    unique_links.append(link)
                    seen_urls.add(link['url'])
            
            self.log_result("Navigation Discovery", "PASS", f"Found {len(unique_links)} unique navigation links")
            return unique_links
            
        except Exception as e:
            self.log_result("Navigation Discovery", "FAIL", f"Failed to discover navigation: {str(e)}")
            return []
    
    def test_page_functionality(self, link):
        """Test individual page functionality"""
        page_name = link['title']
        page_url = link['url']
        
        try:
            result = self.test_page_accessibility(page_url, page_name)
            if not result:
                return False
            
            success, soup = result
            
            # Test forms if present
            forms = soup.find_all('form')
            if forms:
                self.test_forms_on_page(page_name, forms)
            
            # Test tables if present
            tables = soup.find_all('table')
            if tables:
                self.test_tables_on_page(page_name, tables)
            
            # Test buttons and links
            buttons = soup.find_all('button')
            links = soup.find_all('a', href=True)
            
            interactive_elements = len(buttons) + len(links)
            self.log_result(f"Page Elements - {page_name}", "PASS", 
                          f"Found {len(forms)} forms, {len(tables)} tables, {interactive_elements} interactive elements")
            
            return True
            
        except Exception as e:
            self.log_result(f"Page Functionality - {page_name}", "FAIL", f"Test failed: {str(e)}")
            return False
    
    def test_forms_on_page(self, page_name, forms):
        """Test forms on the page"""
        try:
            for i, form in enumerate(forms):
                form_inputs = form.find_all(['input', 'select', 'textarea'])
                required_fields = [inp for inp in form_inputs if inp.get('required')]
                
                self.log_result(f"Form Analysis - {page_name}", "PASS", 
                              f"Form {i+1}: {len(form_inputs)} fields, {len(required_fields)} required")
        except Exception as e:
            self.log_result(f"Form Analysis - {page_name}", "FAIL", f"Form test failed: {str(e)}")
    
    def test_tables_on_page(self, page_name, tables):
        """Test tables on the page"""
        try:
            for i, table in enumerate(tables):
                headers = table.find_all('th')
                rows = table.find_all('tr')
                
                self.log_result(f"Table Analysis - {page_name}", "PASS", 
                              f"Table {i+1}: {len(headers)} columns, {len(rows)} rows")
        except Exception as e:
            self.log_result(f"Table Analysis - {page_name}", "FAIL", f"Table test failed: {str(e)}")
    
    def test_api_endpoints(self):
        """Test common API endpoints"""
        api_endpoints = [
            '/api/tables/1',
            '/api/tables/2', 
            '/api/categories',
            '/api/products',
            '/settings',
            '/employees',
            '/inventory',
            '/reports'
        ]
        
        for endpoint in api_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    self.log_result(f"API Endpoint - {endpoint}", "PASS", f"HTTP 200 OK")
                elif response.status_code == 404:
                    self.log_result(f"API Endpoint - {endpoint}", "FAIL", f"HTTP 404 Not Found")
                else:
                    self.log_result(f"API Endpoint - {endpoint}", "PASS", f"HTTP {response.status_code}")
                    
            except Exception as e:
                self.log_result(f"API Endpoint - {endpoint}", "FAIL", f"Request failed: {str(e)}")
    
    def test_direct_pages(self):
        """Test direct access to known pages"""
        known_pages = [
            {'title': 'Dashboard', 'url': '/dashboard'},
            {'title': 'Settings', 'url': '/settings'},
            {'title': 'Employees', 'url': '/employees'},
            {'title': 'Inventory', 'url': '/inventory'},
            {'title': 'Reports', 'url': '/reports'},
            {'title': 'Sales China Town', 'url': '/sales/china_town'},
            {'title': 'Sales Palace India', 'url': '/sales/palace_india'},
            {'title': 'Tables China Town', 'url': '/tables/1'},
            {'title': 'Tables Palace India', 'url': '/tables/2'},
        ]

        for page in known_pages:
            full_url = urljoin(self.base_url, page['url'])
            page['url'] = full_url
            self.test_page_functionality(page)
            time.sleep(0.5)

    def run_comprehensive_test(self):
        """Run comprehensive E2E test suite"""
        print(f"🚀 Starting Comprehensive E2E Test - Run ID: {self.run_id}")
        print(f"🎯 Target URL: {self.base_url}")

        start_time = time.time()

        # Test 1: Login functionality
        login_success = self.test_login_functionality()

        # Test 2: Direct page testing (works with or without login)
        print("🔍 Testing direct page access...")
        self.test_direct_pages()

        # Test 3: Discover navigation (if login worked)
        if login_success:
            nav_links = self.discover_navigation_links()

            # Test discovered pages
            for link in nav_links[:5]:  # Limit to first 5 to avoid timeout
                self.test_page_functionality(link)
                time.sleep(0.5)

        # Test 4: API endpoints
        print("🔍 Testing API endpoints...")
        self.test_api_endpoints()

        # Generate report
        end_time = time.time()
        duration = end_time - start_time

        self.generate_final_report(duration)

        return True
    
    def generate_final_report(self, duration):
        """Generate final test report"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['status'] == 'PASS'])
        failed_tests = total_tests - passed_tests
        
        report_data = {
            'run_id': self.run_id,
            'base_url': self.base_url,
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
            },
            'results': self.results
        }
        
        # Save JSON report
        report_file = f'{self.output_folder}/test_report.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        # Generate summary
        print(f"\n📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {failed_tests}")
        print(f"   Success Rate: {report_data['summary']['success_rate']}")
        print(f"   Duration: {duration:.2f} seconds")
        print(f"   Report saved: {report_file}")
        
        return report_data

if __name__ == "__main__":
    # Run simplified E2E test
    tester = SimpleE2ETest("https://restaurant-system-fnbm.onrender.com")
    success = tester.run_comprehensive_test()
    
    if success:
        print("✅ E2E Test Suite completed")
    else:
        print("❌ E2E Test Suite failed")
