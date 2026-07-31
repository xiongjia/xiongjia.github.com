---
title: MapLibre GL JS & Protomaps Research
created: 2026-07-31
tags: [maps, gis, research, maplibre, protomaps]
---

# MapLibre GL JS & Protomaps Research

## Goal

Research MapLibre GL JS (^5.5.0) and Protomaps (PMTiles) for web mapping
in the vine project. Covers: map creation, controls, markers/layers, events,
camera/animation, clustering/heatmap, PMTiles integration, @protomaps/basemaps,
Tippecanoe, and self-hosted tile deployment.

Document findings under `docs/notes/research/` with hands-on notes, code snippets,
and integration workflow for the playground and atlas apps.

## Tasks

- [ ] **Research: MapLibre basics**

  - Map creation, style (inline JSON vs URL), coordinate system
  - Explore: center, zoom, attribution, interaction properties
  - Published to `docs/notes/research/`

- [ ] **Research: Controls & Markers**

  - NavigationControl, ScaleControl, GeolocateControl
  - Custom Marker (CSS/SVG), Popup (attached & independent)
  - Marker lifecycle in React (useRef, cleanup)
  - Published to `docs/notes/research/`

- [ ] **Research: Layers & Styles**

  - RasterSource, GeoJSONSource, VectorSource
  - Layer types: circle, symbol, line, fill, heatmap
  - Style Spec expressions: data-driven styling, zoom interpolation
  - Compare Marker vs Layer performance trade-offs
  - Published to `docs/notes/research/`

- [ ] **Research: Events & Camera**

  - Map events (load, move, click) vs Layer events (click features)
  - Event cleanup in React useEffect
  - flyTo, fitBounds, rotateTo, camera animation
  - Published to `docs/notes/research/`

- [ ] **Research: Clustering & Heatmap**

  - GeoJSON clustering (clusterMaxZoom, clusterRadius)
  - Cluster circle + count label layers
  - Heatmap layer (radius, weight, color ramp)
  - Published to `docs/notes/research/`

- [ ] **Research: Protomaps PMTiles integration**

  - pmtiles protocol registration with MapLibre
  - @protomaps/basemaps: layers(), namedFlavor(), lang support
  - Local testing with http-server or Vite public/
  - Published to `docs/notes/research/`

- [ ] **Research: PMTiles extraction & deployment**

  - pmtiles CLI: extract region from remote global file
  - bbox and GeoJSON region clipping
  - Upload to R2/S3, CORS config
  - Published to `docs/notes/research/`

- [ ] **Research: Tippecanoe & self-built tiles**

  - Convert GeoJSON → PMTiles with tippecanoe
  - source-layer mapping, projection notes
  - Protomaps Planetiler pipeline (OSM PBF → PMTiles)
  - Published to `docs/notes/research/`

- [ ] **Integration guide: vine project end-to-end**

  - Playground MDX page for MapLibre experiments
  - AtlasMap: toggle basemap (OSM raster ↔ Protomaps vector)
  - Marker → Layer migration strategy for product markers
  - Bundle optimization (Vite manualChunks)
  - Published to `docs/notes/research/`

## Notes

- Source material: `~/Work/self/vine/docs/learn-maplibre-draft.md`
- Target: integrate MapLibre + Protomaps into vine's atlas and playground apps
- All tools are open-source / free
- Each research doc should include: overview, code snippets, hands-on notes

## References

- [Collection: Maps](../../docs/notes/collection/maps.md)
