"use client";

import { MiniMeter } from "./Meter";

export default function TrackPad({ n, state, setState, level, isActive = false, isPrevActive = false }) {
  const letter = n === 1 ? "A" : n === 2 ? "B" : n === 3 ? "C" : "D";

  const next = () => {
    const order = ["idle", "rec", "play", "mute"];
    const idx = order.indexOf(state);
    setState(order[(idx + 1) % order.length]);
  };

  const badge =
    state === "rec"
      ? "REC"
      : state === "play"
        ? "PLAY"
        : state === "mute"
          ? "MUTE"
          : "IDLE";

  const badgeStyles =
    state === "rec"
      ? "bg-red-500/20 text-red-200/90 border-red-400/30"
      : state === "play"
        ? "bg-emerald-500/20 text-emerald-200/90 border-emerald-400/30"
        : state === "mute"
          ? "bg-zinc-500/20 text-zinc-200/80 border-zinc-300/20"
          : "bg-zinc-800/50 text-zinc-200/60 border-zinc-200/10";

  const glow =
    state === "rec"
      ? "shadow-[0_0_25px_rgba(239,68,68,0.22)]"
      : state === "play"
        ? "shadow-[0_0_25px_rgba(16,185,129,0.22)]"
        : "shadow-none";

  const activeOutline = state === "rec"
    ? "ring-2 ring-red-400/70 ring-offset-2 ring-offset-zinc-950 shadow-[0_0_32px_rgba(239,68,68,0.35)]"
    : isActive
      ? "ring-2 ring-emerald-400/65 ring-offset-2 ring-offset-zinc-950 shadow-[0_0_32px_rgba(16,185,129,0.28)]"
      : isPrevActive
        ? "ring-2 ring-amber-400/70 ring-offset-2 ring-offset-zinc-950 shadow-[0_0_28px_rgba(251,191,36,0.32)]"
        : "";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="h-1.5 w-28 rounded-full bg-zinc-700/30" />

      <div
        className={
          "w-44 rounded-2xl bg-gradient-to-b from-zinc-800/70 to-zinc-950/90 p-[1px] shadow-[0_18px_40px_rgba(0,0,0,0.55)] " +
          activeOutline
        }
      >
        <button
          type="button"
          onClick={next}
          className={
            "w-full rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950/95 p-3 text-left transition active:translate-y-[1px] " +
            glow
          }
        >
          <div className="mb-2 flex items-center justify-between">
            <div className="text-[13px] font-semibold tracking-wider text-zinc-200/85">
              TRACK {n}
            </div>
            <div className="flex items-center gap-2">
              <div className="rounded-md bg-zinc-800/60 px-2 py-0.5 text-[11px] font-semibold tracking-widest text-zinc-200/70">
                {letter}
              </div>
              <div
                className={
                  "rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-widest " +
                  badgeStyles
                }
              >
                {badge}
              </div>
            </div>
          </div>

          <MiniMeter value={level} />

          <div className="mt-3 h-1 rounded-full bg-zinc-700/35" />
          <div className="mt-2 text-[11px] tracking-widest text-zinc-200/45">Click to cycle</div>
        </button>
      </div>
    </div>
  );
}
