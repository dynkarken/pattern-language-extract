#!/usr/bin/env python3
"""
Claude Vision Extraction Pipeline
For each page JPEG of a pattern:
  1. detect_visual_regions() — crops out embedded photos and diagrams (scan-extract)
  2. extract_text_from_page() — transcribes all text via Claude Vision
  3. Links extracted visuals to the page text they came from

Input:  folder of JPEGs named pattern_76_1.jpg, pattern_76_2.jpg, etc.
Output: JSON with per-page text+visuals, quantitative rules, qualitative features

Usage:
  python claude_vision_extraction.py <images_dir> <pattern_name> <pattern_number> [output.json]
"""

import base64
import json
import os
import re
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image
import anthropic

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

# Rotation for A Pattern Language scans (from scan-extract SKILL.md):
# Photos are printed sideways in the book; diagrams are already upright.
PHOTO_ROTATION    = 270   # degrees CCW (PIL convention) — corrects 90° CW scan tilt
DIAGRAM_ROTATION  = 0


# ─────────────────────────────────────────────────────────────────────────────
# STAGE A: Visual extraction (scan-extract logic)
# ─────────────────────────────────────────────────────────────────────────────

def detect_visual_regions(img_path: str, output_dir: str, page_label: str,
                           photo_rotation: int = PHOTO_ROTATION,
                           diagram_rotation: int = DIAGRAM_ROTATION,
                           padding: int = 60) -> List[Dict]:
    """
    Detect and crop photos and diagrams from a scanned book page JPEG.
    Uses a heavy Gaussian blur to dissolve text into the background, leaving
    only large photo/diagram blobs, then classifies by tone statistics.

    Naming convention: {page_label}_{kind}_{index:02d}.jpg
    e.g. 076_House_for_a_Small_Family_p1_photo_01.jpg

    Returns list of dicts: {filename, kind, width, height}
    """
    img = cv2.imread(img_path)
    if img is None:
        logger.warning(f"Could not read image: {img_path}")
        return []

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Strong blur dissolves text; photos and diagrams survive as large blobs
    blurred = cv2.GaussianBlur(gray, (51, 51), 0)
    _, thresh = cv2.threshold(blurred, 220, 255, cv2.THRESH_BINARY_INV)

    # Close gaps to form solid, coherent blobs
    kernel = np.ones((60, 60), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * 0.005   # at least 0.5% of page — filters noise/thin rules
    max_area = h * w * 0.95    # skip full-page border artifact

    candidates = []
    for cnt in contours:
        x, y, rw, rh = cv2.boundingRect(cnt)
        area = rw * rh
        if not (min_area <= area <= max_area):
            continue

        # Classify using original (unblurred) crop statistics
        crop_gray = gray[y:y+rh, x:x+rw]
        mean      = np.mean(crop_gray)
        std       = np.std(crop_gray)
        dark_frac = np.sum(crop_gray < 128) / crop_gray.size

        if mean < 195 and dark_frac > 0.20:
            kind = "photo"
        elif dark_frac > 0.15 and std > 75:
            kind = "diagram"
        else:
            continue   # text column — skip

        candidates.append({
            'x': x, 'y': y, 'w': rw, 'h': rh, 'kind': kind,
            'mean': mean, 'std': std, 'dark_frac': dark_frac
        })

    # Sort top-to-bottom (reading order)
    candidates.sort(key=lambda r: r['y'])

    os.makedirs(output_dir, exist_ok=True)
    saved = []
    for idx, r in enumerate(candidates, 1):
        x1 = max(0, r['x'] - padding)
        y1 = max(0, r['y'] - padding)
        x2 = min(w, r['x'] + r['w'] + padding)
        y2 = min(h, r['y'] + r['h'] + padding)

        # BGR → RGB for PIL, then rotate if needed
        crop_pil = Image.fromarray(cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2RGB))
        degrees  = photo_rotation if r['kind'] == 'photo' else diagram_rotation
        if degrees:
            crop_pil = crop_pil.rotate(degrees, expand=True)

        fname = f"{page_label}_{r['kind']}_{idx:02d}.jpg"
        fpath = os.path.join(output_dir, fname)
        crop_pil.save(fpath, quality=92)

        saved.append({
            "filename": fname,
            "kind":     r['kind'],
            "width":    crop_pil.width,
            "height":   crop_pil.height,
        })
        logger.info(f"  → {fname}  ({r['w']}×{r['h']}  "
                    f"mean={r['mean']:.0f}  std={r['std']:.0f}  dark={r['dark_frac']:.3f})")

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# STAGE B: Text extraction (Claude Vision)
# ─────────────────────────────────────────────────────────────────────────────

def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def extract_text_from_page(image_path: str) -> str:
    """Transcribe all text from a scanned book page via Claude Vision."""
    logger.info(f"  Claude Vision transcribing: {os.path.basename(image_path)}")

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type":       "base64",
                        "media_type": "image/jpeg",
                        "data":       encode_image_to_base64(image_path),
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
                    )
                }
            ],
        }],
    )
    return message.content[0].text


# ─────────────────────────────────────────────────────────────────────────────
# Metric conversion
# ─────────────────────────────────────────────────────────────────────────────

def convert_to_metric(value: str, original_unit: str) -> Tuple[str, str]:
    FEET_TO_METERS = 0.3048
    INCH_TO_METERS = 0.0254
    SQ_FT_TO_SQ_M  = 0.092903

    numbers = re.findall(r'\d+(?:\.\d+)?', value)
    if not numbers:
        return value, original_unit

    try:
        if "square" in original_unit.lower() or "sq" in original_unit.lower():
            converted = [round(float(n) * SQ_FT_TO_SQ_M, 1) for n in numbers]
            return ("–".join(str(v) for v in converted) if len(converted) > 1
                    else str(converted[0])), "m²"

        elif original_unit.lower() in ["feet", "ft"]:
            converted = [round(float(n) * FEET_TO_METERS, 2) for n in numbers]
            return ("–".join(str(v) for v in converted) if len(converted) > 1
                    else str(converted[0])), "m"

        elif original_unit.lower() in ["inches", "in"]:
            converted = [round(float(n) * INCH_TO_METERS * 100, 1) for n in numbers]
            return ("–".join(str(v) for v in converted) if len(converted) > 1
                    else str(converted[0])), "cm"

        elif original_unit.lower() in ["meters", "m"]:
            return value, "m"

        else:
            return value, original_unit

    except Exception as e:
        logger.warning(f"Conversion failed for {value} {original_unit}: {e}")
        return value, original_unit


# ─────────────────────────────────────────────────────────────────────────────
# Structured data extraction (quantitative + qualitative)
# ─────────────────────────────────────────────────────────────────────────────

def extract_quantitative_rules(text: str) -> List[Dict]:
    rules = []
    range_pattern = (r'(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)'
                     r'\s*(?:feet|ft|meters|m|inches|in|square feet|sq\.?\s*ft)')
    seen = set()

    for match in re.finditer(range_pattern, text, re.IGNORECASE):
        match_text = match.group(0).strip()
        if match_text in seen or len(match_text) < 5:
            continue
        seen.add(match_text)

        numbers = re.findall(r'\d+(?:\.\d+)?', match_text)
        if len(numbers) < 2:
            continue

        original_unit = "other"
        if "feet" in match_text.lower() or "ft" in match_text.lower():
            original_unit = "feet"
        elif "square" in match_text.lower() or "sq" in match_text.lower():
            original_unit = "square feet"
        elif "inch" in match_text.lower() or " in" in match_text.lower():
            original_unit = "inches"
        elif "meter" in match_text.lower():
            original_unit = "meters"

        metric_min, metric_unit = convert_to_metric(numbers[0], original_unit)
        metric_max, _           = convert_to_metric(numbers[1], original_unit)

        try:
            rules.append({
                "metric":     "Dimension/Area measurement",
                "type":       "Range",
                "value_min":  float(metric_min),
                "value_max":  float(metric_max),
                "unit":       metric_unit,
                "condition":  "As stated in text",
                "source_text": match_text,
                "confidence": "high",
            })
        except ValueError:
            continue

    count_pattern = r'(\d+)\s*(?:zones?|rooms?|elements?|pavilions?|stories?|levels?|bedrooms?)'
    for match in re.finditer(count_pattern, text, re.IGNORECASE):
        match_text = match.group(0).strip()
        if match_text in seen:
            continue
        seen.add(match_text)
        numbers = re.findall(r'\d+', match_text)
        if numbers:
            rules.append({
                "metric":     "Count measurement",
                "type":       "Count",
                "value":      int(numbers[0]),
                "unit":       "count",
                "condition":  "As stated in text",
                "source_text": match_text,
                "confidence": "high",
            })

    logger.info(f"Extracted {len(rules)} quantitative rules")
    return rules[:30]


def extract_qualitative_features(text: str) -> List[Dict]:
    category_keywords = {
        'Visual':      ['view', 'light', 'transparent', 'enclosure', 'visibility',
                        'see', 'sight', 'dark', 'bright', 'color', 'outlook'],
        'Spatial':     ['volume', 'proportion', 'open', 'close', 'zone', 'shape',
                        'dimension', 'space', 'layout', 'arrangement', 'pavilion',
                        'courtyard', 'scale'],
        'Social':      ['gather', 'community', 'privacy', 'autonomy', 'social',
                        'people', 'together', 'alone', 'family', 'intimate',
                        'supervise', 'connection'],
        'Atmospheric': ['mood', 'feeling', 'character', 'calm', 'lively',
                        'atmosphere', 'ambiance', 'warmth', 'welcoming', 'refuge'],
        'Haptic':      ['touch', 'texture', 'material', 'warm', 'cool', 'smooth',
                        'rough', 'temperature', 'tactile'],
        'Acoustic':    ['sound', 'noise', 'silence', 'voice', 'hearing', 'acoustic',
                        'echo', 'quiet', 'carry'],
        'Temporal':    ['time', 'day', 'season', 'year', 'change', 'aging',
                        'duration', 'morning', 'evening', 'seasonal'],
        'Political':   ['ownership', 'territory', 'control', 'agency', 'govern',
                        'realm', 'authority', 'power', 'autonomy', 'distinct'],
    }

    features = []
    seen     = set()

    for sentence in re.split(r'[.!?]+', text):
        s = sentence.strip()
        if not s or len(s) < 30 or s in seen:
            continue
        seen.add(s)

        matched = [cat for cat, kws in category_keywords.items()
                   if any(kw in s.lower() for kw in kws)]
        if matched:
            features.append({
                "quality":     s[:150],
                "categories":  matched,
                "source_text": s,
                "confidence":  "high",
            })

    logger.info(f"Extracted {len(features)} qualitative features")
    return features[:30]


# ─────────────────────────────────────────────────────────────────────────────
# File discovery
# ─────────────────────────────────────────────────────────────────────────────

def find_pattern_pages(images_dir: str, pattern_number: int) -> List[str]:
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
        f for f in os.listdir(images_dir)
        if (f.startswith(scan_prefix) or f.startswith(legacy_prefix))
        and f.lower().endswith((".jpg", ".jpeg"))
    ]

    if not matched:
        logger.error(
            f"No files matching '{scan_prefix}*.jpeg' or '{legacy_prefix}*.jpg' in {images_dir}\n"
            f"Files present: {os.listdir(images_dir)}"
        )
        return []

    def sort_key(fname):
        # Works for both "076_Name_1.jpeg" and "pattern_76_1.jpg"
        stem = Path(fname).stem
        try:
            return int(stem.rsplit("_", 1)[-1])
        except ValueError:
            return 0

    return [os.path.join(images_dir, f) for f in sorted(matched, key=sort_key)]


# ─────────────────────────────────────────────────────────────────────────────
# Main processing function
# ─────────────────────────────────────────────────────────────────────────────

def process_pattern(images_dir: str, pattern_name: str, pattern_number: int,
                    output_json: str) -> Dict:
    """
    Process all pages of a pattern.
    For each page JPEG:
      - Detect and save embedded photos/diagrams (scan-extract)
      - Transcribe all text (Claude Vision)
      - Link the two: visuals found on page N are linked to text from page N
    """
    logger.info(f"\nProcessing Pattern {pattern_number}: {pattern_name}")

    page_paths = find_pattern_pages(images_dir, pattern_number)
    if not page_paths:
        return None

    logger.info(f"Found {len(page_paths)} page(s): "
                f"{[os.path.basename(p) for p in page_paths]}")

    # Output folder for cropped visuals lives next to the JSON file
    json_dir      = os.path.dirname(os.path.abspath(output_json))
    name_slug     = pattern_name.replace(" ", "_")
    visuals_dir   = os.path.join(json_dir, "extracted_visuals",
                                 f"{pattern_number:03d}_{name_slug}")
    os.makedirs(visuals_dir, exist_ok=True)

    pages      = []
    all_text   = []
    total_vis  = 0

    for page_idx, page_path in enumerate(page_paths):
        page_num  = page_idx + 1
        page_file = os.path.basename(page_path)
        page_label = f"{pattern_number:03d}_{name_slug}_p{page_num}"

        logger.info(f"\n── Page {page_num}/{len(page_paths)}: {page_file}")

        # A: extract embedded visuals
        logger.info(f"  Detecting photos/diagrams…")
        visuals = detect_visual_regions(page_path, visuals_dir, page_label)
        total_vis += len(visuals)
        if visuals:
            logger.info(f"  Found {len(visuals)} visual(s): "
                        f"{[v['filename'] for v in visuals]}")
        else:
            logger.info(f"  No photos or diagrams detected on this page.")

        # B: transcribe text
        page_text = extract_text_from_page(page_path)
        all_text.append(page_text)

        pages.append({
            "page_num":         page_num,
            "source_file":      page_file,
            "text":             page_text,
            "extracted_visuals": visuals,   # linked by co-location on the same page
        })

    full_text     = "\n\n--- PAGE BREAK ---\n\n".join(all_text)
    quant_rules   = extract_quantitative_rules(full_text)
    qual_features = extract_qualitative_features(full_text)

    output = {
        "pattern_name":   pattern_name,
        "pattern_number": pattern_number,
        "pages":          pages,           # per-page: text + linked visuals
        "full_text":      full_text,
        "full_text_length": len(full_text),
        "quantitative_rules":   quant_rules,
        "qualitative_features": qual_features,
        "execution_log": {
            "pages_processed":      len(page_paths),
            "visuals_extracted":    total_vis,
            "visuals_output_dir":   visuals_dir,
            "extraction_method":    "Claude Vision (text) + OpenCV scan-extract (visuals)",
            "notes": [
                f"Processed {len(page_paths)} pages",
                f"Extracted {len(full_text):,} characters of text",
                f"Extracted {total_vis} photos/diagrams (saved to {visuals_dir})",
                f"Each visual is linked to the page text it appeared on",
                f"Identified {len(quant_rules)} quantitative rules",
                f"Identified {len(qual_features)} qualitative features",
            ],
        },
    }

    with open(output_json, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*70}")
    print(f"EXTRACTION COMPLETE — Pattern {pattern_number}: {pattern_name}")
    print(f"{'='*70}")
    print(f"✓ Pages processed:      {len(page_paths)}")
    print(f"✓ Text extracted:       {len(full_text):,} characters")
    print(f"✓ Visuals extracted:    {total_vis}  →  {visuals_dir}")
    print(f"✓ Quantitative rules:   {len(quant_rules)}")
    print(f"✓ Qualitative features: {len(qual_features)}")
    print(f"✓ Output JSON:          {output_json}")
    print(f"{'='*70}\n")

    return output


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    images_dir     = sys.argv[1]
    pattern_name   = sys.argv[2]
    pattern_number = int(sys.argv[3])
    output_json    = (sys.argv[4] if len(sys.argv) > 4
                      else f"claude_vision_{pattern_number:03d}_output.json")

    result = process_pattern(images_dir, pattern_name, pattern_number, output_json)
    if result:
        print("✅ Pattern extraction successful!")
    else:
        print("❌ Pattern extraction failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
