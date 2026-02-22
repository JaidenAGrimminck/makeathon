"use client";

import LedBar from "./LedBar";

export default function FootSwitch({ variant, label, active, onClick }) {
  const led =
    variant === "transport"
      ? { color: "green", on: active }
      : variant === "stop"
        ? { color: "white", on: active }
        : { color: "white", on: active };

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="h-2.5 w-28">
        <LedBar color={led.color} active={led.on} />
      </div>

      <div className="w-56 rounded-2xl bg-gradient-to-b from-zinc-800/70 to-zinc-950/90 p-[1px] shadow-[0_20px_48px_rgba(0,0,0,0.65)]">
        <button
          type="button"
          onClick={onClick}
          className={
            "group w-full rounded-2xl bg-gradient-to-b from-zinc-900/85 to-black/95 p-4 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.08),inset_0_-1px_0_rgba(0,0,0,0.75)] transition active:translate-y-[1px] " +
            (active
              ? "ring-1 ring-emerald-400/25 shadow-[0_0_32px_rgba(16,185,129,0.12)]"
              : "")
          }
        >
          <div className="mb-2 flex items-center justify-between">
            {variant === "transport" ? (
              <div className="flex items-center gap-2 text-zinc-200/85">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-800/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <span className="h-2 w-2 rounded-full bg-zinc-100/80" />
                </span>
                <span className="text-[13px] font-semibold tracking-wider">+</span>
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-800/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-zinc-100/80">
                    <path d="M8 5v14l12-7z" />
                  </svg>
                </span>
                <span className="ml-2 text-[12px] font-semibold tracking-widest text-zinc-100/70">
                  {active ? "PAUSE" : "PLAY"}
                </span>
              </div>
            ) : variant === "stop" ? (
              <div className="flex items-center gap-2 text-zinc-200/85">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-lg bg-zinc-800/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-zinc-100/80">
                    <path d="M7 7h10v10H7z" />
                  </svg>
                </span>
                <span className="ml-2 text-[12px] font-semibold tracking-widest text-zinc-100/70">STOP</span>
              </div>
            ) : (
              <div className="text-[12px] font-semibold tracking-widest text-zinc-100/70">{label}</div>
            )}

            <div
              className={
                "rounded-md px-2 py-0.5 text-[10px] font-semibold tracking-widest " +
                (active
                  ? "bg-emerald-500/20 text-emerald-200/85"
                  : "bg-zinc-800/60 text-zinc-200/45")
              }
            >
              {active ? "ON" : "OFF"}
            </div>
          </div>

          <div className="h-16 rounded-xl bg-gradient-to-b from-zinc-900 to-black shadow-[inset_0_2px_14px_rgba(0,0,0,0.85)]" />
          <div className="mt-3 h-1 rounded-full bg-zinc-700/35" />
        </button>
      </div>
    </div>
  );
}
