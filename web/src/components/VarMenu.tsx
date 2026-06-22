"use client";

import { useState } from "react";
import type { VarDef } from "@/lib/variables";

export default function VarMenu({
  all,
  selected,
  onChange,
  max,
  label,
}: {
  all: VarDef[];
  selected: string[];
  onChange: (s: string[]) => void;
  max: number;
  label: string;
}) {
  const [open, setOpen] = useState(false);
  function toggle(k: string) {
    let s = selected.includes(k) ? selected.filter((x) => x !== k) : [...selected, k];
    if (s.length === 0) return; // minimal 1
    if (s.length > max) s = s.slice(s.length - max); // buang yang paling lama
    onChange(s);
  }
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[12px] font-semibold text-[#6b7180] border border-[#e6e9f0] rounded-lg px-2.5 py-1.5 hover:border-[#ee4d2d] transition"
      >
        ⚙️ {label} <span className="text-[#9aa0b2]">▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute z-30 mt-1 right-0 w-[220px] card p-2 shadow-xl">
            <div className="text-[11px] text-[#9aa0b2] px-2 py-1">Pilih maksimal {max} variabel</div>
            <div className="max-h-[320px] overflow-auto">
              {all.map((v) => {
                const on = selected.includes(v.key);
                return (
                  <button
                    key={v.key}
                    onClick={() => toggle(v.key)}
                    className={"w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-[13px] text-left " + (on ? "bg-[#fff1ed] text-[#ee4d2d]" : "hover:bg-[#f6f7fb] text-[#3a3f4d]")}
                  >
                    <span className={"w-4 h-4 rounded grid place-items-center text-[10px] shrink-0 " + (on ? "bg-[#ee4d2d] text-white" : "border border-[#cfd3de]")}>{on ? "✓" : ""}</span>
                    <span>{v.ikon}</span>
                    {v.label}
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
