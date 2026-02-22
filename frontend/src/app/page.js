"use client";

import { useEffect, useState } from "react";
import Hand from "./Hand";
import LooperX from "./LooperX";
import Phone from "./phone";


export default function Home() {
    const [page, setPage] = useState("hand");

    useEffect(() => {
        const query = new URLSearchParams(window.location.search);
        const hash = window.location.hash.replace("#", "");
        if (query.has("page")) {
            const p = query.get("page");
            if (["hand", "looperx", "phone"].includes(p)) setPage(p);
        } else if (["hand", "looperx", "phone"].includes(hash)) setPage(hash);
    })

    return (
        <>
        {
            page === "hand" && <Hand />
        }
        {
            page === "looperx" && <LooperX />
        }
        {
            page === "phone" && <Phone />
        }
        </>
    )
}