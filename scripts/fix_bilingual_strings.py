# -*- coding: utf-8 -*-
"""
Replace _('English / Arabic') with _('English') in all templates except thermal receipts.
Output translation pairs for .po files.
"""
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
EXCLUDE = {
    os.path.normpath(os.path.join(TEMPLATES_DIR, "print", "receipt.html")),
    os.path.normpath(os.path.join(TEMPLATES_DIR, "print", "order_slip.html")),
}

# Match _('... / ...') - content between quotes must not contain unescaped single quote
PATTERN = re.compile(r"_\(['\"]([^'\"]+?)\s+/\s+[^'\"]+['\"]\)")

def main():
    translations = {}  # en -> ar (we'll collect from first occurrence)
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.normpath(os.path.join(root, f))
            if path in EXCLUDE:
                continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fp:
                    content = fp.read()
            except Exception as e:
                print("Read error", filepath, e)
                continue
            # Find all _('X / Y') and capture (X, Y)
            pattern_full = re.compile(r"_\((['\"])(.+?)\s+/\s+(.+?)\1\)", re.DOTALL)
            new_content = content
            for m in pattern_full.finditer(content):
                quote, en, ar = m.group(1), m.group(2).strip(), m.group(3).strip()
                if en not in translations:
                    translations[en] = ar
                repl = "_(%s%s%s)" % (quote, en, quote)
                old = m.group(0)
                new_content = new_content.replace(old, repl, 1)
            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as fp:
                    fp.write(new_content)
                print("Updated:", filepath)
    # Write translation pairs for .po
    out_path = os.path.join(PROJECT_ROOT, "scripts", "bilingual_pairs.txt")
    with open(out_path, "w", encoding="utf-8") as fp:
        for en, ar in sorted(translations.items(), key=lambda x: x[0].lower()):
            fp.write("%s\t%s\n" % (en.replace("\n", " "), ar.replace("\n", " ")))
    print("Pairs written:", out_path, "count:", len(translations))

if __name__ == "__main__":
    main()
