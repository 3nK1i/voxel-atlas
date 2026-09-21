// The fixed Patient-LPS -> VoxelAtlas viewer basis in segmentation-surface-viewer.js
// has negative determinant. BufferGeometry.applyMatrix4 transforms positions and
// normals but does not reverse triangle index winding. The display-only copy below
// restores front-face orientation under that reflection. Canonical VXSF bytes
// and the decoded source index buffer remain unchanged.
export function segmentationViewerWinding(sourceIndices) {
  if (!(sourceIndices instanceof Uint32Array)) {
    throw new TypeError("Segmentation source indices must be a Uint32Array");
  }
  if (sourceIndices.length === 0 || sourceIndices.length % 3 !== 0) {
    throw new RangeError("Segmentation surface triangle index count is invalid");
  }
  const viewerIndices = sourceIndices.slice();
  for (let i = 0; i < viewerIndices.length; i += 3) {
    const second = viewerIndices[i + 1];
    viewerIndices[i + 1] = viewerIndices[i + 2];
    viewerIndices[i + 2] = second;
  }
  return viewerIndices;
}
