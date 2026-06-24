---
name: embedded-screenshot-text-editor
description: Edit text inside screenshots embedded in legacy Word .doc files, especially terminal screenshots, network-lab screenshots, Wi-Fi/Phone UI screenshots, and mixed PNG/JPEG OLE Data streams. Use when asked to replace IDs, SSIDs, device names, prompts, labels, MAC-like strings, IP-like strings, or other visible screenshot text while preserving visual realism, avoiding edit artifacts, checking every embedded image format, and validating the final document.
---

# Embedded Screenshot Text Editor

Use this skill for fragile screenshot text replacement inside legacy binary Word `.doc` files. The workflow is intentionally strict. Do not skip validation, do not trust a single OCR pass, and do not deliver a document while any required check is incomplete.

## Non-Negotiable Rules

1. Work from a backup copy. Never edit the only copy of a document.
2. Treat `.doc` as an OLE/CFBF container. Inspect all streams, especially `Data`.
3. Extract every embedded image format found in `Data`: at minimum PNG and JPEG. Do not assume screenshots are all PNG.
4. Use OCR only as navigation unless character-level boxes are available. Word-level OCR boxes are not precise enough for pixel edits.
5. Prefer Tesseract `makebox` character boxes over TSV word boxes.
6. Replace only the intended text occurrences. Check whether multiple old texts exist and whether the user asked to change all of them.
7. Preserve style by image type:
   - Terminal screenshots: use character-level glyph replacement from existing glyphs in the same image/line where possible.
   - UI screenshots with small proportional text: redraw the whole field with a matching UI font instead of patching individual characters.
8. Do not modify topology diagrams, ordinary screenshots, or document body text unless the user explicitly asks for them.
9. After writing back, re-extract the images from the final `.doc` and validate the final artifact, not just intermediate files.
10. If any visual sample shows artifacts, stop and revise the method. Do not rationalize visible patch marks.

## Required Inputs

Before editing, determine:

- `OLD_TEXT`: the visible screenshot text to replace.
- `NEW_TEXT`: the replacement screenshot text.
- Document paths to process.
- Whether additional screenshot text, SSIDs, prompts, labels, filenames, or body text should also change.
- Whether old and new texts are equal length. Equal length is strongly preferred. If not equal length, use full-field redraw for UI text and template/glyph replacement for terminal text; never binary-replace variable-length text in `.doc`.

## Workflow

### 1. Inventory Documents

Run file inspection:

```bash
file *.doc
ls -lh
```

Confirm they are legacy "Composite Document File V2" `.doc` files before using the OLE workflow.

### 2. Backup and Work Directory

Create a work area:

```bash
mkdir -p work/screenshot_text_edit/{backup,input,extracted,edited,verify,samples}
cp -- *.doc work/screenshot_text_edit/backup/
cp -- *.doc work/screenshot_text_edit/input/
```

Never overwrite the backup.

### 3. Inspect All OLE Streams

Use `olefile` to inspect every stream. Count PNG, JPEG, old text ASCII, old text UTF-16LE, and obvious image signatures.

Important: a `.doc` can contain PNG plus JPEG in the same `Data` stream. Missing JPEGs is a common failure.

### 4. Extract Images

Extract:

- PNG spans: `\x89PNG\r\n\x1a\n` through `IEND\xaeB`\x82`
- JPEG spans: `\xff\xd8\xff` through a valid `\xff\xd9` accepted by Pillow

Record every span as `(doc, stream, index, start, end, format)`. The index and byte span are required for exact write-back.

Use the bundled script when possible:

```bash
python3 scripts/ole_image_text_editor.py extract --docs path/to/*.doc --work work/screenshot_text_edit
```

### 5. OCR With Character Boxes

Use Tesseract `makebox` first:

```bash
tesseract image.png stdout -l eng+chi_sim --psm 6 makebox
```

Convert coordinates carefully:

- `makebox` origin is bottom-left.
- Pillow origin is top-left.
- Convert with `top = image_h - y1`, `bottom = image_h - y0`.

Find exact consecutive character sequences matching `OLD_TEXT`. Reject a sequence if boxes are not on the same line.

Use TSV word boxes only for discovery, never as final cutting boxes.

### 6. Terminal Screenshot Replacement

For terminal screenshots:

1. Use `makebox` to locate each character of `OLD_TEXT`.
2. Build a source map from old characters found in the same sequence.
3. For each position where `OLD_TEXT[i] != NEW_TEXT[i]`:
   - erase the destination glyph using local background sampling;
   - paste a soft foreground mask from the source glyph for `NEW_TEXT[i]`;
   - keep the destination character box size and position.
4. If the required source character does not exist in the same text sequence, choose the nearest same-style character from the same image using height, width, and y-position. If none exists, stop and create a manual/template solution.

Do not paste whole rectangular cells when the terminal background has gradients or compression noise; whole-cell paste can create blocks.

### 7. UI Screenshot Replacement

For UI screenshots such as Phone/Wi-Fi configuration windows:

1. Do not patch individual characters if the text is small and proportional.
2. Cover the entire text field or SSID text area with the local row background.
3. Redraw the full string (`henu-NEW_TEXT`, etc.) using a matching UI font, size, color, and baseline.
4. Create preview variants if needed. Compare visually before write-back.

Recommended macOS fonts to try:

- Arial 11-13 px for small HCL UI table text.
- Helvetica 11-13 px for macOS-like UI text.
- Use gray around `(70,70,70)` for table content, not pure black.

### 8. Write Back Without Changing Span Length

Edited image bytes must not exceed the original image span length.

- For PNG: try RGBA, RGB, and quantized PNG variants with `optimize=True` and compression levels.
- For JPEG: lower quality gradually and use `optimize=True`.
- If edited data is shorter, pad with `\x00` to preserve span length.
- If edited data cannot fit, stop and choose a less invasive edit or convert strategy. Do not truncate.

### 9. Validate Final `.doc`

Validation must run on the final written `.doc`:

1. Re-open OLE and confirm `WordDocument` and `Data` exist.
2. Re-count PNG and JPEG images; counts must match the pre-edit inventory.
3. Re-extract all images from the final `.doc`.
4. OCR all final images:
   - `OLD_TEXT` should be zero unless intentionally left.
   - `NEW_TEXT` should appear where expected.
   - search for partial, malformed, truncated, or previous unrelated screenshot text.
5. Generate visual samples/contact sheets for:
   - all changed images;
   - all OCR suspicious images;
   - at least one terminal top prompt, bottom prompt, long interface prompt, and UI screenshot.
6. Run Quick Look:

```bash
qlmanage -t -s 1200 -o work/screenshot_text_edit/ql_output final.doc
```

Only deliver when all checks pass.

## Pitfalls From Real Use

Read [references/pitfalls.md](references/pitfalls.md) before editing a document with mixed screenshots or after any failed visual check.

## Bundled Script

Use [scripts/ole_image_text_editor.py](scripts/ole_image_text_editor.py) for a generic starting point. It is intentionally conservative and may require document-specific UI field coordinates. Read and adapt it before use.
