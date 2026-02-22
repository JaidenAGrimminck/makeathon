import React from 'react';

export default function StatusPill({ ok, label, sublabel }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-500/10 px-3 py-1 shadow-[0_10px_40px_rgba(16,185,129,0.25)]">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
      <div className="leading-tight">
        <div className="text-xs font-semibold uppercase tracking-wide text-emerald-50">{label}</div>
        {sublabel ? <div className="text-[11px] text-zinc-300">{sublabel}</div> : null}
      </div>
    </div>
  );
}
