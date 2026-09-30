"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { useReducedMotion } from "framer-motion";
import type { GeoJSONSource, Map as MlMap, MapLayerMouseEvent } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { CwBadge, NeuCard, RiskBadge, RISK_ICON } from "@/components/neu";
import { HEX, MAP_LEGEND, MAP_SCALE, mapStep, RISK_TEXT_CLASS } from "@/lib/risk";
import { cn } from "@/lib/utils";
import type { RegionConfidence } from "@/types/api";

interface Props {
  geo?: GeoJSON.FeatureCollection;
  regions?: RegionConfidence[];
  thresholds?: { medium: number; high: number };
  selected?: string;
  onSelect: (id: string) => void;
  className?: string;
}

const INDIA_BOUNDS: [[number, number], [number, number]] = [
  [66.5, 6.5],
  [97.8, 37.5],
];

/** MapLibre map inside an inset tray. No external tiles: the "basemap" is a light neutral
 * background and the subdivision polygons derived from the IMD grid. */
export function MapTray({ geo, regions, thresholds, selected, onSelect, className }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const reduce = useReducedMotion();
  const byId = useMemo(() => new Map((regions ?? []).map((r) => [r.id, r])), [regions]);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // create the map once the geometry is available
  useEffect(() => {
    if (!geo || !box.current || map.current) return;
    let cancelled = false;
    (async () => {
      const ml = (await import("maplibre-gl")).default;
      if (cancelled || !box.current) return;
      const m = new ml.Map({
        container: box.current,
        style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": HEX.basemap } }] },
        bounds: INDIA_BOUNDS,
        fitBoundsOptions: { padding: 16 },
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
      });
      m.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
      m.addControl(new ml.AttributionControl({ compact: true, customAttribution: "Subdivisions derived from IMD gridded data" }));
      m.touchZoomRotate.disableRotation();
      m.on("load", () => {
        m.addSource("subs", { type: "geojson", data: geo, promoteId: "id" });
        m.addLayer({
          id: "fill",
          type: "fill",
          source: "subs",
          paint: {
            "fill-color": ["match", ["coalesce", ["feature-state", "step"], -1], 0, MAP_SCALE[0], 1, MAP_SCALE[1], 2, MAP_SCALE[2], 3, MAP_SCALE[3], 4, MAP_SCALE[4], HEX.grid],
            "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.85, 0.7],
          },
        });
        m.addLayer({ id: "outline", type: "line", source: "subs", paint: { "line-color": HEX.outline, "line-width": 0.8 } });
        m.addLayer({
          id: "cw",
          type: "line",
          source: "subs",
          paint: { "line-color": HEX.accent, "line-width": 2.5, "line-dasharray": [2, 1.2], "line-opacity": ["case", ["boolean", ["feature-state", "cw"], false], 1, 0] },
        });
        m.addLayer({
          id: "selected",
          type: "line",
          source: "subs",
          paint: { "line-color": HEX.accent, "line-width": 3.5, "line-opacity": ["case", ["boolean", ["feature-state", "selected"], false], 1, 0] },
        });
        let hovered: string | number | undefined;
        m.on("mousemove", "fill", (e: MapLayerMouseEvent) => {
          const f = e.features?.[0];
          if (!f) return;
          if (hovered !== undefined && hovered !== f.id) m.setFeatureState({ source: "subs", id: hovered }, { hover: false });
          hovered = f.id;
          m.setFeatureState({ source: "subs", id: f.id as string }, { hover: true });
          m.getCanvas().style.cursor = "pointer";
          setHover({ id: String(f.id), x: e.point.x, y: e.point.y });
        });
        m.on("mouseleave", "fill", () => {
          if (hovered !== undefined) m.setFeatureState({ source: "subs", id: hovered }, { hover: false });
          hovered = undefined;
          m.getCanvas().style.cursor = "";
          setHover(null);
        });
        m.on("click", "fill", (e: MapLayerMouseEvent) => {
          const id = e.features?.[0]?.id;
          if (id !== undefined) onSelectRef.current(String(id));
        });
        setReady(true);
      });
      map.current = m;
    })();
    return () => {
      cancelled = true;
    };
  }, [geo]);

  useEffect(() => () => map.current?.remove(), []);

  // colour by risk whenever the data changes
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !geo || !thresholds) return;
    if (!(m.getSource("subs") as GeoJSONSource | undefined)) return;
    geo.features.forEach((f) => {
      const id = String(f.properties?.id);
      const r = byId.get(id);
      m.setFeatureState({ source: "subs", id }, { step: r ? mapStep(r.bust_prob, thresholds) : -1, cw: !!r?.confidently_wrong, selected: id === selected });
    });
  }, [ready, geo, byId, thresholds, selected]);

  // gentle pulse on confidently-wrong outlines (off with reduced motion)
  useEffect(() => {
    const m = map.current;
    if (!ready || !m || reduce) return;
    let on = false;
    const t = setInterval(() => {
      on = !on;
      if (m.getLayer("cw")) m.setPaintProperty("cw", "line-width", on ? 4 : 2.5);
    }, 900);
    return () => clearInterval(t);
  }, [ready, reduce]);

  const hr = hover ? byId.get(hover.id) : undefined;
  return (
    <div className={cn("relative rounded-card bg-bg p-3 shadow-neu-inset-deep", className)}>
      <div ref={box} className="h-full w-full overflow-hidden rounded-panel" aria-label="Map of forecast bust risk by IMD subdivision; use the ranked list for keyboard selection" role="region" />
      {!geo && <div className="absolute inset-3 grid place-items-center rounded-panel text-sm text-muted">Loading map…</div>}
      {hr && hover && (
        <div className="pointer-events-none absolute z-10" style={{ left: Math.min(hover.x + 20, 9999), top: hover.y + 16 }}>
          <NeuCard compact className="w-60 space-y-2 p-4">
            <div className="font-display text-sm font-bold text-fg">{hr.name}</div>
            <div className="flex items-center justify-between">
              <span className="font-display text-2xl font-extrabold tabular text-fg">{(hr.bust_prob * 100).toFixed(1)}%</span>
              <RiskBadge risk={hr.risk} />
            </div>
            {hr.confidently_wrong && <CwBadge />}
            <div className="text-xs text-muted">Spread says: {hr.spread_says}</div>
          </NeuCard>
        </div>
      )}
      <div className="absolute bottom-6 left-6 z-10">
        <NeuCard compact className="space-y-1.5 p-3">
          <div className="text-[11px] font-bold uppercase tracking-wide text-muted">Bust risk</div>
          {[...MAP_LEGEND].reverse().map((l) => {
            const Icon = RISK_ICON[l.risk];
            return (
              <div key={l.step} className="flex items-center gap-2 text-[11px] font-semibold">
                <span className="h-3 w-5 rounded-sm" style={{ background: MAP_SCALE[l.step], opacity: 0.7 }} aria-hidden />
                <Icon className={cn("h-3 w-3", RISK_TEXT_CLASS[l.risk])} aria-hidden />
                <span className={RISK_TEXT_CLASS[l.risk]}>{l.label}</span>
              </div>
            );
          })}
          <div className="flex items-center gap-2 text-[11px] font-semibold text-accent-text">
            <span className="h-0 w-5 border-t-2 border-dashed border-accent" aria-hidden />
            Confidently wrong
          </div>
        </NeuCard>
      </div>
    </div>
  );
}
