#!/usr/bin/env python3
"""Render the Statlocker "hero of the day" item-WPA chart as an SVG.

Pulls https://statlocker.gg/api/info/wpa-homepage-data (public, no key),
sorts items by mean WPA and writes a dark + light SVG bar chart to assets/.
Stdlib only so the GitHub Action needs no pip install.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

URL = "https://statlocker.gg/api/info/wpa-homepage-data"
PER_TIER = 2                     # items shown per cost tier
TIERS = ((800, "T1"), (1600, "T2"), (3200, "T3"), (10**9, "T4"))
OUT_DIR = Path(__file__).resolve().parent.parent / "assets"

# Matches the profile README header (capsule-render + typing-svg colours).
PALETTES = {
    "dark": dict(bg="#10130D", panel="#2E2C27", accent="#FFED79", text="#FFEFD7",
                 muted="#8E876F", grid="#2E2C27", neg="#FF410D"),
    "light": dict(bg="#FDF7EA", panel="#F5EEDC", accent="#B8760A", text="#1B1E14",
                  muted="#6F6A58", grid="#E3DAC5", neg="#C6340B"),
}
FONT = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"

W = 820
ROW_H = 34
TOP = 74
BOTTOM = 48
LABEL_W = 190   # item name column
VALUE_W = 80    # room for "+3.18 pp" after the longest bar
RIGHT_W = 140   # "T4 · n=33.6k" column
BAR_X = 24 + LABEL_W
BAR_MAX_W = W - BAR_X - VALUE_W - RIGHT_W - 24


def fetch() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "flexinharder-profile-chart/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError(f"{URL} returned HTTP {r.status}")
        return json.load(r)


HOMEPAGE_MAX_ITEMS = 50
RANK_NAMES = {"rank_8": "Oracle", "rank_9": "Phantom", "rank_10": "Ascendant", "rank_11": "Eternus"}


def extract_items_for_hero(patch_data: dict, hero: str, ranks: list[str] | None = None,
                           min_samples: int | None = None) -> list[dict]:
    """Mirror of WpaAnalysisService.extractItemsForHero: sample-weighted mean WPA
    across the chosen rank buckets and every cost tier. Default (ranks=None,
    min_samples=None) reproduces the site: all ranks, top HOMEPAGE_MAX_ITEMS by
    sample size. With min_samples set, the cap is replaced by an n >= min_samples floor."""
    agg: dict[str, dict] = {}
    by_rank = patch_data.get("by_rank", {})
    for rank_key in (ranks or list(by_rank)):
        if rank_key not in by_rank:
            raise SystemExit(f"rank {rank_key!r} not in blob; available: {list(by_rank)}")
        for tier_data in by_rank[rank_key].get("by_tier", {}).values():
            for it in tier_data.get("top_by_hero", {}).get(hero, []):
                n = int(it.get("sample_size") or 0)
                if n <= 0:
                    continue
                a = agg.setdefault(it["item"], dict(item=it["item"], category=it.get("category", ""),
                                                  cost=it.get("cost", 0), n=0, wpa_sum=0.0, t_sum=0.0))
                a["n"] += n
                a["wpa_sum"] += float(it.get("mean_wpa") or 0.0) * n
                a["t_sum"] += float(it.get("mean_purchase_time_min") or 0.0) * n
    out = [dict(item=a["item"], category=a["category"], cost=a["cost"], mean_wpa=a["wpa_sum"] / a["n"],
                mean_purchase_time_min=a["t_sum"] / a["n"], sample_size=a["n"]) for a in agg.values()]
    out.sort(key=lambda i: i["sample_size"], reverse=True)
    if min_samples is not None:
        return [i for i in out if i["sample_size"] >= min_samples]
    return out[:HOMEPAGE_MAX_ITEMS]


def load_local(path: Path, hero: str, ranks: list[str] | None = None,
               min_samples: int | None = None) -> dict:
    blob = json.loads(path.read_text())
    by_patch = blob.get("by_patch")
    patch_data = next(iter(by_patch.values())) if by_patch else blob
    heroes = sorted({h for r in patch_data["by_rank"].values() for t in r["by_tier"].values()
                     for h in t.get("top_by_hero", {})})
    if hero not in heroes:
        raise SystemExit(f"hero {hero!r} not in blob; available: {heroes}")
    scope = []
    if ranks:
        scope.append(" / ".join(RANK_NAMES.get(r, r) for r in ranks))
    if min_samples is not None:
        scope.append(f"n ≥ {min_samples}")
    return {"hero": hero, "availableHeroes": heroes, "scope": " · ".join(scope),
            "items": extract_items_for_hero(patch_data, hero, ranks, min_samples)}


def tier_of(cost: int) -> str:
    for ceiling, name in TIERS:
        if cost <= ceiling:
            return name
    return TIERS[-1][1]


def select(items: list[dict]) -> list[dict]:
    """Top PER_TIER items by WPA within each cost tier, T1 first."""
    out: list[dict] = []
    for _, name in TIERS:
        pool = [i for i in items if tier_of(i["cost"]) == name]
        pool.sort(key=lambda i: i["mean_wpa"], reverse=True)
        out.extend(dict(i, tier=name) for i in pool[:PER_TIER])
    return out


def fmt_n(n: int) -> str:
    return f"{n/1000:.1f}k" if n >= 1000 else str(n)


def render(data: dict, p: dict, generated: str, rotating: bool = True) -> str:
    hero = data["hero"].replace("_", " ")
    items = select(data["items"])
    if not items:
        raise RuntimeError("endpoint returned no items")

    max_abs = max(abs(i["mean_wpa"]) for i in items) or 1e-9
    H = TOP + ROW_H * len(items) + BOTTOM
    s: list[str] = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'viewBox="0 0 {W} {H}" font-family="{FONT}">')
    s.append(f'<rect width="{W}" height="{H}" rx="12" fill="{p["bg"]}"/>')

    # Title block
    s.append(f'<text x="24" y="32" font-size="16" font-weight="600" fill="{p["accent"]}">'
             f'Item WPA · {"hero of the day: " if rotating else ""}{escape(hero)}</text>')
    s.append(f'<text x="24" y="52" font-size="11" fill="{p["muted"]}">'
             f'top {PER_TIER} items per cost tier by mean win-probability added per purchase (pp){" · rotates daily" if rotating else ""}'
             f'{(" · " + data["scope"]) if data.get("scope") else ""}</text>')

    # Grid at 25/50/75/100 % of max
    for frac in (0.25, 0.5, 0.75, 1.0):
        gx = BAR_X + BAR_MAX_W * frac
        s.append(f'<line x1="{gx:.1f}" y1="{TOP-8}" x2="{gx:.1f}" y2="{H-BOTTOM+4}" '
                 f'stroke="{p["grid"]}" stroke-width="1" stroke-dasharray="2 4"/>')

    for idx, it in enumerate(items):
        y = TOP + idx * ROW_H
        if idx and it["tier"] != items[idx - 1]["tier"]:
            s.append(f'<line x1="24" y1="{y}" x2="{W-24}" y2="{y}" stroke="{p["grid"]}" stroke-width="1"/>')
        wpa_pp = it["mean_wpa"] * 100
        bar_w = max(2.0, BAR_MAX_W * abs(it["mean_wpa"]) / max_abs)
        colour = p["accent"] if wpa_pp >= 0 else p["neg"]
        name = escape(it["item"])
        if len(it["item"]) > 22:
            name = escape(it["item"][:21]) + "…"
        s.append(f'<text x="24" y="{y+ROW_H/2+4:.1f}" font-size="13" fill="{p["text"]}">{name}</text>')
        s.append(f'<rect x="{BAR_X}" y="{y+8}" width="{bar_w:.1f}" height="{ROW_H-16}" rx="4" '
                 f'fill="{colour}"/>')
        s.append(f'<text x="{BAR_X+bar_w+8:.1f}" y="{y+ROW_H/2+4:.1f}" font-size="12" '
                 f'font-weight="600" fill="{p["text"]}">{wpa_pp:+.2f} pp</text>')
        s.append(f'<text x="{W-24}" y="{y+ROW_H/2+4:.1f}" font-size="11" text-anchor="end" '
                 f'fill="{p["muted"]}">{it["tier"]} · n={fmt_n(it["sample_size"])}</text>')

    # Footer
    s.append(f'<line x1="24" y1="{H-BOTTOM+10}" x2="{W-24}" y2="{H-BOTTOM+10}" '
             f'stroke="{p["grid"]}" stroke-width="1"/>')
    s.append(f'<text x="24" y="{H-16}" font-size="11" fill="{p["muted"]}">'
             f'statlocker.gg/items/meta-model · LightGBM WP model, bias-corrected per-item WPA</text>')
    s.append(f'<text x="{W-24}" y="{H-16}" font-size="11" text-anchor="end" fill="{p["muted"]}">'
             f'updated {generated}</text>')
    s.append("</svg>")
    return "\n".join(s)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--local", type=Path, help="wpa_analysis_by_patch_*.json to read instead of the live endpoint")
    ap.add_argument("--heroes", default="", help="comma-separated hero keys (e.g. Infernus,The_Doorman,Ivy); requires --local")
    ap.add_argument("--ranks", default="", help="comma-separated rank keys to include, e.g. rank_9 (Phantom); default = all")
    ap.add_argument("--min-samples", type=int, default=None, help="replace the site's top-50-by-sample cap with an n >= N floor")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"), help="date stamp for the footer")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.local:
        heroes = [h.strip() for h in args.heroes.split(",") if h.strip()]
        if not heroes:
            raise SystemExit("--heroes is required with --local")
        ranks = [r.strip() for r in args.ranks.split(",") if r.strip()] or None
        jobs = [(load_local(args.local, h, ranks, args.min_samples), h.lower().replace("the_", ""), False)
                for h in heroes]
    else:
        data = fetch()
        jobs = [(data, None, True)]

    for data, slug, rotating in jobs:
        for name, palette in PALETTES.items():
            out = OUT_DIR / (f"wpa-{slug}-{name}.svg" if slug else f"wpa-{name}.svg")
            out.write_text(render(data, palette, args.date, rotating), encoding="utf-8")
            print(f"wrote {out} ({data['hero']}, {len(data['items'])} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
