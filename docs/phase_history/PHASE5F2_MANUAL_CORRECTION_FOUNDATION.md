# Phase 5F2 - Manual Correction Foundation

## Scope

Phase 5F2 introduces a non-destructive correction and review foundation over the
immutable Phase 5C canonical label map. It adds durable edit drafts, Patient LPS
interaction hooks in the actual workspace, reversible history, and explicit
segmentation-quality warnings.

This phase does not silently rewrite a label map, claim that draft intent has
been applied, smooth or repair a 3D surface, or make a clinical accuracy claim.

## Durable draft contract

`SegmentationCorrectionService` stores private manifests below
`data/segmentation/correction-sessions`. A session is bound to the active study,
canonical label-map identity, and canonical artifact SHA-256. That binding is
revalidated whenever a session is read or changed.

Actions are sparse intent records with an include, exclude, or review kind; a
present nonzero label; a three-component Patient LPS center; a bounded physical
radius; and the originating MPR plane. Undo and redo move an applied-action
cursor without changing action content. Adding after undo truncates the redo
branch. Discarded sessions are no longer editable.

Every atomic manifest revision has a canonical SHA-256. Public responses expose
no filesystem paths and state both `source_label_map=immutable` and
`materialization=not_applied`.

## Quality-warning contract

The selected-label quality route checks the current study, label presence,
array geometry, and source artifact seal before inspecting the label. It reports
the voxel count and acquisition-boundary contact, followed by structured warning
records. The persistent notices state that clinical validation is not claimed,
correction drafts are not materialized, and the voxel-boundary 3D geometry is a
preview pending Phase 6 refinement.

The authenticated no-store routes are:

- `GET /api/studies/latest/segmentation-quality/{label_id}`
- `POST /api/segmentation/correction-sessions`
- `GET /api/segmentation/correction-sessions`
- `GET /api/segmentation/correction-sessions/{session_id}`
- `POST /api/segmentation/correction-sessions/{session_id}/actions`
- `POST /api/segmentation/correction-sessions/{session_id}/undo`
- `POST /api/segmentation/correction-sessions/{session_id}/redo`
- `POST /api/segmentation/correction-sessions/{session_id}/discard`

## Workspace contract

The Segmentation Review section follows the Phase 5E selected structure. It
offers a compact action selector, physical radius control, explicit
apply-at-crosshair command, undo, redo, and discard. The last MPR plane used by
the operator and the shared Patient LPS crosshair define the draft action.
The newest valid draft for the active study and label map is resumed after a
workspace reload.

The UI deliberately calls include and exclude records "intent". The sealed MPR
overlays and Phase 5F1 surface do not change until a future materialization
contract exists, preventing a draft from being mistaken for derived anatomy.

## Qualification boundary

Automated checks cover study and digest binding, geometry limits, revision
tamper rejection, reversible history, redo truncation, discard semantics,
authentication, no-store responses, browser validation, patient-data Git
safety, heavy-runtime isolation, and full prior regression.

Real qualification creates one review action on an installed canonical map,
exercises undo and redo, discards the qualification draft, and proves the source
artifact digest did not change. Manual app qualification confirms the selected
structure, crosshair, controls, history state, and warnings remain synchronized.
This remains non-clinical workflow qualification.
