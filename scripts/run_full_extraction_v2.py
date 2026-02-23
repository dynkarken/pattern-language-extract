#!/usr/bin/env python3
"""
Full extraction pipeline v2: Extract images, OCR text, and structure all data.
Uses pytesseract (already installed) for OCR.
"""

import cv2
import numpy as np
from PIL import Image
import subprocess
import os
import sys
import json
import re
import logging
import pytesseract

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_images_from_pdf(pdf_path, output_dir, pattern_label=None,
                             photo_rotation=270, diagram_rotation=0):
    """Extract visual regions (photos, diagrams) from scanned PDF."""
    os.makedirs(output_dir, exist_ok=True)
    if pattern_label is None:
        pattern_label = os.path.splitext(os.path.basename(pdf_path))[0]

    logger.info(f"Extracting images from {os.path.basename(pdf_path)}")

    # Extract page images from PDF
    pages_dir = os.path.join(output_dir, "_pages_tmp")
    os.makedirs(pages_dir, exist_ok=True)

    try:
        subprocess.run(["pdfimages", "-j", pdf_path,
                        os.path.join(pages_dir, "page")], check=True, capture_output=True)
    except Exception as e:
        logger.error(f"pdfimages failed: {e}")
        return []

    page_files = sorted(f for f in os.listdir(pages_dir) if f.endswith(".jpg"))
    logger.info(f"Extracted {len(page_files)} page(s)")

    all_saved = []
    for i, page_file in enumerate(page_files):
        logger.info(f"Processing page {i+1}/{len(page_files)}")
        saved = detect_visual_regions(
            os.path.join(pages_dir, page_file),
            output_dir, f"{pattern_label}_p{i}",
            photo_rotation=photo_rotation,
            diagram_rotation=diagram_rotation
        )
        all_saved.extend(saved)

    logger.info(f"Extracted {len(all_saved)} images total")
    return all_saved, pages_dir


def detect_visual_regions(img_path, output_dir, page_label, padding=60,
                           photo_rotation=0, diagram_rotation=0):
    """Detect and extract photos/diagrams from a page image."""
    try:
        img = cv2.imread(img_path)
        if img is None:
            logger.warning(f"Could not read {img_path}")
            return []

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (51, 51), 0)
        _, thresh = cv2.threshold(blurred, 220, 255, cv2.THRESH_BINARY_INV)
        kernel = np.ones((60, 60), np.uint8)
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        results = []
        for cnt in contours:
            x, y, rw, rh = cv2.boundingRect(cnt)
            area = rw * rh
            if not (h * w * 0.005 <= area <= h * w * 0.95):
                continue

            crop_gray = gray[y:y+rh, x:x+rw]
            mean = np.mean(crop_gray)
            std = np.std(crop_gray)
            dark_frac = np.sum(crop_gray < 128) / crop_gray.size

            if mean < 195 and dark_frac > 0.20:
                kind = "photo"
            elif dark_frac > 0.15 and std > 75:
                kind = "diagram"
            else:
                continue

            results.append({'x': x, 'y': y, 'w': rw, 'h': rh, 'kind': kind,
                            'mean': mean, 'std': std, 'dark_frac': dark_frac})

        results.sort(key=lambda r: r['y'])

        saved = []
        for idx, r in enumerate(results, 1):
            x1 = max(0, r['x'] - padding)
            y1 = max(0, r['y'] - padding)
            x2 = min(w, r['x'] + r['w'] + padding)
            y2 = min(h, r['y'] + r['h'] + padding)

            crop_pil = Image.fromarray(cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2RGB))
            degrees = photo_rotation if r['kind'] == 'photo' else diagram_rotation
            if degrees:
                crop_pil = crop_pil.rotate(degrees, expand=True)

            fname = f"{page_label}_{r['kind']}_{idx:02d}.jpg"
            crop_pil.save(os.path.join(output_dir, fname), quality=92)
            saved.append({'filename': fname, 'kind': r['kind'], 'width': r['w'], 'height': r['h']})
            logger.info(f"  → {fname}  ({r['w']}x{r['h']}  mean={r['mean']:.0f}  std={r['std']:.0f})")

        return saved
    except Exception as e:
        logger.error(f"Region detection failed: {e}")
        return []


def extract_text_from_pages(pages_dir):
    """OCR text from page images in a directory."""
    logger.info("Performing OCR on page images")
    text_parts = []
    confidences = []

    page_files = sorted(f for f in os.listdir(pages_dir)
                       if f.startswith("page-") and f.endswith(".jpg"))

    for page_idx, page_file in enumerate(page_files):
        logger.info(f"  OCR page {page_idx + 1}/{len(page_files)}")
        try:
            img = Image.open(os.path.join(pages_dir, page_file))
            text = pytesseract.image_to_string(img, lang='eng')
            text_parts.append(text)

            # Get OCR confidence data
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data['confidence'] if int(c) > 0]
            if confs:
                page_confidence = sum(confs) / len(confs) / 100.0
                confidences.append(page_confidence)
                logger.info(f"    → OCR confidence: {page_confidence:.1%}")
        except Exception as e:
            logger.warning(f"OCR failed on {page_file}: {e}")

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(text_parts)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    logger.info(f"OCR complete: {len(full_text)} characters, {avg_confidence:.1%} confidence")
    return full_text, avg_confidence


def extract_quantitative_rules(text):
    """Extract quantitative rules from text."""
    logger.info("Extracting quantitative rules")

    # More comprehensive patterns
    patterns = {
        'dimension': [
            r'(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meters|m|inches|in)',
            r'(?:width|height|depth|size|length|diameter)\s*(?:of|is|are)?\s*(?:about|approximately|roughly)?\s*(\d+(?:\.\d+)?)\s*(?:feet|ft|meters|m)',
        ],
        'threshold': [
            r'(?:never|no|not|maximum|minimum|at least|no more than|not more than|not less than)\s+(?:more|less|greater|fewer)?\s*than\s+(\d+(?:\.\d+)?)\s*(?:feet|ft|meters|m)',
            r'(?:at least|minimum of|maximum of)\s+(\d+(?:\.\d+)?)\s*(?:feet|ft|meters|m)',
        ],
        'ratio': [
            r'(?:ratio|proportion|relationship).*?(\d+)\s*(?:to|:)\s*(\d+)',
            r'(\d+)\s*(?:to|:)\s*(\d+)\s*ratio',
        ],
        'area': [
            r'(?:area|square|sq\.?)\s*(?:feet|ft|meters|m)?.*?(\d+(?:\.\d+)?)\s*(?:sq\.?\s*(?:feet|ft|meters|m))?',
        ],
    }

    rules = []
    seen = set()

    for rule_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                key = match.group(0)
                if key in seen or len(key) < 5:
                    continue
                seen.add(key)

                rules.append({
                    "metric": f"{rule_type.capitalize()} measurement",
                    "value": match.group(0),
                    "unit": "feet" if "feet" in match.group(0).lower() else "meters" if "meter" in match.group(0).lower() else "other",
                    "type": rule_type.capitalize(),
                    "condition": "As stated in text",
                    "source_text": match.group(0),
                    "confidence": "medium"
                })

    logger.info(f"Extracted {len(rules)} quantitative rules")
    return rules[:20]  # Top 20


def extract_qualitative_features(text):
    """Extract qualitative features from text."""
    logger.info("Extracting qualitative features")

    category_keywords = {
        'Visual': ['view', 'light', 'transparent', 'enclosure', 'visibility', 'see', 'sight', 'dark', 'bright', 'color', 'pattern'],
        'Spatial': ['volume', 'proportion', 'open', 'close', 'zone', 'shape', 'dimension', 'space', 'layout', 'arrangement'],
        'Social': ['gather', 'community', 'privacy', 'autonomy', 'social', 'people', 'together', 'alone', 'family', 'intimate'],
        'Atmospheric': ['mood', 'feeling', 'character', 'intimate', 'calm', 'lively', 'atmosphere', 'ambiance', 'warmth', 'welcoming'],
        'Haptic': ['touch', 'texture', 'material', 'warm', 'cool', 'smooth', 'rough', 'temperature', 'tactile'],
        'Acoustic': ['sound', 'noise', 'silence', 'voice', 'hearing', 'acoustic', 'echo', 'quiet', 'sound'],
        'Temporal': ['time', 'day', 'season', 'year', 'change', 'aging', 'duration', 'morning', 'evening', 'seasonal'],
        'Political': ['ownership', 'territory', 'control', 'agency', 'govern', 'realm', 'authority', 'power', 'autonomy'],
    }

    features = []
    sentences = re.split(r'[.!?]+', text)

    for sentence in sentences:
        sentence_lower = sentence.lower().strip()
        if not sentence_lower or len(sentence_lower) < 25:
            continue

        matched_categories = []
        for category, keywords in category_keywords.items():
            if any(keyword in sentence_lower for keyword in keywords):
                matched_categories.append(category)

        if matched_categories and len(matched_categories) >= 1:
            features.append({
                "quality": sentence.strip()[:150],
                "categories": matched_categories,
                "source_text": sentence.strip(),
                "confidence": "medium"
            })

    # Remove duplicates and limit
    seen = set()
    unique = []
    for feat in features:
        key = feat['quality']
        if key not in seen:
            seen.add(key)
            unique.append(feat)

    result = unique[:25]
    logger.info(f"Extracted {len(result)} qualitative features")
    return result


def main():
    if len(sys.argv) < 4:
        print("Usage: run_full_extraction_v2.py <pdf_path> <pattern_name> <pattern_number> [output_json]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    pattern_name = sys.argv[2]
    pattern_number = int(sys.argv[3])
    output_json = sys.argv[4] if len(sys.argv) > 4 else "extraction_output.json"

    logger.info(f"Starting extraction for Pattern {pattern_number}: {pattern_name}")

    # Step 1: Extract images from PDF
    images_dir = os.path.join(os.path.dirname(output_json), "extracted_images")
    extracted_images, pages_dir = extract_images_from_pdf(
        pdf_path, images_dir,
        f"{pattern_number}_{pattern_name.replace(' ', '_')}"
    )

    # Step 2: Extract text from page images via OCR
    full_text, ocr_confidence = extract_text_from_pages(pages_dir)

    # Step 3: Extract quantitative rules
    quant_rules = extract_quantitative_rules(full_text)

    # Step 4: Extract qualitative features
    qual_features = extract_qualitative_features(full_text)

    # Build output
    output = {
        "pattern_name": pattern_name,
        "pattern_number": pattern_number,
        "transcribed_text_with_images": full_text[:4000] + "..." if len(full_text) > 4000 else full_text,
        "full_text_length": len(full_text),
        "extracted_images": extracted_images,
        "quantitative_rules": quant_rules,
        "qualitative_features": qual_features,
        "execution_log": {
            "images_extracted": len(extracted_images),
            "pages_processed": len([f for f in os.listdir(pages_dir) if f.startswith("page-") and f.endswith(".jpg")]),
            "ocr_confidence": ocr_confidence,
            "text_extracted": len(full_text) > 0,
            "notes": [
                f"Successfully extracted {len(full_text)} characters of text",
                f"Identified {len(quant_rules)} quantitative rules",
                f"Identified {len(qual_features)} qualitative features"
            ]
        }
    }

    # Save to JSON
    with open(output_json, 'w') as f:
        json.dump(output, f, indent=2)

    logger.info(f"✓ Extraction complete: {output_json}")
    print(f"\n{'='*60}")
    print(f"EXTRACTION RESULTS - Pattern {pattern_number}: {pattern_name}")
    print(f"{'='*60}")
    print(f"✓ Images extracted:        {output['execution_log']['images_extracted']}")
    print(f"✓ Pages processed:         {output['execution_log']['pages_processed']}")
    print(f"✓ Text extracted:          {len(full_text):,} characters")
    print(f"✓ OCR confidence:          {ocr_confidence:.1%}")
    print(f"✓ Quantitative rules:      {len(quant_rules)}")
    print(f"✓ Qualitative features:    {len(qual_features)}")
    print(f"✓ Output file:             {output_json}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
