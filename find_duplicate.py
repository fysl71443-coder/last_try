#!/usr/bin/env python3
"""
Find duplicate routes in app.py
"""

def find_duplicates():
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    routes = {}
    functions = {}
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        # Find @app.route lines
        if line.startswith('@app.route('):
            route_path = line
            # Look for function definition in next few lines
            for j in range(i, min(i+5, len(lines))):
                func_line = lines[j].strip()
                if func_line.startswith('def '):
                    func_name = func_line.split('(')[0].replace('def ', '')
                    
                    if route_path in routes:
                        print(f"DUPLICATE ROUTE: {route_path}")
                        print(f"  First: Line {routes[route_path]} - {functions[route_path]}")
                        print(f"  Second: Line {i} - {func_name}")
                        print()
                    else:
                        routes[route_path] = i
                        functions[route_path] = func_name
                    break
    
    # Also check for duplicate function names
    func_counts = {}
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if line.startswith('def '):
            func_name = line.split('(')[0].replace('def ', '')
            if func_name in func_counts:
                func_counts[func_name].append(i)
            else:
                func_counts[func_name] = [i]
    
    print("DUPLICATE FUNCTIONS:")
    for func_name, line_numbers in func_counts.items():
        if len(line_numbers) > 1:
            print(f"  {func_name}: Lines {line_numbers}")

if __name__ == '__main__':
    find_duplicates()
