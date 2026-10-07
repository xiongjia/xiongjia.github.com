/**
 * Selectors for Recharts' rendered DOM.
 *
 * These are library internals rather than public API, so the whole test suite
 * depends on them through this module: they are pinned through `recharts@3.8.0`
 * and are the first thing to re-check when bumping Recharts.
 */

/** Number of chart SVG surfaces rendered inside `root`. */
export function chartSurfaceCount(root: ParentNode): number {
  return root.querySelectorAll(".recharts-surface").length;
}

/** The `<path>` elements of every drawn line series. */
export function lineCurvePaths(root: ParentNode): Element[] {
  return Array.from(root.querySelectorAll(".recharts-line .recharts-curve"));
}

/** Number of drawn bars (one per category). */
export function barRectangleCount(root: ParentNode): number {
  return root.querySelectorAll(".recharts-bar-rectangle").length;
}

/** Number of drawn pie/donut sectors. */
export function pieSectorCount(root: ParentNode): number {
  return root.querySelectorAll(".recharts-sector").length;
}
