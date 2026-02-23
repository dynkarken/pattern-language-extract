# Metric Conversion: Pattern 76 Quantitative Rules

**Status**: ✅ All imperial units converted to metric
**Conversion Standard**: ISO metric (meters, square meters)
**Applied to**: All quantitative rules in extraction pipeline

---

## Conversion Factors Used

| Imperial Unit | Metric Equivalent | Factor |
|--------------|-------------------|--------|
| 1 foot (ft) | 0.3048 meters (m) | × 0.3048 |
| 1 inch (in) | 0.0254 meters (m) | × 0.0254 |
| 1 square foot (sq ft) | 0.092903 square meters (m²) | × 0.092903 |

---

## Pattern 76 Conversions

### Areas (converted to m²)

| Description | Original | Metric | Notes |
|-------------|----------|--------|-------|
| **Total house area** | 800–1,200 sq ft | **74.3–111.5 m²** | ✓ Small family home |
| **Living pavilion** | 250–350 sq ft | **23.2–32.5 m²** | ✓ Main gathering space |
| **Per bedroom** | 120–180 sq ft | **11.1–16.7 m²** | ✓ 2 bedrooms typical |
| **Kitchen** | 100–150 sq ft | **9.3–13.9 m²** | ✓ Open to courtyard |
| **Courtyard** | 300–400 sq ft | **27.9–37.2 m²** | ✓ Outdoor room |
| **Circulation** | 50–100 sq ft | **4.6–9.3 m²** | ✓ Connections |

### Heights/Depths (converted to m)

| Description | Original | Metric | Notes |
|-------------|----------|--------|-------|
| **Living room ceiling** | 10–12 ft | **3.05–3.66 m** | ✓ High ceilings |
| **Bedroom ceiling** | 8–10 ft | **2.44–3.05 m** | ✓ Standard height |
| **Courtyard short dimension** | 15–20 ft | **4.57–6.1 m** | ✓ Minimum for enclosure |

---

## Implementation in Pipeline

### Extraction Script Changes

The `claude_vision_extraction.py` script now includes:

1. **`convert_to_metric()` function**
   - Detects imperial units in extracted text
   - Automatically converts to metric
   - Handles square feet → m², feet → m, inches → cm
   - Preserves original values for reference

2. **Updated quantitative rule extraction**
   - `value`: Metric measurement (primary)
   - `unit`: Metric unit (m, m², cm, etc.)
   - `original_value`: Original imperial value (for reference)
   - `original_unit`: Original unit type (feet, square feet, etc.)

### Output Format

```json
{
  "metric": "Total house area",
  "value": "74.3-111.5",           // ← METRIC VALUE
  "unit": "m²",                    // ← METRIC UNIT
  "original_value": "800-1200 square feet",  // ← Imperial for reference
  "original_unit": "square feet",
  "type": "Range",
  "condition": "Typical for small family",
  "source_text": "Total area: 800-1200 square feet",
  "confidence": "high"
}
```

---

## For Your Notion Database

### Quantitative Rules Table
- **Value**: Store metric measurements (74.3–111.5, 3.05–3.66, etc.)
- **Unit**: Select from: m, m², cm, ratio, count
- **Original Value**: Optional reference field (800–1,200 sq ft)
- **Original Unit**: Optional reference (square feet, feet, etc.)

### Why Both?
- **Primary**: Use metric values for all calculations and queries
- **Reference**: Keep original values for tracing back to source material
- **Transparency**: Readers can see the original measurements from the book

---

## Automatic Application

All future pattern extractions will:
1. ✅ Detect imperial units automatically
2. ✅ Convert to metric immediately
3. ✅ Store both values (metric primary, imperial reference)
4. ✅ Handle all common units (feet, inches, square feet, etc.)

---

## Verification: Pattern 76 Complete

✅ All 9 quantitative rules converted
✅ All areas now in m²
✅ All heights/depths now in m
✅ Original values preserved for reference
✅ Ready for Notion upload (metric-first)

---

## Next: Notion Uploader

The Notion uploader will:
1. Read metric values from JSON
2. Store in Notion Quantitative Rules database
3. Use metric units as primary field
4. Include original values for historical reference

Example Notion entry:
- **Metric**: Total house area
- **Value**: 74.3–111.5
- **Unit**: m²
- **Original**: 800–1,200 sq ft (reference only)
- **Pattern**: Pattern 76 - House for a Small Family
