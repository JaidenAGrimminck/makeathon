import React from 'react';

export default function Slider({ value, onChange, label, min = 0.5, max = 2.0, step = 0.05 }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-900">{label}</div>
          <div className="mt-1 text-xs text-zinc-500">Scale pressure readings for display</div>
        </div>
        <div className="text-sm font-semibold tabular-nums text-zinc-800">{value.toFixed(2)}×</div>
      </div>
      <input
        className="mt-3 w-full accent-indigo-600"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}
