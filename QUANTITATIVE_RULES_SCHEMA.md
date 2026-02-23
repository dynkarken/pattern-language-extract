# Quantitative Rules Schema - Data Agile Design

**Goal**: Make data importable and queryable in Excel, Power BI, Notion, etc.

---

## Current Problem (❌ Avoid)

```json
{
  "value": "74.3-111.5",        // ← String! Not queryable
  "unit": "m²"
}
```

**Issues:**
- Can't calculate on ranges
- Can't filter "value > 100"
- Excel/Power BI treats as text, not numbers
- Not data agile

---

## Improved Schema (✅ Use This)

For **Range** type rules:
```json
{
  "metric": "Total house area",
  "type": "Range",
  "value_min": 74.3,            // ← Numeric
  "value_max": 111.5,           // ← Numeric
  "unit": "m²",                 // ← Select from controlled list
  "condition": "Typical for small family",
  "source_text": "Total area: 800-1200 square feet",
  "confidence": "high"
}
```

For **Threshold** type rules:
```json
{
  "metric": "Minimum courtyard width",
  "type": "Threshold",
  "value": 4.57,                // ← Single numeric
  "unit": "m",
  "condition": "For proper enclosure feeling",
  "source_text": "minimum 15-20 feet",
  "confidence": "high"
}
```

For **Count** type rules:
```json
{
  "metric": "Number of bedrooms",
  "type": "Count",
  "value": 2,                   // ← Integer
  "unit": "count",
  "condition": "Typical arrangement",
  "source_text": "two bedrooms typical",
  "confidence": "high"
}
```

For **Ratio** type rules:
```json
{
  "metric": "Room proportion",
  "type": "Ratio",
  "value_numerator": 3,         // ← For ratios like 3:2
  "value_denominator": 2,
  "unit": "ratio",
  "condition": "Recommended spatial proportion",
  "source_text": "3 to 2 ratio",
  "confidence": "high"
}
```

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Excel import** | Text (unusable) | Numbers (queryable) |
| **Filtering** | ❌ Can't filter ranges | ✅ Filter value_min > 50 |
| **Calculations** | ❌ Can't calculate | ✅ Sum, average, min, max work |
| **Power BI** | ❌ Needs cleaning | ✅ Direct visualization |
| **Notion** | ⚠️ Text field only | ✅ Number fields + formulas |
| **Future-proof** | ❌ Hard to extend | ✅ Easy to add new types |

---

## Notion Database Fields

### Quantitative Rules Table

| Field | Type | Example |
|-------|------|---------|
| Metric | Title | "Total house area" |
| Type | Select | Range / Threshold / Ratio / Count / Formula |
| Value Min | Number | 74.3 |
| Value Max | Number | 111.5 |
| Unit | Select | m, m², cm, count, ratio |
| Condition | Rich text | "Typical for small family" |
| Pattern | Relation | [Link to Pattern 76] |
| Confidence | Select | High / Medium / Low |
| Source Text | Rich text | "Total area: 800-1200 square feet" |

**Display formula** (optional):
```
prop("Value Min") + " - " + prop("Value Max") + " " + prop("Unit")
```
Would show: "74.3 - 111.5 m²"

---

## What's Gone

❌ **Removed entirely:**
- `original_value` ("800-1200 square feet")
- `original_unit` ("square feet")

**Why?**
- Clutters the dataset
- Not needed for Notion (source_text preserves original)
- Makes data messy for analysis

---

## Pattern 76 Example: Updated

### Before (cluttered)
```json
{
  "metric": "Total house area",
  "value": "74.3-111.5",
  "unit": "m²",
  "original_value": "800-1200 square feet",
  "original_unit": "square feet",
  "type": "Range",
  "condition": "Typical for small family",
  "source_text": "Total area: 800-1200 square feet"
}
```

### After (clean & agile)
```json
{
  "metric": "Total house area",
  "type": "Range",
  "value_min": 74.3,
  "value_max": 111.5,
  "unit": "m²",
  "condition": "Typical for small family",
  "source_text": "Total area: 800-1200 square feet",
  "confidence": "high"
}
```

---

## All Pattern 76 Rules - New Format

| Metric | Type | Min | Max | Unit | Condition |
|--------|------|-----|-----|------|-----------|
| Total house area | Range | 74.3 | 111.5 | m² | Small family |
| Living pavilion area | Range | 23.2 | 32.5 | m² | Main gathering space |
| Living room ceiling height | Range | 3.05 | 3.66 | m | Good spatial feeling |
| Bedroom dimensions | Range | 11.1 | 16.7 | m² | Per bedroom |
| Kitchen area | Range | 9.3 | 13.9 | m² | Open to courtyard |
| Courtyard area | Range | 27.9 | 37.2 | m² | Functional outdoor room |
| Circulation space | Range | 4.6 | 9.3 | m² | Connecting pavilions |
| Number of bedrooms | Count | 2 | — | count | Typical |
| Courtyard min dimension | Range | 4.57 | 6.1 | m | Enclosure feeling |

✅ **All numeric, all queryable, all Excel/Power BI ready**

---

## Implementation

Update extraction script:
- For Range: `value_min`, `value_max` (both numeric)
- For Threshold: `value` (single numeric)
- For Count: `value` (integer)
- For Ratio: `value_numerator`, `value_denominator` (both numeric)
- Remove `original_value` and `original_unit` entirely
- Keep `source_text` for traceability

---

## Next: Notion Uploader

The uploader will:
1. Read numeric min/max from JSON
2. Create Notion entries with proper number field types
3. Build display formula to show "74.3 - 111.5 m²" when viewing
4. Enable Excel export that's immediately usable for analysis

Ready to update the script?
