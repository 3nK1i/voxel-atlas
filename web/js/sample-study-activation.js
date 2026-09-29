export function classifySampleStudyActivation(payload) {
  const study = payload?.study;
  if (!study || typeof study !== "object" || Array.isArray(study)) {
    throw new Error("The sample study response was incomplete");
  }
  if (study.volume_ready === true) return "restore";
  if (study.reconstruction_ready === true) return "construct";
  return "review";
}
