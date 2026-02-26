#!/usr/bin/env python3
"""
Knowledge extraction — reads a _text.json, calls Claude once, writes a _knowledge.json.

Usage:
  python scripts/extract.py <pattern_number>_text.json

Output:
  {pattern_number:03d}_knowledge.json

Example:
  python scripts/extract.py 076_text.json

The output is the human-in-the-loop checkpoint. Review and edit it before running upload.py.
"""

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

SYSTEM_PROMPT = """\
You are an architectural knowledge extraction specialist working with Christopher Alexander's \
"A Pattern Language" (1977).

Alexander's patterns resolve competing forces — tensions between opposing human needs or physical \
realities. The problem statement names the forces. The solution (after "Therefore:") is the \
geometric/spatial move that resolves them. The research section is evidence that the forces are \
real and the move resolves them.

Forces always have two poles (e.g., "privacy vs. accessibility"). Every pattern has at least 2.

Typed rules: some are invariant (Alexander says "never", "always", "must") — these hold \
regardless of site. Others are site-adaptive ("typically", "in temperate climates", "about", \
"generally") — they have preferred values that flex with site conditions.

Failure modes: Alexander frequently describes what happens when a pattern is violated — \
"when this is missing...", "if too small...", "without this...". Extract these as \
action-oriented failure descriptions.

Return ONLY valid JSON. No preamble or explanation outside the JSON.\
"""

SCHEMA_EXAMPLE = """\
{
  "pattern_name": "House for a Small Family",
  "pattern_number": 76,

  "verbatim": {
    "problem_statement": "exact framed text",
    "solution_statement": "exact Therefore: directive",
    "confidence_rating": "**"
  },

  "forces": [
    {
      "name": "family unity vs. individual privacy",
      "type": "social",  // one of: social, spatial, dimensional, light, movement, privacy, territorial, temporal
      "pole_a": "the need to share meals, gather, supervise children",
      "pole_b": "the need to retreat, work alone, rest",
      "description": "central tension Pattern 76 resolves",
      "resolved_by": "pavilion arrangement around shared courtyard"
    }
  ],

  "typed_rules": [
    {
      "metric": "Courtyard diameter",
      "rule_type": "hard_constraint",
      "mutability": "invariant",
      "operator": "max",
      "value": 21.0,
      "unit": "m",
      "rationale": "beyond 21m enclosure disappears",
      "source_text": "never more than about 70 feet across"
    },
    {
      "metric": "Courtyard orientation",
      "rule_type": "soft_preference",
      "mutability": "site-adaptive",
      "preferred_value": "south-facing in northern hemisphere",
      "rationale": "maximises winter sun; adapt to local climate",
      "source_text": "all rooms which face the courtyard get maximum sun"
    }
  ],

  "adjacency_rules": [
    {
      "target_pattern_number": 106,
      "target_pattern_name": "Positive Outdoor Space",
      "relationship": "required",
      "note": "courtyard only works if bounded on 3-4 sides"
    }
  ],

  "failure_modes": [
    {
      "description": "When the courtyard is too large it loses enclosure and becomes an unused lawn.",
      "violated_rule": "Courtyard diameter",
      "symptom": "outdoor space goes unused; family gravitates to single room",
      "source_text": "When the open area becomes too large it becomes a lawn..."
    }
  ]
}\
"""


def extract_knowledge(text_json_path: str) -> dict:
    with open(text_json_path) as f:
        data = json.load(f)

    pattern_name   = data["pattern_name"]
    pattern_number = data["pattern_number"]
    # support both new (full_text) and legacy (transcribed_text_with_images) field names
    full_text = data.get("full_text") or data.get("transcribed_text_with_images", "")

    if not full_text:
        raise ValueError(f"No text content found in {text_json_path}")

    user_prompt = f"""\
Extract structured knowledge from Pattern {pattern_number} — {pattern_name}.

TEXT:
{full_text}

Return JSON with exactly these keys: verbatim, forces, typed_rules, adjacency_rules, failure_modes.
Use this schema:
{SCHEMA_EXAMPLE}

Rules:
- Convert all imperial to metric (feet × 0.3048 = m, sq ft × 0.0929 = m²)
- Extract 2–5 forces (minimum 2). Every force must have both pole_a and pole_b populated.
- Every typed_rule must have source_text with a traceable quote from the text.
- Invariant rules must NOT use hedging language ("typically", "about", "generally").
- adjacency_rules: capture every explicitly numbered cross-reference in the text. relationship must be exactly one of: required, enhanced_by, incompatible_with. Use "required" for patterns Alexander names as prerequisites or structural dependencies; "enhanced_by" for patterns that complement or scale the pattern; "incompatible_with" for conflicts.
- typed_rules: "value" must be numeric (float). If the rule is qualitative (no number), use "preferred_value" (string) instead and omit "value".
- failure_modes: describe failure, do not re-state the rule. Must have source_text.
- problem_statement and solution_statement must be verbatim text, not summaries.
- confidence_rating: use * (unverified), ** (plausible), or *** (well-supported by Alexander's research).

Include pattern_name and pattern_number at the top level of the JSON.\
"""

    logger.info(f"Calling Claude for pattern {pattern_number} — {pattern_name} ...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        knowledge = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.error(f"Raw response (first 500 chars): {raw[:500]}")
        raise

    # Ensure top-level identifiers are set correctly
    knowledge["pattern_name"]   = pattern_name
    knowledge["pattern_number"] = pattern_number

    return knowledge


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    text_json_path = sys.argv[1]
    if not os.path.exists(text_json_path):
        print(f"Error: file not found: {text_json_path}")
        sys.exit(1)

    knowledge = extract_knowledge(text_json_path)

    pattern_number = knowledge["pattern_number"]
    out_path = f"{pattern_number:03d}_knowledge.json"
    with open(out_path, "w") as f:
        json.dump(knowledge, f, indent=2)

    print(f"\nExtraction complete.")
    print(f"Output: {out_path}")
    print(f"\nReview this file before uploading:")
    print(f"  - Verify verbatim problem/solution statements")
    print(f"  - Check all forces have both poles")
    print(f"  - Confirm invariant rules have no hedging language")
    print(f"  - Verify adjacency_rules captures numbered cross-references")
    print(f"\nThen run:  python scripts/upload.py {out_path}")


if __name__ == "__main__":
    main()
