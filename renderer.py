import os, math, random, glob
from dataclasses import dataclass
from typing import List, Tuple, Optional
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# ============================================================
# CONFIG
# ============================================================

# Render quality (supersampling)
SCALE = int(os.getenv("SCALE", "2"))  # 2 is good, 3 is crisper but slower
TARGET_IMPACT = (1080, 1400)
W, H = TARGET_IMPACT[0]*SCALE, TARGET_IMPACT[1]*SCALE

# Assets
ASSET_ROOT = os.getenv("ASSET_ROOT", "assets")
BG_DIR = os.path.join(ASSET_ROOT, "backgrounds")
CROP_DIR = os.path.join(ASSET_ROOT, "crops")
FARMER_DIR = os.path.join(ASSET_ROOT, "farmers")

# Colors
CREAM = (245, 242, 234)
PANEL = (250, 248, 242)
INK = (18, 18, 18)
MUTED = (78, 78, 78)
MID = (92, 92, 92)
BORDER = (224, 218, 204)
GREEN = (23, 63, 45)
GREEN_DARK = (16, 48, 35)
WHITE = (255, 255, 255)

# Plan constants (edit to match your plan)
TOTAL_PROJECT_COST_JMD = 56_557_890
TOTAL_PROJECT_ACRES = 200
TOTAL_PROJECT_FARMERS = 100
COST_PER_ACRE_JMD = TOTAL_PROJECT_COST_JMD / TOTAL_PROJECT_ACRES
ACRES_PER_FARMER = TOTAL_PROJECT_ACRES / TOTAL_PROJECT_FARMERS
FX_JMD_PER_GBP = 200.0

MICRO_ACRE_THRESHOLD = 0.25

# Parish + dominant crops (potatoes always included via shares)
PARISH_DOMINANT_CROP = {"Clarendon": "hot_pepper", "Westmoreland": "banana", "St. Elizabeth": "escallion", "Manchester": "carrot"}
PARISH_LIST = ["Manchester", "Clarendon", "St. Elizabeth", "Westmoreland"]

SHARE_SWEET_POTATO = 0.45
SHARE_IRISH_POTATO = 0.15
SHARE_DOMINANT = 0.40

# Crop data (replace with Appendix 2 when ready)
CROP_DATA = {
    "banana":       {"yield_kg_per_acre": 15000, "price_jmd_per_kg": 150},
    "hot_pepper":   {"yield_kg_per_acre": 5073,  "price_jmd_per_kg": 450},
    "carrot":       {"yield_kg_per_acre": 5972,  "price_jmd_per_kg": 400},
    "escallion":    {"yield_kg_per_acre": 4251,  "price_jmd_per_kg": 600},
    "sweet_potato": {"yield_kg_per_acre": 6883,  "price_jmd_per_kg": 300},
    "irish_potato": {"yield_kg_per_acre": 5870,  "price_jmd_per_kg": 300},
}

# ------------------------------------------------------------
# Fonts (IMPORTANT for Streamlit Cloud)
# Put font files into your repo: assets/fonts/
#   assets/fonts/PlayfairDisplay-Regular.ttf
#   assets/fonts/PlayfairDisplay-Bold.ttf (optional)
#   assets/fonts/Inter-Regular.ttf
#   assets/fonts/Inter-SemiBold.ttf (optional)
# ------------------------------------------------------------
FONT_DIR = os.path.join(ASSET_ROOT, "fonts")
PLAYFAIR_REG = os.path.join(FONT_DIR, "PlayfairDisplay-Regular.ttf")
PLAYFAIR_BOLD = os.path.join(FONT_DIR, "PlayfairDisplay-Bold.ttf")
INTER_REG = os.path.join(FONT_DIR, "Inter-Regular.ttf")
INTER_SEMI = os.path.join(FONT_DIR, "Inter-SemiBold.ttf")
INTER_BOLD = os.path.join(FONT_DIR, "Inter-Bold.ttf")

def _font(path_fallback: str, size: int) -> ImageFont.FreeTypeFont:
    # If bold font not provided, fall back to regular
    path = path_fallback if os.path.isfile(path_fallback) else path_fallback
    return ImageFont.truetype(path, int(size*SCALE))

def f_playfair(size, bold=False):
    path = PLAYFAIR_BOLD if bold and os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "Missing fonts in assets/fonts/. "
            "Add PlayfairDisplay-Regular.ttf and Inter-Regular.ttf at minimum."
        )
    return ImageFont.truetype(path, int(size*SCALE))

def f_inter(size, weight="reg"):
    path = INTER_REG
    if weight in ("semi","semibold") and os.path.isfile(INTER_SEMI):
        path = INTER_SEMI
    if weight == "bold" and os.path.isfile(INTER_BOLD):
        path = INTER_BOLD
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "Missing fonts in assets/fonts/. "
            "Add Inter-Regular.ttf at minimum."
        )
    return ImageFont.truetype(path, int(size*SCALE))

# ============================================================
# COPY (no em dashes)
# ============================================================
PARISH_COPY = {
    "Manchester": {
        "hero_template": "{amt} restores farms, livelihoods,\nand the next harvest in Manchester",
        "hero_sub": "Rebuilding damaged farmland so local farmers can harvest again within one season.",
        "why_title": "Why this matters",
        "why_body": ("Severe land damage has left Manchester farmers unable to plant for the upcoming season. "
                    "Without rapid support, families lose income for an entire year. "
                    "This recovery enables farmers to replant within the next harvest cycle."),
        "kpi_title": "What your {amt} achieves:",
        "crops_line": "Carrot, sweet potato, Irish potato",
        "crop_body": {
            "sweet_potato": "Reliable staple crop supporting household food security and fast income recovery.",
            "irish_potato": "High-yield crop that supports quick market sales and cash flow.",
            "dominant": "Primary market crop strengthening local supply chains and income stability.",
        },
        "quote": "“Without replanting support,\nwe lose the whole year.”\n- Local Manchester farmer",
        "cta_title": "Restore the next harvest",
        "cta_body": "Your donation today ensures farmers can plant in time for the next growing season.",
        "cta_button": "Support recovery now",
        "cta_note": "Funding closes once planting begins.",
    },
    "Clarendon": {
        "hero_template": "{amt} restores farms, livelihoods,\nand the next harvest in Clarendon",
        "hero_sub": "Rapid replanting support so farmers can earn again and keep food moving to markets.",
        "why_title": "Why this matters",
        "why_body": ("Hurricane damage has disrupted planting schedules and household income. "
                    "Without immediate support, farmers miss the season and communities face higher food costs. "
                    "This package helps farmers replant quickly and restart cash flow."),
        "kpi_title": "What your {amt} achieves:",
        "crops_line": "Hot pepper, sweet potato, Irish potato",
        "crop_body": {
            "sweet_potato": "Fast-growing staple crop supporting food security and quick recovery.",
            "irish_potato": "High-demand staple that turns planting support into rapid sales.",
            "dominant": "High-value market crop that restores income and local trade quickly.",
        },
        "quote": "“If we miss this season,\nwe fall behind for the whole year.”\n- Clarendon farmer",
        "cta_title": "Restore the next harvest",
        "cta_body": "Help farmers replant now so they can harvest and earn again this season.",
        "cta_button": "Support recovery now",
        "cta_note": "Funding closes once planting begins.",
    },
    "St. Elizabeth": {
        "hero_template": "{amt} restores farms, livelihoods,\nand the next harvest in St Elizabeth",
        "hero_sub": "Restoring a key food region so families and markets recover together.",
        "why_title": "Why this matters",
        "why_body": ("St Elizabeth supplies food across Jamaica. When land is damaged, farmers lose income and communities lose stable supply. "
                    "This recovery supports fast replanting so the next harvest arrives on time."),
        "kpi_title": "What your {amt} achieves:",
        "crops_line": "Escallion, sweet potato, Irish potato",
        "crop_body": {
            "sweet_potato": "Staple crop that improves household resilience and food access.",
            "irish_potato": "High-yield crop that supports quick turnaround and market sales.",
            "dominant": "High-demand crop supporting stable supply and stronger local markets.",
        },
        "quote": "“When our fields are down,\nour whole community feels it.”\n- St Elizabeth farmer",
        "cta_title": "Restore the next harvest",
        "cta_body": "Your donation helps farmers replant now and protects food security for the next season.",
        "cta_button": "Support recovery now",
        "cta_note": "Funding closes once planting begins.",
    },
    "Westmoreland": {
        "hero_template": "{amt} restores farms, livelihoods,\nand the next harvest in Westmoreland",
        "hero_sub": "Stabilising farms after crop loss so families can return to production.",
        "why_title": "Why this matters",
        "why_body": ("Crop loss and land damage threaten both food supply and household income. This package supports "
                    "fast recovery and replanting so farmers can harvest again and rebuild livelihoods."),
        "kpi_title": "What your {amt} achieves:",
        "crops_line": "Banana, sweet potato, Irish potato",
        "crop_body": {
            "sweet_potato": "Reliable staple crop supporting food security and fast recovery.",
            "irish_potato": "Quick market crop supporting cash flow and household income.",
            "dominant": "Longer-horizon income crop rebuilding stability for families and markets.",
        },
        "quote": "“We just need help to replant so\nwe can earn again.”\n- Westmoreland farmer",
        "cta_title": "Restore the next harvest",
        "cta_body": "Help farmers restart now so they can supply food and return to work this season.",
        "cta_button": "Support recovery now",
        "cta_note": "Funding closes once planting begins.",
    },
}

# ============================================================
# Utilities
# ============================================================
def fmt_gbp(x: float) -> str:
    return f"£{x:,.0f}"

def fmt_gbp_smart(x: float) -> str:
    return f"£{x:.2f}" if x < 1 else f"£{x:,.0f}"

def fmt_acres_smart(acres: float) -> str:
    if acres <= 0:
        return "0"
    if acres < 0.1:
        return "<0.1"
    if acres < 10:
        return f"{acres:.1f}".rstrip("0").rstrip(".")
    return f"{int(round(acres))}"

def fmt_families_smart(farmers: float) -> str:
    if farmers <= 0:
        return "0 families"
    n = int(round(farmers))
    return "1 family" if n <= 1 else f"{n} families"

def fmt_crop(c: str) -> str:
    return c.replace("_", " ").title()

def list_images(folder: str) -> List[str]:
    if not os.path.isdir(folder):
        return []
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]

def cover(path: str, size: Tuple[int, int]) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

def grade(img: Image.Image, contrast=1.10, saturation=1.03, brightness=1.00) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(saturation)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    return img

def pick_crop_photo(crop: str) -> Optional[str]:
    imgs = list_images(CROP_DIR)
    if not imgs:
        return None
    kw = {
        "sweet_potato": ["sweet_potato","sweetpotato","sweet potato"],
        "irish_potato": ["irish_potato","irishpotato","irish potato","potato"],
        "carrot": ["carrot"],
        "banana": ["banana"],
        "hot_pepper": ["hot_pepper","hotpepper","pepper","chili"],
        "escallion": ["escallion","scallion","spring_onion","spring onion","onion"],
    }.get(crop, [crop])
    filtered = [p for p in imgs if any(k in os.path.basename(p).lower() for k in kw)]
    return random.choice(filtered if filtered else imgs)

def pick_hero_for_parish(parish: str, dominant_crop: str) -> Optional[str]:
    farmers = list_images(FARMER_DIR)
    if farmers:
        return random.choice(farmers)
    bgs = list_images(BG_DIR)
    if not bgs:
        return None
    parish_kw = parish.replace(" ", "_").lower()
    dom_kw = dominant_crop.lower()
    filtered = [p for p in bgs if (parish_kw in os.path.basename(p).lower()) or (dom_kw in os.path.basename(p).lower())]
    return random.choice(filtered if filtered else bgs)

def soft_shadow(img: Image.Image, box, r=24, blur=20, alpha=70):
    x0,y0,x1,y1 = box
    sh = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle((x0,y0,x1,y1), radius=r, fill=(0,0,0,alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.paste(sh, (0,0), sh)

def rounded(draw: ImageDraw.ImageDraw, box, r=24, fill=None, outline=None, w=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w if outline else 0)

def hero_left_gradient(base: Image.Image, hero_h: int):
    ov = Image.new("RGBA", (W, hero_h), (0,0,0,0))
    d = ImageDraw.Draw(ov)
    for x in range(W):
        a = int(230 * max(0, 1 - x/(W*0.52)))
        d.line([(x,0),(x,hero_h)], fill=(0,0,0,a))
    base.paste(ov, (0,0), ov)

def bottom_fade(img: Image.Image, box, strength=185):
    x0,y0,x1,y1 = box
    w,h = x1-x0, y1-y0
    ov = Image.new("RGBA", (w,h), (0,0,0,0))
    d = ImageDraw.Draw(ov)
    for yy in range(h):
        a = int(strength * (yy / max(1,h)))
        d.line([(0,yy),(w,yy)], fill=(0,0,0,a))
    img.paste(ov, (x0,y0), ov)

# -------------------------
# Text in box (no overflow)
# -------------------------
def _wrap_lines(draw, text, font, max_w):
    words = text.split()
    lines, line = [], []
    for w_ in words:
        t = " ".join(line + [w_])
        if draw.textlength(t, font=font) <= max_w:
            line.append(w_)
        else:
            if line:
                lines.append(" ".join(line))
            line = [w_]
    if line:
        lines.append(" ".join(line))
    return lines

def _text_block_h(font, n_lines, line_spacing_px):
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    return n_lines * line_h + max(0, n_lines-1) * line_spacing_px

def draw_text_in_box(draw, box, text, font_path, start_size,
                     min_size=12, fill=(0,0,0),
                     align="left", valign="top",
                     line_spacing=6, max_lines=None,
                     ellipsis=True, shadow=None):
    x0,y0,x1,y1 = box
    max_w, max_h = x1-x0, y1-y0

    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, int(size*SCALE))
        lines = _wrap_lines(draw, text, font, max_w)
        if max_lines is not None:
            lines = lines[:max_lines]
        h = _text_block_h(font, len(lines), int(line_spacing*SCALE))
        if h <= max_h:
            break
        size -= 1

    font = ImageFont.truetype(font_path, int(max(size, min_size)*SCALE))
    lines = _wrap_lines(draw, text, font, max_w)
    if max_lines is not None:
        lines = lines[:max_lines]
    h = _text_block_h(font, len(lines), int(line_spacing*SCALE))

    if h > max_h and ellipsis and lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = " ".join(last.split()[:-1])
        lines[-1] = (last + "…") if last else "…"

    h = _text_block_h(font, len(lines), int(line_spacing*SCALE))
    if valign == "center":
        ty = y0 + (max_h - h)//2
    elif valign == "bottom":
        ty = y1 - h
    else:
        ty = y0

    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    ls = int(line_spacing*SCALE)

    for line in lines:
        line_w = draw.textlength(line, font=font)
        if align == "center":
            tx = x0 + (max_w - line_w)//2
        elif align == "right":
            tx = x1 - line_w
        else:
            tx = x0

        if shadow:
            dx = shadow.get("dx", 2*SCALE)
            dy = shadow.get("dy", 2*SCALE)
            scol = shadow.get("fill", (0,0,0,160))
            draw.text((tx+dx, ty+dy), line, font=font, fill=scol)

        draw.text((tx, ty), line, font=font, fill=fill)
        ty += line_h + ls

# ============================================================
# Impact computation
# ============================================================
@dataclass
class Impact:
    donation_gbp: float
    parish: str
    dominant_crop: str
    acres: float
    farmers: float
    acres_sp: float
    acres_ip: float
    acres_dom: float
    value_gbp: float

def crop_yield_kg(crop: str, acres: float) -> float:
    return acres * CROP_DATA[crop]["yield_kg_per_acre"]

def crop_value_jmd(crop: str, acres: float) -> float:
    return crop_yield_kg(crop, acres) * CROP_DATA[crop]["price_jmd_per_kg"]

def donation_to_acres(gbp: float) -> float:
    return (gbp * FX_JMD_PER_GBP) / COST_PER_ACRE_JMD if COST_PER_ACRE_JMD > 0 else 0.0

def acres_to_farmers(acres: float) -> float:
    return acres / ACRES_PER_FARMER if ACRES_PER_FARMER > 0 else 0.0

def compute_impact(donation_gbp: float, parish: Optional[str] = None) -> Impact:
    if parish is None:
        parish = random.choice(PARISH_LIST)
    dominant = PARISH_DOMINANT_CROP[parish]

    acres = donation_to_acres(donation_gbp)
    farmers = acres_to_farmers(acres)

    acres_sp = acres * SHARE_SWEET_POTATO
    acres_ip = acres * SHARE_IRISH_POTATO
    acres_dom = acres * SHARE_DOMINANT

    v_jmd = (
        crop_value_jmd("sweet_potato", acres_sp) +
        crop_value_jmd("irish_potato", acres_ip) +
        crop_value_jmd(dominant, acres_dom)
    )
    v_gbp = v_jmd / FX_JMD_PER_GBP if FX_JMD_PER_GBP else 0.0

    return Impact(donation_gbp, parish, dominant, acres, farmers, acres_sp, acres_ip, acres_dom, v_gbp)

# ============================================================
# Renderer
# ============================================================
def render_impact_menu_png(donation_gbp: float, parish: Optional[str] = None) -> Tuple[bytes, Impact]:
    imp = compute_impact(donation_gbp, parish=parish)
    copy = PARISH_COPY[imp.parish]

    base = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(base)

    hero_path = pick_hero_for_parish(imp.parish, imp.dominant_crop)
    if not hero_path:
        raise FileNotFoundError("Add images to assets/farmers/ or assets/backgrounds/")

    hero_h = int(0.37*H)
    hero = grade(cover(hero_path, (W, hero_h)), contrast=1.10, saturation=1.06)
    base.paste(hero, (0, 0))
    hero_left_gradient(base, hero_h)

    # Hero text
    headline = copy["hero_template"].format(amt=fmt_gbp(imp.donation_gbp))
    amt_len = len(fmt_gbp(imp.donation_gbp))
    start_head = 52 if amt_len <= 8 else 48 if amt_len <= 10 else 44

    draw_text_in_box(
        draw, (70*SCALE, 70*SCALE, int(0.92*W), hero_h-80*SCALE),
        headline, PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
        start_size=start_head, min_size=30,
        fill=WHITE, align="left", valign="top", line_spacing=10,
        shadow={"dx":2*SCALE, "dy":2*SCALE, "fill":(0,0,0,170)}
    )

    draw_text_in_box(
        draw, (70*SCALE, hero_h-145*SCALE, int(0.92*W), hero_h-90*SCALE),
        copy["hero_sub"], INTER_REG,
        start_size=20, min_size=15,
        fill=WHITE, align="left", valign="bottom", line_spacing=8,
        shadow={"dx":2*SCALE, "dy":2*SCALE, "fill":(0,0,0,140)}
    )

    # WHY PANEL
    y = int(0.33*H)
    why_box = (50*SCALE, y, W-50*SCALE, y+155*SCALE)
    soft_shadow(base, why_box, r=26*SCALE, blur=22*SCALE, alpha=55)
    rounded(draw, why_box, r=26*SCALE, fill=PANEL, outline=BORDER, w=2*SCALE)

    draw_text_in_box(draw, (80*SCALE, y+18*SCALE, W-80*SCALE, y+62*SCALE),
                     copy["why_title"], PLAYFAIR_REG, start_size=28, min_size=20, fill=INK)
    draw.line((300*SCALE, y+54*SCALE, W-80*SCALE, y+54*SCALE), fill=(210,205,192), width=2*SCALE)
    draw_text_in_box(draw, (80*SCALE, y+70*SCALE, W-80*SCALE, y+145*SCALE),
                     copy["why_body"], INTER_REG, start_size=20, min_size=16,
                     fill=INK, line_spacing=10, max_lines=3, ellipsis=True)

    # KPI BAND
    y = y + 175*SCALE
    kpi_box = (50*SCALE, y, W-50*SCALE, y+175*SCALE)
    soft_shadow(base, kpi_box, r=26*SCALE, blur=24*SCALE, alpha=65)
    rounded(draw, kpi_box, r=26*SCALE, fill=GREEN, outline=None)

    is_micro = (imp.acres > 0) and (imp.acres < MICRO_ACRE_THRESHOLD)
    kpi_title = copy["kpi_title"].format(amt=fmt_gbp(imp.donation_gbp))
    if is_micro:
        kpi_title = f"What your {fmt_gbp(imp.donation_gbp)} starts today:"

    draw_text_in_box(draw, (80*SCALE, y+10*SCALE, W-80*SCALE, y+60*SCALE),
                     kpi_title, PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=26, min_size=18, fill=WHITE, line_spacing=8)

    draw.line((420*SCALE, y+54*SCALE, W-80*SCALE, y+54*SCALE), fill=(255,255,255,80), width=2*SCALE)

    fam_txt = fmt_families_smart(imp.farmers)
    acres_txt = f"{fmt_acres_smart(imp.acres)} acres"
    crops_txt = copy["crops_line"]

    draw.line((390*SCALE, y+66*SCALE, 390*SCALE, y+162*SCALE), fill=(255,255,255,70), width=2*SCALE)
    draw.line((710*SCALE, y+66*SCALE, 710*SCALE, y+162*SCALE), fill=(255,255,255,70), width=2*SCALE)

    draw_text_in_box(draw, (95*SCALE, y+70*SCALE, 370*SCALE, y+104*SCALE),
                     "Farmers supported", INTER_SEMI if os.path.isfile(INTER_SEMI) else INTER_REG,
                     start_size=18, min_size=14, fill=WHITE)
    draw_text_in_box(draw, (95*SCALE, y+102*SCALE, 370*SCALE, y+164*SCALE),
                     fam_txt, PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=36, min_size=22, fill=WHITE)

    draw_text_in_box(draw, (430*SCALE, y+70*SCALE, 690*SCALE, y+104*SCALE),
                     "Land restored", INTER_SEMI if os.path.isfile(INTER_SEMI) else INTER_REG,
                     start_size=18, min_size=14, fill=WHITE)
    draw_text_in_box(draw, (430*SCALE, y+102*SCALE, 690*SCALE, y+164*SCALE),
                     acres_txt, PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=36, min_size=22, fill=WHITE)

    draw_text_in_box(draw, (740*SCALE, y+70*SCALE, W-80*SCALE, y+104*SCALE),
                     "Crops replanted", INTER_SEMI if os.path.isfile(INTER_SEMI) else INTER_REG,
                     start_size=18, min_size=14, fill=WHITE)
    draw_text_in_box(draw, (740*SCALE, y+104*SCALE, W-80*SCALE, y+164*SCALE),
                     crops_txt, INTER_REG, start_size=20, min_size=14, fill=WHITE, max_lines=2, ellipsis=True)

    # CROP CARDS
    y = y + 200*SCALE
    gap = 18*SCALE
    card_w = (W - 100*SCALE - 2*gap)//3
    card_h = 300*SCALE
    card_xs = [50*SCALE, 50*SCALE + card_w + gap, 50*SCALE + 2*(card_w + gap)]

    cards = [
        ("Sweet Potato", "sweet_potato", imp.acres_sp, copy["crop_body"]["sweet_potato"]),
        ("Irish Potato", "irish_potato", imp.acres_ip, copy["crop_body"]["irish_potato"]),
        (fmt_crop(imp.dominant_crop), imp.dominant_crop, imp.acres_dom, copy["crop_body"]["dominant"]),
    ]

    for i,(title,crop,acres,body) in enumerate(cards):
        x0 = card_xs[i]
        box = (x0, y, x0+card_w, y+card_h)
        soft_shadow(base, box, r=22*SCALE, blur=18*SCALE, alpha=55)
        rounded(draw, box, r=22*SCALE, fill=WHITE, outline=BORDER, w=2*SCALE)

        img_path = pick_crop_photo(crop) or hero_path
        img = grade(cover(img_path, (card_w, 160*SCALE)), contrast=1.06, saturation=1.08)
        base.paste(img, (x0, y))

        draw_text_in_box(draw, (x0+18*SCALE, y+170*SCALE, x0+card_w-18*SCALE, y+205*SCALE),
                         title, PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                         start_size=22, min_size=18, fill=INK)

        subline = "Included in recovery mix" if imp.acres <= 0 else f"{fmt_acres_smart(acres)} acres restored"
        draw_text_in_box(draw, (x0+18*SCALE, y+205*SCALE, x0+card_w-18*SCALE, y+240*SCALE),
                         subline, INTER_SEMI if os.path.isfile(INTER_SEMI) else INTER_REG,
                         start_size=18, min_size=14, fill=INK)

        draw_text_in_box(draw, (x0+18*SCALE, y+240*SCALE, x0+card_w-18*SCALE, y+card_h-18*SCALE),
                         body, INTER_REG, start_size=17, min_size=14,
                         fill=MID, line_spacing=9, max_lines=3, ellipsis=True)

    # VALUE BAND
    y = y + card_h + 24*SCALE
    val_box = (50*SCALE, y, W-50*SCALE, y+98*SCALE)
    soft_shadow(base, val_box, r=24*SCALE, blur=18*SCALE, alpha=45)
    rounded(draw, val_box, r=24*SCALE, fill=PANEL, outline=BORDER, w=2*SCALE)

    roi = (imp.value_gbp / imp.donation_gbp) if imp.donation_gbp > 0 else 0.0
    roi_txt = f"{max(1,int(round(roi)))}x"

    draw_text_in_box(draw, (80*SCALE, y+24*SCALE, 330*SCALE, y+78*SCALE),
                     "Projected impact value", PLAYFAIR_REG, start_size=22, min_size=16, fill=INK)

    draw_text_in_box(draw, (330*SCALE, y+10*SCALE, 720*SCALE, y+88*SCALE),
                     f"≈ {fmt_gbp_smart(imp.value_gbp)}",
                     PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=44, min_size=26, fill=INK, align="center", valign="center")

    rhs = f"in harvest value, returning over {roi_txt} the original donation to local farmers and markets."
    draw_text_in_box(draw, (740*SCALE, y+22*SCALE, W-80*SCALE, y+78*SCALE),
                     rhs, INTER_REG, start_size=18, min_size=13, fill=MUTED, max_lines=2, ellipsis=True)

    # QUOTE + CTA
    y = y + 120*SCALE
    left = (50*SCALE, y, 560*SCALE, H-40*SCALE)
    right = (580*SCALE, y, W-50*SCALE, H-40*SCALE)

    qimg_path = pick_crop_photo("sweet_potato") or (random.choice(list_images(FARMER_DIR)) if list_images(FARMER_DIR) else hero_path)
    qimg = grade(cover(qimg_path, (left[2]-left[0], left[3]-left[1])), contrast=1.05, saturation=1.02)
    base.paste(qimg, (left[0], left[1]))
    bottom_fade(base, left, strength=185)
    soft_shadow(base, left, r=22*SCALE, blur=18*SCALE, alpha=50)
    rounded(draw, left, r=22*SCALE, fill=None, outline=(240,235,225), w=2*SCALE)

    draw_text_in_box(
        draw, (left[0]+34*SCALE, left[1]+28*SCALE, left[2]-34*SCALE, left[3]-28*SCALE),
        copy["quote"], PLAYFAIR_REG, start_size=30, min_size=18,
        fill=WHITE, line_spacing=10, max_lines=4, ellipsis=True,
        shadow={"dx":2*SCALE, "dy":2*SCALE, "fill":(0,0,0,160)}
    )

    soft_shadow(base, right, r=22*SCALE, blur=18*SCALE, alpha=45)
    rounded(draw, right, r=22*SCALE, fill=PANEL, outline=BORDER, w=2*SCALE)

    draw_text_in_box(draw, (right[0]+34*SCALE, right[1]+24*SCALE, right[2]-34*SCALE, right[1]+78*SCALE),
                     copy["cta_title"], PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=32, min_size=22, fill=INK)

    draw_text_in_box(draw, (right[0]+34*SCALE, right[1]+78*SCALE, right[2]-34*SCALE, right[1]+150*SCALE),
                     copy["cta_body"], INTER_REG, start_size=20, min_size=15, fill=MUTED,
                     line_spacing=10, max_lines=3, ellipsis=True)

    btn = (right[0]+34*SCALE, right[1]+165*SCALE, right[2]-34*SCALE, right[1]+245*SCALE)
    soft_shadow(base, btn, r=16*SCALE, blur=14*SCALE, alpha=70)
    rounded(draw, btn, r=16*SCALE, fill=GREEN_DARK, outline=None)
    draw_text_in_box(draw, btn, copy["cta_button"],
                     PLAYFAIR_BOLD if os.path.isfile(PLAYFAIR_BOLD) else PLAYFAIR_REG,
                     start_size=26, min_size=18, fill=WHITE,
                     align="center", valign="center")

    draw_text_in_box(draw, (right[0]+34*SCALE, right[1]+252*SCALE, right[2]-34*SCALE, right[1]+290*SCALE),
                     copy["cta_note"], INTER_REG, start_size=16, min_size=12, fill=MUTED)

    # Downsample to target size and export PNG bytes
    out = base.resize(TARGET_IMPACT, Image.Resampling.LANCZOS)
    bio = BytesIO()
    out.save(bio, format="PNG", optimize=True)
    return bio.getvalue(), imp