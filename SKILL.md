---
name: zircon-spot-selector
description: Register reflected-light, transmitted-light, and CL images of the same zircon field, build modality-specific defect masks, and select 30 µm or other circular microanalysis targets using hard full-footprint exclusion. Use for zircon targeting that must avoid cracks, inclusions, damage, grain edges, and CL boundaries; never treat the result as proof that sub-resolution defects are absent.
---

# Zircon Spot Selector

Create a reviewable targeting overlay, not an assurance that a site is defect-free. Treat subtle fractures, sub-resolution inclusions, and ambiguous zoning as uncertainties and flag them for petrographer/operator review.

## Inputs

Require three distinct images of the same field: reflected light, transmitted light, and CL. Do not run automatic selection with a missing modality, duplicate image content, or failed registration. Use the highest-resolution originals available.

Before selecting sites, establish:

- requested physical spot diameter; default to 30 µm only when the request or established task context specifies it;
- scale-bar value and measured pixel length for each independently resized panel;
- whether the desired output is one preferred site per grain, multiple ranked candidates, or a specified number of analyses;
- whether inherited cores, rims, growth zones, metamict domains, or previous ablation pits are intentionally targeted or excluded.

If the user's intent is otherwise clear, proceed with one preferred candidate per usable grain and mark alternates only where useful.

## Calibration and registration

Calculate `diameter_px = spot_diameter_µm × scale_bar_px / scale_bar_µm`. For a 30 µm spot beside a 100 µm bar, the circle diameter is 30% of that bar's measured pixel length.

Never reuse a pixel diameter across panels that may have been resized independently. Never infer physical size from magnification text alone when a usable scale bar exists. Record the bar endpoints, bar value, derived pixels per micrometre, and final pixel diameter.

Use reflected light as the reference coordinate system. The script first tries ORB gradient features with RANSAC homography and then gradient ECC affine registration. For cross-modality failures, use `manual_registration.html` to select corresponding control points and pass the exported JSON back with `--registration-points`. If error exceeds the configured threshold or overlap is inadequate, stop without recommending targets.

## Site selection

Read [references/selection-criteria.md](references/selection-criteria.md) before choosing or scoring sites.

Evaluate grain integrity before evaluating sites. Exclude clearly broken, fragmented, severely chipped, or image-truncated grains as a whole, even if one remaining fragment appears large enough for a circle. Mark ambiguous edge loss or concavity for review rather than treating the grain as intact.

Build separate defect masks for all three registered modalities, then take their logical union. Dilate defects and grain boundaries by the requested safety distance plus registration error. A candidate is eligible only if its entire circular footprint is disjoint from the buffered union and remains inside the buffered grain interior. Any intersection is a hard rejection; scoring only ranks candidates that already passed.

Do not erase, retouch, or conceal source features. Use non-destructive overlays. Distinguish clear exclusions from ambiguous features, and prefer no site over forcing an unsuitable grain.

## Output

Produce diagnostics for registration and screening, but place final target marks only on CL. The formal result is `zircon_targets_editable.pdf`: each CL image is an unaltered page background, each target is an independent `/Subtype /Circle` annotation, and each ID is an independent `/FreeText` annotation grouped with its circle where supported. Never flatten targets into the background. Preserve the CL pixel dimensions as the PDF page dimensions; multiple CL images become separate proportion-preserving pages.

Also produce `cl_target_coordinates.csv` with CL filename, centre coordinates, pixel diameter, physical diameter, scale, confidence, and score. PNG overlays are previews only.

Use `scripts/zircon_spots.py` and read [references/usage.md](references/usage.md). Install `requirements.txt`; when `python` is unavailable on `PATH`, use the Codex bundled Python runtime.

Use consistent coordinates relative to the top-left of the delivered original image. Label sites as `preferred`, `alternate`, `review`, or `rejected`. Do not report more precision than the image calibration supports.

## Verification

Before delivery, confirm that circle diameter matches the calibration, every accepted footprint clears visible exclusions in every registered modality, IDs match the CL coordinate table, and the PDF retains the source aspect ratio and resolution. Parse the final PDF and enumerate `/Circle` annotations. Confirm circles are not flattened. On a PDF containing at least one target, modify one circle rectangle, save, reopen, and verify the new rectangle. Explicitly identify grains for which no defensible 30 µm site exists.
