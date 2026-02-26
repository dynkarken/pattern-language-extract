#!/usr/bin/env python3
"""
Notion upload — reads a reviewed _knowledge.json, uploads to 5 Notion databases.

Usage:
  python scripts/upload.py <pattern_number>_knowledge.json

Required environment variables (in .env at project root):
  NOTION_API_KEY             — Notion integration token
  NOTION_PATTERNS_DB_ID      — Patterns database ID
  NOTION_FORCES_DB_ID        — Forces database ID
  NOTION_TYPED_RULES_DB_ID   — Typed Rules database ID
  NOTION_FAILURE_MODES_DB_ID — Failure Modes database ID
  NOTION_RELATIONSHIPS_DB_ID — Pattern Relationships database ID

Idempotent: checks if the pattern already exists (by Pattern # field) before creating.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# Load .env from project root
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
BASE_URL       = "https://api.notion.com/v1"


class NotionClient:
    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _req(self, method: str, path: str, **kwargs) -> dict:
        url = f"{BASE_URL}{path}"
        resp = requests.request(method, url, headers=self.headers, **kwargs)
        if not resp.ok:
            logger.error(f"Notion API error {resp.status_code}: {resp.text[:400]}")
            resp.raise_for_status()
        return resp.json()

    def query_db(self, db_id: str, filter_body: dict) -> list[dict]:
        result = self._req("POST", f"/databases/{db_id}/query",
                           json={"filter": filter_body})
        return result.get("results", [])

    def create_page(self, parent_db_id: str, properties: dict,
                    children: list | None = None) -> dict:
        body = {
            "parent": {"database_id": parent_db_id},
            "properties": properties,
        }
        if children:
            body["children"] = children
        return self._req("POST", "/pages", json=body)

    def update_page(self, page_id: str, properties: dict) -> dict:
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": properties})


# ─── Property builders ───────────────────────────────────────────────────────

def title_prop(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}

def rich_text_prop(text: str) -> dict:
    if not text:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": str(text)[:2000]}}]}

def number_prop(value) -> dict:
    return {"number": float(value) if value is not None else None}

def select_prop(value: str) -> dict:
    return {"select": {"name": str(value)} if value else None}

def relation_prop(page_ids: list[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids]}


# ─── Upload functions ─────────────────────────────────────────────────────────

def find_existing_pattern(client: NotionClient, db_id: str, pattern_number: int) -> Optional[str]:
    """Return the Notion page ID if this pattern already exists, else None."""
    results = client.query_db(db_id, {
        "property": "Pattern #",
        "number": {"equals": pattern_number},
    })
    if results:
        page_id = results[0]["id"]
        logger.info(f"Pattern {pattern_number} already exists: {page_id}")
        return page_id
    return None


def upload_pattern(client: NotionClient, db_id: str, data: dict,
                   force_ids: list[str], rule_ids: list[str],
                   failure_ids: list[str], rel_ids: list[str]) -> str:
    """Create or update the Pattern page. Returns its Notion page ID."""
    existing_id = find_existing_pattern(client, db_id, data["pattern_number"])

    props = {
        "Name":              title_prop(data["pattern_name"]),
        "Pattern #":         number_prop(data["pattern_number"]),
        "Confidence":        select_prop(data.get("verbatim", {}).get("confidence_rating")),
        "Problem Statement": rich_text_prop(data.get("verbatim", {}).get("problem_statement", "")),
        "Solution Statement": rich_text_prop(data.get("verbatim", {}).get("solution_statement", "")),
    }
    if force_ids:
        props["Forces"] = relation_prop(force_ids)
    if rule_ids:
        props["Typed Rules"] = relation_prop(rule_ids)
    if failure_ids:
        props["Failure Modes"] = relation_prop(failure_ids)
    if rel_ids:
        props["Outgoing Relationships"] = relation_prop(rel_ids)

    if existing_id:
        client.update_page(existing_id, props)
        logger.info(f"Updated pattern page {existing_id}")
        return existing_id
    else:
        page = client.create_page(db_id, props)
        logger.info(f"Created pattern page {page['id']}")
        return page["id"]


def upload_forces(client: NotionClient, db_id: str, forces: list[dict],
                  pattern_page_id: str) -> list[str]:
    ids = []
    for force in forces:
        props = {
            "Name":        title_prop(force.get("name", "Unnamed force")),
            "Type":        select_prop(force.get("type")),
            "Pole A":      rich_text_prop(force.get("pole_a", "")),
            "Pole B":      rich_text_prop(force.get("pole_b", "")),
            "Description": rich_text_prop(force.get("description", "")),
            "Resolved By": rich_text_prop(force.get("resolved_by", "")),
            "Pattern":     relation_prop([pattern_page_id]),
        }
        page = client.create_page(db_id, props)
        ids.append(page["id"])
        logger.info(f"  Created force: {force.get('name')}")
    return ids


def upload_typed_rules(client: NotionClient, db_id: str, rules: list[dict],
                       pattern_page_id: str) -> list[str]:
    ids = []
    for rule in rules:
        props = {
            "Metric":         title_prop(rule.get("metric", "Unnamed rule")),
            "Rule Type":      select_prop(rule.get("rule_type")),
            "Mutability":     select_prop(rule.get("mutability")),
            "Operator":       select_prop(rule.get("operator")),
            "Unit":           select_prop(rule.get("unit")),
            "Rationale":      rich_text_prop(rule.get("rationale", "")),
            "Source Text":    rich_text_prop(rule.get("source_text", "")),
            "Preferred Value": rich_text_prop(rule.get("preferred_value", "")),
            "Pattern":        relation_prop([pattern_page_id]),
        }
        # Value fields — only set if numeric (qualitative rules use preferred_value instead)
        raw_val = rule.get("value")
        if raw_val is not None:
            try:
                props["Value"] = number_prop(float(raw_val))
            except (TypeError, ValueError):
                # Non-numeric value — treat as preferred_value
                if not rule.get("preferred_value"):
                    props["Preferred Value"] = rich_text_prop(str(raw_val))
        if rule.get("value_min") is not None:
            try:
                props["Value Min"] = number_prop(float(rule["value_min"]))
            except (TypeError, ValueError):
                pass
        if rule.get("value_max") is not None:
            try:
                props["Value Max"] = number_prop(float(rule["value_max"]))
            except (TypeError, ValueError):
                pass

        page = client.create_page(db_id, props)
        ids.append(page["id"])
        logger.info(f"  Created rule: {rule.get('metric')}")
    return ids


def upload_failure_modes(client: NotionClient, db_id: str, failures: list[dict],
                         pattern_page_id: str) -> list[str]:
    ids = []
    for failure in failures:
        desc = failure.get("description", "")
        props = {
            "Description":  title_prop(desc[:100]),
            "Violated Rule": rich_text_prop(failure.get("violated_rule", "")),
            "Symptom":      rich_text_prop(failure.get("symptom", "")),
            "Source Text":  rich_text_prop(failure.get("source_text", "")),
            "Pattern":      relation_prop([pattern_page_id]),
        }
        page = client.create_page(db_id, props)
        ids.append(page["id"])
        logger.info(f"  Created failure mode: {desc[:60]}")
    return ids


def upload_relationships(client: NotionClient, db_id: str,
                         adjacency_rules: list[dict],
                         pattern_page_id: str,
                         pattern_number: int) -> list[str]:
    ids = []
    for rule in adjacency_rules:
        target_num  = rule.get("target_pattern_number")
        target_name = rule.get("target_pattern_name", "")
        rel_type    = rule.get("relationship", "")
        label = f"{pattern_number} → {target_num} ({rel_type})"
        props = {
            "Label":           title_prop(label),
            "Source Pattern":  relation_prop([pattern_page_id]),
            "Target Pattern #": number_prop(target_num),
            "Target Name":     rich_text_prop(target_name),
            "Relationship":    select_prop(rel_type),
            "Note":            rich_text_prop(rule.get("note", "")),
        }
        page = client.create_page(db_id, props)
        ids.append(page["id"])
        logger.info(f"  Created relationship: {label}")
    return ids


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    knowledge_path = sys.argv[1]
    if not os.path.exists(knowledge_path):
        print(f"Error: file not found: {knowledge_path}")
        sys.exit(1)

    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        print("Error: NOTION_API_KEY not set. Add it to .env at the project root.")
        sys.exit(1)

    db_ids = {
        "patterns":      os.environ.get("NOTION_PATTERNS_DB_ID"),
        "forces":        os.environ.get("NOTION_FORCES_DB_ID"),
        "typed_rules":   os.environ.get("NOTION_TYPED_RULES_DB_ID"),
        "failure_modes": os.environ.get("NOTION_FAILURE_MODES_DB_ID"),
        "relationships": os.environ.get("NOTION_RELATIONSHIPS_DB_ID"),
    }

    missing = [k for k, v in db_ids.items() if not v]
    if missing:
        print(f"Error: missing environment variables for databases: {missing}")
        print("Set these in .env after rebuilding the Notion schema.")
        sys.exit(1)

    with open(knowledge_path) as f:
        data = json.load(f)

    client = NotionClient(api_key)

    pattern_number = data["pattern_number"]
    pattern_name   = data["pattern_name"]
    print(f"\nUploading Pattern {pattern_number}: {pattern_name}")

    # Upload child records first (need their IDs to link from the pattern page)
    # We create a placeholder pattern page first, then update it with relations.
    # Actually: create pattern page first, then children link back to it.
    # Create pattern without relations first, add relations after.

    print("  Creating pattern page ...")
    placeholder_props = {
        "Name":      title_prop(pattern_name),
        "Pattern #": number_prop(pattern_number),
    }
    existing_id = find_existing_pattern(client, db_ids["patterns"], pattern_number)
    if existing_id:
        pattern_page_id = existing_id
        print(f"  Pattern already exists ({pattern_page_id}) — will update relations.")
    else:
        page = client.create_page(db_ids["patterns"], placeholder_props)
        pattern_page_id = page["id"]
        print(f"  Created pattern page: {pattern_page_id}")

    print("  Uploading forces ...")
    force_ids = upload_forces(client, db_ids["forces"],
                              data.get("forces", []), pattern_page_id)

    print("  Uploading typed rules ...")
    rule_ids = upload_typed_rules(client, db_ids["typed_rules"],
                                  data.get("typed_rules", []), pattern_page_id)

    print("  Uploading failure modes ...")
    failure_ids = upload_failure_modes(client, db_ids["failure_modes"],
                                       data.get("failure_modes", []), pattern_page_id)

    print("  Uploading pattern relationships ...")
    rel_ids = upload_relationships(client, db_ids["relationships"],
                                   data.get("adjacency_rules", []),
                                   pattern_page_id, pattern_number)

    # Final update: set all verbatim fields and relations on the pattern page
    print("  Finalising pattern page ...")
    upload_pattern(client, db_ids["patterns"], data,
                   force_ids, rule_ids, failure_ids, rel_ids)

    print(f"\nDone.")
    print(f"  Pattern page:       {pattern_page_id}")
    print(f"  Forces:             {len(force_ids)}")
    print(f"  Typed rules:        {len(rule_ids)}")
    print(f"  Failure modes:      {len(failure_ids)}")
    print(f"  Relationships:      {len(rel_ids)}")


if __name__ == "__main__":
    main()
