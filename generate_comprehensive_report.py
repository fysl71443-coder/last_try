#!/usr/bin/env python3
"""
Generate Comprehensive E2E Test Report
Combines all test results into a detailed HTML report
"""

import json
import glob
import os
from datetime import datetime

def load_test_results():
    """Load all test result files"""
    results = {}
    
    # Find all JSON report files
    report_files = glob.glob("*e2e_report_*.json")
    
    for file in report_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Determine test type from filename or content
            if 'quick_e2e' in file:
                test_type = 'Quick E2E Test'
            elif 'functional_e2e' in file:
                test_type = 'Functional E2E Test'
            else:
                test_type = 'E2E Test'
            
            results[test_type] = data
            
        except Exception as e:
            print(f"Error loading {file}: {e}")
    
    return results

def generate_html_report(test_results):
    """Generate comprehensive HTML report"""
    
    # Calculate overall statistics
    total_tests = sum(data['summary']['total_tests'] for data in test_results.values())
    total_passed = sum(data['summary']['passed'] for data in test_results.values())
    total_failed = sum(data['summary']['failed'] for data in test_results.values())
    total_warnings = sum(data['summary'].get('warnings', 0) for data in test_results.values())
    
    overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Restaurant System E2E Test Report</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5em;
                font-weight: 300;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
                font-size: 1.1em;
            }}
            .summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                padding: 30px;
                background: #f8f9fa;
            }}
            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                border-left: 4px solid #667eea;
            }}
            .stat-card.success {{ border-left-color: #28a745; }}
            .stat-card.danger {{ border-left-color: #dc3545; }}
            .stat-card.warning {{ border-left-color: #ffc107; }}
            .stat-number {{
                font-size: 2.5em;
                font-weight: bold;
                margin: 0;
                color: #333;
            }}
            .stat-label {{
                color: #666;
                margin: 5px 0 0 0;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .test-section {{
                margin: 30px;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                overflow: hidden;
            }}
            .test-section-header {{
                background: #343a40;
                color: white;
                padding: 15px 20px;
                font-size: 1.2em;
                font-weight: 500;
            }}
            .test-results {{
                padding: 20px;
            }}
            .test-result {{
                display: flex;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid #f1f3f4;
            }}
            .test-result:last-child {{
                border-bottom: none;
            }}
            .status-icon {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                margin-right: 15px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 12px;
                color: white;
            }}
            .status-pass {{ background: #28a745; }}
            .status-fail {{ background: #dc3545; }}
            .status-warn {{ background: #ffc107; color: #333; }}
            .test-name {{
                flex: 1;
                font-weight: 500;
            }}
            .test-message {{
                color: #666;
                font-size: 0.9em;
                margin-left: 35px;
                margin-top: 5px;
            }}
            .timestamp {{
                color: #999;
                font-size: 0.8em;
                margin-left: auto;
            }}
            .footer {{
                background: #f8f9fa;
                padding: 20px;
                text-align: center;
                color: #666;
                border-top: 1px solid #e9ecef;
            }}
            .progress-bar {{
                width: 100%;
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
                margin: 10px 0;
            }}
            .progress-fill {{
                height: 100%;
                background: linear-gradient(90deg, #28a745, #20c997);
                transition: width 0.3s ease;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.75em;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .badge-success {{ background: #d4edda; color: #155724; }}
            .badge-danger {{ background: #f8d7da; color: #721c24; }}
            .badge-warning {{ background: #fff3cd; color: #856404; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧪 Restaurant System E2E Test Report</h1>
                <p>Comprehensive End-to-End Testing Results</p>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="summary">
                <div class="stat-card">
                    <div class="stat-number">{total_tests}</div>
                    <div class="stat-label">Total Tests</div>
                </div>
                <div class="stat-card success">
                    <div class="stat-number">{total_passed}</div>
                    <div class="stat-label">Passed</div>
                </div>
                <div class="stat-card danger">
                    <div class="stat-number">{total_failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat-card warning">
                    <div class="stat-number">{total_warnings}</div>
                    <div class="stat-label">Warnings</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{overall_success_rate:.1f}%</div>
                    <div class="stat-label">Success Rate</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {overall_success_rate}%"></div>
                    </div>
                </div>
            </div>
    """
    
    # Add each test section
    for test_type, data in test_results.items():
        html_content += f"""
            <div class="test-section">
                <div class="test-section-header">
                    {test_type} - {data['summary']['success_rate']} Success Rate
                    <span style="float: right;">
                        <span class="badge badge-success">{data['summary']['passed']} Passed</span>
                        <span class="badge badge-danger">{data['summary']['failed']} Failed</span>
                        {f'<span class="badge badge-warning">{data["summary"].get("warnings", 0)} Warnings</span>' if data['summary'].get('warnings', 0) > 0 else ''}
                    </span>
                </div>
                <div class="test-results">
        """
        
        # Add test results
        for result in data.get('results', []):
            status_class = f"status-{result['status'].lower()}"
            status_symbol = "✓" if result['status'] == 'PASS' else "✗" if result['status'] == 'FAIL' else "!"
            
            timestamp = datetime.fromisoformat(result['timestamp']).strftime('%H:%M:%S')
            
            html_content += f"""
                    <div class="test-result">
                        <div class="status-icon {status_class}">{status_symbol}</div>
                        <div>
                            <div class="test-name">{result['test_name']}</div>
                            <div class="test-message">{result['message']}</div>
                        </div>
                        <div class="timestamp">{timestamp}</div>
                    </div>
            """
        
        html_content += """
                </div>
            </div>
        """
    
    # Add footer
    html_content += f"""
            <div class="footer">
                <p>🏢 Restaurant Management System - E2E Test Suite</p>
                <p>Target URL: <strong>{list(test_results.values())[0].get('base_url', 'N/A')}</strong></p>
                <p>Report generated automatically by E2E Test Framework</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def main():
    """Main function to generate comprehensive report"""
    print("📊 Generating Comprehensive E2E Test Report...")
    
    # Load test results
    test_results = load_test_results()
    
    if not test_results:
        print("❌ No test result files found!")
        return
    
    print(f"✅ Found {len(test_results)} test result files")
    
    # Generate HTML report
    html_content = generate_html_report(test_results)
    
    # Save report
    report_filename = f"comprehensive_e2e_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    
    try:
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Comprehensive report generated: {report_filename}")
        print(f"🌐 Open the file in your browser to view the detailed report")
        
        # Print summary to console
        total_tests = sum(data['summary']['total_tests'] for data in test_results.values())
        total_passed = sum(data['summary']['passed'] for data in test_results.values())
        total_failed = sum(data['summary']['failed'] for data in test_results.values())
        
        print(f"\n📈 Overall Results:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {total_passed}")
        print(f"   Failed: {total_failed}")
        print(f"   Success Rate: {(total_passed/total_tests*100):.1f}%")
        
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")

if __name__ == "__main__":
    main()
