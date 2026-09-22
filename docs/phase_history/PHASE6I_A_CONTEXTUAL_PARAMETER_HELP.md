# Phase 6I-A — contextual parameter help

## Scope

Presentation-only help added to the existing CT / segmentation workspace. This step
changes `web/index.html`, `web/css/styles.css`, and introduces the isolated
`web/js/parameter-help.js` module. It does not change rendering, clipping,
segmentation, source artefacts, or 6H qualification behavior.

The help module enhances all three left-sidebar reconstruction modes with
independent, keyboard-accessible help controls adjacent to the existing mode
buttons (including when a mode button is disabled), static controls in the
right sidebar (including controls currently hidden by unavailable modes), and dynamically rendered anatomical
structure rows. Descriptions cover volume display, surface sources, CT
isosurface threshold and region visibility, segmentation overlays, structure
presentation, two-sided Patient-LPS clipping boundaries, and reversible draft
segmentation review. Each control provides an explicit click-to-open `?`
explanation. Information is injected as text, never fetched or loaded from
patient data. The popover supports Enter/Space, Escape, click-away, close,
focus return, and viewport-aware positioning. Clicking a help icon must not
operate its containing parameter even if the caption is inside a native label.

## Explicitly deferred

- Phase 6I-B: automatic Direct CT surface lifecycle and segmentation action styling.
- Phase 6I-C: two-sided clipping slider auto-activation / checkbox removal.
- Phase 6I-D: Presentation-only UI and Direct CT visibility dropdown correction.

## Qualification and acceptance

Before applying the 6I-A completion patch, verify the actual Phase I.6 baseline
`1978288ba19e1d62ab1e29bb7f5c6804da64b8ef`, the six-file working-tree
candidate, and the SHA256 values of the expected pre-patch files. The completion
patch updates only the existing help JavaScript, HTML, CSS, contract tests, and
this documentation; the six-file Phase 6I-A candidate remains the Git scope.
Run `bash scripts/run_phase6i_a_checks.sh` in the development checkout.
Then start the isolated local UI preview and verify click, keyboard, dark/light
appearance, long text, help on all three modes (including unavailable modes),
hidden/conditionally revealed controls, dynamically
recreated structure rows, and no changes to existing checkbox/slider/select
values or reconstruction modes when help is opened. Sample both CT and segmentation controls. Follow
up with a small Surface/Volume/Combined backward-compatibility sanity check.
Do not assert production deployment or clinical qualification from this UI test.
