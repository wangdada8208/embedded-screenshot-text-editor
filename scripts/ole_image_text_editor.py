#!/usr/bin/env python3
"""Conservative helper for replacing equal-length screenshot text in OLE .doc images.

This is a reusable starting point, not a blind one-command solution. It extracts
PNG/JPEG images from the OLE Data stream, uses Tesseract makebox character boxes
to locate exact OLD_TEXT sequences, edits terminal-like glyphs with a soft mask,
and writes images back without changing span length.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_END = b"IEND\xaeB`\x82"
JPG_SIG = b"\xff\xd8\xff"
JPG_END = b"\xff\xd9"


@dataclass
class Span:
    doc: Path
    index: int
    fmt: str
    start: int
    end: int
    path: Path


def luma(p):
    return (p[0] + p[1] + p[2]) / 3


def median(vals):
    vals = sorted(vals)
    return vals[len(vals) // 2] if vals else 0


def png_spans(data):
    pos = 0
    while True:
        s = data.find(PNG_SIG, pos)
        if s < 0:
            break
        e = data.find(PNG_END, s)
        if e < 0:
            break
        e += len(PNG_END)
        yield s, e
        pos = e


def jpeg_spans(data):
    pos = 0
    while True:
        s = data.find(JPG_SIG, pos)
        if s < 0:
            break
        e = s + 2
        found = False
        while True:
            e = data.find(JPG_END, e)
            if e < 0:
                break
            e2 = e + 2
            raw = data[s:e2]
            try:
                Image.open(io.BytesIO(raw)).verify()
                yield s, e2
                pos = e2
                found = True
                break
            except Exception:
                e = e2
        if not found:
            pos = s + 3


def extract_docs(docs, work: Path):
    try:
        import olefile
    except ImportError as exc:
        raise SystemExit("Install olefile first: python3 -m pip install olefile") from exc
    out = work / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for doc in docs:
        ole = olefile.OleFileIO(doc)
        data = ole.openstream("Data").read()
        ole.close()
        doc_dir = out / doc.stem
        doc_dir.mkdir(parents=True, exist_ok=True)
        idx = 0
        for fmt, spans in (("png", png_spans(data)), ("jpg", jpeg_spans(data))):
            for start, end in spans:
                path = doc_dir / f"{idx:03d}_{start}_{end}.{fmt}"
                path.write_bytes(data[start:end])
                manifest.append({"doc": str(doc), "index": idx, "fmt": fmt, "start": start, "end": end, "path": str(path)})
                idx += 1
        print(doc.name, "images", idx)
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def makebox(path: Path, image_h: int):
    proc = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", "eng+chi_sim", "--psm", "6", "makebox"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    boxes = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            x0, y0, x1, y1 = map(int, parts[1:5])
        except ValueError:
            continue
        boxes.append({"ch": parts[0], "rect": (x0, image_h - y1, x1, image_h - y0)})
    return boxes


def find_sequences(boxes, old_text: str):
    chars = [b["ch"] for b in boxes]
    seqs = []
    n = len(old_text)
    for i in range(0, len(chars) - n + 1):
        if "".join(chars[i : i + n]) != old_text:
            continue
        rects = [boxes[j]["rect"] for j in range(i, i + n)]
        if max(r[1] for r in rects) - min(r[1] for r in rects) <= 8:
            seqs.append(rects)
    return seqs


def bg_color(im, rect):
    x0, y0, x1, y1 = rect
    pix = []
    for y in range(max(0, y0), min(im.height, y1)):
        for x in range(max(0, x0), min(im.width, x1)):
            p = im.getpixel((x, y))
            if luma(p) < 95:
                pix.append(p)
    if not pix:
        pix = [im.getpixel((x, y)) for y in range(max(0, y0), min(im.height, y1)) for x in range(max(0, x0), min(im.width, x1))]
    return tuple(int(median([p[i] for p in pix])) for i in range(3)) + (255,)


def erase_glyph(out, rect):
    x0, y0, x1, y1 = rect
    rect = (max(0, x0 - 1), max(0, y0 - 1), min(out.width, x1 + 1), min(out.height, y1 + 1))
    bg = bg_color(out, rect)
    bg_l = luma(bg)
    patch = out.crop(rect)
    new = []
    for p in patch.getdata():
        new.append(bg if luma(p) > bg_l + 18 else p)
    patch.putdata(new)
    out.paste(patch, rect[:2])


def paste_glyph(out, original, src_rect, dst_rect):
    src = original.crop(src_rect)
    dw, dh = dst_rect[2] - dst_rect[0], dst_rect[3] - dst_rect[1]
    if src.size != (dw, dh):
        src = src.resize((max(1, dw), max(1, dh)), Image.Resampling.LANCZOS)
    dst = out.crop(dst_rect)
    bg = bg_color(original, src_rect)
    bg_l = luma(bg)
    mixed = []
    for s, d in zip(src.getdata(), dst.getdata()):
        alpha = max(0, min(255, int(max(0, luma(s) - bg_l) / 95 * 255)))
        mixed.append(d if alpha < 16 else tuple(int((s[i] * alpha + d[i] * (255 - alpha)) / 255) for i in range(3)) + (255,))
    dst.putdata(mixed)
    out.paste(dst, dst_rect[:2])


def edit_image(path: Path, old_text: str, new_text: str, out_path: Path):
    if len(old_text) != len(new_text):
        raise ValueError("This helper only supports equal-length text replacement. Use full-field redraw for variable length.")
    im = Image.open(path).convert("RGBA")
    boxes = makebox(path, im.height)
    seqs = find_sequences(boxes, old_text)
    if not seqs:
        return 0
    out = im.copy()
    changes = 0
    for rects in seqs:
        sources = {}
        for i, ch in enumerate(old_text):
            sources.setdefault(ch, rects[i])
        for i, (old, new) in enumerate(zip(old_text, new_text)):
            if old == new:
                continue
            src = sources.get(new)
            if not src:
                raise RuntimeError(f"Need character {new!r} but no same-sequence source exists in {path}")
            erase_glyph(out, rects[i])
            paste_glyph(out, im, src, rects[i])
            changes += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        out.convert("RGB").save(out_path, format="JPEG", quality=95)
    else:
        out.save(out_path)
    return changes


def fit_image(path: Path, fmt: str, target_len: int):
    im = Image.open(path)
    if fmt == "jpg":
        rgb = im.convert("RGB")
        for quality in range(95, 20, -2):
            bio = io.BytesIO()
            rgb.save(bio, format="JPEG", quality=quality, optimize=True)
            data = bio.getvalue()
            if len(data) <= target_len:
                return data + b"\x00" * (target_len - len(data))
    else:
        rgba = im.convert("RGBA")
        rgb = rgba.convert("RGB")
        variants = [rgba, rgb] + [rgb.quantize(colors=c) for c in (256, 128, 64, 32, 16)]
        for variant in variants:
            for optimize in (True, False):
                for level in range(9, -1, -1):
                    bio = io.BytesIO()
                    variant.save(bio, format="PNG", optimize=optimize, compress_level=level)
                    data = bio.getvalue()
                    if len(data) <= target_len:
                        return data + b"\x00" * (target_len - len(data))
    raise RuntimeError(f"Edited {fmt} does not fit original span length {target_len}")


def write_back(docs, work: Path):
    try:
        import olefile
    except ImportError as exc:
        raise SystemExit("Install olefile first: python3 -m pip install olefile") from exc
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    by_doc = {}
    for item in manifest:
        edited = work / "edited" / Path(item["path"]).relative_to(work / "extracted")
        if edited.exists():
            by_doc.setdefault(Path(item["doc"]), []).append((item, edited))
    for doc in docs:
        target = work / "output" / doc.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(doc, target)
        ole = olefile.OleFileIO(target, write_mode=True)
        data = ole.openstream("Data").read()
        for item, edited in sorted(by_doc.get(doc, []), key=lambda x: x[0]["start"]):
            start, end = item["start"], item["end"]
            data = data[:start] + fit_image(edited, item["fmt"], end - start) + data[end:]
        ole.write_stream("Data", data)
        ole.close()
        print("wrote", target)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract")
    ex.add_argument("--work", required=True)
    ex.add_argument("--docs", nargs="+", required=True)
    ed = sub.add_parser("edit")
    ed.add_argument("--work", required=True)
    ed.add_argument("--old-text", required=True)
    ed.add_argument("--new-text", required=True)
    wb = sub.add_parser("write-back")
    wb.add_argument("--work", required=True)
    wb.add_argument("--docs", nargs="+", required=True)
    args = parser.parse_args()
    work = Path(args.work)
    if args.cmd == "extract":
        extract_docs([Path(p) for p in args.docs], work)
    elif args.cmd == "edit":
        manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
        total = 0
        for item in manifest:
            src = Path(item["path"])
            dst = work / "edited" / src.relative_to(work / "extracted")
            try:
                total += edit_image(src, args.old_text, args.new_text, dst)
            except RuntimeError as exc:
                print(f"skip/manual-needed: {exc}", file=sys.stderr)
        print("glyph changes", total)
    elif args.cmd == "write-back":
        write_back([Path(p) for p in args.docs], work)


if __name__ == "__main__":
    main()
