import { useEffect, useRef, useState } from "react";

function objToString(obj) {
    return Object.entries(obj).map(([k, v]) => `${k}: ${v}`).join(", ");
}

export default function Phone() {
    const [size, setSize] = useState(150);
    const [ws, setWs] = useState(null);
    const [beat, setBeat] = useState(0);
    const [maxBeats, setMaxBeats] = useState(8);
    const [msg, setMsg] = useState("");
    const [mod, setMod] = useState(Math.floor(255 / 2));

    const buttonsDownRef = useRef(new Set());

    useEffect(() => {
        const host = window.location.hostname;
        const socket = new WebSocket(`ws://${host}:8765`);
        let cancelled = false;

        socket.addEventListener("open", () => {
            if (cancelled) {
                // Now it's open, closing sends a proper close frame.
                socket.close(1000, "unmounted");
                return;
            }
            setWs(socket);

            //socket.send(new Uint8Array([0x67, 0x00])); // just a test message to confirm it works

            console.log("WebSocket connected");
            setMsg("WebSocket connected");

            // setInterval(() => {
            //     socket.send(new Uint8Array([0x00]));
            // }, 20); // send a dummy message every 20ms to keep the connection alive and test latency
        });

        socket.addEventListener("message", async (e) => {
            const data = e.data || new Blob();
            

            const bytes = data.arrayBuffer ? new Uint8Array(await data.arrayBuffer()) : new Uint8Array(data);

            //data is a binary message with first byte as message type, rest as payload
            const type = bytes[0];
            
            if (type == 0x62) {
                const beat = bytes[1];
                setBeat(beat);
                setMsg(`Beat: ${beat}`);
            }
        });

        socket.addEventListener("close", (e) => {
            if (!cancelled) console.log("WebSocket disconnected");
            setMsg("WebSocket disconnected " + e.code + " " + e.reason);
            setWs(null);
        });

        socket.addEventListener("error", (e) => {
            setMsg(e);
            // /throw new Error(e.message || "WebSocket error " + host);
            // IMPORTANT: don't call socket.close() here; it can be mid-handshake.
        });

        return () => {
            cancelled = true;

            // Key change: don't close during CONNECTING (avoids handshake abort on server)
            if (socket.readyState === WebSocket.OPEN) {
                socket.close(1000, "component cleanup");
            }
        };
    }, []);


    const onClick = (n) => {
        // send buffer [0x67, n]
        if (ws && ws.readyState === WebSocket.OPEN) {
            const buffer = new Uint8Array([0x67, n]);
            ws.send(buffer);
            console.log("Sent", buffer);
        } else {
            console.warn("WebSocket not connected, can't send", n);
        }
    }

    const broadcastModulation = (n) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            const clamped = Math.max(0, Math.min(255, n));
            const buffer = new Uint8Array([0x6c, clamped]);
            ws.send(buffer);
            console.log("Sent modulation", buffer);
        } else {
            console.warn("WebSocket not connected, can't send modulation", n);
        }

        setMod(n);
    }

    const setupClick = (n) => {
        return (e) => {
            onClick(n);
        }
    }

    const onMouseDown = (n, e) => {
        buttonsDownRef.current.add(n);
        const intv = setInterval(() => {
            if (!buttonsDownRef.current.has(n)) {
                clearInterval(intv);
                return;
            }

            if (ws && ws.readyState === WebSocket.OPEN) {
                const buffer = new Uint8Array([0x10, n]);
                ws.send(buffer);
                // console.log("Sent", buffer);
            }
        }, 50)
    }

    const setupMouseDown = (n) => {
        return (e) => {
            onMouseDown(n, e);
        }
    }

    const onMouseUp = (n, e) => {
        buttonsDownRef.current.delete(n);
        if (ws && ws.readyState === WebSocket.OPEN) {
            const buffer = new Uint8Array([0x12]);
            ws.send(buffer);
            // console.log("Sent", buffer);
        }
    }

    const setupMouseUp = (n) => {
        return (e) => {
            onMouseUp(n, e);
        }
    }

    return (
        <>
        <h1>{msg}</h1>
        <div>
            {/* 4 smaller green squares that light up per beat */}
            {new Array(maxBeats).fill(0).map((_, i) => i).map((n) => (
                <div key={n} className={`inline-block m-2 rounded-lg ${beat === n ? 'bg-emerald-400' : 'bg-zinc-700'}`} style={{ width: `${size/4 - 10}px`, height: `${size/4 - 10}px` }} />
            ))}
        </div>
        <div className="flex w-full h-[40vh] px-5 py-8 justify-around items-center">
            {/* five buttons blank */}
            {
                [0, 1, 2, 3].map((n) => (
                    <div key={n} onMouseDown={setupMouseDown(n)} onMouseUp={setupMouseUp(n)} className={`bg-emerald-500/10 border border-emerald-400/25 rounded-xl w-[${size}px] h-[${size}px] active:bg-emerald-500/25`} style={{ width: `${size}px`, height: `${size}px` }} />
                ))
            }
        </div>
        <div className="flex w-full h-[40vh] px-5 py-8 justify-around items-center">
            {/* five buttons blank */}
            {
                [0, 1, 2, 3, 4].map((n) => (
                    <div key={n} onClick={setupClick(n)} className={`bg-emerald-500/10 border border-emerald-400/25 rounded-xl w-[${size}px] h-[${size}px] active:bg-emerald-500/25`} style={{ width: `${size}px`, height: `${size}px` }} />
                ))
            }
        </div>
        <div className="flex w-full px-5 justify-around items-center">
            <input className="w-max-6xl" type="range" min="0" max="255" value={mod} onChange={(e) => broadcastModulation(e.target.value)} />
        </div>
        </>
    )
}