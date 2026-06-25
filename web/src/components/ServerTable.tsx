"use client";

import { useCallback, useEffect, useState } from "react";
import { fmtVal } from "@/lib/variables";
import type { Fmt } from "@/lib/variables";

export type SCol = {
  key: string;
  label: string;
  fmt?: Fmt;
  w?: number;
  sort?: string;
  edit?: boolean; // cell input manual (nominal)
  computeMax?: string[]; // nilai = MAX dari kolom-kolom ini (pakai nilai edit bila ada)
};

export default function ServerTable({
  kind,
  filter,
  columns,
  defaultSort,
  pageSize = 50,
  downloadName,
  editKey,
}: {
  kind: "jual" | "iklan";
  filter: { g: string; d: string; s: string; t: string };
  columns: SCol[];
  defaultSort: string;
  pageSize?: number;
  downloadName?: string;
  editKey?: string;
}) {
  const [edits, setEdits] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editKey) return;
    try {
      const s = localStorage.getItem("edits:" + editKey);
      if (s) setEdits(JSON.parse(s));
    } catch {}
  }, [editKey]);

  const numEdits = Object.keys(edits).length;

  function setEdit(kode: string, key: string, val: string) {
    setEdits((prev) => {
      const next = { ...prev, [kode]: { ...(prev[kode] || {}), [key]: val } };
      if (editKey) {
        try { localStorage.setItem("edits:" + editKey, JSON.stringify(next)); } catch {}
      }
      return next;
    });
  }

  function cellNum(r: Record<string, unknown>, key: string): number {
    const e = edits[String(r.kode)]?.[key];
    const v = e !== undefined && e !== "" ? Number(e) : Number(r[key] ?? 0);
    return Number.isFinite(v) ? v : 0;
  }

  async function handleSave() {
    if (numEdits === 0) return;
    setSaving(true);
    try {
      const res = await fetch("/api/produk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edits }),
      });
      if (res.ok) {
        setEdits({});
        if (editKey) {
          localStorage.removeItem("edits:" + editKey);
        }
        // Force refresh rows
        setPage(1);
        const r = await fetch(`/api/produk?${params({ page: "1", size: String(pageSize) })}`);
        const j = await r.json();
        setRows(j.rows || []);
        alert("Perubahan berhasil disimpan!");
      } else {
        alert("Gagal menyimpan perubahan.");
      }
    } catch (e) {
      console.error(e);
      alert("Error menyimpan perubahan.");
    } finally {
      setSaving(false);
    }
  }
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState(defaultSort);
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fkey = `${filter.g}|${filter.d}|${filter.s}|${filter.t}`;

  useEffect(() => {
    const t = setTimeout(() => { setQ(qInput); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [qInput]);
  useEffect(() => { setPage(1); }, [fkey]);

  const params = useCallback(
    (extra: Record<string, string>) =>
      new URLSearchParams({ kind, g: filter.g, d: filter.d, s: filter.s, t: filter.t, sort, dir, q, ...extra }).toString(),
    [kind, filter.g, filter.d, filter.s, filter.t, sort, dir, q]
  );

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch(`/api/produk?${params({ page: String(page), size: String(pageSize) })}`)
      .then((r) => r.json())
      .then((j) => { if (alive) { setRows(j.rows || []); setTotal(j.total || 0); } })
      .catch(() => { if (alive) { setRows([]); setTotal(0); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [params, page, pageSize]);

  const pages = Math.max(1, Math.ceil(total / pageSize));
  function clickSort(c: SCol) {
    if (!c.sort) return;
    if (sort === c.sort) setDir(dir === "asc" ? "desc" : "asc");
    else { setSort(c.sort); setDir("desc"); }
    setPage(1);
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <input
          value={qInput}
          onChange={(e) => setQInput(e.target.value)}
          placeholder="Cari nama / kode produk / SKU…"
          className="flex-1 min-w-[220px] max-w-[340px] border border-[#e6e9f0] rounded-lg px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none"
        />
        {downloadName && (
          <a
            href={`/api/produk?${params({ download: "csv" })}`}
            className="text-[13px] font-semibold text-white px-3 py-2 rounded-lg"
            style={{ background: "linear-gradient(135deg,#16b8a6,#0ea596)" }}
          >
            ⬇️ Download Laporan
          </a>
        )}
        {editKey && numEdits > 0 && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-[13px] font-semibold text-white px-3 py-2 rounded-lg disabled:opacity-50 transition-all duration-150 shadow-md flex items-center gap-1.5 hover:brightness-105"
            style={{ background: "linear-gradient(135deg,#f43f5e,#e11d48)" }}
          >
            {saving ? "⏳ Menyimpan..." : `💾 Simpan ${numEdits} Perubahan`}
          </button>
        )}
        <span className="text-[12px] text-[#9aa0b2] ml-auto">{total.toLocaleString("id-ID")} produk</span>
      </div>

      <div className="card p-0 overflow-auto max-h-[600px] relative">
        {loading && (
          <div className="absolute inset-0 bg-white/60 grid place-items-center z-20 text-[13px] text-[#8a90a2]">Memuat…</div>
        )}
        <table className="text-[12px] border-collapse">
          <thead className="sticky top-0 bg-white z-10">
            <tr className="text-[#8a90a2] text-left">
              <th className="px-3 py-2.5 font-semibold border-b border-[#eef0f6]">No</th>
              {columns.map((c) => {
                const active = c.sort && sort === c.sort;
                return (
                  <th
                    key={c.key}
                    onClick={() => clickSort(c)}
                    className={"px-3 py-2.5 font-semibold whitespace-nowrap border-b border-[#eef0f6] " + (c.sort ? "cursor-pointer select-none hover:text-[#ee4d2d]" : "")}
                    style={c.w ? { minWidth: c.w } : undefined}
                  >
                    {c.label}
                    {c.sort ? <span className={"ml-1 " + (active ? "text-[#ee4d2d]" : "text-[#cfd3de]")}>{active ? (dir === "asc" ? "▲" : "▼") : "↕"}</span> : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[#f3f4f8] hover:bg-[#fafbfd]">
                <td className="px-3 py-2 text-[#9aa0b2]">{(page - 1) * pageSize + i + 1}</td>
                {columns.map((c) => {
                  if (c.edit && editKey) {
                    const dbv = r[c.key];
                    const val = edits[String(r.kode)]?.[c.key] ?? (dbv === null || dbv === undefined || dbv === "" ? "" : String(dbv));
                    
                    let deltaNode = null;
                    if (c.key === "rekomRoas") {
                      const targetVal = Number(r.targetRoas || 0);
                      const curVal = val !== "" ? Number(val) : 0;
                      if (targetVal > 0 && curVal > 0) {
                        const diff = curVal - targetVal;
                        if (diff > 0) {
                          deltaNode = <span className="text-[10px] text-emerald-600 font-bold ml-1">↑ +{diff.toFixed(1)}</span>;
                        } else if (diff < 0) {
                          deltaNode = <span className="text-[10px] text-rose-600 font-bold ml-1">↓ {diff.toFixed(1)}</span>;
                        }
                      }
                    }
                    
                    return (
                      <td key={c.key} className="px-2 py-1.5 whitespace-nowrap">
                        <div className="flex items-center gap-1 justify-end">
                          <input
                            type="number"
                            step="any"
                            value={val}
                            onChange={(e) => setEdit(String(r.kode), c.key, e.target.value)}
                            placeholder="—"
                            className="w-[90px] border border-[#e6e9f0] rounded-md px-2 py-1 text-right text-[12px] focus:border-[#ee4d2d] outline-none font-medium text-slate-800"
                          />
                          {deltaNode}
                        </div>
                      </td>
                    );
                  }
                  
                  if (c.computeMax) {
                    const m = Math.max(0, ...c.computeMax.map((k) => cellNum(r, k)));
                    return (
                      <td key={c.key} className="px-3 py-2 whitespace-nowrap text-right tabular-nums font-bold text-slate-800">
                        {m > 0 ? fmtVal(m, c.fmt || "rp") : <span className="text-[#c4c8d4]">—</span>}
                      </td>
                    );
                  }

                  const raw = r[c.key];
                  const empty = raw === undefined || raw === null || raw === "";

                  if (c.key === "ratingIklan") {
                    const rating = String(raw || "");
                    if (!rating) return <td key={c.key} className="px-3 py-2 text-[#c4c8d4] text-center">—</td>;
                    
                    let style = "bg-slate-100 text-slate-700 border-slate-200";
                    if (rating === "Super") {
                      style = "bg-[#f3e5f5] text-[#7b1fa2] border-[#e1bee7] font-extrabold shadow-sm";
                    } else if (rating === "Excellent") {
                      style = "bg-[#e8f5e9] text-[#2e7d32] border-[#c8e6c9] font-bold shadow-sm";
                    } else if (rating === "Good") {
                      style = "bg-[#e0f2f1] text-[#00695c] border-[#b2dfdb] font-medium";
                    } else if (rating === "Average") {
                      style = "bg-[#e3f2fd] text-[#1565c0] border-[#bbdefb]";
                    } else if (rating === "Bad") {
                      style = "bg-[#fff3e0] text-[#e65100] border-[#ffe0b2]";
                    } else if (rating === "Takedown") {
                      style = "bg-[#ffebee] text-[#c62828] border-[#ffcdd2] font-semibold";
                    }
                    
                    return (
                      <td key={c.key} className="px-3 py-2 whitespace-nowrap">
                        <span className={`px-2 py-0.5 rounded text-[11px] border inline-block text-center min-w-[75px] ${style}`}>
                          {rating}
                        </span>
                      </td>
                    );
                  }

                  if (c.key === "rekomRoas") {
                    const targetVal = Number(r.targetRoas || 0);
                    const val = raw !== undefined && raw !== null && raw !== "" ? Number(raw) : 0;
                    
                    let bg = "transparent";
                    let fg = "inherit";
                    if (val === 0 || r.ratingIklan === "Takedown") {
                      bg = "#fff1f2"; fg = "#be123c";
                    } else if (val < 10) {
                      bg = "#fff7ed"; fg = "#c2410c";
                    } else if (val > 33) {
                      bg = "#f0fdfa"; fg = "#0f766e";
                    }
                    
                    let deltaNode = null;
                    if (targetVal > 0 && val > 0) {
                      const diff = val - targetVal;
                      if (diff > 0) {
                        deltaNode = <span className="text-[10px] text-emerald-600 font-bold ml-1">↑ +{diff.toFixed(1)}</span>;
                      } else if (diff < 0) {
                        deltaNode = <span className="text-[10px] text-rose-600 font-bold ml-1">↓ {diff.toFixed(1)}</span>;
                      }
                    }
                    
                    return (
                      <td key={c.key} className="px-3 py-2 whitespace-nowrap font-semibold text-right tabular-nums" style={{ backgroundColor: bg, color: fg }}>
                        {val > 0 ? val.toFixed(1) : <span className="text-[#c4c8d4]">—</span>}
                        {deltaNode}
                      </td>
                    );
                  }

                  return (
                    <td key={c.key} className={"px-3 py-2 whitespace-nowrap " + (c.fmt ? "text-right tabular-nums" : "")}>
                      {empty ? <span className="text-[#c4c8d4]">—</span> : c.fmt ? fmtVal(Number(raw), c.fmt) : String(raw)}
                    </td>
                  );
                })}
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={columns.length + 1} className="px-3 py-8 text-center text-[#9aa0b2]">Tidak ada produk.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-3 text-[12px]">
        <span className="text-[#9aa0b2]">Halaman {page} dari {pages}</span>
        <div className="flex items-center gap-1.5">
          <button onClick={() => setPage(1)} disabled={page <= 1} className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40">⏮</button>
          <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="px-3 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40">‹ Prev</button>
          <button onClick={() => setPage(page + 1)} disabled={page >= pages} className="px-3 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40">Next ›</button>
          <button onClick={() => setPage(pages)} disabled={page >= pages} className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40">⏭</button>
        </div>
      </div>
    </div>
  );
}
