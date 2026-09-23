/** 6J-B2B: safe, non-executing pre-volume MRI admission presentation.
 * Runs on the public study descriptor from the existing sample and upload paths.
 * Canonical MR geometry and stored-source validation remain server-authoritative.
 */
const UID = /^[0-9]+(?:\.[0-9]+)+$/;

export function prevolumeMriWorkflow(study, { volumeBuildFailed = false } = {}) {
  if (!study || study.volume_ready === true) return null;
  const series = Array.isArray(study.series) ? study.series : [];
  const selectedUid = study.reconstruction_series_uid || study.primary_series_uid;
  const selected = series.find(item => item?.series_instance_uid === selectedUid);
  // A mixed study whose selected series is CT must retain the existing CT UI.
  if (selected?.modality !== "MR") {
    if (!Array.isArray(study.modalities) || study.modalities.length !== 1
        || study.modalities[0] !== "MR") return null;
  }
  const geometricallyReady = Boolean(
    study.reconstruction_ready === true
    && typeof study.reconstruction_series_uid === "string"
    && UID.test(study.reconstruction_series_uid)
    && selected?.series_instance_uid === study.reconstruction_series_uid
    && selected?.modality === "MR"
    && selected?.geometry?.reconstruction_ready === true,
  );
  const state = geometricallyReady && !volumeBuildFailed ? "waiting" : "unsupported";
  const message = !geometricallyReady
    ? "MRI segmentation is unavailable: no reconstruction-qualified MR series is selected. Review the DICOM series and geometry before building a volume."
    : volumeBuildFailed
      ? "MRI segmentation is unavailable: canonical volume construction failed. Review the volume-building status and source series."
      : "MRI series geometry is qualified. Waiting for canonical patient volume construction before MRI segmentation source qualification.";
  return {
    schema_version: 1,
    study_id: study.study_id,
    modality: "MR",
    provider_id: "totalsegmentator",
    model_id: "total_mr",
    provider_available: false,
    provider_reason: message,
    source_qualified: false,
    source_qualification_reason: message,
    clinical_validation: "not_claimed",
    state, message,
    can_start: false, can_cancel: false, can_use: false,
    label_map_id: null, present_label_count: 0, job_id: null, progress: null,
  };
}
