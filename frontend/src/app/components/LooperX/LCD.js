"use client";

import { Meter } from "./Meter";

export default function LCD({ title, levels, transportOn }) {
  const cols = ["GUITAR", "BOOM", "LOOPER+", "VOX"];

  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between px-2">
        <div className="flex items-center gap-2 text-zinc-100/80">
          <span className="inline-flex h-2 w-2 rounded-sm bg-zinc-200/60" />
          <span className="text-[11px] tracking-widest">CPU</span>
          <span className="inline-flex h-2 w-2 rounded-sm bg-zinc-200/40" />
          <span className="text-[11px] tracking-widest">MEM</span>
        </div>

        <div className="text-[12px] font-semibold tracking-[0.35em] text-zinc-100/80">{title}</div>
      </div>

      <div className="rounded-xl bg-gradient-to-b from-zinc-800/80 to-zinc-950/95 p-[1px] shadow-[0_18px_40px_rgba(0,0,0,0.55)]">
        <div className="rounded-xl bg-gradient-to-b from-zinc-950/85 to-black/95 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),inset_0_-1px_0_rgba(0,0,0,0.7)]">
          <div className="grid grid-cols-4 gap-4">
            {cols.map((c, i) => (
              <div key={c} className="flex flex-col gap-2">
                <div className="text-[12px] font-semibold tracking-widest text-zinc-200/85">{c}</div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] uppercase tracking-wider text-zinc-200/45">fx</span>
                    <span
                      className={
                        "h-2.5 w-10 rounded-sm transition " +
                        (transportOn
                          ? "bg-emerald-400/80 shadow-[0_0_14px_rgba(16,185,129,0.45)]"
                          : "bg-zinc-800/70")
                      }
                    />
                  </div>
                </div>

                <Meter value={levels[i] ?? 0} />

                <div className="flex items-center justify-between text-[12px] text-zinc-200/60">
                  <span className="font-semibold">{(levels[i] ?? 0).toFixed(2)}</span>
                  <span className="font-semibold">0:00:0</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
