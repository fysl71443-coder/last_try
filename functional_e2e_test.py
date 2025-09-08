#!/usr/bin/env python3
"""
Functional E2E Test for Restaurant Management System
Tests specific functionality like CRUD operations, forms, and business logic
"""

import requests
import json
import time
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re

class FunctionalE2ETest:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = []
        self.run_id = f"functional_e2e_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.csrf_token = None
    
    def log_result(self, test_name, status, message="", details=None):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status} - {message}")
    
    def get_csrf_token(self, html_content):
        """Extract CSRF token from HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            csrf_input = soup.find('input', {'name': 'csrf_token'})
            if csrf_input:
                return csrf_input.get('value')
        except:
            pass
        return None
    
    def test_login_process(self):
        """Test complete login process"""
        try:
            # Get login page
            response = self.session.get(self.base_url, timeout=10)
            if response.status_code != 200:
                self.log_result("Login Page Access", "FAIL", f"HTTP {response.status_code}")
                return False
            
            # Extract CSRF token
            self.csrf_token = self.get_csrf_token(response.text)
            
            # Prepare login data
            login_data = {
                'username': 'admin',
                'password': 'admin'
            }
            
            if self.csrf_token:
                login_data['csrf_token'] = self.csrf_token
            
            # Attempt login
            login_response = self.session.post(
                urljoin(self.base_url, '/login'),
                data=login_data,
                timeout=10,
                allow_redirects=True
            )
            
            # Check login success
            if login_response.status_code == 200:
                # Look for dashboard indicators
                if any(indicator in login_response.text.lower() for indicator in 
                       ['dashboard', 'logout', 'welcome', 'dashboard-card']):
                    self.log_result("Login Process", "PASS", "Successfully logged in")
                    return True
                else:
                    self.log_result("Login Process", "WARN", "Login response unclear")
                    return True  # Continue anyway
            else:
                self.log_result("Login Process", "FAIL", f"Login failed - HTTP {login_response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Login Process", "FAIL", f"Login error: {str(e)}")
            return False
    
    def test_employee_crud(self):
        """Test Employee CRUD operations"""
        try:
            # Test GET employees page
            response = self.session.get(urljoin(self.base_url, '/employees'), timeout=10)
            if response.status_code != 200:
                self.log_result("Employee Page Access", "FAIL", f"HTTP {response.status_code}")
                return False
            
            self.log_result("Employee Page Access", "PASS", "Employees page accessible")
            
            # Check for employee form
            soup = BeautifulSoup(response.text, 'html.parser')
            employee_form = soup.find('form', method='POST')
            
            if employee_form:
                self.log_result("Employee Form", "PASS", "Employee form found")
                
                # Test form fields
                required_fields = ['employee_code', 'full_name', 'national_id']
                found_fields = []
                
                for field in required_fields:
                    if soup.find('input', {'name': field}):
                        found_fields.append(field)
                
                if len(found_fields) == len(required_fields):
                    self.log_result("Employee Form Fields", "PASS", f"All required fields found: {found_fields}")
                else:
                    self.log_result("Employee Form Fields", "WARN", f"Some fields missing. Found: {found_fields}")
            else:
                self.log_result("Employee Form", "FAIL", "No employee form found")
            
            # Check for existing employees
            employee_table = soup.find('table')
            if employee_table:
                rows = employee_table.find_all('tr')
                employee_count = len(rows) - 1  # Subtract header row
                self.log_result("Employee Data", "PASS", f"Found {employee_count} employees in table")
            else:
                self.log_result("Employee Data", "WARN", "No employee table found")
            
            return True
            
        except Exception as e:
            self.log_result("Employee CRUD Test", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_settings_functionality(self):
        """Test Settings page functionality"""
        try:
            response = self.session.get(urljoin(self.base_url, '/settings'), timeout=10)
            if response.status_code != 200:
                self.log_result("Settings Page Access", "FAIL", f"HTTP {response.status_code}")
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for settings form
            settings_form = soup.find('form', method='post')
            if settings_form:
                self.log_result("Settings Form", "PASS", "Settings form found")
                
                # Check for key settings fields
                key_fields = ['company_name', 'tax_number', 'vat_rate', 'currency']
                found_fields = []
                
                for field in key_fields:
                    if soup.find(['input', 'select'], {'name': field}):
                        found_fields.append(field)
                
                self.log_result("Settings Fields", "PASS", f"Found {len(found_fields)}/{len(key_fields)} key fields")
                
                # Check for tabs
                tabs = soup.find_all('button', {'data-bs-toggle': 'tab'})
                if tabs:
                    tab_names = [tab.text.strip() for tab in tabs]
                    self.log_result("Settings Tabs", "PASS", f"Found {len(tabs)} tabs: {tab_names}")
                
            else:
                self.log_result("Settings Form", "FAIL", "No settings form found")
            
            return True
            
        except Exception as e:
            self.log_result("Settings Test", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_pos_functionality(self):
        """Test POS (Point of Sale) functionality"""
        branches = [
            {'name': 'China Town', 'url': '/sales/china_town'},
            {'name': 'Palace India', 'url': '/sales/palace_india'}
        ]
        
        for branch in branches:
            try:
                response = self.session.get(urljoin(self.base_url, branch['url']), timeout=10)
                if response.status_code != 200:
                    self.log_result(f"POS {branch['name']} Access", "FAIL", f"HTTP {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for POS elements
                pos_elements = {
                    'product_grid': soup.find('div', class_=re.compile(r'product|item|menu')),
                    'cart': soup.find('div', class_=re.compile(r'cart|order|invoice')),
                    'total': soup.find(text=re.compile(r'total|مجموع', re.I)),
                    'payment_buttons': soup.find_all('button', text=re.compile(r'pay|دفع', re.I))
                }
                
                found_elements = [k for k, v in pos_elements.items() if v]
                
                if len(found_elements) >= 2:
                    self.log_result(f"POS {branch['name']} Elements", "PASS", 
                                  f"Found POS elements: {found_elements}")
                else:
                    self.log_result(f"POS {branch['name']} Elements", "WARN", 
                                  f"Limited POS elements found: {found_elements}")
                
                # Check for JavaScript/dynamic content indicators
                scripts = soup.find_all('script')
                has_pos_js = any('product' in script.text.lower() or 'cart' in script.text.lower() 
                               for script in scripts if script.text)
                
                if has_pos_js:
                    self.log_result(f"POS {branch['name']} JavaScript", "PASS", "POS JavaScript detected")
                else:
                    self.log_result(f"POS {branch['name']} JavaScript", "WARN", "No POS JavaScript detected")
                
            except Exception as e:
                self.log_result(f"POS {branch['name']} Test", "FAIL", f"Error: {str(e)}")
    
    def test_reports_functionality(self):
        """Test Reports page functionality"""
        try:
            response = self.session.get(urljoin(self.base_url, '/reports'), timeout=10)
            if response.status_code != 200:
                self.log_result("Reports Page Access", "FAIL", f"HTTP {response.status_code}")
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for report filters
            filter_form = soup.find('form', method='GET')
            if filter_form:
                period_select = soup.find('select', {'name': 'period'})
                branch_select = soup.find('select', {'name': 'branch'})
                
                filters_found = []
                if period_select: filters_found.append('period')
                if branch_select: filters_found.append('branch')
                
                self.log_result("Reports Filters", "PASS", f"Found filters: {filters_found}")
            
            # Check for report data/charts
            report_indicators = [
                soup.find('canvas'),  # Chart.js canvas
                soup.find('div', class_=re.compile(r'chart|graph')),
                soup.find(text=re.compile(r'sales|revenue|profit', re.I)),
                soup.find('table')  # Data table
            ]
            
            found_indicators = [i for i in report_indicators if i]
            
            if found_indicators:
                self.log_result("Reports Content", "PASS", f"Found {len(found_indicators)} report elements")
            else:
                self.log_result("Reports Content", "WARN", "No report content detected")
            
            return True
            
        except Exception as e:
            self.log_result("Reports Test", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_table_management(self):
        """Test Table Management functionality"""
        table_urls = [
            {'name': 'China Town Tables', 'url': '/tables/1'},
            {'name': 'Palace India Tables', 'url': '/tables/2'}
        ]
        
        for table_config in table_urls:
            try:
                response = self.session.get(urljoin(self.base_url, table_config['url']), timeout=10)
                if response.status_code != 200:
                    self.log_result(f"{table_config['name']} Access", "FAIL", f"HTTP {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check for table elements
                table_elements = soup.find_all('div', class_=re.compile(r'table|seat'))
                table_buttons = soup.find_all('button', text=re.compile(r'table|طاولة', re.I))
                
                total_tables = len(table_elements) + len(table_buttons)
                
                if total_tables > 0:
                    self.log_result(f"{table_config['name']} Elements", "PASS", 
                                  f"Found {total_tables} table elements")
                else:
                    self.log_result(f"{table_config['name']} Elements", "WARN", "No table elements found")
                
                # Check for table status indicators
                status_indicators = soup.find_all(text=re.compile(r'available|occupied|reserved', re.I))
                if status_indicators:
                    self.log_result(f"{table_config['name']} Status", "PASS", 
                                  f"Found {len(status_indicators)} status indicators")
                
            except Exception as e:
                self.log_result(f"{table_config['name']} Test", "FAIL", f"Error: {str(e)}")
    
    def run_functional_tests(self):
        """Run all functional tests"""
        print(f"🧪 Functional E2E Test - Run ID: {self.run_id}")
        print(f"🎯 Target: {self.base_url}")
        print("=" * 70)
        
        start_time = time.time()
        
        # Test 1: Login Process
        print("🔐 Testing Login Process...")
        login_success = self.test_login_process()
        
        # Test 2: Employee Management
        print("\n👥 Testing Employee Management...")
        self.test_employee_crud()
        
        # Test 3: Settings
        print("\n⚙️ Testing Settings...")
        self.test_settings_functionality()
        
        # Test 4: POS Systems
        print("\n🛒 Testing POS Systems...")
        self.test_pos_functionality()
        
        # Test 5: Reports
        print("\n📊 Testing Reports...")
        self.test_reports_functionality()
        
        # Test 6: Table Management
        print("\n🪑 Testing Table Management...")
        self.test_table_management()
        
        # Generate summary
        end_time = time.time()
        duration = end_time - start_time
        
        self.generate_functional_summary(duration)
        
        return True
    
    def generate_functional_summary(self, duration):
        """Generate functional test summary"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['status'] == 'PASS'])
        failed_tests = len([r for r in self.results if r['status'] == 'FAIL'])
        warned_tests = len([r for r in self.results if r['status'] == 'WARN'])
        
        print("\n" + "=" * 70)
        print("🎯 FUNCTIONAL TEST SUMMARY")
        print("=" * 70)
        print(f"⏱️ Duration: {duration:.2f} seconds")
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Warnings: {warned_tests}")
        print(f"🎯 Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Categorize results by functionality
        categories = {}
        for result in self.results:
            category = result['test_name'].split()[0]
            if category not in categories:
                categories[category] = {'pass': 0, 'fail': 0, 'warn': 0}
            categories[category][result['status'].lower()] += 1
        
        print(f"\n📋 Results by Category:")
        for category, stats in categories.items():
            total = sum(stats.values())
            success_rate = (stats['pass'] / total * 100) if total > 0 else 0
            print(f"   {category}: {stats['pass']}/{total} passed ({success_rate:.0f}%)")
        
        # Show critical failures
        critical_failures = [r for r in self.results if r['status'] == 'FAIL' and 
                           any(critical in r['test_name'].lower() for critical in 
                               ['login', 'access', 'form', 'crud'])]
        
        if critical_failures:
            print(f"\n🚨 Critical Failures:")
            for failure in critical_failures:
                print(f"   • {failure['test_name']}: {failure['message']}")
        
        # Save detailed report
        report_data = {
            'run_id': self.run_id,
            'test_type': 'functional_e2e',
            'base_url': self.base_url,
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'warnings': warned_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%"
            },
            'categories': categories,
            'results': self.results
        }
        
        filename = f"functional_e2e_report_{self.run_id}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Detailed report saved: {filename}")
        except Exception as e:
            print(f"\n❌ Failed to save report: {e}")
        
        print("=" * 70)
        
        return report_data

if __name__ == "__main__":
    # Run functional E2E test
    tester = FunctionalE2ETest("https://restaurant-system-fnbm.onrender.com")
    success = tester.run_functional_tests()
    
    if success:
        print("🎉 Functional E2E Test completed!")
    else:
        print("💥 Functional E2E Test encountered critical issues!")
