"use client";

import { useMemo } from "react";

export default function Knob({ label, top, value, setValue, highlight = false, highlightIcon = "" }) {
  const deg = useMemo(() => -135 + value * 270, [value]);

  return (
    <div className="flex flex-col items-center gap-2">
      {top ? (
        <div className="text-[11px] tracking-[0.35em] text-zinc-300/70">{top}</div>
      ) : null}

      <div className={"relative " + (highlight ? "animate-pulse" : "")}
        >
        <div className={
          "h-12 w-12 rounded-full bg-gradient-to-b from-zinc-700 to-zinc-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_rgba(0,0,0,0.55)] " +
          (highlight ? "ring-2 ring-amber-400/80 shadow-[0_0_28px_rgba(251,191,36,0.35)]" : "")
        }
        />
        <div className="absolute inset-1 rounded-full bg-gradient-to-b from-zinc-800 to-zinc-950" />
        {highlight && highlightIcon ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-amber-200/90 drop-shadow">
            <span className="text-lg">{highlightIcon}</span>
          </div>
        ) : null}
        <div
          className="absolute left-1/2 top-2 h-4 w-0.5 -translate-x-1/2 rounded-full bg-zinc-200/60"
          style={{ transform: `translateX(-50%) rotate(${deg}deg) translateY(-2px)` }}
        />

        <input
          aria-label={label || top || "knob"}
          type="range"
          min={0}
          max={100}
          value={Math.round(value * 100)}
          onChange={(e) => setValue(Number(e.target.value) / 100)}
          className="absolute inset-0 cursor-pointer opacity-0"
        />
      </div>

      <div className="text-[11px] font-medium tracking-widest text-zinc-300/70">{label}</div>
      <div className="text-[10px] tracking-widest text-zinc-200/40">{Math.round(value * 100)}</div>
    </div>
  );
}
