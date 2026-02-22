import { useEffect, useRef, useState } from 'react';
import { DEFAULT_PRESSURES, SENSOR_IDS } from './constants';
import { clamp } from './utils';

export default function useHandStream({ wsUrl, demoMode, demoHz = 30 }) {
  const [left, setLeft] = useState({ connected: false, battery: 0, rttMs: 0, sensors: { ...DEFAULT_PRESSURES } });
  const [right, setRight] = useState({ connected: false, battery: 0, rttMs: 0, sensors: { ...DEFAULT_PRESSURES } });
  const [lastTs, setLastTs] = useState(null);

  const wsRef = useRef(null);
  const demoTimerRef = useRef(null);

  useEffect(() => {
    if (demoMode) {
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {}
        wsRef.current = null;
      }

      const step = () => {
        const now = Date.now();
        const mk = (phase) => {
          const sensors = {};
          for (const id of SENSOR_IDS) {
            const base = id.includes('tip') ? 0.4 : id.includes('mid') ? 0.25 : id === 'palm_center' ? 0.18 : 0.12;
            const wobble =
              0.5 +
              0.5 *
                Math.sin(
                  (now / 1000) * (id.includes('tip') ? 2.1 : 1.4) +
                    phase +
                    (id.length * 0.77) /
                      (id.includes('thumb') ? 1.3 : id.includes('pinky') ? 1.6 : 1.0)
                );
            const jitter = (Math.random() - 0.5) * 0.06;
            sensors[id] = clamp(base + wobble * 0.55 + jitter, 0, 1);
          }
          return sensors;
        };

        setLeft({
          connected: true,
          battery: 82 + Math.sin(now / 9000) * 4,
          rttMs: 14 + Math.abs(Math.sin(now / 1200)) * 8,
          sensors: mk(0.0),
        });
        setRight({
          connected: true,
          battery: 79 + Math.sin(now / 8500) * 5,
          rttMs: 16 + Math.abs(Math.sin(now / 1300)) * 10,
          sensors: mk(1.6),
        });
        setLastTs(now);
      };

      step();
      demoTimerRef.current = setInterval(step, Math.max(16, Math.floor(1000 / demoHz)));
      return () => {
        if (demoTimerRef.current) clearInterval(demoTimerRef.current);
      };
    }

    if (!wsUrl) return;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {};

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg?.left?.sensors && msg?.right?.sensors) {
            setLeft(msg.left);
            setRight(msg.right);
            setLastTs(msg.ts ?? Date.now());
          }
        } catch {}
      };

      ws.onerror = () => {};

      ws.onclose = () => {
        setLeft((p) => ({ ...p, connected: false }));
        setRight((p) => ({ ...p, connected: false }));
      };

      return () => {
        try {
          ws.close();
        } catch {}
      };
    } catch {}
  }, [wsUrl, demoMode, demoHz]);

  return { left, right, lastTs };
}
