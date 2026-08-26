# github-profile

Static item-WPA charts for the `flexinharder/flexinharder` profile README.
Isolated from every other workstream in `Transformer/` — nothing here is imported by anything else.

## Files

- `assets/wpa-{infernus,doorman,ivy}-{dark,light}.svg` — rendered 2026-08-26 from WPA blob **v140**
  (`wpa_analysis_data_compressed` id 140, active on statlocker.gg, created 2026-08-24). Verified to
  reproduce the live `wpa-homepage-data` endpoint item-for-item before rendering.
- `PROFILE_README.md` — the full profile README with the chart section added under "Selected Work".
- `scripts/render_wpa.py` — the renderer. Stdlib only.

## Install

```bash
# in a clone of github.com/flexinharder/flexinharder
cp /media/justin-ubuntu/ML-SPACE/Transformer/github-profile/PROFILE_README.md README.md
mkdir -p assets && cp /media/justin-ubuntu/ML-SPACE/Transformer/github-profile/assets/*.svg assets/
git add README.md assets && git commit -m "Add item WPA charts" && git push
```

## Re-rendering (after a new WPA run)

`?hero=` on the public endpoint is API-key gated, so hero-specific renders read the analysis blob directly.
Either a local `WPA/outputs/wpa_analysis_by_patch_*.json` or the active row from the statlock DB
(`SELECT TO_BASE64(data_json_compressed) FROM wpa_analysis_data_compressed WHERE is_active=1` → `base64 -d | gunzip`):

```bash
python3 scripts/render_wpa.py --local /path/to/blob.json --heroes Infernus,The_Doorman,Ivy --date 2026-08-24
```

`extract_items_for_hero` mirrors `WpaAnalysisService.extractItemsForHero` in statlock (sample-weighted
mean across rank_8–11 × all tiers, top 50 by sample size); chart shows the top 2 per cost tier.
Without `--local` the script fetches the public hero-of-the-day endpoint instead.

## Palette

Matches the README header: bg `#0d1117`, panel `#1e3a5f`, accent `#0ea5e9`, text `#c9d1d9`.
