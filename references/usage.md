# Usage

Install `requirements.txt` with Python 3.10+. When `python` is not on `PATH`, use the Codex bundled Python executable reported by the workspace dependency loader.

## Mandatory inputs

Supply three distinct files showing the same zircon field:

```powershell
python scripts/zircon_spots.py analyze `
  --reflected reflected.png `
  --transmitted transmitted.png `
  --cl cl.png `
  --output-dir results `
  --spot-um 30 --safety-um 4 `
  --scale-bar-um 100 --auto-scale
```

Duplicate files, failed registration, registration error above `--max-registration-error-px` (default 5 px), or inadequate overlap stop the run before selection.

## Registration

Automatic registration tries gradient-domain ORB feature matching with RANSAC homography, then gradient ECC affine registration. Check `registration.json` and the three `registered_*.png` files.

The output directory always contains `manual_registration.html`. If automatic registration fails, open it, select at least four widely separated corresponding points for transmitted→reflected and CL→reflected, export `registration_points.json`, then rerun:

```powershell
python scripts/zircon_spots.py analyze ... `
  --registration-points registration_points.json
```

## Calibration and safety buffer

Use `--auto-scale`, `--scale-bar-px 98`, or `--scale-bar x1,y1,x2,y2`. The physical safety distance is set with `--safety-um`; registration error is automatically added to this buffer in pixels.

## Detection and hard rejection

- Reflected light: surface cracks/dark lines, holes/inclusions, polishing or damaged heterogeneous regions, grain edges.
- Transmitted light: internal cracks, transparent/dark inclusions, holes, and internal heterogeneity.
- CL: cracks, dark/bright anomalies, abnormal-emission texture, zoning and inherited-core boundaries.

Masks are not averaged. Their buffered logical union is used. The union is further dilated by the target radius, which is equivalent to checking whether the complete circular footprint intersects an exclusion. Grain-edge distance is checked using the target radius plus safety buffer. Only candidates passing all hard tests are scored.

## Diagnostic outputs

- `registered_reflected.png`, `registered_transmitted.png`, `registered_cl.png`
- `mask_reflected*.png`, `mask_transmitted*.png`, `mask_cl*.png`
- `mask_combined_exclusion.png`, `mask_grains.png`
- `rejected_candidates.csv`, `rejected_candidates.png`
- `cl_targets_registered_preview.png`, `cl_targets_original_preview.png`
- `zircon_targets_editable.pdf` - formal output; CL background plus editable annotations
- `cl_target_coordinates.csv`
- `pdf_validation.json`
- `zircon_spots.csv`, `registration.json`, `summary.json`
- `manual_registration.html`

`zircon_spots.csv` reports clearance from the circle boundary to the nearest detected crack, inclusion, grain edge, and CL boundary. Zero accepted targets is valid and is reported explicitly in `summary.json`.

## Editable CL PDF

The PDF page uses the original CL pixel dimensions as its page size. The CL image is embedded once as the page background. Targets are not painted into the page content:

- circle: independent `/Annot` with `/Subtype /Circle` and a transparent interior;
- ID: independent `/Annot` with `/Subtype /FreeText`;
- association: label uses `/IRT` and `/RT /Group` to reference its circle where the viewer supports grouped annotations.

Use `verify-pdf` to enumerate annotations and perform a saved rectangle mutation:

```powershell
python scripts/zircon_spots.py verify-pdf `
  --pdf results/zircon_targets_editable.pdf `
  --report results/pdf_validation.json `
  --mutation-output results/annotation_edit_test.pdf
```

For multiple CL pages, create a manifest whose `pages` entries contain `cl_image`, `spots_csv`, and optional `image_name`, then run:

```powershell
python scripts/zircon_spots.py export-pdf `
  --manifest pages.json --output targets.pdf --coordinates targets.csv
```

## Limitations

The masks are conservative screening aids. Low resolution, saturation, weak contrast, polishing artefacts, overlapping grains, and imperfect segmentation can cause missed defects or false exclusions. Inspect every mask and rejected reason. Final instrument targeting requires expert review of the original images.
