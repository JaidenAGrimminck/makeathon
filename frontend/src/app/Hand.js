'use client';

import React, { useMemo, useState } from 'react';
import Card from './components/hand/Card';
import HandViz from './components/hand/HandViz';
import Slider from './components/hand/Slider';
import StatusPill from './components/hand/StatusPill';
import Toggle from './components/hand/Toggle';
import { DEFAULT_PRESSURES, SENSOR_IDS } from './components/hand/constants';
import { clamp, formatBattery, formatMs } from './components/hand/utils';
import useHandStream from './components/hand/useHandStream';

export default function Hand() {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL;

  const [demoMode, setDemoMode] = useState(false);
  const [mirrorMode, setMirrorMode] = useState(false);
  const [gain, setGain] = useState(1.0);

  const { left, right, lastTs } = useHandStream({ wsUrl, demoMode, demoHz: 30 });

  const leftScaled = useMemo(() => {
    const sensors = { ...DEFAULT_PRESSURES };
    for (const k of SENSOR_IDS) sensors[k] = clamp((left?.sensors?.[k] ?? 0) * gain, 0, 1);
    return { ...left, sensors };
  }, [left, gain]);

  const rightScaled = useMemo(() => {
    const sensors = { ...DEFAULT_PRESSURES };
    for (const k of SENSOR_IDS) sensors[k] = clamp((right?.sensors?.[k] ?? 0) * gain, 0, 1);
    return { ...right, sensors };
  }, [right, gain]);

  const leftDisplay = mirrorMode ? rightScaled : leftScaled;
  const rightDisplay = mirrorMode ? leftScaled : rightScaled;

  const overallConnected = Boolean(leftDisplay.connected || rightDisplay.connected);
  const lastUpdateText = lastTs ? new Date(lastTs).toLocaleTimeString() : '—';

  return (
    <div className="relative min-h-screen bg-gradient-to-b from-black via-zinc-950 to-black text-zinc-100">
      <div className="pointer-events-none absolute inset-0 opacity-70">
        <div className="absolute inset-x-12 top-[-12%] h-64 rounded-full bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.28),transparent_55%)] blur-3xl" />
        <div className="absolute inset-x-24 top-28 h-72 rounded-full bg-[radial-gradient(circle_at_center,rgba(14,165,233,0.22),transparent_55%)] blur-3xl" />
      </div>

      <header className="sticky top-0 z-30 border-b border-emerald-500/20 bg-black/75 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-emerald-400/30 bg-emerald-500/10 text-xs font-semibold tracking-[0.18em] text-emerald-100 shadow-[0_10px_40px_rgba(16,185,129,0.35)]">
              HX
            </div>
            <div>
              <div className="text-sm font-semibold text-zinc-50">LooperX // Hand Monitor</div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-emerald-200/70">Live pressure telemetry</div>
            </div>
          </div>

          <div className="hidden items-center gap-2 md:flex">
            <StatusPill ok={overallConnected} label={overallConnected ? 'Streaming' : 'Idle'} sublabel={`Last: ${lastUpdateText}`} />
            <StatusPill ok label="UI" sublabel={demoMode ? 'Demo mode' : wsUrl ? 'WebSocket' : 'No WS URL'} />
          </div>
        </div>
      </header>

      <main className="relative mx-auto w-[100vw] px-5 py-8 flex flex-row gap-8 align-top px-5 py-8 align-center justify-center">
          <HandViz
            title="Left glove"
            handedness="Left"
            pressures={leftDisplay.sensors}
            connected={leftDisplay.connected}
          />
          <HandViz
            title="Right glove"
            handedness="Right"
            pressures={rightDisplay.sensors}
            connected={rightDisplay.connected}
          />
      </main>
    </div>
  );
}
