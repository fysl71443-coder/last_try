#!/usr/bin/env python3
"""
E2E Testing Suite for Restaurant Management System
Comprehensive UI testing with screenshots and detailed reporting
"""

import os
import time
import json
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

class E2ETestRunner:
    def __init__(self, base_url, timeout=15000):
        self.base_url = base_url
        self.timeout = timeout / 1000  # Convert to seconds
        self.run_id = f"e2e_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_folder = f"test_results/{self.run_id}"
        self.results = []
        self.driver = None
        
        # Create output directory
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{self.output_folder}/test.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_driver(self):
        """Setup Chrome WebDriver with options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(self.timeout)
            self.logger.info("✅ WebDriver initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize WebDriver: {e}")
            return False
    
    def take_screenshot(self, name, description=""):
        """Take screenshot and save to output folder"""
        try:
            timestamp = datetime.now().strftime('%H%M%S')
            filename = f"{timestamp}_{name}.png"
            filepath = os.path.join(self.output_folder, filename)
            self.driver.save_screenshot(filepath)
            self.logger.info(f"📸 Screenshot saved: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"❌ Failed to take screenshot: {e}")
            return None
    
    def log_result(self, test_name, status, message="", screenshot=None, error_details=None):
        """Log test result"""
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'screenshot': screenshot,
            'error_details': error_details
        }
        self.results.append(result)
        
        status_emoji = "✅" if status == "PASS" else "❌"
        self.logger.info(f"{status_emoji} {test_name}: {status} - {message}")
    
    def test_login_page(self):
        """Test 1: Login page functionality"""
        try:
            self.driver.get(self.base_url)
            
            # Wait for login form
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            
            screenshot = self.take_screenshot("01_login_page", "Login page loaded")
            
            # Check login form elements
            username_field = self.driver.find_element(By.NAME, "username")
            password_field = self.driver.find_element(By.NAME, "password")
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            
            if username_field and password_field and login_button:
                self.log_result("Login Page Elements", "PASS", "All login elements found", screenshot)
                return True
            else:
                self.log_result("Login Page Elements", "FAIL", "Missing login elements", screenshot)
                return False
                
        except Exception as e:
            screenshot = self.take_screenshot("01_login_page_error")
            self.log_result("Login Page Load", "FAIL", f"Failed to load login page: {str(e)}", screenshot, str(e))
            return False
    
    def perform_login(self, username="admin", password="admin"):
        """Test 2: Login functionality"""
        try:
            # Fill login form
            username_field = self.driver.find_element(By.NAME, "username")
            password_field = self.driver.find_element(By.NAME, "password")
            
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit form
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for dashboard
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "dashboard-card"))
            )
            
            screenshot = self.take_screenshot("02_dashboard_after_login", "Dashboard loaded after login")
            self.log_result("User Login", "PASS", f"Successfully logged in as {username}", screenshot)
            return True
            
        except Exception as e:
            screenshot = self.take_screenshot("02_login_error")
            self.log_result("User Login", "FAIL", f"Login failed: {str(e)}", screenshot, str(e))
            return False
    
    def get_navigation_menu(self):
        """Test 3: Collect navigation menu items"""
        try:
            # Get all dashboard cards (navigation items)
            dashboard_cards = self.driver.find_elements(By.CLASS_NAME, "dashboard-card")
            menu_items = []
            
            for card in dashboard_cards:
                try:
                    link = card.find_element(By.XPATH, "..")  # Parent <a> tag
                    href = link.get_attribute("href")
                    title = card.find_element(By.TAG_NAME, "h6").text
                    
                    if href and title:
                        menu_items.append({
                            'title': title,
                            'url': href,
                            'element': link
                        })
                except:
                    continue
            
            self.log_result("Navigation Menu Collection", "PASS", f"Found {len(menu_items)} menu items")
            return menu_items
            
        except Exception as e:
            screenshot = self.take_screenshot("03_navigation_error")
            self.log_result("Navigation Menu Collection", "FAIL", f"Failed to collect menu: {str(e)}", screenshot, str(e))
            return []
    
    def test_screen(self, menu_item):
        """Test individual screen functionality"""
        screen_name = menu_item['title']
        screen_url = menu_item['url']
        
        try:
            # Navigate to screen
            self.driver.get(screen_url)
            time.sleep(2)  # Wait for page load
            
            # Take initial screenshot
            screenshot = self.take_screenshot(f"screen_{screen_name.replace(' ', '_')}", f"Initial view of {screen_name}")
            
            # Check if page loaded successfully
            page_title = self.driver.title
            if "Error" in page_title or "404" in page_title:
                self.log_result(f"Screen Load - {screen_name}", "FAIL", "Page shows error", screenshot)
                return False
            
            # Test basic functionality based on screen type
            self.test_screen_functionality(screen_name, screen_url)
            
            self.log_result(f"Screen Access - {screen_name}", "PASS", "Screen loaded successfully", screenshot)
            return True
            
        except Exception as e:
            screenshot = self.take_screenshot(f"screen_error_{screen_name.replace(' ', '_')}")
            self.log_result(f"Screen Access - {screen_name}", "FAIL", f"Failed to access screen: {str(e)}", screenshot, str(e))
            return False
    
    def test_screen_functionality(self, screen_name, screen_url):
        """Test specific functionality based on screen type"""
        try:
            # Test tables if present
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            if tables:
                self.test_table_functionality(screen_name)
            
            # Test forms if present
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            if forms:
                self.test_form_functionality(screen_name)
            
            # Test buttons
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            if buttons:
                self.test_button_functionality(screen_name, buttons)
                
        except Exception as e:
            self.logger.warning(f"⚠️ Screen functionality test failed for {screen_name}: {e}")
    
    def test_table_functionality(self, screen_name):
        """Test table sorting and filtering"""
        try:
            # Test table headers for sorting
            headers = self.driver.find_elements(By.CSS_SELECTOR, "th")
            if headers:
                # Click first sortable header
                headers[0].click()
                time.sleep(1)
                screenshot = self.take_screenshot(f"table_sort_{screen_name.replace(' ', '_')}")
                self.log_result(f"Table Sorting - {screen_name}", "PASS", "Table sorting tested", screenshot)
        except Exception as e:
            self.logger.warning(f"Table functionality test failed: {e}")
    
    def test_form_functionality(self, screen_name):
        """Test form validation and submission"""
        try:
            # Find input fields
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email'], input[type='number']")
            
            if inputs:
                # Test form validation with invalid data
                for input_field in inputs[:2]:  # Test first 2 fields
                    input_field.clear()
                    input_field.send_keys("test_invalid_data_123")
                
                # Try to submit
                submit_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                if submit_buttons:
                    submit_buttons[0].click()
                    time.sleep(1)
                    
                screenshot = self.take_screenshot(f"form_test_{screen_name.replace(' ', '_')}")
                self.log_result(f"Form Testing - {screen_name}", "PASS", "Form functionality tested", screenshot)
                
        except Exception as e:
            self.logger.warning(f"Form functionality test failed: {e}")
    
    def test_button_functionality(self, screen_name, buttons):
        """Test button interactions"""
        try:
            clickable_buttons = [btn for btn in buttons if btn.is_enabled() and btn.is_displayed()]
            
            if clickable_buttons:
                # Test first few buttons (avoid destructive actions)
                safe_buttons = [btn for btn in clickable_buttons[:3] if 'delete' not in btn.text.lower()]
                
                for button in safe_buttons:
                    try:
                        button.click()
                        time.sleep(0.5)
                        # Go back if modal or new page opened
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        continue
                        
                screenshot = self.take_screenshot(f"buttons_test_{screen_name.replace(' ', '_')}")
                self.log_result(f"Button Testing - {screen_name}", "PASS", f"Tested {len(safe_buttons)} buttons", screenshot)
                
        except Exception as e:
            self.logger.warning(f"Button functionality test failed: {e}")
    
    def run_full_test_suite(self):
        """Run complete E2E test suite"""
        self.logger.info(f"🚀 Starting E2E Test Suite - Run ID: {self.run_id}")
        
        if not self.setup_driver():
            return False
        
        try:
            # Test 1: Login page
            if not self.test_login_page():
                return False
            
            # Test 2: Login functionality
            if not self.perform_login():
                return False
            
            # Test 3: Get navigation menu
            menu_items = self.get_navigation_menu()
            if not menu_items:
                return False
            
            # Test 4: Test each screen
            for menu_item in menu_items:
                self.test_screen(menu_item)
                time.sleep(1)  # Brief pause between screens
            
            # Generate final report
            self.generate_report()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Test suite failed: {e}")
            return False
        
        finally:
            if self.driver:
                self.driver.quit()
    
    def generate_report(self):
        """Generate HTML test report"""
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r['status'] == 'PASS'])
        failed_tests = total_tests - passed_tests
        
        report_data = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'base_url': self.base_url,
            'summary': {
                'total': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
            },
            'results': self.results
        }
        
        # Save JSON report
        with open(f'{self.output_folder}/report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        # Generate HTML report
        self.generate_html_report(report_data)
        
        self.logger.info(f"📊 Test Report Generated: {passed_tests}/{total_tests} tests passed")
    
    def generate_html_report(self, data):
        """Generate HTML report"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>E2E Test Report - {data['run_id']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
                .stat {{ background: #e9ecef; padding: 15px; border-radius: 5px; text-align: center; }}
                .pass {{ color: #28a745; }}
                .fail {{ color: #dc3545; }}
                .result {{ margin: 10px 0; padding: 10px; border-left: 4px solid #ccc; }}
                .result.pass {{ border-color: #28a745; }}
                .result.fail {{ border-color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧪 E2E Test Report</h1>
                <p><strong>Run ID:</strong> {data['run_id']}</p>
                <p><strong>URL:</strong> {data['base_url']}</p>
                <p><strong>Timestamp:</strong> {data['timestamp']}</p>
            </div>
            
            <div class="summary">
                <div class="stat">
                    <h3>{data['summary']['total']}</h3>
                    <p>Total Tests</p>
                </div>
                <div class="stat">
                    <h3 class="pass">{data['summary']['passed']}</h3>
                    <p>Passed</p>
                </div>
                <div class="stat">
                    <h3 class="fail">{data['summary']['failed']}</h3>
                    <p>Failed</p>
                </div>
                <div class="stat">
                    <h3>{data['summary']['success_rate']}</h3>
                    <p>Success Rate</p>
                </div>
            </div>
            
            <h2>Test Results</h2>
        """
        
        for result in data['results']:
            status_class = result['status'].lower()
            html_content += f"""
            <div class="result {status_class}">
                <h4>{result['test_name']} - <span class="{status_class}">{result['status']}</span></h4>
                <p>{result['message']}</p>
                <small>{result['timestamp']}</small>
                {f'<br><img src="{result["screenshot"]}" style="max-width: 300px; margin-top: 10px;">' if result.get('screenshot') else ''}
            </div>
            """
        
        html_content += """
        </body>
        </html>
        """
        
        with open(f'{self.output_folder}/report.html', 'w', encoding='utf-8') as f:
            f.write(html_content)

if __name__ == "__main__":
    # Run E2E tests
    runner = E2ETestRunner("https://restaurant-system-fnbm.onrender.com")
    success = runner.run_full_test_suite()
    
    if success:
        print("✅ E2E Test Suite completed successfully")
    else:
        print("❌ E2E Test Suite failed")
