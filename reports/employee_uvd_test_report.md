# تقرير فحص شاشة الموظفين الجديدة

تاريخ الفحص: 2025-11-26 21:56

## الأزرار التي تعمل
- Login: ✅ تعمل — http://127.0.0.1:5000/dashboard
- Open UVD: ✅ تعمل — 
- Add Employee: ✅ تعمل — 
- Global Search: ✅ تعمل — 
- Reports Monthly: ✅ تعمل — 
- Filter Dept: ✅ تعمل — 
- Grant Advance: ✅ تعمل — 
- Verify Journal API: ✅ تعمل — {'credit': 0, 'date': '2025-10-07', 'debit': 350, 'desc': 'منح سلفة', 'entry': 'ADV944832'}
- Advances Panel: ✅ تعمل — 
- Ledger List API: ✅ تعمل — rows=2

## الأزرار التي بها مشاكل
- Edit Employee: ❌ مشكلة — Message: element not interactable
  (Session info: MicrosoftEdge=142.0.3595.94); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#elementnotinteractableexception
Stacktrace:
Symbols not available. Dumping unresolved backtrace:
	0x7ff6dc72a715
	0x7ff6dc72a774
	0x7ff6dc49d4c6
	0x7ff6dc4e5402
	0x7ff6dc4db95e
	0x7ff6dc503c8a
	0x7ff6dc4db3d5
	0x7ff6dc4db2ed
	0x7ff6dc4db3d5
	0x7ff6dc51e6f2
	0x7ff6dc4da8aa
	0x7ff6dc4d9bd1
	0x7ff6dc4da6d3
	0x7ff6dc5981f4
	0x7ff6dc594717
	0x7ff6dc757375
	0x7ff6dc7457d1
	0x7ff6dc74dc79
	0x7ff6dc731c64
	0x7ff6dc731db3
	0x7ff6dc71fae6
	0x7ffeea27257d
	0x7ffeea3eaf08

- Pay Salary: ❌ مشكلة — Message: element not interactable
  (Session info: MicrosoftEdge=142.0.3595.94); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#elementnotinteractableexception
Stacktrace:
Symbols not available. Dumping unresolved backtrace:
	0x7ff6dc72a715
	0x7ff6dc72a774
	0x7ff6dc49d4c6
	0x7ff6dc4e5402
	0x7ff6dc4db95e
	0x7ff6dc503c8a
	0x7ff6dc4db3d5
	0x7ff6dc4db2ed
	0x7ff6dc4db3d5
	0x7ff6dc51e6f2
	0x7ff6dc4da8aa
	0x7ff6dc4d9bd1
	0x7ff6dc4da6d3
	0x7ff6dc5981f4
	0x7ff6dc594717
	0x7ff6dc757375
	0x7ff6dc7457d1
	0x7ff6dc74dc79
	0x7ff6dc731c64
	0x7ff6dc731db3
	0x7ff6dc71fae6
	0x7ffeea27257d
	0x7ffeea3eaf08

- Preview Journal: ❌ مشكلة — Message: element not interactable
  (Session info: MicrosoftEdge=142.0.3595.94); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#elementnotinteractableexception
Stacktrace:
Symbols not available. Dumping unresolved backtrace:
	0x7ff6dc72a715
	0x7ff6dc72a774
	0x7ff6dc49d4c6
	0x7ff6dc4e5402
	0x7ff6dc4db95e
	0x7ff6dc503c8a
	0x7ff6dc4db3d5
	0x7ff6dc4db2ed
	0x7ff6dc4db3d5
	0x7ff6dc51e6f2
	0x7ff6dc4da8aa
	0x7ff6dc4d9bd1
	0x7ff6dc4da6d3
	0x7ff6dc5981f4
	0x7ff6dc594717
	0x7ff6dc757375
	0x7ff6dc7457d1
	0x7ff6dc74dc79
	0x7ff6dc731c64
	0x7ff6dc731db3
	0x7ff6dc71fae6
	0x7ffeea27257d
	0x7ffeea3eaf08

- Delete Employee: ❌ مشكلة — Message: element click intercepted: Element is not clickable at point (1300, 1697)
  (Session info: MicrosoftEdge=142.0.3595.94); For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors#elementclickinterceptedexception
Stacktrace:
Symbols not available. Dumping unresolved backtrace:
	0x7ff6dc72a715
	0x7ff6dc72a774
	0x7ff6dc8dc558
	0x7ff6dc4e9c7c
	0x7ff6dc4e8291
	0x7ff6dc4e61c9
	0x7ff6dc4e56c5
	0x7ff6dc4db95e
	0x7ff6dc503c8a
	0x7ff6dc4db3d5
	0x7ff6dc4db2ed
	0x7ff6dc4db3d5
	0x7ff6dc51e6f2
	0x7ff6dc4da8aa
	0x7ff6dc4d9bd1
	0x7ff6dc4da6d3
	0x7ff6dc5981f4
	0x7ff6dc594717
	0x7ff6dc757375
	0x7ff6dc7457d1
	0x7ff6dc74dc79
	0x7ff6dc731c64
	0x7ff6dc731db3
	0x7ff6dc71fae6
	0x7ffeea27257d
	0x7ffeea3eaf08


## الأخطاء في الكونسول
- http://127.0.0.1:5000/favicon.ico - Failed to load resource: the server responded with a status of 404 (NOT FOUND)
- http://127.0.0.1:5000/static/media/restaurant_bg_poster.jpg - Failed to load resource: the server responded with a status of 404 (NOT FOUND)
- http://127.0.0.1:5000/static/media/restaurant_bg_1080p.mp4 - Failed to load resource: the server responded with a status of 404 (NOT FOUND)
- http://127.0.0.1:5000/api/employees - Failed to load resource: the server responded with a status of 400 (BAD REQUEST)
- http://127.0.0.1:5000/employee-uvd 0:0 Uncaught (in promise) SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON
- http://127.0.0.1:5000/api/reports/monthly?year=2025 - Failed to load resource: the server responded with a status of 500 (INTERNAL SERVER ERROR)
- http://127.0.0.1:5000/api/advances - Failed to load resource: the server responded with a status of 400 (BAD REQUEST)
- http://127.0.0.1:5000/employee-uvd 0:0 Uncaught (in promise) SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON

## لقطات شاشة
- Open UVD: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\open_uvd.png)
- Add Employee: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\add_employee.png)
- Global Search: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\global_search.png)
- Reports Monthly: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\reports_monthly.png)
- Filter Dept: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\filter_kitchen.png)
- Grant Advance: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\grant_advance.png)
- Advances Panel: ![](C:\Users\DELL\Documents\augment-projects\CHINA TOWN-PLACE INDIA\screenshots\employee_uvd\panel_adv.png)
