#!/usr/bin/env python3
"""
Unified Pattern Language Extraction Pipeline
Extracts text, visuals, and structured data from scanned JPEG pages and uploads to Notion.

Input:
    A folder containing JPEG scans named:
        pattern_76_1.jpg
        pattern_76_2.jpg
        pattern_76_3.jpg  ... etc.

Usage:
    python scripts/unified_pipeline.py <images_dir> <pattern_name> <pattern_number>

Example:
    python scripts/unified_pipeline.py ./scans "House for a Small Family" 76

Stages:
    1. Extraction — for each page JPEG:
         a. Detect and crop embedded photos/diagrams (OpenCV scan-extract)
         b. Transcribe all text via Claude Vision (99%+ accuracy on 1970s typography)
         c. Extract quantitative rules (metric units, value_min/value_max) and
            qualitative features from the full text
         All outputs linked by page: visuals ↔ text co-located on the same page
    2. Upload to Notion:
         - Pattern page with embedded 'Extracted Visuals' section listing photos/diagrams
         - Quantitative Rules database (one row per rule, numeric value_min/value_max)
         - Qualitative Features database (one row per feature, multi-select categories)

Environment variables required:
    NOTION_API_KEY
    NOTION_PATTERNS_DB_ID
    NOTION_QUANT_RULES_DB_ID
    NOTION_QUAL_FEATURES_DB_ID
"""

import json
import os
import sys
import logging
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedPipeline:
    def __init__(self, images_dir: str, pattern_name: str, pattern_number: int):
        self.images_dir = Path(images_dir).resolve()
        self.pattern_name = pattern_name
        self.pattern_number = pattern_number
        self.script_dir = Path(__file__).parent
        self.project_dir = self.script_dir.parent

        # Output JSON path
        self.output_json = self.project_dir / f"claude_vision_{pattern_number:03d}_output.json"

        # Validate inputs
        if not self.images_dir.exists():
            raise FileNotFoundError(f"Images folder not found: {images_dir}")

        # Check that at least one matching JPEG exists (scan or legacy naming)
        scan_prefix   = f"{pattern_number:03d}_"
        legacy_prefix = f"pattern_{pattern_number}_"
        matching = [
            f for f in self.images_dir.iterdir()
            if (f.name.startswith(scan_prefix) or f.name.startswith(legacy_prefix))
            and f.suffix.lower() in (".jpg", ".jpeg")
        ]
        if not matching:
            raise FileNotFoundError(
                f"No files matching '{scan_prefix}*.jpeg' or '{legacy_prefix}*.jpg' "
                f"found in: {images_dir}\n"
                f"Files found: {[f.name for f in self.images_dir.iterdir()]}"
            )

        logger.info(f"\n{'='*70}")
        logger.info(f"UNIFIED PIPELINE — Pattern {pattern_number}: {pattern_name}")
        logger.info(f"Images folder:  {self.images_dir}")
        logger.info(f"Pages found:    {len(matching)}")
        logger.info(f"Output JSON:    {self.output_json}")
        logger.info(f"{'='*70}\n")

    def stage_extract(self) -> str:
        """Stage 1: Extract text, visuals, and structured data from JPEGs."""
        logger.info("── STAGE 1: Extracting text + visuals from scanned pages "
                    "(OpenCV scan-extract + Claude Vision)")

        extraction_script = self.script_dir / "claude_vision_extraction.py"
        cmd = [
            "python", str(extraction_script),
            str(self.images_dir),
            self.pattern_name,
            str(self.pattern_number),
            str(self.output_json)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            logger.info(result.stdout.strip())
        if result.stderr:
            logger.warning(result.stderr.strip())

        if result.returncode != 0:
            raise RuntimeError(f"Text extraction failed (exit code {result.returncode})")

        if not self.output_json.exists():
            raise FileNotFoundError(f"Extraction completed but output file not found: {self.output_json}")

        logger.info(f"✅ Stage 1 complete — JSON saved to: {self.output_json}")
        return str(self.output_json)

    def stage_upload(self, json_path: str):
        """Stage 2: Upload extracted JSON (text, visuals, rules, features) to Notion."""
        logger.info("── STAGE 2: Uploading to Notion (patterns, visuals, rules, features)")

        # Check environment variables
        required_vars = [
            "NOTION_API_KEY",
            "NOTION_PATTERNS_DB_ID",
            "NOTION_QUANT_RULES_DB_ID",
            "NOTION_QUAL_FEATURES_DB_ID"
        ]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            raise EnvironmentError(
                f"Missing environment variables: {', '.join(missing)}\n"
                f"See NOTION_SETUP_GUIDE.md for instructions."
            )

        uploader_script = self.script_dir / "notion_uploader.py"
        cmd = ["python", str(uploader_script), json_path]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            logger.info(result.stdout.strip())
        if result.stderr:
            logger.warning(result.stderr.strip())

        if result.returncode != 0:
            raise RuntimeError(f"Notion upload failed (exit code {result.returncode})")

        logger.info("✅ Stage 2 complete — data uploaded to Notion")

    def run(self):
        """Run full pipeline: extract → upload."""
        try:
            json_path = self.stage_extract()
            self.stage_upload(json_path)

            # Print final summary from JSON
            with open(json_path) as f:
                data = json.load(f)

            n_quant   = len(data.get("quantitative_rules", []))
            n_qual    = len(data.get("qualitative_features", []))
            n_chars   = data.get("full_text_length", 0)
            pages     = data.get("pages", [])
            n_visuals = sum(len(p.get("extracted_visuals", [])) for p in pages)
            vis_dir   = data.get("execution_log", {}).get("visuals_output_dir", "")

            logger.info(f"\n{'='*70}")
            logger.info(f"✅  PIPELINE COMPLETE")
            logger.info(f"{'='*70}")
            logger.info(f"Pattern:               {self.pattern_name} (#{self.pattern_number})")
            logger.info(f"Pages processed:       {len(pages)}")
            logger.info(f"Text extracted:        {n_chars:,} characters")
            logger.info(f"Visuals extracted:     {n_visuals}  →  {vis_dir}")
            logger.info(f"Quantitative rules:    {n_quant}")
            logger.info(f"Qualitative features:  {n_qual}")
            logger.info(f"Notion entries:        {n_quant + n_qual + 1} (pattern + rules + features)")
            logger.info(f"JSON output:           {self.output_json}")
            logger.info(f"{'='*70}\n")

        except Exception as e:
            logger.error(f"\n{'='*70}")
            logger.error(f"❌  PIPELINE FAILED: {e}")
            logger.error(f"{'='*70}\n")
            raise


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    images_dir    = sys.argv[1]
    pattern_name  = sys.argv[2]
    pattern_number = int(sys.argv[3])

    try:
        pipeline = UnifiedPipeline(images_dir, pattern_name, pattern_number)
        pipeline.run()
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
