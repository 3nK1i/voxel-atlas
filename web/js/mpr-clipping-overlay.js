// Display-only Patient LPS clipping overlays. Never alter reference pixels.
const AXIS_PLANE = Object.freeze({ x: "sagittal", y: "coronal", z: "axial" });
const inactive = () => ({ active: false, outside: false, rectangles: [], lines: [] });
const clamp01 = (value) => Math.max(0, Math.min(1, value));

export function projectMprClipping(plane, request, displayedPositionLpsMm) {
  if (!plane || !Number.isFinite(displayedPositionLpsMm)) return inactive();
  const axes = [plane.horizontal_axis, plane.vertical_axis, plane.normal_axis];
  if (new Set(axes).size !== 3 || axes.some((a) => !AXIS_PLANE[a])) return inactive();
  const ranges = [plane.horizontal_range_mm, plane.vertical_range_mm];
  if (ranges.some((r) => !Array.isArray(r) || r.length !== 2
      || !r.every(Number.isFinite) || r[1] <= r[0])) return inactive();
  const limits = axes.map((a) => request?.[AXIS_PLANE[a]]);
  if (!limits.some((b) => b?.enabled)) return inactive();
  if (limits.some((b) => b?.enabled && (!Number.isFinite(b.minimumLpsMm)
      || !Number.isFinite(b.maximumLpsMm) || b.maximumLpsMm <= b.minimumLpsMm))) return inactive();

  const normal = limits[2];
  const outside = Boolean(normal?.enabled && (displayedPositionLpsMm < normal.minimumLpsMm
    || displayedPositionLpsMm > normal.maximumLpsMm));
  if (outside) return {
    active: true, outside: true,
    rectangles: [{ x: 0, y: 0, width: 1, height: 1 }], lines: [],
  };
  const normalized = (limit, range, reverse) => {
    if (!limit?.enabled) return [0, 1];
    const values = [limit.minimumLpsMm, limit.maximumLpsMm].map((v) => {
      const f = clamp01((v - range[0]) / (range[1] - range[0]));
      return reverse ? 1 - f : f;
    });
    return values.sort((a, b) => a - b);
  };
  const [left, right] = normalized(limits[0], ranges[0], false);
  const [top, bottom] = normalized(limits[1], ranges[1], Boolean(plane.vertical_reverse));
  // Four disjoint strips: exclusions never become darker at overlapping corners.
  const rectangles = [
    { x: 0, y: 0, width: 1, height: top },
    { x: 0, y: bottom, width: 1, height: 1 - bottom },
    { x: 0, y: top, width: left, height: bottom - top },
    { x: right, y: top, width: 1 - right, height: bottom - top },
  ].filter((r) => r.width > 0 && r.height > 0);
  const lines = [];
  if (limits[0]?.enabled) for (const x of [left, right]) {
    lines.push({ x1: x, x2: x, y1: 0, y2: 1 });
  }
  if (limits[1]?.enabled) for (const y of [top, bottom]) {
    lines.push({ x1: 0, x2: 1, y1: y, y2: y });
  }
  return { active: true, outside: false, rectangles, lines };
}

const overlays = new WeakMap();
export function renderMprClippingOverlay(surface, geometry) {
  let nodes = overlays.get(surface);
  if (!nodes) {
    if (!geometry?.active) return;
    const doc = surface.ownerDocument;
    const svgNode = (tag) => doc.createElementNS("http://www.w3.org/2000/svg", tag);
    const svg = svgNode("svg");
    svg.setAttribute("class", "mpr-clipping-overlay");
    svg.setAttribute("viewBox", "0 0 1 1");
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const rectangles = Array.from({ length: 4 }, () => svgNode("rect"));
    const lines = Array.from({ length: 4 }, () => {
      const line = svgNode("line");
      line.setAttribute("vector-effect", "non-scaling-stroke");
      return line;
    });
    svg.append(...rectangles, ...lines);
    const status = doc.createElement("span");
    status.setAttribute("class", "mpr-clipping-status");
    status.textContent = "Slice outside clipping ROI";
    status.hidden = true;
    surface.append(svg, status);
    nodes = { svg, status, rectangles, lines };
    overlays.set(surface, nodes);
  }
  nodes.svg.style.display = geometry?.active ? "block" : "none";
  nodes.status.hidden = !geometry?.active || !geometry.outside;
  if (!geometry?.active) return;
  const update = (elements, attributes) => elements.forEach((element, i) => {
    element.style.display = attributes[i] ? "" : "none";
    if (attributes[i]) for (const [name, value] of Object.entries(attributes[i])) {
      element.setAttribute(name, value);
    }
  });
  update(nodes.rectangles, geometry.rectangles);
  update(nodes.lines, geometry.lines);
}
