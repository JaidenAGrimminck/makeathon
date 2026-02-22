import React, { useMemo } from 'react';
import SensorGrid from './SensorGrid';
import { clamp, pressureToColor } from './utils';

export default function HandViz({ title, handedness, pressures, connected }) {
  const mirror = handedness === 'Right';

  const sensorPoints = useMemo(
    () => [
      { id: 'thumb_tip', x: 80, y: 50, r: 10 },
      // { id: 'thumb_mid', x: 58, y: 82, r: 10 },

      { id: 'index_tip', x: 104, y: 28, r: 10 },
      // { id: 'index_mid', x: 106, y: 60, r: 10 },

      { id: 'middle_tip', x: 130, y: 25, r: 10 },
      // { id: 'middle_mid', x: 142, y: 58, r: 10 },

      { id: 'ring_tip', x: 155, y: 30, r: 10 },
      // { id: 'ring_mid', x: 176, y: 66, r: 10 },

      { id: 'pinky_tip', x: 180, y: 50, r: 10 },
      // { id: 'pinky_mid', x: 200, y: 80, r: 10 },

      // { id: 'palm_center', x: 140, y: 112, r: 18 },
      // { id: 'wrist', x: 140, y: 166, r: 14 },
    ],
    []
  );

  return (
    <div className="relative overflow-hidden rounded-[28px] border border-emerald-400/20 bg-gradient-to-b from-zinc-900/70 via-zinc-950 to-black p-5 shadow-[0_30px_120px_rgba(0,0,0,0.55)]">
      <div className="pointer-events-none absolute inset-0 opacity-70">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(34,197,94,0.18),transparent_40%),radial-gradient(circle_at_80%_50%,rgba(14,165,233,0.18),transparent_45%),radial-gradient(circle_at_50%_90%,rgba(34,197,94,0.12),transparent_50%)]" />
      </div>

      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-zinc-50">{title}</div>
          <div className="mt-1 text-xs uppercase tracking-[0.18em] text-emerald-200/70">
            {connected ? 'Live stream' : 'No signal'} · {handedness} hand
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
              connected
                ? 'bg-emerald-500/20 text-emerald-100 ring-emerald-400/40'
                : 'bg-zinc-800/80 text-zinc-200 ring-zinc-700'
            }`}
          >
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div className="relative mt-4 grid gap-4 md:grid-cols-[1fr_220px]">
        <div className="relative overflow-hidden rounded-2xl border border-emerald-400/20 bg-gradient-to-b from-zinc-900/80 via-zinc-950 to-black">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,197,94,0.16),transparent_42%),radial-gradient(circle_at_80%_40%,rgba(14,165,233,0.12),transparent_50%)]" />

          <svg
            viewBox="0 0 280 190"
            className="relative block h-[260px] w-full"
            aria-label={`${handedness} hand visualization`}
          >
            <g transform={!mirror ? 'translate(280,0) scale(-1,1)' : undefined}>
              <path
                d={`M84 66
                   C78 60,72 52,76 44
                   C82 34,95 38,97 50
                   L98 72
                   L98 34
                   C98 20,114 18,114 34
                   L114 76
                   L120 28
                   C121 14,138 14,140 28
                   L140 78
                   L146 34
                   C148 20,165 20,166 34
                   L166 86
                   L170 52
                   C172 38,188 38,188 54
                   L188 96
                   C188 130,168 156,140 156
                   C114 156,92 136,92 108
                   L92 84
                   C92 76,90 72,84 66
                   Z`.replaceAll("\n", ' ')}
                fill="rgba(12,12,18,0.92)"
                stroke={connected ? 'rgba(52,211,153,0.45)' : 'rgba(63,63,70,0.65)'}
                strokeWidth="2"
              />

              <path
                d={`M110 98
                   C120 82,160 82,170 98
                   C182 116,168 140,140 142
                   C112 140,98 116,110 98
                   Z`.replaceAll("\n", ' ')}
                fill="rgba(16,185,129,0.06)"
              />

              {sensorPoints.map((pt) => {
                const p = connected ? pressures?.[pt.id] ?? 0 : 0;
                const glow = pressureToColor(p, { dim: !connected });
                const stroke = connected ? 'rgba(52,211,153,0.45)' : 'rgba(63,63,70,0.55)';
                return (
                  <g key={pt.id}>
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={pt.r + 10}
                      fill={glow}
                      opacity={connected ? 1 : 0.6}
                    />
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={pt.r}
                      fill={connected ? 'rgba(10,10,15,0.95)' : 'rgba(24,24,27,0.85)'}
                      stroke={stroke}
                      strokeWidth="2"
                    />
                    <circle
                      cx={pt.x}
                      cy={pt.y}
                      r={Math.max(3.5, 3.5 + 7.5 * clamp(p, 0, 1))}
                      fill={connected ? pressureToColor(p) : 'rgba(113,113,122,0.5)'}
                    />
                  </g>
                );
              })}
            </g>
          </svg>

          <div className="flex items-center justify-between gap-3 border-t border-emerald-400/15 bg-black/30 px-4 py-3">
            <div className="text-xs uppercase tracking-[0.18em] text-zinc-400">Pressure intensity</div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-zinc-400">Low</span>
              <div className="h-2 w-28 overflow-hidden rounded-full bg-zinc-800/70">
                <div
                  className="h-full"
                  style={{
                    background:
                      'linear-gradient(90deg, rgba(14,165,233,0.6), rgba(34,197,94,0.85), rgba(234,179,8,0.85))',
                  }}
                />
              </div>
              <span className="text-[11px] text-zinc-400">High</span>
            </div>
          </div>
        </div>

        <div className="relative rounded-2xl border border-emerald-400/20 bg-gradient-to-b from-zinc-900/80 via-zinc-950 to-black p-4">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-100">Channel summary</div>
          <div className="mt-3">
            <SensorGrid pressures={pressures} />
          </div>
        </div>
      </div>
    </div>
  );
}
