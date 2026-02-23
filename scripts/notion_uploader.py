#!/usr/bin/env python3
"""
Notion Uploader for Pattern Language Extraction Pipeline
Reads extracted pattern JSON and uploads to Notion database.

JSON structure (new — with per-page visuals):
  {
    "pattern_name": "House for a Small Family",
    "pattern_number": 76,
    "pages": [
      {
        "page_num": 1,
        "source_file": "pattern_76_1.jpg",
        "text": "...",
        "extracted_visuals": [
          {"filename": "076_House_for_a_Small_Family_p1_photo_01.jpg",
           "kind": "photo", "width": 1200, "height": 900}
        ]
      },
      ...
    ],
    "full_text": "...",
    "quantitative_rules": [...],
    "qualitative_features": [...]
  }

What gets uploaded to Notion:
  - Pattern page:         title, number, status, extracted visuals listed as content blocks
  - Quantitative Rules:   one row per rule (value_min/max as numbers, unit, condition, etc.)
  - Qualitative Features: one row per feature (quality text, categories, confidence)

Requirements:
  NOTION_API_KEY            — your Notion integration token
  NOTION_PATTERNS_DB_ID     — Patterns database ID
  NOTION_QUANT_RULES_DB_ID  — Quantitative Rules database ID
  NOTION_QUAL_FEATURES_DB_ID — Qualitative Features database ID

Setup:
  1. Create a Notion integration at https://www.notion.so/my-integrations
  2. Copy your API token to NOTION_API_KEY environment variable
  3. Create three Notion databases with fields as documented in QUANTITATIVE_RULES_SCHEMA.md
  4. Share each database with your integration
  5. Copy database IDs to the environment variables above
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional
import requests


def _load_dotenv():
    """Load .env from project root if present."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

_load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Notion API configuration
NOTION_API_VERSION = "2022-06-28"
NOTION_API_URL = "https://api.notion.com/v1"


class NotionUploader:
    def __init__(self, api_key: str, patterns_db_id: str,
                 quant_rules_db_id: str, qual_features_db_id: str):
        """Initialize Notion uploader with database IDs and API token."""
        self.api_key = api_key
        self.patterns_db_id = patterns_db_id
        self.quant_rules_db_id = quant_rules_db_id
        self.qual_features_db_id = qual_features_db_id

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Notion API."""
        url = f"{NOTION_API_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # Notion block builders for visuals section
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _text(content: str, bold: bool = False) -> Dict:
        """Build a Notion rich_text text object."""
        rt = {"type": "text", "text": {"content": content}}
        if bold:
            rt["annotations"] = {"bold": True}
        return rt

    @staticmethod
    def _heading2(content: str) -> Dict:
        return {
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": content}}]
            }
        }

    @staticmethod
    def _heading3(content: str) -> Dict:
        return {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": content}}]
            }
        }

    @staticmethod
    def _paragraph(rich_text: List[Dict]) -> Dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": rich_text}
        }

    @staticmethod
    def _divider() -> Dict:
        return {"object": "block", "type": "divider", "divider": {}}

    def _build_visuals_blocks(self, pages: List[Dict]) -> List[Dict]:
        """
        Build Notion content blocks for the 'Extracted Visuals' section.
        Groups visuals by page number. Returns an empty list if no visuals found.
        """
        # Gather pages that actually have visuals
        pages_with_visuals = [p for p in pages if p.get("extracted_visuals")]
        if not pages_with_visuals:
            return []

        total = sum(len(p["extracted_visuals"]) for p in pages_with_visuals)
        blocks = [
            self._divider(),
            self._heading2("Extracted Visuals"),
            self._paragraph([
                self._text(
                    f"{total} visual(s) extracted across "
                    f"{len(pages_with_visuals)} page(s)"
                )
            ]),
        ]

        for page in pages_with_visuals:
            page_num = page["page_num"]
            visuals  = page["extracted_visuals"]
            source   = page.get("source_file", f"page {page_num}")

            blocks.append(self._heading3(f"Page {page_num}  ({source})"))

            for v in visuals:
                kind   = v.get("kind", "?").capitalize()
                fname  = v.get("filename", "?")
                w      = v.get("width", "?")
                h      = v.get("height", "?")
                blocks.append(
                    self._paragraph([
                        self._text(f"{kind}: ", bold=True),
                        self._text(f"{fname}  ({w} × {h} px)"),
                    ])
                )

        return blocks

    # ─────────────────────────────────────────────────────────────────────────
    # Pattern page
    # ─────────────────────────────────────────────────────────────────────────

    def _find_or_create_pattern_page(self, pattern_name: str, pattern_number: int,
                                      children: Optional[List[Dict]] = None) -> str:
        """
        Find existing pattern page or create a new one.
        If creating, optionally add content blocks (e.g. visuals section).
        Returns page ID.
        """
        # Search for existing page by pattern number
        query_data = {
            "filter": {
                "property": "Pattern #",
                "number": {"equals": pattern_number}
            }
        }
        try:
            result = self._request("POST", f"/databases/{self.patterns_db_id}/query", query_data)
            if result.get("results"):
                page_id = result["results"][0]["id"]
                logger.info(f"Found existing pattern page: {page_id}")
                # Append visuals blocks to existing page if provided
                if children:
                    self._append_blocks(page_id, children)
                return page_id
        except Exception as e:
            logger.warning(f"Could not search for existing pattern: {e}")

        # Create new pattern page, including visuals content if provided
        page_data = {
            "parent": {"database_id": self.patterns_db_id},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": pattern_name}}]
                },
                "Pattern #": {
                    "number": pattern_number
                },
                "Source": {
                    "select": {"name": "A Pattern Language"}
                }
            }
        }
        if children:
            page_data["children"] = children

        result = self._request("POST", "/pages", page_data)
        page_id = result["id"]
        logger.info(f"Created new pattern page: {page_id}")
        return page_id

    def _append_blocks(self, page_id: str, blocks: List[Dict]) -> None:
        """Append content blocks to an existing Notion page."""
        # Notion accepts max 100 blocks per request
        for i in range(0, len(blocks), 100):
            batch = blocks[i:i + 100]
            self._request("PATCH", f"/blocks/{page_id}/children", {"children": batch})
        logger.info(f"  Appended {len(blocks)} content block(s) to page {page_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # Quantitative rule
    # ─────────────────────────────────────────────────────────────────────────

    # Unit names as they appear in the Notion database select options
    _UNIT_MAP = {
        "m":      "meters",
        "m²":     "other",
        "cm":     "other",
        "feet":   "feet",
        "ft":     "feet",
        "count":  "other",
        "meters": "meters",
        "ratio":  "ratio",
        "zones":  "zones",
        "degrees": "degrees",
        "percent": "percent",
        "stories": "stories",
    }

    def _format_value(self, rule: Dict) -> str:
        """Format rule value as a display string."""
        if rule["type"] == "Range":
            return f"{rule['value_min']}–{rule['value_max']}"
        elif rule["type"] in ("Count", "Threshold"):
            return str(rule.get("value", ""))
        else:
            return rule.get("source_text", "")[:100]

    def upload_quantitative_rule(self, rule: Dict, pattern_page_id: str) -> str:
        """Upload a quantitative rule to Notion. Returns entry ID."""
        unit_raw = rule.get("unit", "other")
        unit = self._UNIT_MAP.get(unit_raw, "other")
        value_str = self._format_value(rule)

        properties = {
            "Metric": {
                "title": [{"text": {"content": rule["metric"]}}]
            },
            "Value": {
                "rich_text": [{"text": {"content": value_str}}]
            },
            "Type": {
                "select": {"name": rule["type"]}
            },
            "Unit": {
                "select": {"name": unit}
            },
            "Condition": {
                "rich_text": [{"text": {"content": rule.get("condition", "")}}]
            },
            "Pattern": {
                "relation": [{"id": pattern_page_id}]
            }
        }

        result = self._request("POST", "/pages", {
            "parent": {"database_id": self.quant_rules_db_id},
            "properties": properties
        })
        logger.info(f"  ✓ Quantitative rule: {rule['metric']}  ({value_str} {unit})")
        return result["id"]

    # ─────────────────────────────────────────────────────────────────────────
    # Qualitative feature
    # ─────────────────────────────────────────────────────────────────────────

    def upload_qualitative_feature(self, feature: Dict, pattern_page_id: str) -> str:
        """Upload a qualitative feature to Notion. Returns entry ID."""
        properties = {
            "Quality": {
                "title": [{"text": {"content": feature["quality"][:100]}}]
            },
            "Category": {
                "multi_select": [{"name": cat} for cat in feature.get("categories", [])]
            },
            "Pattern": {
                "relation": [{"id": pattern_page_id}]
            }
        }

        result = self._request("POST", "/pages", {
            "parent": {"database_id": self.qual_features_db_id},
            "properties": properties
        })
        logger.info(f"  ✓ Qualitative feature: {feature['quality'][:80]}")
        return result["id"]

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────

    def upload_pattern(self, json_file: str) -> Dict:
        """Upload complete pattern from JSON file to Notion."""
        with open(json_file, 'r') as f:
            data = json.load(f)

        pattern_name   = data["pattern_name"]
        pattern_number = data["pattern_number"]
        pages          = data.get("pages", [])

        logger.info(f"\n{'='*70}")
        logger.info(f"UPLOADING PATTERN {pattern_number}: {pattern_name}")
        logger.info(f"{'='*70}")

        # Count visuals across all pages
        total_visuals = sum(len(p.get("extracted_visuals", [])) for p in pages)
        if total_visuals:
            logger.info(f"Visuals to record in Notion: {total_visuals}")

        # Build visuals content blocks (empty list if none)
        visuals_blocks = self._build_visuals_blocks(pages)

        # Create or find pattern page — pass visuals blocks to embed on creation
        pattern_page_id = self._find_or_create_pattern_page(
            pattern_name, pattern_number, children=visuals_blocks or None
        )

        # Upload quantitative rules
        quant_rule_ids = []
        for rule in data.get("quantitative_rules", []):
            try:
                rule_id = self.upload_quantitative_rule(rule, pattern_page_id)
                quant_rule_ids.append(rule_id)
            except Exception as e:
                logger.error(f"  ✗ Failed to upload rule '{rule['metric']}': {e}")

        # Upload qualitative features
        qual_feature_ids = []
        for feature in data.get("qualitative_features", []):
            try:
                feature_id = self.upload_qualitative_feature(feature, pattern_page_id)
                qual_feature_ids.append(feature_id)
            except Exception as e:
                logger.error(f"  ✗ Failed to upload feature: {e}")

        result = {
            "pattern_id":                    pattern_page_id,
            "pattern_name":                  pattern_name,
            "pattern_number":                pattern_number,
            "quantitative_rules_uploaded":   len(quant_rule_ids),
            "qualitative_features_uploaded": len(qual_feature_ids),
            "visuals_recorded":              total_visuals,
            "total_uploaded":                len(quant_rule_ids) + len(qual_feature_ids),
        }

        logger.info(f"\n{'='*70}")
        logger.info(f"✅ UPLOAD COMPLETE")
        logger.info(f"{'='*70}")
        logger.info(f"Pattern ID:                  {pattern_page_id}")
        logger.info(f"Quantitative rules:          {len(quant_rule_ids)}")
        logger.info(f"Qualitative features:        {len(qual_feature_ids)}")
        logger.info(f"Visuals recorded in page:    {total_visuals}")
        logger.info(f"Total DB entries created:    {result['total_uploaded']}")
        logger.info(f"{'='*70}\n")

        return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    api_key            = os.getenv("NOTION_API_KEY")
    patterns_db_id     = os.getenv("NOTION_PATTERNS_DB_ID")
    quant_rules_db_id  = os.getenv("NOTION_QUANT_RULES_DB_ID")
    qual_features_db_id = os.getenv("NOTION_QUAL_FEATURES_DB_ID")

    if not all([api_key, patterns_db_id, quant_rules_db_id, qual_features_db_id]):
        print("Error: Missing environment variables:")
        print("  NOTION_API_KEY")
        print("  NOTION_PATTERNS_DB_ID")
        print("  NOTION_QUANT_RULES_DB_ID")
        print("  NOTION_QUAL_FEATURES_DB_ID")
        print("\nSee NOTION_SETUP_GUIDE.md for setup instructions.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: notion_uploader.py <json_file>")
        print("Example: notion_uploader.py claude_vision_076_output.json")
        sys.exit(1)

    json_file = sys.argv[1]
    if not os.path.exists(json_file):
        print(f"Error: File not found: {json_file}")
        sys.exit(1)

    uploader = NotionUploader(api_key, patterns_db_id, quant_rules_db_id, qual_features_db_id)
    result = uploader.upload_pattern(json_file)
    print(f"✅ Successfully uploaded Pattern {result['pattern_number']}: {result['pattern_name']}")


if __name__ == "__main__":
    main()
