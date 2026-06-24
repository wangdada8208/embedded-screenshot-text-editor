# Pitfalls

## Do Not Assume All Images Are PNG

Legacy `.doc` files can store screenshots as both PNG and JPEG in the OLE `Data` stream. A workflow that extracts only PNGs can miss entire screenshots. Always scan for PNG and JPEG signatures and validate extracted images with Pillow.

## Word-Level OCR Boxes Cause Visible Artifacts

Tesseract TSV boxes often cover an entire token such as:

```text
[SW-OLD_TEXT-GigabitEthernet1/0/1]dis
```

Cutting a substring out of that word box by proportional math can shift by half a character. The result is wrong characters, doubled characters, or malformed text. Use `makebox` character boxes.

## Whole-Cell Copy Can Create Background Blocks

Terminal screenshots often have non-uniform black backgrounds, JPEG compression, or subtle gradients. Pasting a whole source character rectangle into another position can create a visible block. Prefer:

1. erase destination glyph using sampled local background;
2. paste source glyph foreground through a soft mask;
3. leave destination background intact.

## Small UI Text Should Be Redrawn as a Whole Field

Phone/Wi-Fi UI table text uses proportional small UI fonts. Patching individual characters usually looks fake. Cover the complete SSID/text field and redraw the full string using a consistent font, size, color, and baseline.

## Required Digit May Not Exist in the Same Old text

When changing one ID to another, the new text may require a character not present in the old text. Choose a matching source character from the same image if possible. Match height, width, row, and rendering style. If no good source exists, use full-field redraw or manual template repair.

## OCR Can Miss Visual Problems

An OCR result of "old text zero" does not guarantee the image looks real. Always inspect changed samples. Conversely, OCR may truncate a visually correct string. Treat suspicious OCR as a prompt for visual inspection, not an automatic failure.

## Check Every Old text Variant the User Mentions

A folder may contain more than one old text in screenshots: terminal prompts, SSIDs, filename/body text, or stale sample labels. Ask or infer scope carefully, then validate all requested old texts.

## Do Not Leak Personal Information Into Skills

Skills must be reusable. Do not store real personal identifiers, names, document filenames, local project paths, screenshots, or keys. Use placeholders such as `OLD_TEXT`, `NEW_TEXT`, `input.doc`, and `work/screenshot_text_edit`.
