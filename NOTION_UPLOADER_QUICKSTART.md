# Notion Uploader — Quick Start

## Prerequisites

✅ Notion API key set in `NOTION_API_KEY`
✅ Database IDs set in environment variables
✅ Pattern JSON file ready (e.g., `claude_vision_076_output.json`)
✅ Dependencies installed: `pip install requests --break-system-packages`

---

## One-Time Setup (First Time Only)

```bash
# 1. Set API token
export NOTION_API_KEY="secret_abcd1234efgh5678..."

# 2. Set database IDs (from Notion URLs)
export NOTION_PATTERNS_DB_ID="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5"
export NOTION_QUANT_RULES_DB_ID="p6q7r8s9t0u1v2w3x4y5z6a7b8c9d"
export NOTION_QUAL_FEATURES_DB_ID="e0f1g2h3i4j5k6l7m8n9o0p1q2r3s"

# 3. Install dependencies
pip install requests --break-system-packages
```

## Upload a Pattern

```bash
# Pattern 76 (test)
python scripts/notion_uploader.py claude_vision_076_output.json

# Pattern 61
python scripts/notion_uploader.py claude_vision_061_output.json

# Any other pattern
python scripts/notion_uploader.py claude_vision_XXX_output.json
```

## What Gets Created

| Database | Entries | Example |
|----------|---------|---------|
| **Patterns** | 1 | Pattern 76: House for a Small Family |
| **Quantitative Rules** | ~10 | Total house area: 74.3-111.5 m² |
| **Qualitative Features** | ~14 | "Creates positive outdoor space" |

All linked together with relations.

## View Results

1. **Open Notion workspace**
2. **Patterns database** → See new pattern with status "Extracted"
3. **Quantitative Rules database** → Filter by Pattern 76
4. **Qualitative Features database** → Filter by Pattern 76

## Next: Extract More Patterns

```bash
# Pattern 61
python scripts/claude_vision_extraction.py ./extracted_images/_pages_tmp "Small Public Squares" 61 claude_vision_061_output.json
python scripts/notion_uploader.py claude_vision_061_output.json

# Pattern 77-81 (repeat for each)
python scripts/claude_vision_extraction.py ./extracted_images/_pages_tmp "Pattern Name" 77 claude_vision_077_output.json
python scripts/notion_uploader.py claude_vision_077_output.json
```

## Full Documentation

See: `NOTION_SETUP_GUIDE.md`
