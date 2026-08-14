import maplibregl, { Map as MLMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import type { DetectionFeature, DetectionFeatureCollection, Scene } from "./types";

const API_BASE = "/api";

const SEVERITY_COLOR: Record<string, string> = {
  low: "#f5c542",
  moderate: "#f57c1f",
  high: "#c62828",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);

  const [scenes, setScenes] = useState<Scene[]>([]);
  const [detections, setDetections] = useState<DetectionFeature[]>([]);
  const [selected, setSelected] = useState<DetectionFeature | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/scenes`).then((r) => r.json()),
      fetch(`${API_BASE}/detections`).then((r) => r.json()),
    ])
      .then(([sceneData, detectionData]: [Scene[], DetectionFeatureCollection]) => {
        setScenes(sceneData);
        setDetections(detectionData.features);
      })
      .catch(() => setError("Could not reach the WildfireWatch API. Is it running on :8000?"));
  }, []);

  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return;
    mapRef.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [20, 30],
      zoom: 2,
    });
    mapRef.current.addControl(new maplibregl.NavigationControl(), "top-right");
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || detections.length === 0) return;

    const geojson: DetectionFeatureCollection = { type: "FeatureCollection", features: detections };

    const render = () => {
      if (map.getSource("detections")) {
        (map.getSource("detections") as maplibregl.GeoJSONSource).setData(geojson as never);
        return;
      }
      map.addSource("detections", { type: "geojson", data: geojson as never });
      map.addLayer({
        id: "detections-fill",
        type: "fill",
        source: "detections",
        paint: {
          "fill-color": [
            "match",
            ["get", "severity"],
            "low",
            SEVERITY_COLOR.low,
            "moderate",
            SEVERITY_COLOR.moderate,
            "high",
            SEVERITY_COLOR.high,
            "#999999",
          ],
          "fill-opacity": 0.55,
        },
      });
      map.addLayer({
        id: "detections-outline",
        type: "line",
        source: "detections",
        paint: { "line-color": "#3a0d0d", "line-width": 1 },
      });
      map.on("click", "detections-fill", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const match = detections.find((d) => d.properties.id === feature.properties?.id);
        if (match) setSelected(match);
      });
      map.on("mouseenter", "detections-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "detections-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) render();
    else map.once("load", render);

    const bounds = new maplibregl.LngLatBounds();
    detections.forEach((d) => d.geometry.coordinates[0].forEach((c) => bounds.extend(c as [number, number])));
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 60, maxZoom: 12 });
    }
  }, [detections]);

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>WildfireWatch</h1>
        <p className="subtitle">Sentinel-2 burned-area detection</p>

        {error && <div className="error">{error}</div>}

        <section>
          <h2>Detections ({detections.length})</h2>
          <ul className="detection-list">
            {detections.map((d) => (
              <li
                key={d.properties.id}
                className={selected?.properties.id === d.properties.id ? "selected" : ""}
                onClick={() => {
                  setSelected(d);
                  const bounds = new maplibregl.LngLatBounds();
                  d.geometry.coordinates[0].forEach((c) => bounds.extend(c as [number, number]));
                  mapRef.current?.fitBounds(bounds, { padding: 100, maxZoom: 14 });
                }}
              >
                <span className="severity-dot" style={{ background: SEVERITY_COLOR[d.properties.severity] }} />
                <div>
                  <div className="row-title">
                    {d.properties.severity} · {d.properties.area_ha.toFixed(1)} ha
                  </div>
                  <div className="row-sub">{formatDate(d.properties.detected_at)}</div>
                </div>
              </li>
            ))}
            {detections.length === 0 && !error && <li className="empty">No detections yet.</li>}
          </ul>
        </section>

        {selected && (
          <section className="detail">
            <h2>Detection detail</h2>
            <dl>
              <dt>Severity</dt>
              <dd>{selected.properties.severity}</dd>
              <dt>Mean dNBR</dt>
              <dd>{selected.properties.dnbr_mean.toFixed(3)}</dd>
              <dt>Area</dt>
              <dd>{selected.properties.area_ha.toFixed(2)} ha</dd>
              <dt>Detected</dt>
              <dd>{formatDate(selected.properties.detected_at)}</dd>
            </dl>
          </section>
        )}

        <section>
          <h2>Scenes ({scenes.length})</h2>
          <ul className="scene-list">
            {scenes.map((s) => (
              <li key={s.id}>
                <div className="row-title">{formatDate(s.sensing_time)}</div>
                <div className="row-sub">
                  {s.cloud_cover.toFixed(1)}% cloud · {s.processing_status}
                </div>
              </li>
            ))}
          </ul>
        </section>
      </aside>
      <div ref={mapContainer} className="map" />
    </div>
  );
}
