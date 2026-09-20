# Zircon Spot Selector

A Codex skill for assisting zircon microanalysis target selection. It jointly analyzes reflected-light, transmitted-light, and cathodoluminescence (CL) images of the same field, registers the three modalities, detects defects, screens circular 30 µm target areas, and exports final targets as independently editable annotations on the original CL image in PDF format.

> This is a conservative screening aid, not proof that a target is free of sub-resolution fractures or invisible inclusions. A qualified operator or petrographer must review the source images, masks, and recommended positions before instrument analysis.

## Features

- Requires three distinct images of the same field: reflected light, transmitted light, and CL.
- Attempts ORB feature matching with RANSAC homography, followed by gradient-domain ECC affine registration as a fallback.
- Stops automatic recommendation when registration is unreliable and produces a browser-based tool for manual control-point registration.
- Builds separate modality-specific masks for cracks, inclusions, holes, damage, grain edges, internal heterogeneity, and CL zoning boundaries.
- Uses a hard "detected in any modality means excluded" union rule; the three images are never averaged or decided by majority vote.
- Checks the complete 30 µm circular footprint, not only its center, with configurable safety buffers for defects, grain edges, and registration uncertainty.
- Allows zero accepted targets when no safe area exists rather than forcing a low-quality recommendation.
- Produces registered images, diagnostic masks, rejected-candidate reasons, coordinate tables, previews, and an editable PDF.
- Writes each target as an independent PDF `/Subtype /Circle` annotation and each label as an independent `/FreeText` annotation, without flattening them into the CL background.

## Install as a Codex Skill

Clone or download this repository into your Codex skills directory:

```powershell
git clone https://github.com/Jiachen-123/zircon-spot-selector.git "$env:CODEX_HOME/skills/zircon-spot-selector"
```

If `CODEX_HOME` is not configured, the usual Windows location is:

```text
C:\Users\<username>\.codex\skills\zircon-spot-selector
```

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Python 3.10 or newer is required. If system Python is not available on `PATH`, use the Python runtime bundled with Codex.

## Required Inputs

Every dataset must contain three different images showing the same zircon grains in the same field of view:

1. reflected-light image;
2. transmitted-light image;
3. CL image.

Use the highest-resolution, unscaled originals whenever possible. The default analysis diameter is 30 µm. The scale bar may be detected automatically or supplied manually as a pixel length or a pair of endpoints.

## Basic Usage

```powershell
python scripts/zircon_spots.py analyze `
  --reflected reflected.png `
  --transmitted transmitted.png `
  --cl cl.png `
  --output-dir results `
  --spot-um 30 `
  --safety-um 4 `
  --scale-bar-um 100 `
  --auto-scale
```

To provide the scale-bar pixel length manually:

```powershell
python scripts/zircon_spots.py analyze ... `
  --scale-bar-um 100 `
  --scale-bar-px 98
```

If automatic registration fails, open `manual_registration.html` from the output directory. Select at least four widely distributed corresponding points for transmitted→reflected and CL→reflected, export the JSON file, and rerun:

```powershell
python scripts/zircon_spots.py analyze ... `
  --registration-points registration_points.json
```

## Main Outputs

- `zircon_targets_editable.pdf` — formal deliverable using the original CL image as the background with independently editable circle annotations.
- `cl_target_coordinates.csv` — target ID, CL image name, center coordinates, pixel diameter, physical diameter, scale, score, and confidence.
- `registered_reflected.png`, `registered_transmitted.png`, and `registered_cl.png` — registered modality images.
- `mask_reflected*.png`, `mask_transmitted*.png`, and `mask_cl*.png` — separate modality-specific defect masks.
- `mask_combined_exclusion.png` — union of all exclusion masks.
- `rejected_candidates.csv` and `rejected_candidates.png` — rejected locations and rejection reasons.
- `cl_targets_original_preview.png` — raster preview for quick inspection only.
- `registration.json`, `summary.json`, and `pdf_validation.json` — registration, screening, and PDF validation reports.

## Validate the Editable PDF

```powershell
python scripts/zircon_spots.py verify-pdf `
  --pdf results/zircon_targets_editable.pdf `
  --report results/pdf_validation.json `
  --mutation-output results/annotation_edit_test.pdf
```

Validation enumerates `/Circle` annotations, modifies the position and size of one test circle, saves the PDF, and reopens it to confirm that the annotation remains editable and was not flattened.

## Selection Rules

A candidate is accepted only when its complete circular footprint satisfies all of the following:

- it does not intersect a crack, inclusion, hole, or damaged area detected in any modality;
- it does not cross a CL zoning or inherited-core boundary;
- it remains fully inside an intact zircon grain with the configured safety clearance from the grain edge;
- brightness, texture, and CL response within the circle are sufficiently homogeneous;
- registration error is below the configured threshold and is included in the exclusion buffer.

See [`references/selection-criteria.md`](references/selection-criteria.md) for detailed rules and [`references/usage.md`](references/usage.md) for complete usage guidance.

## Limitations

- Low resolution, defocus, saturation, poor contrast, or noise may cause missed defects or false exclusions.
- Sub-pixel fractures and inclusions that are not visible under the supplied imaging conditions cannot be reliably excluded.
- Polishing artefacts, overlapping grains, complex zoning, and strong luminescence anomalies may affect segmentation.
- Automatic registration and every diagnostic mask must be reviewed manually. The output does not replace petrographic judgment or instrument-operator approval.

## License

No open-source license has been added yet. All rights are reserved until a license is provided.
