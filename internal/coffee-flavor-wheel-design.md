# Coffee Flavor Wheel — Design Document

> An interactive SCA-style coffee flavor wheel for the Notes site Tools
> section. Pure vanilla HTML + CSS + SVG + JavaScript, zero dependencies,
> data-driven rendering from a nested flavor tree.

## Overview

A concentric-ring flavor wheel rendered as a single SVG. Users explore from
the center (generic "风味") outward through broad categories (花香, 水果,
糖类/焦糖 …) down to specific flavor notes (草莓, 葡萄干, 烟熏 …). Hovering
highlights the hovered node's whole clan — itself, all ancestors, and all
descendants — while dimming everything else; clicking locks the selection and
shows the full path and a short description. Clicking the center circle or
empty SVG area unlocks.

Implementation lives as a single self-contained page
(`docs/notes/tools/coffee-flavor-wheel.md`) with shared widget styles in
`docs/assets/stylesheets/tools.css` (`.cfw-*` prefix), following the Ramen
Timer / Med Tracker tool pattern.

## Architecture

```
┌────────────────────────────────────────────────┐
│ Data Layer    flavor tree → flatten (id/depth/ │
│               parentId/children) → byId index  │
│               → assignAngles (equal 360° split)│
├────────────────────────────────────────────────┤
│ Render Layer  SVG <path> annulus per node →    │
│               arcPath() (2 arcs + 2 radial     │
│               lines) → label placement/rotation│
├────────────────────────────────────────────────┤
│ Interaction   hover → highlight clan + dim     │
│               click → lock + info panel        │
│               center/blank → unlock            │
├────────────────────────────────────────────────┤
│ UI Layer      info panel (title/desc/path) +   │
│               category legend + hint           │
└────────────────────────────────────────────────┘
```

## Data Layer

### Flavor tree (in-page constant)

Nested tree: root `风味` → 8 categories (花香, 水果, 糖类/焦糖, 坚果/可可,
香料, 烘焙, 谷物/植物, 化学/瑕疵) → sub-categories (only under 水果:
浆果/干果/柑橘/其他水果) → leaf notes. Each node carries `name` and `color`.

### Flatten (id-based, fixes design-doc bug)

The original design doc flattened nodes but kept `children` pointing at the
raw tree, then ran angle assignment and rendering on the raw tree — which has
no `depth`/`id`, producing `NaN` paths. The implementation builds a **fully
flat tree**: every node gets `id`, `depth`, `parentId` and a `children` array
of flat descendants; all downstream phases (angles, render, highlight) operate
on this single tree, with a `byId` map for O(1) lookups.

```js
function flatten(node, depth, parentId) {
  var flat = { id: nextId++, name: node.name, color: node.color,
               depth: depth, parentId: parentId, children: [] };
  allNodes.push(flat); byId[flat.id] = flat;
  (node.children || []).forEach(function (c) {
    flat.children.push(flatten(c, depth + 1, flat.id));
  });
  return flat;
}
```

### Angle assignment

Top-down equal split of 2π. Each node stores `startAngle`/`endAngle`
(radians); children evenly divide the parent's span.

```js
function assignAngles(node, sa, ea) {
  node.startAngle = sa; node.endAngle = ea;
  var n = node.children.length;
  if (n === 0) return;
  var span = (ea - sa) / n, cur = sa;
  node.children.forEach(function (c) {
    assignAngles(c, cur, cur + span); cur += span;
  });
}
assignAngles(root, 0, Math.PI * 2);
```

## Render Layer

### Sector path (`arcPath`)

Each non-root node becomes an annulus: outer arc, inner arc, and two radial
lines. `largeArc` flag handles spans > π (never occurs with 8+ categories,
kept for generality).

```js
function arcPath(sa, ea, rIn, rOut) {
  // x1..x4 = inner-start, outer-start, outer-end, inner-end
  var largeArc = (ea - sa) > Math.PI ? 1 : 0;
  return "M " + x1 + " " + y1 + " L " + x2 + " " + y2 +
         " A " + rOut + " " + rOut + " 0 " + largeArc + " 1 " + x3 + " " + y3 +
         " L " + x4 + " " + y4 +
         " A " + rIn + " " + rIn + " 0 " + largeArc + " 0 " + x1 + " " + y1 + " Z";
}
```

### Radii

- `viewBox 0 0 600 600`, center `(300, 300)`, `innerR = 45` (center circle),
  `outerR = 280`
- **Ring width is computed per category**, not globally: each top-level
  category's ring width is `(outerR − innerR) / subtreeMaxDepth(category)`,
  where `subtreeMaxDepth` is the deepest node level within that category.
  This keeps every category's leaves flush to the outer edge even though
  branches have different depths (e.g. 2-level 花香 vs 3-level 水果) — a
  global `maxDepth` would leave a blank outer band for shallow categories.
- Node at depth d: inner `innerR + (d−1)·ringWidth`, outer
  `innerR + d·ringWidth − 2` (2px gap between rings)

### Labels

Placed at mid-angle, mid-radius. Rotated to radial alignment when the sector
is narrow (`depth >= 3` or span < 0.25 rad) so text follows the spoke instead
of overflowing neighbors; rotation flips 180° on the left half of the wheel
to keep text upright. Labels are omitted entirely (no `<text>` node created)
when the sector's arc length at the label radius — `span × labelR` — is
smaller than the label font size (`LABEL_FONT_PX = 11`, matching
`.cfw-label` font-size); the sector stays hoverable and its name still
appears in the info panel.

### Styling notes

Sector `fill` is the node color (set as attribute); `stroke`/center circle/
text colors use Material theme variables via CSS (`.cfw-sector`,
`.cfw-center`, `.cfw-center-text`) — SVG presentation attributes cannot hold
`var()`, so those live in `tools.css`, not inline attributes.

## Interaction Layer

State machine:

```
 idle ──hover──▶ highlighted ──mouseleave──▶ idle
  │                 │
  │ click           │ click (same node)
  ▼                 ▼
 locked ◀───────────┘  (or center/blank click)
```

- **highlight(node, isLocked)**: collect node id + all descendant ids (recursive) +
  all ancestor ids (walk `parentId` chain); toggle `.cfw-dimmed` on every
  `.cfw-sector` not in the set; update info panel with `isLocked` (false for
  hover preview, true for locked).
- **toggleLock(node)**: same-node click unlocks (restore all, reset panel);
  new-node click locks via `highlight(node, true)`, marks panel with 🔒.
- **Unlock**: clicking the center circle or the SVG background clears lock
  and highlight.

## UI Layer

- **Info panel**: title (🔒 when locked), description (own description, else
  falls back to parent category's description, else generic text), and the
  full path `root → … → node` built by walking `parentId`.
- **Legend**: one dot + name per top-level category, built from `root.children`.
- **Hint**: one-line usage reminder below the legend.
- Responsive: label font shrinks under 600px (`@media`), SVG scales via
  `viewBox` + `width:100%`.

## Page & File Layout

| File                                      | Change                                                                                                                                                                  |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/notes/tools/coffee-flavor-wheel.md` | **New** — tool page: frontmatter (`icon: material/coffee`, hide tags), embedded SVG container + info panel + legend + hint, inline `<script>` (IIFE, ES5), usage tables |
| `docs/assets/stylesheets/tools.css`       | Append `.cfw-*` widget styles (Material theme variables, light/dark aware)                                                                                              |
| `mkdocs.yml`                              | Register `Coffee Flavor Wheel: notes/tools/coffee-flavor-wheel.md` under Tools nav                                                                                      |
| `docs/notes/tools/index.md`               | Add `[:material-coffee: 咖啡风味轮](./coffee-flavor-wheel.md)` row to the tools table                                                                                   |

## Dependencies

| Component    | Usage                        |
| ------------ | ---------------------------- |
| Vanilla JS   | Data, rendering, interaction |
| SVG          | Wheel geometry (no libs)     |
| CSS vars     | Light/dark theme adaptation  |
| No libraries | Zero external dependencies   |

## Edge Cases

- **Duplicate names**: avoided by using ids (not name+depth lookup) for
  highlight/path logic.
- **Narrow sectors**: radial label rotation + small font under 600px;
  labels whose arc length at the label radius is below the font size are
  omitted entirely (info panel still shows the name on hover/click).
- **Dark mode**: sector colors are fixed pastels; strokes/center/text use
  theme variables, so the wheel adapts automatically.
- **Touch devices**: `click` events work on tap; sectors are large enough to
  be tappable.

## Acceptance Checklist

- [x] Wheel renders with all 70 sectors (8 categories + 4 sub-categories + 58 leaves)
- [x] Hover highlights clan (self + ancestors + descendants), dims the rest
- [x] Click locks; info panel shows title/description/path; re-click unlocks
- [x] Center circle / blank click unlocks
- [x] Legend lists all 8 categories with colors
- [x] `node --check` passes on extracted script; `poe build` succeeds
- [x] mdformat clean on the tool page and tools index

## Extensions (future)

| Direction     | Idea                                                          |
| ------------- | ------------------------------------------------------------- |
| Full SCA data | Replace the 70-node subset with the complete SCA 110+ lexicon |
| Chemistry     | Per-node compounds (e.g. 芳樟醇 C₁₀H₁₈O), thresholds, OAV     |
| Multi-select  | Lock several flavors, export a "flavor report"                |
| Voice input   | Say a flavor, auto-highlight the matching node                |
| Temperature   | Slider simulating hot→cool flavor evolution                   |

## Related

- [Tools index](../docs/notes/tools/index.md) — site listing
- [Ramen Timer Tool](../docs/notes/tools/ramen-timer.md) — sibling tool,
  same `.tools.css` shared stylesheet
- [Architecture](./architecture.md)
