# -*- coding: utf-8 -*-
"""
Merge clean (en, ar) pairs from bilingual_pairs.txt into ar and en .po files.
Only use pairs where the English key is "clean" (no template junk).
Uses babel.messages.pofile to preserve .po format.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAIRS_FILE = os.path.join(PROJECT_ROOT, "scripts", "bilingual_pairs.txt")
AR_PO = os.path.join(PROJECT_ROOT, "translations", "ar", "LC_MESSAGES", "messages.po")
EN_PO = os.path.join(PROJECT_ROOT, "translations", "en", "LC_MESSAGES", "messages.po")

def is_clean_key(key):
    if not key or len(key) > 250:
        return False
    bad = ["{{", "}}", "')", "_('", "\n", "\r"]
    return not any(b in key for b in bad)

def load_pairs():
    pairs = {}
    with open(PAIRS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n\r")
            if "\t" not in line:
                continue
            en, ar = line.split("\t", 1)
            en, ar = en.strip(), ar.strip()
            if is_clean_key(en) and ar:
                pairs[en] = ar
    return pairs

def main():
    from babel.messages.pofile import read_po, write_po
    pairs = load_pairs()
    print("Clean pairs:", len(pairs))
    for path, locale, use_ar in [(AR_PO, "ar", True), (EN_PO, "en", False)]:
        with open(path, "rb") as f:
            catalog = read_po(f, locale=locale)
        for msgid, ar in pairs.items():
            if not msgid:
                continue
            entry = catalog.get(msgid)
            if entry is None:
                catalog.add(msgid, string=ar if use_ar else msgid)
            elif use_ar and (not entry.string or not entry.string.strip()):
                entry.string = ar
            elif not use_ar:
                entry.string = msgid
        with open(path, "wb") as f:
            write_po(f, catalog, width=0)
        print("Updated", path)

if __name__ == "__main__":
    main()
