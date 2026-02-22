import React from 'react';

export default function Toggle({ checked, onChange, label, description }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="group flex w-full items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white px-4 py-3 text-left shadow-sm transition hover:bg-zinc-50"
    >
      <div>
        <div className="text-sm font-semibold text-zinc-900">{label}</div>
        {description ? <div className="mt-1 text-xs text-zinc-500">{description}</div> : null}
      </div>
      <div
        className={`relative h-6 w-11 rounded-full ring-1 ring-inset transition ${
          checked ? 'bg-indigo-600 ring-indigo-200' : 'bg-zinc-200 ring-zinc-300'
        }`}
      >
        <div
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${
            checked ? 'left-5' : 'left-0.5'
          }`}
        />
      </div>
    </button>
  );
}
