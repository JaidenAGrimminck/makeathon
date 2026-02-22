"use client";

import { clamp01 } from "../../utils/clamp";

export function Meter({ value = 0 }) {
  const v = clamp01(value);
  return (
    <div className="h-32 rounded-lg bg-gradient-to-b from-zinc-900 to-black shadow-[inset_0_2px_18px_rgba(0,0,0,0.85)]">
      <div className="h-full w-full rounded-lg p-2">
        <div className="relative h-full w-full overflow-hidden rounded-md bg-gradient-to-b from-zinc-950 to-black">
          <div
            className="absolute bottom-0 left-0 right-0 rounded-md bg-emerald-400/80 shadow-[0_0_18px_rgba(16,185,129,0.35)] transition"
            style={{ height: `${Math.round(v * 100)}%` }}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-emerald-400/15 to-transparent" />
        </div>
      </div>
    </div>
  );
}

export function MiniMeter({ value = 0 }) {
  const v = clamp01(value);
  return (
    <div className="h-20 rounded-xl bg-gradient-to-b from-zinc-900 to-black shadow-[inset_0_2px_12px_rgba(0,0,0,0.8)]">
      <div className="h-full w-full rounded-xl p-2">
        <div className="relative h-full w-full overflow-hidden rounded-md bg-gradient-to-b from-zinc-950 to-black">
          <div
            className="absolute bottom-0 left-0 right-0 rounded-md bg-emerald-400/75 shadow-[0_0_16px_rgba(16,185,129,0.3)]"
            style={{ height: `${Math.round(v * 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
}
