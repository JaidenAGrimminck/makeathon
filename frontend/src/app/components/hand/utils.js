export function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

export function pressureToColor(p, { dim = false } = {}) {
  const x = clamp(p, 0, 1);
  const hue = 210 + (10 - 210) * x;
  const sat = dim ? 45 : 70;
  const light = dim ? 52 : 48;
  const alpha = 0.18 + 0.72 * x;
  return `hsla(${hue.toFixed(0)}, ${sat}%, ${light}%, ${alpha.toFixed(3)})`;
}

export function formatPct(n) {
  if (Number.isNaN(n)) return '—';
  return `${Math.round(clamp(n, 0, 1) * 100)}%`;
}

export function formatBattery(n) {
  if (n == null || Number.isNaN(n)) return '—';
  return `${Math.round(clamp(n, 0, 100))}%`;
}

export function formatMs(n) {
  if (n == null || Number.isNaN(n)) return '—';
  return `${Math.round(Math.max(0, n))} ms`;
}
