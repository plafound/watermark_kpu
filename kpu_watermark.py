#!/usr/bin/env python3
import os
import pikepdf
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO

# ---------- CONFIG ----------
INPUT_DIR = "input_pdf"      # folder PDF input
OUTPUT_DIR = "wm_output"     # folder hasil
os.makedirs(OUTPUT_DIR, exist_ok=True)

WMAP = {
    "A4L": "wm_a4_landscape.png",
    "A4P": "wm_a4_portrait.png",
    "F4L": "wm_f4_landscape.png",
    "F4P": "wm_f4_portrait.png",
}

# rasio standar (tinggi / lebar)
A4_RATIO = 297.0 / 210.0     # ~1.414
F4_RATIO = 330.0 / 210.0     # ~1.571
RATIO_TOLERANCE = 0.04
# ----------------------------

def box_width_height(box):
    """Hitung lebar/tinggi dari MediaBox/CropBox"""
    x0 = float(box[0]); y0 = float(box[1])
    x1 = float(box[2]); y1 = float(box[3])
    return abs(x1 - x0), abs(y1 - y0)

def detect_page_size(page):
    """Deteksi A4/F4 + orientasi. Kalau gagal → fallback ke A4."""
    box = page.obj.get("/CropBox") or page.obj.get("/MediaBox") or page.MediaBox
    raw_w, raw_h = box_width_height(box)

    rotate = int(page.obj.get("/Rotate") or 0)
    eff_w, eff_h = (raw_h, raw_w) if rotate in (90, 270) else (raw_w, raw_h)

    ratio = max(eff_w, eff_h) / (min(eff_w, eff_h) or 1)

    # deteksi A4
    if abs(ratio - A4_RATIO) <= RATIO_TOLERANCE:
        return "A4P" if eff_h > eff_w else "A4L"
    # deteksi F4
    if abs(ratio - F4_RATIO) <= RATIO_TOLERANCE:
        return "F4P" if eff_h > eff_w else "F4L"

    # fallback → A4
    return "A4P" if eff_h > eff_w else "A4L"

def add_watermark_image(page, image_file):
    """Tempel watermark ke halaman, cover full tanpa distorsi"""
    from pikepdf import Pdf
    buf = BytesIO()

    # ambil ukuran halaman + rotasi
    box = page.obj.get("/CropBox") or page.obj.get("/MediaBox") or page.MediaBox
    raw_w, raw_h = box_width_height(box)
    rotate = int(page.obj.get("/Rotate") or 0)

    if rotate in (90, 270):
        page_w, page_h = raw_h, raw_w
    else:
        page_w, page_h = raw_w, raw_h

    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    # ambil ukuran watermark
    img = ImageReader(image_file)
    iw, ih = img.getSize()
    img_ratio = iw / ih
    page_ratio = page_w / page_h

    # mode COVER (selalu nutup halaman tanpa distorsi)
    if img_ratio > page_ratio:
        new_h = page_h
        new_w = page_h * img_ratio
    else:
        new_w = page_w
        new_h = page_w / img_ratio

    # center (boleh overflow)
    x = (page_w - new_w) / 2
    y = (page_h - new_h) / 2

    # --- DEBUG LOG ---
    print(f"     [DEBUG] Page {page_w:.1f}x{page_h:.1f} pt | "
          f"WM {iw}x{ih} px → scaled {new_w:.1f}x{new_h:.1f} pt | "
          f"pos=({x:.1f},{y:.1f})")

    c.drawImage(image_file, x, y, width=new_w, height=new_h,
                preserveAspectRatio=True, mask='auto')

    c.showPage()
    c.save()
    buf.seek(0)
    wm_pdf = Pdf.open(buf)
    wm_page = wm_pdf.pages[0]
    page.add_overlay(wm_page)

# ---------- MAIN ----------
for fname in os.listdir(INPUT_DIR):
    if not fname.lower().endswith(".pdf"):
        continue
    inpath = os.path.join(INPUT_DIR, fname)
    outpath = os.path.join(OUTPUT_DIR, fname)
    print(f"\n📄 Processing: {fname}")

    with pikepdf.open(inpath) as pdf:
        new_pdf = pikepdf.Pdf.new()
        for i, page in enumerate(pdf.pages, start=1):
            size = detect_page_size(page)
            if size and size in WMAP:
                wm_file = WMAP[size]
                print(f"   → Halaman {i}: {size} → pakai {wm_file}")
                add_watermark_image(page, wm_file)
            else:
                print(f"   → Halaman {i}: dilewati (tidak dikenali).")
            new_pdf.pages.append(page)
        new_pdf.save(outpath)

print("\n✅ Semua selesai! Cek folder:", OUTPUT_DIR)