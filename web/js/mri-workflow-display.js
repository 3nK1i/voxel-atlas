/** C4C: identity-bound MRI status in the existing panel; never authorizes inference. */
export function isReadOnlyMri(workflow) {
  return workflow?.modality === 'MR' && workflow?.model_id === 'total_mr';
}

export function workflowMatchesStudy(workflow, study) {
  if (!workflow || !study || workflow.study_id !== study.study_id) return false;
  const series = Array.isArray(study.series) ? study.series : [];
  const selectedUid = study.reconstruction_series_uid || study.primary_series_uid;
  const selected = series.find(item => item?.series_instance_uid === selectedUid);
  const modality = selected?.modality || study.volume?.modality ||
    (Array.isArray(study.modalities) && study.modalities.length === 1 ? study.modalities[0] : null);
  if (modality === 'MR') {
    return isReadOnlyMri(workflow) && typeof workflow.source_series_uid === 'string'
      && workflow.source_series_uid === selectedUid;
  }
  if (modality === 'CT') {
    return workflow.modality === 'CT' && !isReadOnlyMri(workflow);
  }
  return false;
}
