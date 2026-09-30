// Canonical semantic-segmentation 3D anatomical colors for pinned TotalSegmentator
// structure identities. Never infer anatomy from label ID, intensity-derived Direct MR,
// or a structure's previous RGB. Do not mutate the shared MPR label palette.
const ANATOMICAL_3D_COLORS = Object.freeze({
  bone: '#d8c9a5',
  cartilage: '#c7bba5',
  muscle: '#a66c62',
  lung: '#b78384',
  trachea: '#b3a4a0',
  liver: '#8f5844',
  spleen: '#8e667b',
  kidney: '#a36c60',
  kidneyCyst: '#c4ad9a',
  gallbladder: '#69775b',
  stomach: '#c59485',
  pancreas: '#c9a078',
  adrenal: '#a98268',
  bowel: '#c38d80',
  duodenum: '#cba092',
  colon: '#ba887d',
  esophagus: '#b58b82',
  thyroid: '#ac7180',
  bladder: '#c1a389',
  prostate: '#a97978',
  heart: '#9f4b55',
  artery: '#a65355',
  vein: '#7485a3',
  portalVein: '#817b9b',
  brain: '#c8a5a0',
  spinalCord: '#c9b4a0',
});

const KNOWN_ORGANS = Object.freeze({
  spleen: ANATOMICAL_3D_COLORS.spleen,
  kidney_left: ANATOMICAL_3D_COLORS.kidney,
  kidney_right: ANATOMICAL_3D_COLORS.kidney,
  gallbladder: ANATOMICAL_3D_COLORS.gallbladder,
  liver: ANATOMICAL_3D_COLORS.liver,
  stomach: ANATOMICAL_3D_COLORS.stomach,
  pancreas: ANATOMICAL_3D_COLORS.pancreas,
  adrenal_gland_left: ANATOMICAL_3D_COLORS.adrenal,
  adrenal_gland_right: ANATOMICAL_3D_COLORS.adrenal,
  esophagus: ANATOMICAL_3D_COLORS.esophagus,
  thyroid_gland: ANATOMICAL_3D_COLORS.thyroid,
  small_bowel: ANATOMICAL_3D_COLORS.bowel,
  duodenum: ANATOMICAL_3D_COLORS.duodenum,
  colon: ANATOMICAL_3D_COLORS.colon,
  urinary_bladder: ANATOMICAL_3D_COLORS.bladder,
  prostate: ANATOMICAL_3D_COLORS.prostate,
  kidney_cyst_left: ANATOMICAL_3D_COLORS.kidneyCyst,
  kidney_cyst_right: ANATOMICAL_3D_COLORS.kidneyCyst,
});

const KNOWN_CARDIOVASCULAR = Object.freeze({
  heart: ANATOMICAL_3D_COLORS.heart,
  atrial_appendage_left: ANATOMICAL_3D_COLORS.heart,
  aorta: ANATOMICAL_3D_COLORS.artery,
  brachiocephalic_trunk: ANATOMICAL_3D_COLORS.artery,
  subclavian_artery_right: ANATOMICAL_3D_COLORS.artery,
  subclavian_artery_left: ANATOMICAL_3D_COLORS.artery,
  common_carotid_artery_right: ANATOMICAL_3D_COLORS.artery,
  common_carotid_artery_left: ANATOMICAL_3D_COLORS.artery,
  iliac_artery_left: ANATOMICAL_3D_COLORS.artery,
  iliac_artery_right: ANATOMICAL_3D_COLORS.artery,
  pulmonary_vein: ANATOMICAL_3D_COLORS.vein,
  brachiocephalic_vein_left: ANATOMICAL_3D_COLORS.vein,
  brachiocephalic_vein_right: ANATOMICAL_3D_COLORS.vein,
  superior_vena_cava: ANATOMICAL_3D_COLORS.vein,
  inferior_vena_cava: ANATOMICAL_3D_COLORS.vein,
  portal_vein_and_splenic_vein: ANATOMICAL_3D_COLORS.portalVein,
  iliac_vena_left: ANATOMICAL_3D_COLORS.vein,
  iliac_vena_right: ANATOMICAL_3D_COLORS.vein,
});

const KNOWN_RESPIRATORY = Object.freeze({
  lung_left: ANATOMICAL_3D_COLORS.lung,
  lung_right: ANATOMICAL_3D_COLORS.lung,
  lung_upper_lobe_left: ANATOMICAL_3D_COLORS.lung,
  lung_lower_lobe_left: ANATOMICAL_3D_COLORS.lung,
  lung_upper_lobe_right: ANATOMICAL_3D_COLORS.lung,
  lung_middle_lobe_right: ANATOMICAL_3D_COLORS.lung,
  lung_lower_lobe_right: ANATOMICAL_3D_COLORS.lung,
  trachea: ANATOMICAL_3D_COLORS.trachea,
});

const KNOWN_NERVOUS = Object.freeze({
  brain: ANATOMICAL_3D_COLORS.brain,
  spinal_cord: ANATOMICAL_3D_COLORS.spinalCord,
});

const EXTRA_BONES = new Set([
  'sacrum', 'sternum', 'skull',
  'humerus_left', 'humerus_right',
  'scapula_left', 'scapula_right',
  'clavicula_left', 'clavicula_right',
  'femur_left', 'femur_right',
  'hip_left', 'hip_right',
]);

function anatomicalColorForStructure(structure) {
  const name = structure?.name;
  if (typeof name !== 'string') return null;
  switch (structure.groupId) {
    case 'spine':
      if (name === 'intervertebral_discs') return ANATOMICAL_3D_COLORS.cartilage;
      return name === 'sacrum' || name === 'vertebrae'
        || /^vertebrae_[CLST](?:[1-9]|1[0-2])$/.test(name)
        ? ANATOMICAL_3D_COLORS.bone : null;
    case 'skeletal':
      if (name === 'costal_cartilages') return ANATOMICAL_3D_COLORS.cartilage;
      return EXTRA_BONES.has(name) || /^rib_(?:left|right)_(?:[1-9]|1[0-2])$/.test(name)
        ? ANATOMICAL_3D_COLORS.bone : null;
    case 'muscles':
      return /^(?:(?:gluteus_(?:maximus|medius|minimus)|iliopsoas|autochthon)_(?:left|right))$/.test(name)
        ? ANATOMICAL_3D_COLORS.muscle : null;
    case 'organs':
      return Object.hasOwn(KNOWN_ORGANS, name) ? KNOWN_ORGANS[name] : null;
    case 'respiratory':
      return Object.hasOwn(KNOWN_RESPIRATORY, name) ? KNOWN_RESPIRATORY[name] : null;
    case 'cardiovascular':
      return Object.hasOwn(KNOWN_CARDIOVASCULAR, name) ? KNOWN_CARDIOVASCULAR[name] : null;
    case 'nervous_system':
      return Object.hasOwn(KNOWN_NERVOUS, name) ? KNOWN_NERVOUS[name] : null;
    default:
      return null; // Unrecognized provider/task: preserve current scientific color.
  }
}

export function build3dAnatomicalColorOverrides(presentation) {
  if (!(presentation?.structures instanceof Map)) return new Map();
  const overrides = new Map();
  for (const structure of presentation.structures.values()) {
    const color = anatomicalColorForStructure(structure);
    if (color && Number.isInteger(structure.labelId) && structure.labelId > 0) {
      overrides.set(structure.labelId, color);
    }
  }
  return overrides;
}

export function resolve3dAppearanceContext(mode, descriptor, presentation) {
  if (mode !== 'scientific' && mode !== 'anatomical') {
    throw new RangeError('Unknown segmentation 3D color appearance');
  }
  const hasSemanticIdentity = descriptor?.provider_id !== undefined
    || descriptor?.model_id !== undefined
    || descriptor?.source_modality !== undefined;
  const semanticTask = !hasSemanticIdentity
    || (
      descriptor?.provider_id === 'totalsegmentator'
      && (
        (descriptor?.source_modality === 'CT' && descriptor?.model_id === 'total')
        || (descriptor?.source_modality === 'MR' && descriptor?.model_id === 'total_mr')
      )
    );
  const ready = semanticTask
    && descriptor?.ready === true
    && typeof descriptor.label_map_id === 'string'
    && descriptor.label_map_id.length > 0
    && descriptor.label_map_id === presentation?.labelMapId
    && presentation?.structures instanceof Map;
  return {
    ready,
    overrides: ready && mode === 'anatomical'
      ? build3dAnatomicalColorOverrides(presentation)
      : new Map(),
  };
}
