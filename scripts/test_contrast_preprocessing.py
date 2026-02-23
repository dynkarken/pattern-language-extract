#!/usr/bin/env python3
"""
Test OCR improvement from contrast preprocessing.
Compares OCR output before and after applying high-contrast black & white conversion.
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance
import pytesseract
import os
import json

def preprocess_scan(image_path, contrast_boost=2.0, brightness_offset=0):
    """
    Apply contrast and brightness preprocessing to improve OCR.

    Args:
        image_path: Path to original scan
        contrast_boost: Contrast multiplier (1.0 = no change, 2.0 = double contrast)
        brightness_offset: Brightness adjustment (-100 to +100)
    """
    img = Image.open(image_path).convert('L')  # Convert to grayscale

    # Apply contrast enhancement
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast_boost)

    # Apply brightness adjustment if needed
    if brightness_offset != 0:
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1 + brightness_offset / 100.0)

    # Convert to numpy for threshold
    img_array = np.array(img)

    # Apply aggressive thresholding to get pure black and white
    _, binary = cv2.threshold(img_array, 150, 255, cv2.THRESH_BINARY)

    return Image.fromarray(binary)


def extract_text_with_confidence(image):
    """Extract text and return both text and confidence metrics."""
    text = pytesseract.image_to_string(image)

    # Try to get confidence data (may not be available in all pytesseract versions)
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        # Try different possible keys for confidence
        if 'conf' in data:
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
        elif 'confidence' in data:
            confidences = [int(c) for c in data['confidence'] if int(c) > 0]
        else:
            # Fallback: no confidence data available
            confidences = []
    except:
        confidences = []

    avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
    words_detected = len([c for c in confidences if c > 50]) if confidences else len(text.split())

    return {
        'text': text,
        'avg_confidence': avg_confidence,
        'words_detected': words_detected,
        'text_length': len(text),
        'sample_text': text[:500]
    }


def main():
    # Find one of the extracted page images from Pattern 76
    pages_dir = "/sessions/brave-happy-cori/mnt/Projects/pattern-language-extract/extracted_images/_pages_tmp"

    if not os.path.exists(pages_dir):
        print("Error: extracted pages directory not found")
        print(f"Expected at: {pages_dir}")
        return

    page_files = sorted([f for f in os.listdir(pages_dir) if f.endswith('.jpg')])

    if not page_files:
        print("No page images found to test")
        return

    # Test with the first page
    test_page = os.path.join(pages_dir, page_files[0])
    print(f"\n{'='*70}")
    print(f"OCR Preprocessing Test: Contrast Enhancement Impact")
    print(f"{'='*70}")
    print(f"Test image: {page_files[0]}")
    print(f"File size: {os.path.getsize(test_page) / (1024*1024):.1f} MB\n")

    # Original OCR
    print("1. ORIGINAL IMAGE (as-is)")
    print("-" * 70)
    original_img = Image.open(test_page)
    original_results = extract_text_with_confidence(original_img)
    print(f"Average confidence: {original_results['avg_confidence']:.1%}")
    print(f"Words detected (>50% confidence): {original_results['words_detected']}")
    print(f"Sample text:\n{original_results['sample_text']}\n")

    # Preprocessed OCR - Moderate contrast boost
    print("2. PREPROCESSED (Moderate: 1.5x contrast)")
    print("-" * 70)
    preprocessed_moderate = preprocess_scan(test_page, contrast_boost=1.5)
    moderate_results = extract_text_with_confidence(preprocessed_moderate)
    print(f"Average confidence: {moderate_results['avg_confidence']:.1%}")
    print(f"Words detected (>50% confidence): {moderate_results['words_detected']}")
    print(f"Sample text:\n{moderate_results['sample_text']}\n")

    # Preprocessed OCR - Aggressive contrast boost
    print("3. PREPROCESSED (Aggressive: 2.5x contrast + threshold)")
    print("-" * 70)
    preprocessed_aggressive = preprocess_scan(test_page, contrast_boost=2.5)
    aggressive_results = extract_text_with_confidence(preprocessed_aggressive)
    print(f"Average confidence: {aggressive_results['avg_confidence']:.1%}")
    print(f"Words detected (>50% confidence): {aggressive_results['words_detected']}")
    print(f"Sample text:\n{aggressive_results['sample_text']}\n")

    # Comparison
    print("="*70)
    print("COMPARISON & RECOMMENDATIONS")
    print("="*70)

    improvement_mod = ((moderate_results['avg_confidence'] - original_results['avg_confidence']) /
                       (original_results['avg_confidence'] + 0.001) * 100)
    improvement_agg = ((aggressive_results['avg_confidence'] - original_results['avg_confidence']) /
                       (original_results['avg_confidence'] + 0.001) * 100)

    print(f"\nConfidence improvement:")
    print(f"  Moderate contrast:   {improvement_mod:+.1f}%")
    print(f"  Aggressive contrast: {improvement_agg:+.1f}%")

    # Save preprocessed images for visual comparison
    preprocessed_moderate.save("/sessions/brave-happy-cori/mnt/Projects/pattern-language-extract/test_preprocessed_moderate.jpg", quality=95)
    preprocessed_aggressive.save("/sessions/brave-happy-cori/mnt/Projects/pattern-language-extract/test_preprocessed_aggressive.jpg", quality=95)

    print(f"\nPreprocessed test images saved:")
    print(f"  • test_preprocessed_moderate.jpg")
    print(f"  • test_preprocessed_aggressive.jpg")

    print("\n" + "="*70)
    if improvement_agg >= 15:
        print("✅ RECOMMENDATION: Re-scanning with high contrast would help significantly!")
        print("   Preprocessing improved OCR confidence by {:.0f}%.".format(improvement_agg))
        print("   Re-scan with 300 DPI + high contrast B&W conversion.")
    elif improvement_agg >= 5:
        print("⚠️  RECOMMENDATION: Moderate improvement. May be worth it.")
        print("   Preprocessing improved OCR confidence by {:.0f}%.".format(improvement_agg))
        print("   Re-scan selectively for problematic pages.")
    else:
        print("❌ RECOMMENDATION: Not worth re-scanning. Improvement is minimal.")
        print("   Stick with hybrid workflow (type text, use automatic extractors).")
        print("   Better ROI than chasing OCR optimization.")
    print("="*70 + "\n")

    # Save results
    results = {
        "test_image": page_files[0],
        "original": original_results,
        "preprocessed_moderate": moderate_results,
        "preprocessed_aggressive": aggressive_results,
        "improvements": {
            "moderate_improvement_pct": improvement_mod,
            "aggressive_improvement_pct": improvement_agg
        }
    }

    with open("/sessions/brave-happy-cori/mnt/Projects/pattern-language-extract/preprocessing_test_results.json", 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
