---
name: pattern-language-extract
description: |
  Extract images, transcribe text, and automatically structure data from scanned pattern books for direct upload to Notion databases.

  This skill is specifically designed for the Pattern Language Design Model project and similar archival/pattern library work. It performs end-to-end extraction from scanned PDFs or images:
  - Extracts all images (photographs, diagrams, floor plans) with intelligent cropping and rotation correction
  - Performs accurate OCR on full text including research sections
  - Intelligently links images to their corresponding text descriptions with [Image: description] markers
  - Automatically identifies and extracts Quantitative Rules (dimensions, ratios, formulas, thresholds)
  - Automatically identifies and extracts Qualitative Features (experiential, spatial, social, atmospheric qualities)
  - Produces structured JSON output ready for Notion database ingestion

  USE THIS SKILL whenever: extracting structured data from scanned pattern books, linking images to descriptive text, transcribing research sections from scans, or preparing data for pattern/design databases. This skill is particularly useful for Christopher Alexander's "A Pattern Language" or similar design pattern libraries where images must be linked to research text.

  TRIGGER PHRASES: "extract from scans", "transcribe pattern book", "link images to text", "extract pattern data", "OCR scans and upload", "pull images from PDF", continuing Pattern Language Design Model work
---

# Pattern Language Extract Skill

This skill automates end-to-end data extraction from scanned pattern books, producing clean, structured JSON ready for Notion database upload.

## Input

- **Source material**: PDF file or set of JPEG/PNG images (scanned book pages)
- **Notion configuration**: Pattern #, Pattern Name, Notion database IDs (optional, used only if uploading directly)

## Output

JSON file with structure:
```json
{
  "pattern_name": "Small Public Squares",
  "pattern_number": 61,
  "transcribed_text_with_images": "...[Image: 1a - Street corner entrance] ... Full transcribed text ...",
  "extracted_images": [
    {
      "image_id": "1a",
      "description": "Street corner entrance showing typical width",
      "filename": "061_smallpublicsquares_image_1a.jpg",
      "linked_in_text": true,
      "context": "Text passage describing the image"
    }
  ],
  "quantitative_rules": [
    {
      "metric": "Width (short direction)",
      "value": "45-60",
      "unit": "feet",
      "condition": "Short direction only",
      "type": "Range",
      "source_text": "The square should be between 45 and 60 feet in its short direction..."
    }
  ],
  "qualitative_features": [
    {
      "quality": "Sense of enclosure from surrounding buildings",
      "categories": ["Spatial", "Visual"],
      "source_text": "The buildings should form a coherent edge...",
      "confidence": "high"
    }
  ],
  "execution_log": {
    "images_extracted": 12,
    "pages_processed": 5,
    "ocr_confidence": 0.92,
    "notes": "High-quality scans, no significant OCR errors"
  }
}
```

## Workflow

### Step 1: Prepare Input
Provide a scanned PDF or folder of JPEG/PNG page images. Ideally name them with pattern number and name for easy tracking: `061_Small_Public_Squares_page1.jpeg`

### Step 2: OCR & Image Extraction
The skill:
1. **Extracts images** from each page using computer vision (pytesseract + PIL)
   - Detects regions containing diagrams, photographs, floor plans
   - Crops and cleans images
   - Corrects rotation automatically
   - Discards text-only regions
2. **Transcribes full text** via OCR
   - Captures all text including research sections
   - Maintains paragraph structure for readability
   - Flags regions with low OCR confidence for review

### Step 3: Intelligent Image-Text Linking
For each extracted image:
1. Extract surrounding text context (500 words before/after image location)
2. Analyze image content (detect if it's a diagram, photo, floor plan, etc.)
3. Use contextual analysis to infer which text passage describes the image
4. Create explicit [Image: {id} - {description}] markers in transcribed text
5. Flag high-uncertainty matches for manual review

### Step 4: Extract Quantitative Rules
Parse transcribed text to identify:
- Specific dimensions (feet, meters, ratios)
- Ranges and thresholds ("between X and Y", "never more than Z")
- Formulas or calculable relationships
- Counts and discrete numbers
- Population or density metrics
- Angles, percentages, stories

For each quantitative rule found:
- Extract the specific value/range
- Infer the unit (feet, meters, ratio, etc.)
- Record the type (Range / Threshold / Ratio / Formula / Count)
- Capture surrounding text as source context
- Note confidence level

### Step 5: Extract Qualitative Features
Parse transcribed text to identify experiential and design qualities:
- **Visual**: sight, views, light quality, transparency, visual enclosure
- **Spatial**: volume, proportion, openness/enclosure, shape, layout
- **Social**: gathering, privacy, community, autonomy
- **Atmospheric**: mood, feeling, character, ambiance
- **Haptic**: texture, materiality, temperature
- **Acoustic**: sound, noise, silence, voice carrying
- **Temporal**: time of day, seasonal variation, aging
- **Political**: governance, ownership, territory, agency

For each quality identified:
- Extract the quality description
- Classify with one or more category tags
- Capture source text passage
- Rate confidence (high/medium/low)

### Step 6: Output & Review
Skill produces `extraction_output.json` with all data. You:
1. Review the JSON for accuracy
2. Verify image linkages are correct
3. Spot-check quantitative extractions
4. Confirm qualitative features match intent
5. Approve for Notion upload (separate step)

## Technical Details

### Image Extraction
- Uses PIL (Python Imaging Library) for image processing
- Uses pytesseract for OCR confidence scoring
- Detects non-text regions using edge detection and color analysis
- Crops to remove margins and borders
- Corrects rotation via orientation detection
- Saves clean images as JPEG with descriptive filenames

### OCR Processing
- Uses pytesseract (Tesseract OCR engine)
- Processes page-by-page for accuracy tracking
- Maintains spatial relationships between text and images
- Captures confidence scores per text block
- Flags low-confidence regions (< 0.85 confidence)

### Data Extraction Strategy
- **Quantitative**: Regex patterns for common measurement formats + LLM analysis for context understanding
- **Qualitative**: LLM analysis of text passages to identify design intentions and experiential goals
- **Image-Text Linking**: Spatial proximity + semantic similarity between image and nearby text

### Confidence Scoring
All extracted data includes confidence scores:
- **Image linkage**: 0.0-1.0 (how likely the linked text describes the image)
- **Quantitative rule**: How certain the extraction is (dimension vs. vague reference)
- **Qualitative feature**: How strongly the text supports the quality claim

## Limitations & Considerations

- **OCR accuracy**: Skill works best on high-quality, clear scans. Handwritten notes or unusual fonts may have errors.
- **Image inference**: Smart linking works well for typical layout books but may struggle with unusual page designs.
- **Language**: Currently optimized for English text. Other languages may have lower OCR accuracy.
- **Complex tables**: Tables and multi-column layouts may be transcribed less accurately than body text.

## Example Usage

Input: `061_Small_Public_Squares_scans.pdf`

Output: `061_extraction_output.json` containing:
- Full transcribed text with [Image: x] markers
- 12 extracted and linked images
- 8 quantitative rules (dimensions, ratios, counts)
- 15 qualitative features (spatial, social, atmospheric)
- Execution log with OCR confidence stats

You then:
1. Review the JSON
2. Correct any mislinked images or extraction errors
3. Approve for Notion upload via a separate import script
