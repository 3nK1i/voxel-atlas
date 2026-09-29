#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'web/js/app.js').read_text(encoding='utf-8')
VOL = (ROOT / 'web/js/volume-surface-viewer.js').read_text(encoding='utf-8')
SEG = (ROOT / 'web/js/segmentation-surface-viewer.js').read_text(encoding='utf-8')
SHARED = (ROOT / 'web/js/reconstruction-surface-presentation.js').read_text(encoding='utf-8')
INDEX = (ROOT / 'web/index.html').read_text(encoding='utf-8')
DOC = (ROOT / 'docs/phase_history/PHASE6E_B_SHARED_LIGHTING_MATERIAL_FOUNDATION.md').read_text(encoding='utf-8')


def require(cond: bool, label: str):
    if not cond:
        raise SystemExit(f'{label}=FAIL')
    print(f'{label}=PASS')


def block(text: str, start: str, end: str):
    a = text.index(start); b = text.index(end, a); return text[a:b]

profile_apply = block(APP, 'function applyReconstructionPresentationProfileSnapshot(', 'function requestReconstructionPresentationProfile(')
scene_block = block(APP, 'const scene = new THREE.Scene();', 'const camera = new THREE.PerspectiveCamera')

require('createSurfaceLightingRig' in APP and 'surfaceLightingRig' in APP, 'PHASE6E_B_SHARED_LIGHT_RIG_WIRED')
require('new THREE.HemisphereLight' not in scene_block and 'new THREE.DirectionalLight' not in scene_block, 'PHASE6E_B_INLINE_LIGHTS_REMOVED')
require('surfaceLightingRig.setProfile(snapshot.profile)' in profile_apply, 'PHASE6E_B_PROFILE_DRIVES_LIGHTING')
require('volumeSurfaceLayer?.setPresentationProfile(snapshot.profile)' in profile_apply, 'PHASE6E_B_PROFILE_DRIVES_DIRECT_CT_MATERIAL')
require('segmentationSurfaceLayer?.setPresentationProfile(snapshot.profile)' in profile_apply, 'PHASE6E_B_PROFILE_DRIVES_SEGMENTATION_MATERIAL')
require(all(t not in profile_apply.lower() for t in ('fetch(', '.build(', 'clearsurface', 'segmentation-workflow')), 'PHASE6E_B_PROFILE_SWITCH_NO_IO_BUILD')
require('setPresentationProfile(profileId)' in VOL and 'applyVolumeSurfaceMaterialProfile' in VOL, 'PHASE6E_B_DIRECT_CT_SHARED_MATERIAL')
require('setPresentationProfile(profileId)' in SEG and 'applySegmentationSurfaceMaterialProfile' in SEG, 'PHASE6E_B_SEGMENTATION_SHARED_MATERIAL')
require('structure?.colorHex' in SHARED and 'applySegmentationSurfaceMaterialProfile' in SEG, 'PHASE6E_B_SEMANTIC_COLOR_PRESERVED')
require('fidelity:' in SHARED and 'presentation:' in SHARED, 'PHASE6E_B_BOTH_PROFILES_HAVE_RENDER_PRESETS')
require('value="300"' in INDEX and 'Bone baseline: 300 HU when in range' in INDEX, 'PHASE6D1_300HU_BASELINE_PRESERVED')
require('phase6e-b-r1' in INDEX and 'phase6e-b-r1' in APP, 'PHASE6E_B_BROWSER_CACHE_BOUNDARY')
require('6E-C' in DOC and '6E-D' in DOC, 'PHASE6E_B_LATER_QUALIFICATION_BOUNDARIES')
require('Clinical validation is not claimed' in DOC, 'CLINICAL_VALIDATION_NOT_CLAIMED')
print('PHASE6E_B_ARCHITECTURE_OK=YES')
