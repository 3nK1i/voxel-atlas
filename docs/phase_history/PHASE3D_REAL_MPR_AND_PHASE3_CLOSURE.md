# Phase 3D - Real MPR Integration and Phase 3 Closure

Phase 3D connects the Phase 3C canonical patient volume to the Axial, Coronal, and Sagittal panels and closes the Phase 3 data foundation.

## Scope

- serve authenticated patient-space MPR descriptors and grayscale slices from the canonical volume
- reformat in DICOM patient LPS coordinates, independent from acquisition orientation
- preserve physical aspect through per-plane pixel spacing
- use conventional orientation labels: Axial R/L/A/P, Coronal R/L/S/I, Sagittal A/P/S/I
- synchronize a patient-space crosshair across all three panels
- support wheel-based slice navigation
- support right-drag window/level adjustment with CT default W/L 400/40
- show real slice index, patient-space position, and W/L values
- keep the demo skull explicitly separate from patient-specific anatomy
- do not enable Full Volume, Brain, or Skull + Brain 3D layers yet

## Rendering contract

The canonical source array remains `[slice, row, column]`. Its `array_index_to_patient_lps` affine maps source indices to DICOM patient LPS coordinates. Phase 3D derives the patient-space bounds and effective sampling interval along LPS X/Y/Z, then resamples orthogonal MPR planes with trilinear interpolation.

The display conventions are:

- Axial: left R, right L, top A, bottom P
- Coronal: left R, right L, top S, bottom I
- Sagittal: left A, right P, top S, bottom I

CT defaults to W/L 400/40. MR uses the stored modality intensity range as its initial window.

## HTTP boundary

Authenticated endpoints:

- `GET /api/studies/latest/mpr` returns the safe MPR descriptor
- `GET /api/studies/latest/mpr/{plane}` returns raw 8-bit grayscale pixels with width/height/index/position headers

Responses use `Cache-Control: no-store`. Internal study paths, DICOM filenames, and derived artifact paths are not exposed.

## Phase 3 closure

After Phase 3D acceptance, the complete Phase 3 pipeline is:

`DICOM upload -> Study/Series discovery -> geometry qualification -> canonical patient volume -> real synchronized MPR`

Patient-specific 3D anatomy extraction remains the next major phase.
