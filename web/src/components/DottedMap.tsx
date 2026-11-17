import { useEffect, useRef } from 'react';
import { inRegion, mapAspect, mapCols, type MapRegion } from '../data/mapMasks';
import { isLinked, onMap, type NetNode } from '../types/models';
import { colors, stateColor } from '../utils/format';

export function DottedMap({ region, nodes }: { region: MapRegion; nodes: NetNode[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const regionRef = useRef(region);
  regionRef.current = region;

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    let raf = 0;
    const start = performance.now();
    const period = 1800;

    const draw = (now: number) => {
      const t = ((now - start) % period) / period;
      paint(canvas, wrap, regionRef.current, nodesRef.current, t);
      raf = requestAnimationFrame(draw);
    };
    const ro = new ResizeObserver(() => paint(canvas, wrap, regionRef.current, nodesRef.current, 0));
    ro.observe(wrap);
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [region]);

  return (
    <div ref={wrapRef} className="dotted-map" style={{ aspectRatio: `1 / ${mapAspect(region)}` }}>
      <canvas ref={canvasRef} />
    </div>
  );
}

export function allInIndia(region: MapRegion, nodes: NetNode[]): boolean {
  const placed = nodes.filter(onMap);
  if (placed.length === 0) return false;
  return placed.every(
    (n) =>
      n.lat != null &&
      n.lon != null &&
      inRegion(region, n.lat, n.lon) &&
      (!isLinked(n) || inRegion(region, n.cluster!.lat!, n.cluster!.lon!)),
  );
}

function paint(
  canvas: HTMLCanvasElement,
  wrap: HTMLElement,
  region: MapRegion,
  nodes: NetNode[],
  t: number,
) {
  const cssW = wrap.clientWidth;
  const cssH = cssW * mapAspect(region);
  if (cssW <= 0 || cssH <= 0) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width = `${cssW}px`;
  canvas.style.height = `${cssH}px`;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, cssW, cssH);
  ctx.clip();

  const cols = mapCols(region);
  const rows = region.rows.length;
  const cw = cssW / cols;
  const ch = cssH / rows;
  const r = Math.min(cw, ch) * 0.3;
  ctx.fillStyle = 'rgba(255, 255, 255, 0.13)';
  for (let j = 0; j < rows; j++) {
    const row = region.rows[j]!;
    for (let i = 0; i < row.length; i++) {
      if (row.charCodeAt(i) === 49) {
        ctx.beginPath();
        ctx.arc((i + 0.5) * cw, (j + 0.5) * ch, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  const size = { width: cssW, height: cssH };
  const dotR = Math.max(2.6, cssW / 120);
  const hubs = new Map<string, { p: Pt; name: string }>();
  for (const n of nodes) {
    if (isLinked(n) && n.cluster) {
      hubs.set(n.cluster.id, {
        p: project(region, n.cluster.lat!, n.cluster.lon!, size),
        name: n.cluster.name,
      });
    }
  }

  nodes.forEach((n, k) => {
    if (n.lat == null || n.lon == null) return;
    const p = project(region, n.lat, n.lon, size);
    const color = stateColor(n.state);
    const hub = n.cluster && isLinked(n) ? hubs.get(n.cluster.id)?.p : undefined;
    if (hub && n.state !== 'offline' && dist(hub, p) > 1) {
      const mid = { x: (p.x + hub.x) / 2, y: (p.y + hub.y) / 2 };
      const d = { x: hub.x - p.x, y: hub.y - p.y };
      const ctrl = {
        x: mid.x + d.y * 0.25,
        y: mid.y - d.x * 0.25 - Math.hypot(d.x, d.y) * 0.12,
      };
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      ctx.quadraticCurveTo(ctrl.x, ctrl.y, hub.x, hub.y);
      ctx.strokeStyle = hexAlpha(color, n.state === 'training' ? 0.55 : 0.22);
      ctx.lineWidth = 1.2;
      ctx.stroke();
      if (n.state === 'training') {
        const ph = (t + k * 0.137) % 1;
        const up = ph < 0.5;
        const q = bezier(p, ctrl, hub, up ? ph * 2 : 2 - ph * 2);
        ctx.beginPath();
        ctx.arc(q.x, q.y, 2.2, 0, Math.PI * 2);
        ctx.fillStyle = up ? colors.green : colors.accent;
        ctx.fill();
      }
    }
    ctx.beginPath();
    ctx.arc(p.x, p.y, dotR * 2.2, 0, Math.PI * 2);
    ctx.fillStyle = hexAlpha(color, 0.15);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(p.x, p.y, dotR, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
  });

  const glow = 0.5 + 0.5 * Math.sin(t * 2 * Math.PI);
  ctx.font = '600 10px Inter, system-ui, sans-serif';
  ctx.textBaseline = 'alphabetic';
  for (const hub of hubs.values()) {
    ctx.beginPath();
    ctx.arc(hub.p.x, hub.p.y, dotR * (2.6 + glow), 0, Math.PI * 2);
    ctx.fillStyle = hexAlpha(colors.accent, 0.18);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(hub.p.x, hub.p.y, dotR * 1.4, 0, Math.PI * 2);
    ctx.fillStyle = colors.accent;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(hub.p.x, hub.p.y, dotR * 0.6, 0, Math.PI * 2);
    ctx.fillStyle = colors.bg;
    ctx.fill();

    const label = hub.name;
    const tw = ctx.measureText(label).width;
    const x = clamp(hub.p.x - tw / 2, 2, Math.max(2, cssW - tw - 2));
    const yAbove = hub.p.y - dotR * 3.2 - 2;
    const y = yAbove < 12 ? hub.p.y + dotR * 3.2 + 10 : yAbove;
    ctx.fillStyle = colors.accent;
    ctx.fillText(label, x, y);
  }
  ctx.restore();
}

type Pt = { x: number; y: number };

function project(region: MapRegion, lat: number, lon: number, size: { width: number; height: number }): Pt {
  let x = lon;
  if (x < region.lonMin) x += 360;
  return {
    x: ((x - region.lonMin) / (region.lonMax - region.lonMin)) * size.width,
    y: ((region.latMax - lat) / (region.latMax - region.latMin)) * size.height,
  };
}

function bezier(a: Pt, c: Pt, b: Pt, t: number): Pt {
  const u = 1 - t;
  return {
    x: a.x * (u * u) + c.x * (2 * u * t) + b.x * (t * t),
    y: a.y * (u * u) + c.y * (2 * u * t) + b.y * (t * t),
  };
}

function dist(a: Pt, b: Pt): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function hexAlpha(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
