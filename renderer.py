from __future__ import annotations

import os
import math
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter


# =========================================================
# Paths (Streamlit-safe)
# =========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_ROOT = os.path.join(BASE_DIR, "assets")

FONT_DIR = os.path.join(ASSET_ROOT, "fonts")
BG_DIR = os.path.join(ASSET_ROOT, "backgrounds")
CROP_DIR = os.path.join(ASSET_ROOT, "crops")


# =========================================================
# Public constants
# =========================================================
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


# =========================================================
# Locked impact assumptions (appendix-aligned)
# =========================================================
FIXED_FAMILIES = 17
ACRES_PER_FARMER = 2
FIXED_ACRES = FIXED_FAMILIES * ACRES_PER_FARMER


# =========================================================
# Yield / value model
# =========================================================
CROP_MODEL = {
    "sweet_potato": {"yield_kg_per_acre": 6800, "value_gbp_per_kg": 0.65},
    "irish_potato": {"yield_kg_per_acre": 5800, "value_gbp_per_kg": 0.85},
    "hot_pepper": {"yield_kg_per_acre": 2200, "value_gbp_per_kg": 3.00},
    "carrot": {"yield_kg_per_acre": 6000, "value_gbp_per_kg": 1.10},
    "banana": {"yield_kg_per_acre": 9000, "value_gbp_per_kg": 0.55},
    "escallion": {"yield_kg_per_acre": 4200, "value_gbp_per_kg": 1.70},
}

ALLOC_WEIGHTS = {
    "dominant": 0.40,
    "sweet_potato": 0.35,
    "irish_potato": 0.25,
}


# =========================================================
# Canvas & theme
# =========================================================
TARGET_W, TARGET_H = 1080, 1350
SCALE = 2
W, H = TARGET_W * SCALE, TARGET_H * SCALE

BG_PAPER = (244, 241, 234)
GREEN = (21, 67, 49)
TEXT_DARK = (22, 22, 22)
TEXT_MUTED = (92, 92, 92)


# =========================================================
# Data types
# =========================================================
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
    farmers_supported: int
    crops: List[CropImpact]
    projected_value_gbp: float


# =========================================================
# Formatting helpers
# =========================================================
def fmt_currency(amount: float, currency: str) -> str:
    symbols = {"GBP": "£", "USD": "$", "JMD": "J$"}
    symbol = symbols.get(currency, "")
    return f"{symbol}{int(round(amount)):,}"


def fmt_acres(x: float) -> str:
    return f"{int(round(x))} acres"


# =========================================================
# Font loading (robust)
# =========================================================
def _font_path(name: str) -> str:
    return os.path.join(FONT_DIR, name)


def _first_existing(paths: List[str]) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


def load_fonts() -> Dict[str, str]:
    fonts = {}
    fonts["playfair_bold"] = _first_existing([
        _font_path("PlayfairDisplay-Bold.ttf"),
        _font_path("PlayfairDisplay-ExtraBold.ttf"),
    ])
    fonts["playfair_semibold"] = _first_existing([
        _font_path("PlayfairDisplay-SemiBold.ttf"),
    ])
    fonts["inter_reg"] = _first_existing([
        _font_path("Inter_24pt-Regular.ttf"),
        _font_path("Inter_18pt-Regular.ttf"),
    ])
    fonts["inter_semibold"] = _first_existing([
        _font_path("Inter_24pt-SemiBold.ttf"),
        _font_path("Inter_18pt-SemiBold.ttf"),
    ])
    return fonts


FONTS = load_fonts()


def _ttf(path: Optional[str], size: int):
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def f_playfair(size: int, weight="bold"):
    return _ttf(FONTS.get(f"playfair_{weight}"), size)


def f_inter(size: int, weight="reg"):
    return _ttf(FONTS.get(f"inter_{weight}"), size)


# =========================================================
# Image helpers
# =========================================================
def safe_open_image(path: str) -> Optional[Image.Image]:
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    w, h = img.size
    scale = max(target_w / w, target_h / h)
    img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    x0 = (img.width - target_w) // 2
    y0 = (img.height - target_h) // 2
    return img.crop((x0, y0, x0 + target_w, y0 + target_h))


def pick_image(folder: str, keys: List[str], used: set) -> Optional[Image.Image]:
    for k in keys:
        if k not in CROP_MODEL:
            continue
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            p = os.path.join(folder, k + ext)
            if p in used:
                continue
            img = safe_open_image(p)
            if img:
                used.add(p)
                return img
    return None


# =========================================================
# Copy
# =========================================================
def hero_subline() -> str:
    return "Rejuvenating farms after crop loss so families can return to production"


def why_matters() -> str:
    return (
        "Crop loss and land damage threaten both food supply and household income. "
        "Your donation supports fast recovery and replanting so farmers can harvest "
        "again and rebuild livelihoods."
    )


def crop_blurb(ck: str) -> str:
    return {
        "sweet_potato": "A resilient staple crop strengthening household food security.",
        "irish_potato": "A fast-growing market crop restoring income quickly.",
        "hot_pepper": "A high-value crop that accelerates farmer income recovery.",
        "carrot": "A core market crop supporting stable local supply chains.",
        "banana": "A longer-horizon crop rebuilding household stability.",
        "escallion": "A high-demand crop supporting consistent market supply.",
    }[ck]


# =========================================================
# Impact calculation (LOCKED)
# =========================================================
def compute_impact(donation_gbp: float, parish: Optional[str]) -> Impact:
    parish_final = parish if parish in PARISH_LIST else PARISH_LIST[0]
    dom = DOMINANT_CROP[parish_final]

    weights = [
        ("sweet_potato", ALLOC_WEIGHTS["sweet_potato"]),
        ("irish_potato", ALLOC_WEIGHTS["irish_potato"]),
        (dom, ALLOC_WEIGHTS["dominant"]),
    ]

    total_weight = sum(w for _, w in weights)
    crops: List[CropImpact] = []
    total_value = 0.0

    for ck, w in weights:
        acres = FIXED_ACRES * (w / total_weight)
        model = CROP_MODEL[ck]
        value = acres * model["yield_kg_per_acre"] * model["value_gbp_per_kg"]
        crops.append(CropImpact(ck, acres, value))
        total_value += value

    return Impact(
        donation_gbp=donation_gbp,
        parish=parish_final,
        acres_restored=FIXED_ACRES,
        farmers_supported=FIXED_FAMILIES,
        crops=crops,
        projected_value_gbp=total_value,
    )


# =========================================================
# Main renderer (Streamlit-safe)
# =========================================================
def render_impact_menu_png(
    donation_gbp: float,
    parish: Optional[str] = None,
    currency: str = "GBP",
) -> Tuple[bytes, Impact]:

    imp = compute_impact(donation_gbp, parish)

    base = Image.new("RGB", (W, H), BG_PAPER)
    draw = ImageDraw.Draw(base)

    # -----------------------------------------------------
    # HERO
    # -----------------------------------------------------
    hero_h = int(0.35 * H)
    used = set()

    hero_img = pick_image(
        BG_DIR,
        [f"hero_{imp.parish.lower().replace(' ', '_')}", "hero_generic"],
        used,
    )

    hero = (
        center_crop(hero_img, W, hero_h)
        if hero_img
        else Image.new("RGB", (W, hero_h), (40, 50, 45))
    )
    base.paste(hero, (0, 0))

    overlay = Image.new("RGBA", (W, hero_h), (0, 0, 0, 120))
    base.paste(overlay, (0, 0), overlay)

    headline = (
        f"Your {fmt_currency(imp.donation_gbp, currency)} restores farmers’ income, "
        f"livelihoods and hope for communities in {imp.parish}, Jamaica"
    )

    draw.text(
        (80 * SCALE, 80 * SCALE),
        headline,
        fill=(255, 255, 255),
        font=f_playfair(60 * SCALE),
    )

    draw.text(
        (80 * SCALE, 200 * SCALE),
        hero_subline(),
        fill=(230, 230, 230),
        font=f_inter(26 * SCALE),
    )

    # -----------------------------------------------------
    # FOOTER DISCLAIMER
    # -----------------------------------------------------
    draw.text(
        (80 * SCALE, H - 60 * SCALE),
        "*Based on input costs and market prices as of March 2026.",
        fill=(90, 90, 90),
        font=f_inter(14 * SCALE),
    )

    out = base.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
    bio = BytesIO()
    out.save(bio, format="PNG", optimize=True)

    return bio.getvalue(), imp