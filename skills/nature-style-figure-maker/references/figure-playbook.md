# Figure Playbook

Use this file before plotting. The figure should serve the scientific logic first.

## First move

Write a short contract before making the figure:

```text
Core conclusion:
Figure archetype:
Target journal/output:
Backend: Python or R
Final size:
Panel map:
  a:
  b:
  c:
Evidence hierarchy:
  hero evidence:
  validation evidence:
  controls/robustness:
Statistics needed:
Source data needed:
Image-integrity notes:
Reviewer risk:
```

Start from the conclusion, then choose the minimum number of panels that make the conclusion clear and defensible.

## Backend gate

If the user has not explicitly chosen Python or R, ask one concise question: `Python or R?` Then stop.

Once a backend is selected, use it for all plotting, previews, exports, and visual QA. Do not cross-render with the other language.

## Figure archetypes

- `quantitative grid` — mainly numerical comparison
- `schematic-led composite` — workflow, mechanism, or device first
- `image plate + quant` — microscopy, blots, spatial overlays, or representative images
- `asymmetric mixed-modality figure` — mixed raster, schematic, heatmap, and quantitative panels

## Panel logic

Prefer this order unless the story requires another:

1. Establish the system.
2. Show the main effect.
3. Show mechanism or localization.
4. Quantify the representative observation.
5. Add robustness, controls, or subgroup analysis.

## Aesthetic rules

- Use one neutral family, one signal family, and one accent family.
- Keep the same condition colour across panels.
- Prefer direct labels when stable identities are spatially fixed.
- Keep the background white unless the figure is image-led.
- Avoid equal-sized panels when evidence is not equally important.

## Export and QA

Final outputs should normally include SVG, PDF, and TIFF or PNG preview files with editable text where possible. Check that sample sizes, error bars, source data links, and image-integrity notes are visible and traceable.

If the selected backend is unavailable, stop and report the blocker instead of switching languages.
