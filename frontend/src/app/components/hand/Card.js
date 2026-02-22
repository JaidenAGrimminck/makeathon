import React from 'react';

export default function Card({ title, subtitle, right, children }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-zinc-100 px-5 py-4">
        <div>
          <div className="text-sm font-semibold text-zinc-900">{title}</div>
          {subtitle ? <div className="mt-1 text-xs text-zinc-500">{subtitle}</div> : null}
        </div>
        {right ? <div className="shrink-0">{right}</div> : null}
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}
