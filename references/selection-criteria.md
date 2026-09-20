# Zircon target-selection criteria

Use these criteria to rank candidate microanalysis footprints. The acquisition method and research question can override preferences, but never silently override geometric fit or visible defects.

## Hard exclusions

Reject an entire grain when it is clearly broken into fragments, has substantial material loss, has a major chipped/open margin, or is truncated by the image boundary. Do not place a target merely because one remnant region can geometrically contain the circle. Natural euhedral terminations and elongated habits are not damage by themselves.

Reject any footprint intersecting:

- an open or suspected fracture, crack network, chipped margin, grain boundary, or mounting-medium gap;
- a visible mineral, melt, or fluid inclusion, void, pore, dark pit, polishing defect, or previous ablation crater;
- an obviously altered, highly porous, or metamict-looking patch;
- an image border, label, scale bar, or region whose corresponding modality cannot be located reliably.

Treat a linear feature as a fracture when it cuts across growth zoning, continues to an edge, branches, or appears consistently in reflected/transmitted images. Treat small high-contrast spots, cavities, halos, or phase-like bodies as possible inclusions. When uncertain, mark `review` rather than accepting the site.

Assess breakage jointly from outline continuity and the optical/CL evidence. Fresh irregular missing edges, matching separated fragments, open fractures reaching the rim, and sharp concave loss support a broken-grain classification. Rounded or crystallographic outlines without discontinuity do not. Automated contour concavity is only a screening cue; ambiguous grains require human review.

## Geometric fit

The entire circular footprint must lie within the grain. Prefer a clearance outside the circumference of at least 10% of the spot diameter; use a larger margin where edge geometry or registration is uncertain. A 30 µm spot therefore normally needs a clean interior region wider than 36 µm.

Do not shrink the requested spot to make it fit. Mark the grain unusable at that diameter or, if useful, report the largest visibly feasible diameter as a non-authoritative alternative.

## Internal-domain preferences

CL zoning is geological information, not automatically a defect. Prefer a footprint contained within one interpretable domain and avoid crossing sharp core-rim contacts or narrow oscillatory zones unless the research question explicitly targets mixed material. Avoid very bright saturated or very dark domains when they obscure texture; flag them rather than inferring composition.

When no domain preference is stated, prefer a homogeneous, well-resolved interior area with the greatest combined distance from edges and exclusions.

## Candidate ranking

Rank candidates using evidence visible in the images:

1. whole-grain integrity: not broken, fragmented, severely chipped, or image-truncated;
2. hard-exclusion clearance across all modalities;
3. geometric margin to grain edge and uncertain registration;
4. distance from cracks, inclusions, pits, and altered patches;
5. containment within the intended CL/BSE domain;
6. image clarity and confidence in cross-modal correspondence.

Use `high` confidence only when calibration and registration are reliable and the footprint is clearly clean in all provided modalities. Use `medium` for minor ambiguity outside the footprint or incomplete but adequate modality coverage. Use `low`/`review` when a judgement depends on weak resolution, uncertain feature identity, or imperfect registration.

## Visual conventions

- Preferred: green or cyan unfilled circle.
- Alternate: yellow unfilled circle.
- Review: orange dashed circle.
- Rejected examples, when requested: red dashed circle or cross.
- Keep strokes thin enough to preserve underlying textures; place labels just outside the footprint with leader lines when necessary.

Colors are conventions only; IDs and status fields must carry the meaning for accessibility and print use.
