"use client";

export default function BigRing({ active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="relative h-36 w-36 focus:outline-none"
      aria-label="Toggle ring"
      title="Click"
    >
      <div
        className={
          "absolute inset-0 rounded-full blur-xl transition " +
          (active ? "bg-emerald-400/20" : "bg-zinc-500/10")
        }
      />
      <div className="absolute inset-2 rounded-full bg-gradient-to-b from-zinc-700 to-zinc-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_18px_40px_rgba(0,0,0,0.6)]" />
      <div className="absolute inset-3 rounded-full bg-gradient-to-b from-zinc-950 to-black" />
      <div
        className={
          "absolute inset-0 rounded-full transition " +
          (active
            ? "shadow-[0_0_28px_rgba(16,185,129,0.6)]"
            : "border-[10px] border-zinc-600/40 shadow-none")
        }
        style={
          active
            ? {
                backgroundImage:
                  "conic-gradient(from 0deg, rgba(52,211,153,0.9) 0deg, rgba(52,211,153,0.9) 80deg, rgba(52,211,153,0) 80deg, rgba(52,211,153,0) 360deg)",
                animation: "ring-spin 2s linear infinite",
                WebkitMask:
                  "radial-gradient(farthest-side, transparent calc(100% - 10px), black calc(100% - 10px))",
                mask:
                  "radial-gradient(farthest-side, transparent calc(100% - 10px), black calc(100% - 10px))",
              }
            : undefined
        }
      />
      <div
        className={
          "absolute bottom-5 left-1/2 h-4 w-4 -translate-x-1/2 rounded-full transition " +
          (active
            ? "bg-emerald-200/90 shadow-[0_0_16px_rgba(16,185,129,0.7)]"
            : "bg-zinc-200/30 shadow-none")
        }
      />
      <div className="absolute inset-0 rounded-full border border-zinc-200/10" />
    </button>
  );
}
