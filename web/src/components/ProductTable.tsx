"use client";

import { useState } from "react";
import { fmtVal } from "@/lib/variables";
import type { Fmt } from "@/lib/variables";

export type Col = { key: string; label: string; fmt?: Fmt; w?: number };

export default function ProductTable({
  columns,
  rows,
  searchKeys,
  placeholder,
}: {
  columns: Col[];
  rows: Record<string, unknown>[];
  searchKeys: string[];
  placeholder?: string;
}) {
  const [qy, setQy] = useState("");
  const f = qy.trim().toLowerCase();
  const data = f
    ? rows.filter((r) => searchKeys.some((k) => String(r[k] ?? "").toLowerCase().includes(f)))
    : rows;

  return (
    <div>
      <input
        value={qy}
        onChange={(e) => setQy(e.target.value)}
        placeholder={placeholder || "Cari nama / kode produk / SKU…"}
        className="mb-3 w-full max-w-[340px] border border-[#e6e9f0] rounded-lg px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none"
      />
      <div className="card p-0 overflow-auto max-h-[600px]">
        <table className="text-[12px] border-collapse">
          <thead className="sticky top-0 bg-white z-10">
            <tr className="text-[#8a90a2] text-left">
              {columns.map((c) => (
                <th key={c.key} className="px-3 py-2.5 font-semibold whitespace-nowrap border-b border-[#eef0f6]" style={c.w ? { minWidth: c.w } : undefined}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((r, i) => (
              <tr key={i} className="border-t border-[#f3f4f8] hover:bg-[#fafbfd]">
                {columns.map((c) => {
                  const raw = r[c.key];
                  const empty = raw === undefined || raw === null || raw === "";
                  return (
                    <td key={c.key} className={"px-3 py-2 whitespace-nowrap " + (c.fmt ? "text-right tabular-nums" : "")}>
                      {empty ? <span className="text-[#c4c8d4]">—</span> : c.fmt ? fmtVal(Number(raw), c.fmt) : String(raw)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="text-[11px] text-[#9aa0b2] mt-2">
        {data.length} produk{f ? ` (filter: “${qy}”)` : ""} · geser ke samping untuk lihat semua kolom →
      </div>
    </div>
  );
}
