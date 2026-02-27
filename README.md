# Pattern Language — Interactive Knowledge Graph

A tool for digitizing and exploring *A Pattern Language* (Alexander, 1977) as a physics-driven, interactive graph.

---

## What This Is

Scanned book pages are processed through an extraction pipeline that produces structured JSON files (`*_knowledge.json`). Those files feed a D3.js force-directed visualization (`visualize.html`) where patterns become nodes, their architectural relationships become edges, and environmental overlays (solar, privacy) apply physics forces so patterns negotiate optimal positions collectively.

**Currently loaded patterns:** 76, 128, 129, 131, 136, 143

---

## File Structure

```
pattern-language-extract/
├── visualize.html              — the interactive graph (open in browser)
├── patterns/
│   ├── *_knowledge.json        — one structured data file per pattern
│   └── *_text.json             — intermediate OCR output (pipeline input)
├── images/                     — extracted photos and diagrams per pattern
├── log.txt                     — running conversation log
├── scripts/
│   ├── ocr.py                  — Stage 1: Claude Vision → *_text.json
│   ├── extract.py              — Stage 2: *_text.json → *_knowledge.json
│   └── pipeline.py             — runs Stage 1 + 2 in sequence
└── CLAUDE.md                   — instructions for Claude Code
```

---

## Adding a New Pattern

**Stage 1 — OCR** (JPEG scans → raw transcription):
```bash
python scripts/ocr.py <scans_dir> "<Pattern Name>" <pattern_number>
# e.g. python scripts/ocr.py scans/ "Entrance Room" 130
# Output: 130_text.json
```

**Stage 2 — Extract** (raw transcription → structured knowledge):
```bash
python scripts/extract.py 130_text.json
# Output: 130_knowledge.json
# Review and edit this file before loading into the visualization.
```

**Run both in sequence:**
```bash
python scripts/pipeline.py <scans_dir> "<Pattern Name>" <pattern_number>
```

**Stage 3 — Visualize**: drop the new `*_knowledge.json` into the project root, then reload `visualize.html`. The graph picks it up automatically.

Requires: `ANTHROPIC_API_KEY` in environment (for Claude Vision in `ocr.py` and `extract.py`).

---

## The Visualization

Open `visualize.html` in a browser. No server needed — it reads the JSON files directly.

**Controls:**
- **Edge filters** — toggle required / enhanced_by / incompatible relationships
- **Show external patterns** — reveal unloaded patterns referenced in edges
- **Solar overlay** — patterns with sunlight preferences pull toward the south; stronger preferences win position
- **Privacy overlay** — patterns spread across a public-to-private spectrum

**Interaction:**
- Click a node to open the detail panel (problem, solution, forces, typed rules, failure modes)
- Click the background to dismiss
- Drag nodes; zoom and pan the canvas

**Physics:** the simulation is a negotiation engine. When overlays are active, each pattern exerts a pull proportional to its preference strength. The collective arrangement emerges from those pulls combined with link forces, charge repulsion, and collision. A pattern with a weaker preference yields position to one with a stronger preference.

---

## Knowledge Schema (`*_knowledge.json`)

```json
{
  "pattern_name": "Indoor Sunlight",
  "pattern_number": 128,
  "confidence": "***",
  "verbatim": {
    "problem_statement": "...",
    "solution_statement": "..."
  },
  "forces": [
    { "name": "...", "type": "environmental", "pole_a": "...", "pole_b": "..." }
  ],
  "rules": [
    {
      "metric": "...", "rule_type": "hard_constraint", "mutability": "invariant",
      "operator": ">=", "value": 1.6, "unit": "m", "source_text": "..."
    }
  ],
  "failures": [
    { "description": "...", "symptom": "..." }
  ],
  "relationships": [
    { "target_pattern": 129, "type": "required", "direction": "outgoing", "note": "..." }
  ],
  "solar_preference": 0.8,
  "privacy_score": 0.3
}
```

`solar_preference` (0–1) and `privacy_score` (0 = public, 1 = private) control overlay physics strength.
