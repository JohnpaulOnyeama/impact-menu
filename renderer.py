from __future__ import annotations

import os
import math
import random
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# -------------------------
# Paths (Streamlit-safe)
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_ROOT = os.path.join(BASE_DIR, "assets")

FONT_DIR = os.path.join(ASSET_ROOT, "fonts")
BG_DIR = os.path.join(ASSET_ROOT, "backgrounds")
CROP_DIR = os.path.join(ASSET_ROOT, "crops")

# -------------------------
# Public constants
# -------------------------
PARISH_LIST = ["Clarendon", "Manchester", "St. Elizabeth", "Westmoreland"]

DOMINANT_CROP = {
    "Clarendon": "hot_pepper",
    "Manchester": "carrot",
    "St. Elizabeth": "escallion",
    "Westmoreland": "banana",
}

CROP_DISPLAY = {
    "sweet_potato": "Sweet Potato",
    "irish_potato": "Irish Potato",
    "hot_pepper": "Hot Pepper",
    "carrot": "Carrot",
    "banana": "Banana",
    "escallion": "Escallion",
}

# -------------------------
# Simple economics (EDIT THESE)
# -------------------------
GBP_TO_JMD = 200.0  # rough; for display only
COST_PER_ACRE_GBP = 1400.0  # tune from your plan
COST_PER_FARMER_GBP = 2800.0  # tune from your plan

# Parish remaining need (EDIT THESE)
REMAINING_ACRES = {
    "Clarendon": 50.0,
    "Manchester": 50.0,
    "St. Elizabeth": 50.0,
    "Westmoreland": 50.0,
}

# Yield/value model (EDIT THESE)
# yield_kg_per_acre and value_gbp_per_kg are rough placeholders.
CROP_MODEL = {
    "sweet_potato": {"yield_kg_per_acre": 6800, "value_gbp_per_kg": 0.65},
    "irish_potato": {"yield_kg_per_acre": 5800, "value_gbp_per_kg": 0.85},
    "hot_pepper": {"yield_kg_per_acre": 2200, "value_gbp_per_kg": 3.00},
    "carrot": {"yield_kg_per_acre": 6000, "value_gbp_per_kg": 1.10},
    "banana": {"yield_kg_per_acre": 9000, "value_gbp_per_kg": 0.55},
    "escallion": {"yield_kg_per_acre": 4200, "value_gbp_per_kg": 1.70},
}

# Crop allocation weights (dominant crop gets more, potatoes always included)
ALLOC_WEIGHTS = {
    "dominant": 0.40,
    "sweet_potato": 0.35,
    "irish_potato": 0.25,
}

# -------------------------
# Canvas & render quality
# -------------------------
TARGET_W, TARGET_H = 1080, 1350     # output PNG size
SCALE = 2                            # internal render scale for crisp text
W, H = TARGET_W * SCALE, TARGET_H * SCALE

# Theme colors
BG_PAPER = (244, 241, 234)
GREEN = (21, 67, 49)   # deep green
GREEN_2 = (30, 90, 63)
TEXT_DARK = (22, 22, 22)
TEXT_MUTED = (92, 92, 92)

# -------------------------
# Data types
# -------------------------
@dataclass
class CropImpact:
    key: str
    acres: float
    value_gbp: float

@dataclass
class Impact:
    donation_gbp: float
    parish: str
    acres_restored: float
    farmers_supported: float
    crops: List[CropImpact]
    projected_value_gbp: float


# -------------------------
# Formatting helpers
# -------------------------
def fmt_gbp(x: float) -> str:
    return f"£{int(round(x)):,}"

def fmt_acres(x: float) -> str:
    if x < 1:
        return f"{x:.1f} acres"
    return f"{x:.0f} acres" if x >= 10 else f"{x:.1f} acres"

def clamp(a, lo, hi):
    return max(lo, min(hi, a))

# -------------------------
# Font loading (no crashes)
# -------------------------
def _font_path(name: str) -> str:
    return os.path.join(FONT_DIR, name)

def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None

def load_fonts() -> Dict[str, str]:
    if not os.path.isdir(FONT_DIR):
        return {}

    playfair = {
        "reg": _first_existing([
            _font_path("PlayfairDisplay-Regular.ttf"),
        ]),
        "semibold": _first_existing([
            _font_path("PlayfairDisplay-SemiBold.ttf"),
            _font_path("PlayfairDisplay-Bold.ttf"),
        ]),
        "bold": _first_existing([
            _font_path("PlayfairDisplay-Bold.ttf"),
            _font_path("PlayfairDisplay-ExtraBold.ttf"),
        ]),
    }

    inter = {
        "reg": _first_existing([
            _font_path("Inter_24pt-Regular.ttf"),
            _font_path("Inter_18pt-Regular.ttf"),
        ]),
        "semibold": _first_existing([
            _font_path("Inter_24pt-SemiBold.ttf"),
            _font_path("Inter_18pt-SemiBold.ttf"),
        ]),
        "bold": _first_existing([
            _font_path("Inter_24pt-Bold.ttf"),
            _font_path("Inter_18pt-Bold.ttf"),
        ]),
        "xbold": _first_existing([
            _font_path("Inter_24pt-ExtraBold.ttf"),
            _font_path("Inter_18pt-ExtraBold.ttf"),
        ]),
    }

    # keep only those found
    out = {}
    for k, v in playfair.items():
        if v: out[f"playfair_{k}"] = v
    for k, v in inter.items():
        if v: out[f"inter_{k}"] = v
    return out

FONTS = load_fonts()

def _ttf(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    # fallback to default bitmap font if not found
    if not path or (not os.path.isfile(path)):
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)

def f_playfair(size: int, weight="reg"):
    return _ttf(FONTS.get(f"playfair_{weight}"), size)

def f_inter(size: int, weight="reg"):
    return _ttf(FONTS.get(f"inter_{weight}"), size)


# -------------------------
# Text layout helpers (prevents overflow)
# -------------------------
def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> List[str]:
    words = text.split()
    lines = []
    cur = []
    for w in words:
        trial = " ".join(cur + [w])
        tw = draw.textbbox((0, 0), trial, font=font)[2]
        if tw <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines

def fit_font_size(draw: ImageDraw.ImageDraw, text: str, font_fn, max_w: int, max_h: int,
                  start: int, min_size: int, line_gap: int) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    size = start
    while size >= min_size:
        font = font_fn(size)
        lines = wrap_text(draw, text, font, max_w)
        line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
        total_h = len(lines) * line_h + (len(lines) - 1) * line_gap
        widest = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines) if lines else 0
        if widest <= max_w and total_h <= max_h:
            return font, lines, line_h
        size -= 1
    font = font_fn(min_size)
    lines = wrap_text(draw, text, font, max_w)
    line_h = draw.textbbox((0, 0), "Ag", font=font)[3]
    return font, lines, line_h

def draw_text_block(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int],
                    text: str, font_fn, start_size: int, min_size: int,
                    fill=(255,255,255), line_gap=8, align="left",
                    shadow: Optional[Dict]=None):
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    max_h = y1 - y0
    font, lines, line_h = fit_font_size(draw, text, font_fn, max_w, max_h, start_size, min_size, line_gap)

    total_h = len(lines) * line_h + (len(lines) - 1) * line_gap
    y = y0 + (max_h - total_h)//2

    for ln in lines:
        tw = draw.textbbox((0, 0), ln, font=font)[2]
        if align == "center":
            x = x0 + (max_w - tw)//2
        elif align == "right":
            x = x1 - tw
        else:
            x = x0

        if shadow:
            draw.text((x + shadow.get("dx", 2), y + shadow.get("dy", 2)), ln, font=font, fill=shadow.get("fill", (0,0,0,150)))
        draw.text((x, y), ln, font=font, fill=fill)
        y += line_h + line_gap


# -------------------------
# Image helpers
# -------------------------
def safe_open_image(path: str) -> Optional[Image.Image]:
    try:
        if path and os.path.isfile(path):
            return Image.open(path).convert("RGB")
    except:
        return None
    return None

def center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    w, h = img.size
    scale = max(target_w / w, target_h / h)
    nw, nh = int(w * scale), int(h * scale)
    img2 = img.resize((nw, nh), Image.Resampling.LANCZOS)
    x0 = (nw - target_w) // 2
    y0 = (nh - target_h) // 2
    return img2.crop((x0, y0, x0 + target_w, y0 + target_h))

def hero_left_gradient(base: Image.Image, hero_h: int):
    # darken left/top for text readability
    overlay = Image.new("RGBA", (W, hero_h), (0,0,0,0))
    px = overlay.load()
    for y in range(hero_h):
        for x in range(W):
            # stronger on left, subtle on top
            a = int(170 * (1 - x / (W * 0.75)))
            a = max(0, min(170, a))
            top = int(35 * (1 - y / hero_h))
            a = max(a, top)
            px[x, y] = (0,0,0,a)
    base.paste(overlay, (0,0), overlay)

def rounded_panel(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def pick_image(folder: str, keys: List[str], used: set) -> Optional[Image.Image]:
    """
    Try keys in order; avoid duplicates using `used` set.
    Looks for jpg/jpeg/png.
    """
    exts = [".jpg", ".jpeg", ".png", ".webp"]
    for k in keys:
        for ext in exts:
            p = os.path.join(folder, k + ext)
            if p in used:
                continue
            img = safe_open_image(p)
            if img is not None:
                used.add(p)
                return img
    return None


# -------------------------
# Impact calculation
# -------------------------
def choose_parish(donation: float) -> str:
    # simple rule: pick the parish with the most remaining need
    return max(REMAINING_ACRES.items(), key=lambda kv: kv[1])[0]

def compute_impact(donation_gbp: float, parish: Optional[str]) -> Impact:
    parish_final = parish if parish in PARISH_LIST else choose_parish(donation_gbp)

    acres = donation_gbp / COST_PER_ACRE_GBP
    acres = min(acres, REMAINING_ACRES.get(parish_final, acres))
    acres = max(0.0, acres)

    farmers = donation_gbp / COST_PER_FARMER_GBP
    farmers = max(0.0, farmers)

    dom = DOMINANT_CROP[parish_final]

    # always include potatoes + dominant
    weights = [
        ("sweet_potato", ALLOC_WEIGHTS["sweet_potato"]),
        ("irish_potato", ALLOC_WEIGHTS["irish_potato"]),
        (dom, ALLOC_WEIGHTS["dominant"]),
    ]
    s = sum(w for _, w in weights)
    crops = []
    total_value = 0.0
    for ck, w in weights:
        a = acres * (w / s)
        model = CROP_MODEL[ck]
        v = a * model["yield_kg_per_acre"] * model["value_gbp_per_kg"]
        crops.append(CropImpact(key=ck, acres=a, value_gbp=v))
        total_value += v

    return Impact(
        donation_gbp=donation_gbp,
        parish=parish_final,
        acres_restored=acres,
        farmers_supported=farmers,
        crops=crops,
        projected_value_gbp=total_value,
    )


# -------------------------
# Copy (stronger, parish-aware)
# -------------------------
def hero_subline(parish: str) -> str:
    if parish == "Clarendon":
        return "Rapid replanting support so farmers can earn again and keep food moving to markets."
    if parish == "Manchester":
        return "Rebuilding damaged farmland so local farmers can harvest again within one season."
    if parish == "St. Elizabeth":
        return "Restoring a key food region so families and markets recover together."
    if parish == "Westmoreland":
        return "Stabilising farms after crop loss so families can return to production."
    return "Helping farmers return to work and rebuild food production after Hurricane Melissa."

def why_matters(parish: str) -> str:
    if parish == "Clarendon":
        return ("Hurricane damage has disrupted planting schedules and household income. Without immediate support, "
                "farmers miss the season and communities face higher food costs. This package helps farmers replant quickly "
                "and restart cash flow.")
    if parish == "Manchester":
        return ("Severe land damage has left farmers unable to plant for the upcoming season. Without rapid support, "
                "families lose income for an entire year. This recovery enables farmers to replant in time for the next harvest cycle.")
    if parish == "St. Elizabeth":
        return ("St Elizabeth supplies food across Jamaica. When land is damaged, farmers lose income and communities lose stable supply. "
                "This recovery supports fast replanting so the next harvest arrives on time.")
    if parish == "Westmoreland":
        return ("Crop loss and land damage threaten both food supply and household income. This package supports fast recovery and replanting "
                "so farmers can harvest again and rebuild livelihoods.")
    return "This package restores farmland and supports farming families to return to work."

def crop_blurb(ck: str) -> str:
    return {
        "sweet_potato": "Staple crop that improves household resilience and food access.",
        "irish_potato": "Quick market crop supporting cash flow and household income.",
        "hot_pepper": "High-value market crop that restores income and local trade quickly.",
        "carrot": "Primary market crop strengthening local supply chains and income stability.",
        "banana": "Longer-horizon income crop rebuilding stability for families and markets.",
        "escallion": "High-demand crop supporting stable supply and stronger local markets.",
    }[ck]


# -------------------------
# Main renderer (PNG)
# -------------------------
def render_impact_menu_png(donation_gbp: float, parish: Optional[str] = None) -> Tuple[bytes, Impact]:
    imp = compute_impact(donation_gbp, parish)

    # Canvas
    base = Image.new("RGB", (W, H), BG_PAPER)
    draw = ImageDraw.Draw(base)

    # Hero image
    hero_h = int(0.36 * H)
    used = set()

    # background choice priority: parish-specific -> generic
    hero_img = pick_image(BG_DIR, [f"hero_{imp.parish.lower().replace(' ','_')}", "hero_generic"], used)
    if hero_img is None:
        # fallback: soft gradient background
        hero = Image.new("RGB", (W, hero_h), (40, 50, 45))
    else:
        hero = center_crop(hero_img, W, hero_h)

    base.paste(hero, (0, 0))

    # Dark gradient for text readability
    hero_left_gradient(base, hero_h)

    # Extra blurred panel behind headline for consistent legibility
    overlay = Image.new("RGBA", (W, hero_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        (55*SCALE, 45*SCALE, int(0.94*W), hero_h-70*SCALE),
        radius=28*SCALE,
        fill=(0, 0, 0, 90)
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(10*SCALE))
    base.paste(overlay, (0, 0), overlay)

    # Headline
    headline = f"{fmt_gbp(imp.donation_gbp)} restores farms, livelihoods,\nand the next harvest in {imp.parish}"
    draw_text_block(
        draw,
        (70*SCALE, 55*SCALE, int(0.94*W), int(hero_h*0.72)),
        headline,
        lambda s: f_playfair(s, "bold"),
        start_size=64*SCALE,
        min_size=40*SCALE,
        fill=(255,255,255),
        line_gap=10*SCALE,
        align="left",
        shadow={"dx":2*SCALE, "dy":2*SCALE, "fill":(0,0,0,170)}
    )

    # Subline
    draw_text_block(
        draw,
        (70*SCALE, int(hero_h*0.73), int(0.94*W), hero_h-20*SCALE),
        hero_subline(imp.parish),
        lambda s: f_inter(s, "reg"),
        start_size=26*SCALE,
        min_size=20*SCALE,
        fill=(235,235,235),
        line_gap=6*SCALE,
        align="left",
        shadow={"dx":2*SCALE, "dy":2*SCALE, "fill":(0,0,0,120)}
    )

    # Panels start
    y = hero_h + 26*SCALE

    # Why matters panel
    why_box = (55*SCALE, y, W-55*SCALE, y + 185*SCALE)
    rounded_panel(draw, why_box, radius=26*SCALE, fill=(249, 247, 242), outline=(215, 208, 195), width=2)
    # Title
    draw_text_block(
        draw, (why_box[0]+28*SCALE, why_box[1]+18*SCALE, why_box[2]-28*SCALE, why_box[1]+62*SCALE),
        "Why this matters",
        lambda s: f_playfair(s, "semibold"),
        start_size=34*SCALE, min_size=28*SCALE,
        fill=TEXT_DARK, line_gap=6*SCALE, align="left"
    )
    # divider
    draw.line((why_box[0]+300*SCALE, why_box[1]+56*SCALE, why_box[2]-30*SCALE, why_box[1]+56*SCALE), fill=(190, 180, 165), width=2)
    # Body
    draw_text_block(
        draw, (why_box[0]+28*SCALE, why_box[1]+70*SCALE, why_box[2]-28*SCALE, why_box[3]-18*SCALE),
        why_matters(imp.parish),
        lambda s: f_inter(s, "reg"),
        start_size=22*SCALE, min_size=18*SCALE,
        fill=(40,40,40), line_gap=6*SCALE, align="left"
    )

    y = why_box[3] + 22*SCALE

    # KPI band
    kpi_box = (55*SCALE, y, W-55*SCALE, y + 165*SCALE)
    rounded_panel(draw, kpi_box, radius=28*SCALE, fill=GREEN, outline=None, width=0)

    # band header
    draw_text_block(
        draw,
        (kpi_box[0]+30*SCALE, kpi_box[1]+18*SCALE, kpi_box[2]-30*SCALE, kpi_box[1]+60*SCALE),
        f"What your {fmt_gbp(imp.donation_gbp)} achieves:",
        lambda s: f_playfair(s, "semibold"),
        start_size=32*SCALE, min_size=26*SCALE,
        fill=(235, 240, 236),
        line_gap=6*SCALE,
        align="left"
    )
    draw.line((kpi_box[0]+280*SCALE, kpi_box[1]+60*SCALE, kpi_box[2]-30*SCALE, kpi_box[1]+60*SCALE),
              fill=(235,240,236,120), width=2)

    # KPIs
    col_w = (kpi_box[2]-kpi_box[0])//3
    cols = [
        ("Farmers supported", f"{math.floor(imp.farmers_supported):,} families" if imp.farmers_supported >= 2 else "1 family"),
        ("Land restored", fmt_acres(imp.acres_restored)),
        ("Crops replanted", ", ".join([CROP_DISPLAY[c.key] for c in imp.crops])),
    ]

    for i, (label, value) in enumerate(cols):
        x0 = kpi_box[0] + i*col_w + 30*SCALE
        x1 = kpi_box[0] + (i+1)*col_w - 30*SCALE
        # label
        draw_text_block(
            draw, (x0, kpi_box[1]+68*SCALE, x1, kpi_box[1]+98*SCALE),
            label,
            lambda s: f_inter(s, "semibold"),
            start_size=20*SCALE, min_size=16*SCALE,
            fill=(230, 238, 233),
            line_gap=4*SCALE,
            align="left"
        )
        # value
        draw_text_block(
            draw, (x0, kpi_box[1]+98*SCALE, x1, kpi_box[3]-16*SCALE),
            value,
            lambda s: f_playfair(s, "bold"),
            start_size=40*SCALE, min_size=22*SCALE,
            fill=(245, 248, 246),
            line_gap=6*SCALE,
            align="left"
        )
        if i < 2:
            vx = kpi_box[0] + (i+1)*col_w
            draw.line((vx, kpi_box[1]+70*SCALE, vx, kpi_box[3]-22*SCALE), fill=(255,255,255,90), width=3)

    y = kpi_box[3] + 22*SCALE

    # Crop cards
    card_h = 270*SCALE
    card_gap = 18*SCALE
    card_w = (W - 55*SCALE*2 - card_gap*2)//3

    crop_keys = [c.key for c in imp.crops]  # already dominant + potatoes
    crop_imgs_used = set()

    for i, ck in enumerate(crop_keys):
        cx0 = 55*SCALE + i*(card_w + card_gap)
        cx1 = cx0 + card_w
        cy0 = y
        cy1 = y + card_h

        rounded_panel(draw, (cx0, cy0, cx1, cy1), radius=22*SCALE, fill=(255,255,255), outline=(220, 212, 200), width=2)

        # image area
        img_h = 140*SCALE
        img = pick_image(CROP_DIR, [ck], crop_imgs_used)
        if img is None:
            # fallback neutral placeholder
            ph = Image.new("RGB", (card_w, img_h), (230, 225, 215))
            base.paste(ph, (cx0, cy0))
        else:
            base.paste(center_crop(img, card_w, img_h), (cx0, cy0))

        # crop text
        crop_name = CROP_DISPLAY[ck]
        crop_acres = next(c.acres for c in imp.crops if c.key == ck)
        title_box = (cx0+18*SCALE, cy0+img_h+14*SCALE, cx1-18*SCALE, cy0+img_h+60*SCALE)
        draw_text_block(
            draw, title_box,
            crop_name,
            lambda s: f_playfair(s, "semibold"),
            start_size=30*SCALE, min_size=22*SCALE,
            fill=TEXT_DARK, line_gap=4*SCALE, align="left"
        )

        acres_box = (cx0+18*SCALE, cy0+img_h+62*SCALE, cx1-18*SCALE, cy0+img_h+92*SCALE)
        draw_text_block(
            draw, acres_box,
            f"{fmt_acres(crop_acres)} restored",
            lambda s: f_inter(s, "semibold"),
            start_size=18*SCALE, min_size=16*SCALE,
            fill=(30,30,30), line_gap=4*SCALE, align="left"
        )

        blurb_box = (cx0+18*SCALE, cy0+img_h+92*SCALE, cx1-18*SCALE, cy1-16*SCALE)
        draw_text_block(
            draw, blurb_box,
            crop_blurb(ck),
            lambda s: f_inter(s, "reg"),
            start_size=16*SCALE, min_size=14*SCALE,
            fill=TEXT_MUTED, line_gap=5*SCALE, align="left"
        )

    y = y + card_h + 22*SCALE

    # Value band (final panel)
    val_box = (55*SCALE, y, W-55*SCALE, y + 130*SCALE)
    rounded_panel(draw, val_box, radius=26*SCALE, fill=(249, 247, 242), outline=(220, 212, 200), width=2)

    # left label
    draw_text_block(
        draw, (val_box[0]+30*SCALE, val_box[1]+22*SCALE, val_box[0]+320*SCALE, val_box[3]-22*SCALE),
        "Projected impact value",
        lambda s: f_inter(s, "reg"),
        start_size=18*SCALE, min_size=16*SCALE,
        fill=(55,55,55), line_gap=4*SCALE, align="left"
    )
    # big value
    draw_text_block(
        draw, (val_box[0]+320*SCALE, val_box[1]+16*SCALE, val_box[0]+720*SCALE, val_box[3]-16*SCALE),
        f"≈ {fmt_gbp(imp.projected_value_gbp)}",
        lambda s: f_playfair(s, "bold"),
        start_size=52*SCALE, min_size=38*SCALE,
        fill=TEXT_DARK, line_gap=6*SCALE, align="center"
    )
    # right copy
    draw_text_block(
        draw, (val_box[0]+740*SCALE, val_box[1]+20*SCALE, val_box[2]-30*SCALE, val_box[3]-20*SCALE),
        "in harvest value, returning over\n8× the original donation to local\nfarmers and markets.",
        lambda s: f_inter(s, "reg"),
        start_size=16*SCALE, min_size=14*SCALE,
        fill=(70,70,70), line_gap=5*SCALE, align="left"
    )

    # Done — downsample for crisp output
    out = base.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    bio = BytesIO()
    out.save(bio, format="PNG", optimize=True)
    return bio.getvalue(), imp