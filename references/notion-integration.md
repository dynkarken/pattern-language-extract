# Notion Integration Guide

This document explains how the skill output maps to your Pattern Language Design Model database in Notion.

## Databases

The skill produces JSON that maps directly to three linked Notion databases:

1. **Patterns Database** - Main pattern entry with core identity and narrative content
2. **Quantitative Rules Database** - Extracted measurements, dimensions, formulas, ratios
3. **Qualitative Features Database** - Experiential and design qualities

## Mapping: JSON Output → Notion Fields

### Patterns Database

**Input field**: `pattern_name`, `pattern_number`

**Creates/Updates Notion page with:**
- **Name** (title): `pattern_name`
- **Pattern #**: `pattern_number`
- **Book Page**: Extract from source material (user provides)
- **Problem Statement**: Extract from transcribed text
- **Solution Statement**: Extract from transcribed text
- **Diagram Interpretation**: AI-generated description of main diagram
- **Author Notes**: Left blank for you to fill (never auto-populated)
- **Page content**: Full transcribed text with [Image: x] markers

**Image linking:**
- The transcribed text includes `[Image: {id} - {description}]` markers
- You can manually upload actual image files to the Notion page and replace markers with embedded images
- Each image has a linked entry in the `extracted_images` array with filename and description

### Quantitative Rules Database

**Input field**: `quantitative_rules` array

**Creates entries for each rule:**
- **Metric** (title): Human-readable metric name (e.g., "Width (short direction), typical")
- **Value**: Numeric value or range (e.g., "45–60")
- **Unit** (select): feet / meters / ratio / sq ft/person / zones / degrees / percent / stories / other
- **Type** (select): Range / Threshold / Ratio / Formula / Count
- **Condition**: When/where this applies
- **Pattern** (relation): Auto-link to parent pattern
- **Source text**: The direct quote from the book where this rule appears

**Extraction rules:**
- **Range**: "between X and Y", "X to Y", "X-Y"
- **Threshold**: "never more than X", "maximum of X", "no fewer than Y"
- **Ratio**: "X to Y", "X:Y", "proportion of X"
- **Formula**: "Area ≤ 300P", mathematical relationships
- **Count**: "3 zones", "5 elements", discrete numbers

### Qualitative Features Database

**Input field**: `qualitative_features` array

**Creates entries for each quality:**
- **Quality** (title): Experiential feature description
- **Category** (multi-select): One or more of:
  - Visual (sight, light, transparency, views, enclosure)
  - Spatial (volume, proportion, openness, shape, layout)
  - Social (gathering, privacy, community, autonomy)
  - Atmospheric (mood, feeling, character, ambiance)
  - Haptic (touch, texture, materiality)
  - Acoustic (sound, noise, silence)
  - Temporal (time of day, seasonal, aging)
  - Political (ownership, territory, agency, control)
- **Pattern** (relation): Auto-link to parent pattern
- **Source text**: Direct quote or paraphrase from the book

**Extraction guidelines:**
- One quality per entry (not "families feel safe and private" as one—split into two entries)
- Be specific: "Living room connects visually to entry, allowing parents to supervise" (not "visibility")
- Draw from both solution text and research section
- Research section often contains deeper qualitative intentions
- Confidence level helps you decide whether to review before uploading

## Workflow: From JSON to Notion

### Option 1: Manual Review (Recommended for v1)

1. **Run extraction** → Get `extraction_output.json`
2. **Review JSON** in text editor or viewer
   - Check OCR accuracy
   - Verify image linkages make sense
   - Spot-check quantitative extractions
   - Review qualitative features for accuracy
3. **Approve** or make corrections in the JSON
4. **Upload** via separate import script (to be created)

### Option 2: Direct Upload (When Confident)

Once you're confident in the skill's accuracy:

1. **Run extraction** → Get `extraction_output.json`
2. **Run importer script** with Notion API key
3. Script automatically creates/updates Notion entries

Note: Even with direct upload, you can edit Notion entries afterward.

## Implementation Notes

### Image Extraction

The skill extracts `image_id`, `description`, `filename`, and `linked_in_text` status.

To use images in Notion:
1. Save extracted images from `outputs/images/` folder
2. In Notion, replace `[Image: X - description]` markers with embedded image files
3. The description becomes the caption/alt text

### OCR Confidence

If `ocr_confidence < 0.85`:
- Page may have handwriting, unusual fonts, or poor scan quality
- Review the transcribed text carefully
- Make corrections before uploading to Notion

Low-confidence regions are flagged in the execution log.

### Quantitative Rule Quality

Each quantitative rule includes a `source_text` field. Always check that this text actually contains the stated value. This prevents hallucination.

### Qualitative Feature Categories

Multiple categories can apply to one feature. For example:
- "Rooms open to shared courtyard" → Spatial, Social, Visual
- "Sense of privacy despite proximity" → Social, Spatial, Atmospheric

Use multi-select in Notion to tag appropriately.

### Linking Images to Text

The skill attempts smart image-text linking, but may occasionally get it wrong. Check:
1. Does the linked text actually describe the image?
2. Are diagrams linked to text about layout/spatial concepts?
3. Are photos linked to text about materials/appearance?
4. Are floor plans linked to text about room organization?

If a link is wrong, you can move the `[Image: X]` marker to a better location in the text.

## Example: Complete Mapping

**Input JSON excerpt:**
```json
{
  "pattern_name": "Small Public Squares",
  "pattern_number": 61,
  "quantitative_rules": [
    {
      "metric": "Width (short direction)",
      "value": "45-60",
      "unit": "feet",
      "type": "Range",
      "source_text": "The square should be between 45 and 60 feet in its short direction..."
    }
  ],
  "qualitative_features": [
    {
      "quality": "Sense of enclosure from surrounding buildings",
      "categories": ["Spatial", "Visual"],
      "source_text": "Buildings surrounding the square create visual and spatial enclosure..."
    }
  ]
}
```

**Output in Notion:**
1. **Patterns database**: New page "Small Public Squares" (Pattern #61)
2. **Quantitative Rules database**: New entry "Width (short direction, typical)" with value 45-60 feet, linked to Pattern 61
3. **Qualitative Features database**: New entry "Sense of enclosure from surrounding buildings" tagged with Spatial + Visual, linked to Pattern 61

## Future Enhancements

- Automatic image upload to Notion
- Parser for "Author Notes" field (custom interpretations/disagreements)
- Pattern cross-reference extraction (linking to related patterns)
- Support for Danish building code constraints
- Climate/environmental data layer (future Phase 2b)
