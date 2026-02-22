

import React, { useEffect, useMemo, useState } from "react";
import BigRing from "./components/LooperX/BigRing";
import FootSwitch from "./components/LooperX/FootSwitch";
import InsetScrew from "./components/LooperX/InsetScrew";
import Knob from "./components/LooperX/Knob";
import LCD from "./components/LooperX/LCD";
import LedBar from "./components/LooperX/LedBar";
import NotifyBar from "./components/LooperX/NotifyBar";
import TrackPad from "./components/LooperX/TrackPad";
import { clamp01 } from "./utils/clamp";

const size = 100;

/*
def get_state(self):
        # returns a byte array representing the current state of the looper, including active loop, recording status, and modulation
        state = bytearray()
        state.append(self.active if self.active != -1 else 255) # active loop index (which instrument is being played from/recorded to if recording)
        state.append(1 if self.recording else 0) # recording status
        modulation_byte = int((self.settings.modulation + 1) / 2 * 255) # convert modulation from [-1, 1] to [0, 255]
        state.append(modulation_byte)
        state.append(self.settings.beats_per_loop) # beats per loop

        state.append(len(self.actions)) # number of actions
        for i in range(len(self.actions)):
            state.append(1 if i in self.loops else 0) # whether loop has actions
            if i in self.loops:
                state.append(len(self.loops[i])) # number of actions in loop
                for action_time, finger_index in self.loops[i]:
                    state.append(finger_index)
                    # convert action_time to float32 representation in milliseconds
                    time_ms = int(action_time * 1000)
                    time_bytes = struct.pack('<I', time_ms) # little-endian unsigned int
                    state.extend(time_bytes)

        return state
*/
function parseState(state = new Uint8Array()) {
    if (!state || state.length < 5) return null;

    let offset = 0;
    const readByte = () => {
        if (offset >= state.length) return null;
        return state[offset++];
    };

    const readUint32 = () => {
        if (offset + 4 > state.length) return null;
        const value =
            (state[offset] | (state[offset + 1] << 8) | (state[offset + 2] << 16) | (state[offset + 3] << 24)) >>> 0;
        offset += 4;
        return value;
    };

    const activeRaw = readByte();
    const recordingByte = readByte();
    const modulationByte = readByte();
    const beatsPerLoop = readByte();
    const loopCount = readByte();

    if ([activeRaw, recordingByte, modulationByte, beatsPerLoop, loopCount].some((v) => v === null)) return null;

    const active = activeRaw === 255 ? -1 : activeRaw;
    const recording = recordingByte === 1;
    const modulation = (modulationByte / 255) * 2 - 1;

    const loops = [];
    for (let i = 0; i < loopCount; i += 1) {
        const hasLoopFlag = readByte();
        if (hasLoopFlag === null) break;
        const hasLoop = hasLoopFlag === 1;

        const actions = [];
        if (hasLoop) {
            const actionCount = readByte();
            if (actionCount === null) break;

            for (let j = 0; j < actionCount; j += 1) {
                const fingerIndex = readByte();
                const timeMs = readUint32();
                if (fingerIndex === null || timeMs === null) break;
                actions.push({ fingerIndex, timeMs, timeSeconds: timeMs / 1000 });
            }
        }

        loops.push({ hasLoop, actions });
    }

    // final byte is the volume
    const volumeByte = readByte();
    let volume = null;
    if (volumeByte !== null) {
        volume = volumeByte / 255;
    }

    const notify_ai = readByte() === 1;
    const notify_reset = readByte() === 1;
    const waitingForAI = readByte() === 1;

    return { active, recording, modulation, beatsPerLoop, loops, volume, notify_ai, notify_reset, waitingForAI };
}

export default function LooperX() {
    // Transport
    const [transportOn, setTransportOn] = useState(false);
    const [ringOn, setRingOn] = useState(true);
    const [modeOn, setModeOn] = useState(false);
    const [functionOn, setFunctionOn] = useState(false);
    const [beat, setBeat] = useState(0);
    const [maxBeats, setMaxBeats] = useState(8);

    // Track states
    const [t1, setT1] = useState("idle");
    const [t2, setT2] = useState("idle");
    const [t3, setT3] = useState("idle");
    const [t4, setT4] = useState("idle");
    const [activeTrack, setActiveTrack] = useState(-1);
    const [prevTrack, setPrevTrack] = useState(-1);
    const [notifyAI, setNotifyAI] = useState(false);
    const [notifyReset, setNotifyReset] = useState(false);
    const [waitingForAI, setWaitingForAI] = useState(false);

    // Knobs
    const [k1, setK1] = useState(0.68);
    const [k2, setK2] = useState(0.52);
    const [k3, setK3] = useState(0.72);
    const [k4, setK4] = useState(0.44);
    const [main, setMain] = useState(0.64);
    const [modulation, setModulation] = useState(0.5);
    const [aux, setAux] = useState(0.48);

    const songNames = useMemo(
    () => [
        "Looper View"
    ],
    []
    );
    const [song, setSong] = useState(songNames[0]);

    // Levels
    const [trackLevels, setTrackLevels] = useState([0, 0, 0, 0]);
    const [lcdLevels, setLcdLevels] = useState([0, 0, 0, 0]);

    const [ws, setWs] = useState(null);

    const trackStates = useMemo(() => [t1, t2, t3, t4], [t1, t2, t3, t4]);

    useEffect(() => {
        const host = window.location.hostname;
        let cancelled = false;
        let retryTimeout;
        let socket;

        const cleanupSocket = () => {
            if (!socket) return;
            if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
                socket.close(1000, "component cleanup");
            }
        };

        const scheduleReconnect = () => {
            if (cancelled) return;
            clearTimeout(retryTimeout);
            retryTimeout = setTimeout(() => {
                if (cancelled) return;
                cleanupSocket();
                socket = setupSocket();
            }, 1500);
        };

        function setupSocket() {
            const next = new WebSocket(`ws://${host}:8765`);

            next.addEventListener("open", () => {
                if (cancelled) {
                    next.close(1000, "unmounted");
                    return;
                }
                setWs(next);
                clearTimeout(retryTimeout);

                console.log("WebSocket connected");
            });

            next.addEventListener("message", async (e) => {
                const data = e.data || new Blob();
                

                const bytes = data.arrayBuffer ? new Uint8Array(await data.arrayBuffer()) : new Uint8Array(data);

                //data is a binary message with first byte as message type, rest as payload
                const type = bytes[0];
                
                if (type == 0x62) {
                    const beat = bytes[1];
                    setBeat(beat);
                } else if (type == 0x73) {
                    const state = parseState(bytes.slice(1));
                    if (!state) return;

                    const { active, recording, loops, notify_ai, notify_reset, waitingForAI: waitingFlag } = state;
                    const hasContent = loops.some((loop) => loop.hasLoop);

                    setTransportOn(recording || hasContent);

                    const validActive = active >= 0 && active < loops.length ? active : -1;
                    setActiveTrack(validActive);

                    const loopLen = loops.length || 0;
                    const prev = validActive >= 0 && loopLen > 0 ? (validActive + loopLen - 1) % loopLen : -1;
                    setPrevTrack(prev);

                    setNotifyAI(!!notify_ai);
                    setNotifyReset(!!notify_reset);
                    setWaitingForAI(!!waitingFlag);

                    const resolveTrackState = (index) => {
                        const loop = loops[index];
                        if (!loop || !loop.hasLoop) return "idle";
                        if (recording && active === index) return "rec";
                        return "play";
                    };

                    setT1(resolveTrackState(0));
                    setT2(resolveTrackState(1));
                    setT3(resolveTrackState(2));
                    setT4(resolveTrackState(3));

                    setModulation(state.modulation * 0.5 + 0.5);

                    if (state.volume !== null && state.volume !== undefined) {
                        setMain(clamp01(state.volume));
                    }
                }
            });

            next.addEventListener("close", (e) => {
                if (!cancelled) console.log("WebSocket disconnected");
                setWs(null);
                scheduleReconnect();
            });

            next.addEventListener("error", (e) => {
                //setMsg(e);
                console.warn("WebSocket error", e);
                // Force close to trigger reconnect
                try {
                    next.close();
                } catch (_) {
                    // ignore
                }
                // /throw new Error(e.message || "WebSocket error " + host);
                // IMPORTANT: don't call socket.close() here; it can be mid-handshake.
            });

            return next;
        }

        socket = setupSocket();

        return () => {
            cancelled = true;
            clearTimeout(retryTimeout);

            cleanupSocket();
        };
    }, []);

    // Animate meters
    useEffect(() => {
        const tickMs = 120;
        const id = setInterval(() => {
            const gains = [k1, k2, k3, k4];
            const weights = trackStates.map((s, i) => {
            if (!transportOn) return 0;
            if (s === "mute" || s === "idle") return 0.05;
            if (s === "rec") return 0.95;
            return 0.75; // play
            });

            // Per-track pad meters
            setTrackLevels((prev) =>
            prev.map((p, i) => {
                const target = clamp01(
                (weights[i] * (0.35 + Math.random() * 0.65) * (0.35 + gains[i] * 0.85))
                );
                // Smooth + decay
                const next = transportOn ? p * 0.6 + target * 0.4 : p * 0.82;
                return clamp01(next);
            })
            );

            // LCD channels: combine track activity + output knobs
            setLcdLevels((prev) =>
            prev.map((p, i) => {
                const base =
                (weights[0] + weights[1] + weights[2] + weights[3]) / 4;
                const out = i === 0 ? main : i === 1 ? aux : i === 2 ? modulation : main;
                const wobble = 0.25 + Math.random() * 0.75;
                const target = clamp01(base * wobble * (0.35 + out * 0.85));
                const next = transportOn ? p * 0.55 + target * 0.45 : p * 0.86;
                return clamp01(next);
            })
            );
        }, tickMs);

        return () => clearInterval(id);
    }, [transportOn, trackStates, k1, k2, k3, k4, main, aux, modulation]);

    // Function toggle: quick randomize (just for fun)
    useEffect(() => {
        if (!functionOn) return;
        const id = setInterval(() => {
            setK1((v) => clamp01(v + (Math.random() - 0.5) * 0.04));
            setK2((v) => clamp01(v + (Math.random() - 0.5) * 0.04));
            setK3((v) => clamp01(v + (Math.random() - 0.5) * 0.04));
            setK4((v) => clamp01(v + (Math.random() - 0.5) * 0.04));
        }, 250);
        return () => clearInterval(id);
    }, [functionOn]);

    const stopAll = () => {
        setTransportOn(false);
        setT1("idle");
        setT2("idle");
        setT3("idle");
        setT4("idle");
        setActiveTrack(-1);
        setPrevTrack(-1);
        setNotifyAI(false);
        setNotifyReset(false);
        setWaitingForAI(false);
        setTrackLevels([0, 0, 0, 0]);
        setLcdLevels([0, 0, 0, 0]);
    };

    return (
        <div className="min-h-screen bg-gradient-to-b from-black via-zinc-950 to-black p-6 text-zinc-100">
            <NotifyBar show={notifyAI || notifyReset} kind={notifyReset ? "reset" : "ai"} />
            <div className="mx-auto flex w-[95%] items-center justify-center">
            <div className="relative w-full rounded-[56px] bg-gradient-to-b from-zinc-800/50 to-zinc-950/80 p-[3px] shadow-[0_40px_120px_rgba(0,0,0,0.75)]">
                <div className="relative overflow-hidden rounded-[54px] bg-gradient-to-b from-zinc-900 to-zinc-950 px-10 py-9 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),inset_0_-1px_0_rgba(0,0,0,0.75)]">
                {/* Subtle grain */}
                <div
                    className="pointer-events-none absolute inset-0 opacity-[0.08] mix-blend-overlay"
                    style={{
                    backgroundImage:
                        "radial-gradient(circle at 20% 10%, rgba(255,255,255,0.35), transparent 35%), radial-gradient(circle at 80% 40%, rgba(255,255,255,0.25), transparent 40%), radial-gradient(circle at 50% 90%, rgba(255,255,255,0.2), transparent 40%)",
                    }}
                />

                {/* Screws */}
                <InsetScrew className="absolute left-6 top-6" />
                <InsetScrew className="absolute right-6 top-6" />
                <InsetScrew className="absolute left-6 bottom-6" />
                <InsetScrew className="absolute right-6 bottom-6" />

                {/* Top row */}
                <div className="flex items-start justify-between">
                    {/* Left brand + ring */}
                    <div className="flex gap-10 w-[33%] h-[300px] flex-col justify-center items-center">
                        <div className="pt-2">
                            <BigRing active={ringOn} onClick={() => setRingOn((v) => !v)} />

                            <div className="mt-3 text-xs text-zinc-300/55">
                            Running: <span className="font-semibold">{ringOn ? "ON" : "OFF"}</span>
                            </div>
                        </div>
                    </div>

                    {/* LCD */}
                    <div className="flex flex-col align-center gap-2 pt-2 w-[33%]">
                    <LCD
                        title={song}
                        levels={lcdLevels}
                        transportOn={transportOn}
                    />
                    <div className="flex flex-row align-center items-center justify-center pt-[5px]">
                        {/* 4 smaller green squares that light up per beat */}
                        {new Array(maxBeats).fill(0).map((_, i) => i).map((n) => (
                            <div key={n} className={`inline-block m-2 rounded-lg ${beat === n ? 'bg-emerald-400' : 'bg-zinc-700'}`} style={{ width: `${size/4 - 10}px`, height: `${size/4 - 10}px` }} />
                        ))}
                    </div>
                    </div>

                    {/* Right knobs / logo */}
                    <div className="pt-2 w-[33%] px-10">
                        <div className="mt-3 text-center text-[12px] font-semibold tracking-[0.25em] text-zinc-200/55">
                            INPUT GAIN
                        </div>

                        <div className="mt-6 grid grid-cols-3 gap-6">
                            <Knob label="MAIN" value={main} setValue={setMain} />
                            <Knob label="MODULATION" value={modulation} setValue={setModulation} />
                            <Knob label="AI" value={0} setValue={setAux} highlight={waitingForAI} highlightIcon="⏳" />
                        </div>
                    </div>
                </div>

                <div className="flex flex-col align-center items-center">

                {/* Middle row: track pads */}
                <div className="max-w-6xl mt-10 grid grid-cols-4 items-start gap-10">
                    <TrackPad n={1} state={t1} setState={setT1} level={trackLevels[0]} isActive={activeTrack === 0} isPrevActive={notifyAI && prevTrack === 0} />
                    <TrackPad n={2} state={t2} setState={setT2} level={trackLevels[1]} isActive={activeTrack === 1} isPrevActive={notifyAI && prevTrack === 1} />
                    <TrackPad n={3} state={t3} setState={setT3} level={trackLevels[2]} isActive={activeTrack === 2} isPrevActive={notifyAI && prevTrack === 2} />
                    <TrackPad n={4} state={t4} setState={setT4} level={trackLevels[3]} isActive={activeTrack === 3} isPrevActive={notifyAI && prevTrack === 3} />
                </div>

                {/* Bottom row: footswitches */}
                <div className="mt-10 grid grid-cols-4 items-start gap-10">
                    <FootSwitch
                    variant="transport"
                    label=""
                    active={transportOn}
                    onClick={() => setTransportOn((v) => !v)}
                    />
                    <FootSwitch
                    variant="stop"
                    label=""
                    active={!transportOn && (t1 !== "idle" || t2 !== "idle" || t3 !== "idle" || t4 !== "idle")}
                    onClick={stopAll}
                    />
                    <FootSwitch
                    variant="mode"
                    label="MODE"
                    active={modeOn}
                    onClick={() => setModeOn((v) => !v)}
                    />
                    <FootSwitch
                    variant="function"
                    label="FUNCTION"
                    active={functionOn}
                    onClick={() => setFunctionOn((v) => !v)}
                    />
                </div>

                </div>

                {/* Mode overlay */}
                {modeOn ? (
                    <div className="pointer-events-none absolute inset-6 rounded-[42px] border border-emerald-400/20 bg-emerald-500/5 shadow-[0_0_60px_rgba(16,185,129,0.12)]">
                    <div className="absolute right-8 top-8 rounded-xl bg-zinc-950/60 px-3 py-2 text-xs tracking-widest text-emerald-100/70">
                        ALT MODE
                    </div>
                    </div>
                ) : null}
                </div>
            </div>
            </div>
        </div>
    );
}
