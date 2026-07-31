---
icon: material/map
hide:
  - tags
---

# :material-map: Maps

## Web Map Library — MapLibre GL JS

Open-source map rendering library, fork of Mapbox GL JS v1.

- [MapLibre GL JS Docs](https://maplibre.org/maplibre-gl-js/docs/)
- [MapLibre Style Spec v8](https://maplibre.org/maplibre-style-spec/)
- [MapLibre Examples](https://maplibre.org/maplibre-gl-js/docs/examples/)
- [MapLibre API Reference](https://maplibre.org/maplibre-gl-js/docs/API/)
- [GitHub: maplibre/maplibre-gl-js](https://github.com/maplibre/maplibre-gl-js)
- [Awesome MapLibre](https://github.com/maplibre/awesome-maplibre)
- [Demo Tiles](https://demotiles.maplibre.org/)
- npm: `maplibre-gl` — vector `^5.5.0`

### Controls

- `NavigationControl` — zoom, compass, pitch reset
- `ScaleControl` — scale bar
- `FullscreenControl` — fullscreen toggle
- `GeolocateControl` — user location
- `TerrainControl` — 3D pitch toggle

______________________________________________________________________

## Self-hosted Basemaps — Protomaps

Open-source map tile system using PMTiles (single-file tile archive).

- [Protomaps Docs](https://docs.protomaps.com/)
- [Getting Started Guide](https://docs.protomaps.com/guide/getting-started)
- [Basemap Download & Preview](https://maps.protomaps.com/)
- [PMTiles Viewer](https://pmtiles.io/)
- [PMTiles Spec](https://github.com/protomaps/PMTiles)
- [GitHub: protomaps/go-pmtiles](https://github.com/protomaps/go-pmtiles)

### npm Packages

- `pmtiles` — register custom `pmtiles://` protocol for MapLibre
- `@protomaps/basemaps` — generate full basemap style (roads, buildings, water, labels)

### CLI Tools

- `pmtiles` (go-pmtiles) — install via `brew install protomaps/tap/pmtiles`
- `tippecanoe` — install via `brew install tippecanoe`; converts GeoJSON → PMTiles

### Resources

- [bboxfinder.com](http://bboxfinder.com/) — draw rectangle, copy bbox coords
- [geojson.io](https://geojson.io) — draw shapes, export GeoJSON

______________________________________________________________________

## Other Map Tools

- [Leaflet](https://leafletjs.com/) — Lightweight open-source map library
- [OpenStreetMap](https://www.openstreetmap.org/) — Free raster tile source
- [MapLibre Demo Tiles](https://demotiles.maplibre.org/) — Free vector tiles for testing
