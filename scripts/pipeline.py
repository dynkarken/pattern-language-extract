#!/usr/bin/env python3
"""
Pipeline orchestrator — chains ocr → extract → (review pause) → upload.

Usage:
  python scripts/pipeline.py <scans_dir> <pattern_name> <pattern_number> [--auto]

Options:
  --auto   Skip the human review pause and upload immediately after extraction.

Example:
  python scripts/pipeline.py scans/ "House for a Small Family" 76
  python scripts/pipeline.py scans/ "House for a Small Family" 76 --auto
"""

import sys
import os
from pathlib import Path

# Allow importing sibling scripts directly
sys.path.insert(0, str(Path(__file__).parent))

import ocr
import extract as extract_mod
import json


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    scans_dir      = sys.argv[1]
    pattern_name   = sys.argv[2]
    pattern_number = int(sys.argv[3])
    auto           = "--auto" in sys.argv

    # ── Step 1: OCR ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 1 — OCR: Pattern {pattern_number}: {pattern_name}")
    print(f"{'='*60}")

    page_paths = ocr.find_pattern_pages(scans_dir, pattern_number)
    if not page_paths:
        print(f"Error: no scan files found for pattern {pattern_number} in {scans_dir}")
        sys.exit(1)

    pages    = []
    all_text = []
    for idx, page_path in enumerate(page_paths):
        page_num  = idx + 1
        page_text = ocr.extract_text_from_page(page_path)
        all_text.append(page_text)
        pages.append({
            "page_num":    page_num,
            "source_file": os.path.basename(page_path),
            "text":        page_text,
        })

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(all_text)
    text_data = {
        "pattern_name":   pattern_name,
        "pattern_number": pattern_number,
        "pages":          pages,
        "full_text":      full_text,
    }

    text_json_path = f"patterns/{pattern_number:03d}_text.json"
    with open(text_json_path, "w") as f:
        json.dump(text_data, f, indent=2)
    print(f"\nOCR complete: {text_json_path}")

    # ── Step 2: Extract ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 2 — Extract knowledge")
    print(f"{'='*60}")

    knowledge = extract_mod.extract_knowledge(text_json_path)

    knowledge_json_path = f"patterns/{pattern_number:03d}_knowledge.json"
    with open(knowledge_json_path, "w") as f:
        json.dump(knowledge, f, indent=2)
    print(f"\nExtraction complete: {knowledge_json_path}")

    # ── Review pause ──────────────────────────────────────────────────────────
    if not auto:
        print(f"\n{'='*60}")
        print(f"REVIEW CHECKPOINT")
        print(f"{'='*60}")
        print(f"Knowledge JSON written to: {knowledge_json_path}")
        print(f"\nReview checklist:")
        print(f"  [ ] Problem statement is verbatim, not a summary")
        print(f"  [ ] Solution statement is the 'Therefore:' directive")
        print(f"  [ ] All forces have both poles populated")
        print(f"  [ ] All typed_rules with numbers have source_text")
        print(f"  [ ] No invariant rule has hedging language")
        print(f"  [ ] adjacency_rules captures numbered cross-references")
        print(f"  [ ] failure_modes describe failure, not re-state the rule")
        print(f"  [ ] JSON is valid")
        print(f"\nEdit {knowledge_json_path} if needed, then press Enter to upload.")
        print(f"(Ctrl+C to abort without uploading.)\n")
        try:
            input("Press Enter to continue to upload > ")
        except KeyboardInterrupt:
            print("\nAborted. Run upload manually:")
            print(f"  python scripts/upload.py {knowledge_json_path}")
            sys.exit(0)

    # ── Step 3: Upload ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 3 — Upload to Notion")
    print(f"{'='*60}")

    # Import upload here to avoid crashing if env vars aren't set during OCR/extract
    import upload as upload_mod
    upload_mod.main.__module__  # trigger import check

    # Re-invoke upload.main with the knowledge path as argv
    original_argv = sys.argv[:]
    sys.argv = ["upload.py", knowledge_json_path]
    try:
        upload_mod.main()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
