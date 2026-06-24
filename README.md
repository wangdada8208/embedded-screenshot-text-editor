# Embedded Screenshot Text Editor

A Codex skill for high-fidelity text editing inside screenshots embedded in legacy Word `.doc` files.

This skill is designed for fragile document-editing tasks where visible screenshot text must be changed without leaving obvious artifacts. It was built around network-lab style Word reports that contain terminal screenshots, Wi-Fi/Phone UI screenshots, and mixed PNG/JPEG images stored inside OLE `Data` streams.

## What It Helps With

- Replace visible text inside embedded screenshots.
- Handle legacy binary Word `.doc` files.
- Extract and write back embedded PNG and JPEG images.
- Use character-level OCR boxes for terminal-style screenshots.
- Redraw small UI text fields when glyph patching would look fake.
- Validate the final `.doc` after write-back, not only intermediate images.

Typical targets include:

- terminal prompts
- SSIDs
- device names
- command output labels
- numeric identifiers
- MAC-like or IP-like strings
- small UI table text

## Why This Exists

Naive screenshot patching usually fails in subtle ways:

- OCR word boxes are too coarse for per-character edits.
- Pasting full rectangles creates visible background blocks.
- Small proportional UI fonts look fake when edited digit-by-digit.
- Legacy `.doc` files may contain both PNG and JPEG screenshots.
- A final Word document can differ from intermediate extracted images after compression and write-back.

This skill captures a stricter workflow: inspect all image formats, use character-level OCR where possible, choose the right repair method for the image type, and validate the final artifact.

## Installation

Clone or copy this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/wangdada8208/embedded-screenshot-text-editor.git \
  ~/.codex/skills/embedded-screenshot-text-editor
```

Then invoke it in Codex with:

```text
$embedded-screenshot-text-editor
```

## Dependencies

The workflow may use:

- Python 3
- Pillow
- olefile
- Tesseract OCR
- macOS `qlmanage` for Quick Look validation

Install Python dependencies when needed:

```bash
python3 -m pip install Pillow olefile
```

Install Tesseract separately, for example on macOS:

```bash
brew install tesseract
```

For Chinese/English screenshots, make sure the needed OCR language data is available, such as `eng` and `chi_sim`.

## Repository Layout

```text
embedded-screenshot-text-editor/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── pitfalls.md
└── scripts/
    └── ole_image_text_editor.py
```

## Script Usage

The bundled script is a conservative starting point. It supports equal-length text replacement in extracted OLE images.

Extract images:

```bash
python3 scripts/ole_image_text_editor.py extract \
  --docs input.doc \
  --work work/screenshot_text_edit
```

Edit equal-length text:

```bash
python3 scripts/ole_image_text_editor.py edit \
  --work work/screenshot_text_edit \
  --old-text OLD_TEXT \
  --new-text NEW_TEXT
```

Write edited images back to `.doc` copies:

```bash
python3 scripts/ole_image_text_editor.py write-back \
  --docs input.doc \
  --work work/screenshot_text_edit
```

Outputs are written under:

```text
work/screenshot_text_edit/output/
```

## Important Limitations

- The script is not a blind one-command solution.
- It only handles equal-length text replacement.
- It is best suited to terminal-like glyph edits.
- UI screenshots often need full-field redraw rather than per-character replacement.
- Some documents require document-specific coordinates or manual visual review.
- Always inspect changed samples before delivery.

## Required Validation

Before considering a result complete:

1. Backup originals.
2. Extract every embedded image format, including PNG and JPEG.
3. Apply edits only to intended occurrences.
4. Write images back without changing original span lengths.
5. Re-extract images from the final `.doc`.
6. OCR the final images for old text, new text, and malformed remnants.
7. Inspect visual samples for artifacts.
8. Confirm the final document opens or previews correctly.

## Contributors

- [moxiao-hash](https://github.com/moxiao-hash) - workflow feedback and validation

## License

MIT License. See [LICENSE](LICENSE).
