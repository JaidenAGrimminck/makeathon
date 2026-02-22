import React from 'react';
import { clamp, formatPct, pressureToColor } from './utils';

function SegBar({ label, value }) {
  const v = clamp(value ?? 0, 0, 1);
  return (
    <div className="grid grid-cols-[88px_1fr_48px] items-center gap-2">
      <div className="truncate text-xs text-zinc-200/90">{label}</div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-800/80">
        <div
          className="h-full rounded-full shadow-[0_0_16px_rgba(34,197,94,0.28)]"
          style={{ width: `${v * 100}%`, background: pressureToColor(v) }}
        />
      </div>
      <div className="text-right text-xs font-semibold tabular-nums text-emerald-100">{formatPct(v)}</div>
    </div>
  );
}

export default function SensorGrid({ pressures }) {
  return (
    <div className="grid gap-2">
      <SegBar label="Thumb" value={Math.max(pressures.thumb_tip, pressures.thumb_mid)} />
      <SegBar label="Index" value={Math.max(pressures.index_tip, pressures.index_mid)} />
      <SegBar label="Middle" value={Math.max(pressures.middle_tip, pressures.middle_mid)} />
      <SegBar label="Ring" value={Math.max(pressures.ring_tip, pressures.ring_mid)} />
      <SegBar label="Pinky" value={Math.max(pressures.pinky_tip, pressures.pinky_mid)} />
    </div>
  );
}
