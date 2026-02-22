"use client";

const palette = {
  green: "bg-emerald-400/90 shadow-[0_0_22px_rgba(16,185,129,0.55)]",
  orange: "bg-orange-500/90 shadow-[0_0_22px_rgba(249,115,22,0.55)]",
  white: "bg-zinc-100/90 shadow-[0_0_18px_rgba(244,244,245,0.45)]",
  off: "bg-zinc-700/40 shadow-none",
};

export default function LedBar({ color = "green", active = true }) {
  const tone = palette[color] || palette.green;
  return (
    <div
      className={
        "h-2.5 w-24 rounded-full transition " +
        (active ? tone : palette.off) +
        (active ? " animate-pulse" : "")
      }
    />
  );
}
