#!/usr/bin/env python3
"""
OCR — transcribe scanned pattern pages to text JSON.

Usage:
  python scripts/ocr.py <scans_dir> <pattern_name> <pattern_number>

Output:
  {pattern_number:03d}_text.json

Example:
  python scripts/ocr.py scans/ "House for a Small Family" 76
"""

import base64
import json
import logging
import os
import sys
from pathlib import Path

# Load .env from project root
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

client = anthropic.Anthropic()


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_text_from_page(image_path: str) -> str:
    """Transcribe all text from a scanned book page via Claude Vision."""
    logger.info(f"  Transcribing: {os.path.basename(image_path)}")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": encode_image(image_path),
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Please transcribe ALL the text from this scanned book page accurately.\n\n"
                        "Preserve:\n"
                        "- Exact wording and punctuation\n"
                        "- Paragraph breaks and structure\n"
                        "- All numbers, dimensions, and measurements\n"
                        "- Any diagrams or illustrations — insert a tag like "
                        "[DIAGRAM: brief description of what it shows]\n"
                        "- Any photographs — insert a tag like "
                        "[PHOTOGRAPH: brief description of what it depicts]\n\n"
                        "Format as clean, readable text. Do not add interpretations or summaries."
                    ),
                },
            ],
        }],
    )
    return message.content[0].text


def find_pattern_pages(scans_dir: str, pattern_number: int) -> list[str]:
    """
    Find and sort JPEG page files for a given pattern number.
    Supports two naming conventions:
      Scan format:  076_House_for_a_Small_Family_1.jpeg
      Legacy:       pattern_76_1.jpg
    Returns sorted list of full file paths.
    """
    scan_prefix   = f"{pattern_number:03d}_"
    legacy_prefix = f"pattern_{pattern_number}_"

    matched = [
        f for f in os.listdir(scans_dir)
        if (f.startswith(scan_prefix) or f.startswith(legacy_prefix))
        and f.lower().endswith((".jpg", ".jpeg"))
    ]

    if not matched:
        logger.error(
            f"No files matching '{scan_prefix}*.jpeg' or '{legacy_prefix}*.jpg' in {scans_dir}\n"
            f"Files present: {os.listdir(scans_dir)}"
        )
        return []

    def sort_key(fname):
        stem = Path(fname).stem
        try:
            return int(stem.rsplit("_", 1)[-1])
        except ValueError:
            return 0

    return [os.path.join(scans_dir, f) for f in sorted(matched, key=sort_key)]


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    scans_dir      = sys.argv[1]
    pattern_name   = sys.argv[2]
    pattern_number = int(sys.argv[3])

    page_paths = find_pattern_pages(scans_dir, pattern_number)
    if not page_paths:
        print(f"Error: no scan files found for pattern {pattern_number} in {scans_dir}")
        sys.exit(1)

    logger.info(f"Found {len(page_paths)} page(s): {[os.path.basename(p) for p in page_paths]}")

    pages    = []
    all_text = []

    for idx, page_path in enumerate(page_paths):
        page_num  = idx + 1
        page_text = extract_text_from_page(page_path)
        all_text.append(page_text)
        pages.append({
            "page_num":    page_num,
            "source_file": os.path.basename(page_path),
            "text":        page_text,
        })

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(all_text)

    output = {
        "pattern_name":   pattern_name,
        "pattern_number": pattern_number,
        "pages":          pages,
        "full_text":      full_text,
    }

    out_path = f"{pattern_number:03d}_text.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nOCR complete — {len(pages)} page(s), {len(full_text):,} chars")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
