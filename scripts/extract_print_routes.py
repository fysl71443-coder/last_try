"""Extract remaining print routes to routes/sales.py."""
from __future__ import annotations

ROUTES_PATH = "app/routes.py"
SALES_PATH = "routes/sales.py"

# Line ranges for print routes (1-based)
# These need to be found dynamically based on current file
BLOCKS = [
    (3570, 3634, 'print_order_slip'),  # approximate
    (3432, 3569, 'print_order_preview'),
    (3305, 3431, 'print_receipt'),
]


def transform_block(text: str) -> str:
    s = text
    s = s.replace("@main.route(", "@bp.route(")
    s = s.replace("url_for('main.print_receipt'", "url_for('sales.print_receipt'")
    s = s.replace("url_for('main.print_order_preview'", "url_for('sales.print_order_preview'")
    s = s.replace("url_for('main.print_order_slip'", "url_for('sales.print_order_slip'")
    return s


def main():
    with open(ROUTES_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Find actual end of print_order_slip (next @main.route)
    for i in range(3570, min(len(lines), 3700)):
        if lines[i].strip().startswith("@main.route("):
            BLOCKS[0] = (3570, i, 'print_order_slip')
            break
    
    print(f"Total lines in {ROUTES_PATH}: {len(lines)}")
    
    # Extract chunks
    extracted = []
    for start, end, name in sorted(BLOCKS, key=lambda x: x[0]):
        chunk = "".join(lines[start - 1 : end])
        transformed = transform_block(chunk)
        extracted.append(transformed)
        print(f"Extracted {name}: lines {start}-{end}")
    
    # Append to sales.py
    with open(SALES_PATH, "a", encoding="utf-8") as f:
        f.write("\n\n# === Print Routes ===\n")
        f.write("\n".join(extracted))
    print(f"Appended to {SALES_PATH}")
    
    # Remove from app/routes.py (bottom to top)
    for start, end, name in sorted(BLOCKS, key=lambda x: -x[0]):
        del lines[start - 1 : end]
        print(f"Removed {name}")
    
    with open(ROUTES_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"Updated {ROUTES_PATH}")


if __name__ == "__main__":
    main()
