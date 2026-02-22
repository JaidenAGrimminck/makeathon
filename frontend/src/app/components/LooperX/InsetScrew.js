"use client";

export default function InsetScrew({ className = "" }) {
  return (
    <div
      className={
        "h-2 w-2 rounded-full bg-zinc-900/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),inset_0_-1px_0_rgba(0,0,0,0.65)] " +
        className
      }
    />
  );
}
