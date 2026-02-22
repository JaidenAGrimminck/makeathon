"use client";

import { useEffect, useState } from "react";

export default function NotifyBar({ show, kind = "ai" }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let rafId;

    if (show) {
      setProgress(0);
      rafId = requestAnimationFrame(() => setProgress(100));
    } else {
      setProgress(0);
    }

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [show, kind]);

  if (!show) return null;

  const isReset = kind === "reset";
  const barColor = isReset ? "bg-amber-400" : "bg-emerald-400";
  const label = isReset ? "Resetting" : "AI Update";

  return (
    <div className="pointer-events-none fixed left-1/2 top-6 z-50 w-[460px] -translate-x-1/2 rounded-[18px] border border-emerald-300/35 bg-black/75 px-6 py-3 shadow-[0_26px_90px_rgba(0,0,0,0.65)]">
      <div className="mb-2 text-center text-[12px] font-semibold tracking-[0.38em] text-emerald-50/85 uppercase">
        {label}
      </div>
      <div className="h-3 w-full rounded-full bg-zinc-800/85 shadow-inner">
        <div
          className={`${barColor} h-3 rounded-full transition-[width] duration-1000 ease-linear shadow-[0_0_18px_rgba(16,185,129,0.55)]`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
