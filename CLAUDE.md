# Claude Code Instructions

## Commits

Commit after completing any meaningful unit of work — a feature, a fix, a new pattern, a schema change. Small, focused commits. Do not batch unrelated changes.

## Project Overview

This is an interactive knowledge graph of *A Pattern Language* (Alexander, 1977). The deliverable is `visualize.html` — a D3.js force-directed graph where patterns are nodes, relationships are edges, and environmental overlays (solar, privacy) drive physics so patterns collectively negotiate optimal positions.

Data lives in `*_knowledge.json` files (one per pattern). The extraction pipeline (`scripts/ocr.py` → `scripts/extract.py`) produces these from JPEG scans of the book using Claude Vision.

## Conversation Log

Maintain `log.txt` as a running word-for-word log of conversations between user and Claude, unless told otherwise. Append new sessions; do not rewrite old entries.

## Architecture Principles

- `visualize.html` is a single-file app. Keep it that way — no build step, no server, opens directly in browser.
- Pattern data is loaded at runtime from `*_knowledge.json` files via fetch. The graph auto-discovers any file matching that pattern.
- The physics simulation is the negotiation engine. Environmental forces express individual preferences; the collective arrangement emerges from their interaction with link forces, charge, and collision.
- Keep the schema in `*_knowledge.json` consistent across all patterns. If you change the schema, update all existing files and the README.

## Key Files

- `visualize.html` — the entire frontend (D3.js, CSS, JS in one file)
- `*_knowledge.json` — structured pattern data (see README for schema)
- `*_text.json` — intermediate OCR output; input to `extract.py`
- `scripts/ocr.py` — Stage 1: JPEG scans → `*_text.json` via Claude Vision
- `scripts/extract.py` — Stage 2: `*_text.json` → `*_knowledge.json` via Claude
- `scripts/pipeline.py` — orchestrates Stage 1 + 2
- `images/` — extracted photos and diagrams per pattern

## What Does Not Belong Here

- Notion integration (removed)
- Tesseract / pytesseract (replaced by Claude Vision)
- Delivery summaries, skill definitions, evaluation frameworks
- Any script not part of the extraction pipeline or visualization
