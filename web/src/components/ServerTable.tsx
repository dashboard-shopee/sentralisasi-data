"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fmtVal, VARS_JUAL, VARS_IKLAN } from "@/lib/variables";
import type { Fmt, VarDef } from "@/lib/variables";
import type { Options } from "@/lib/filters";
import { caption } from "@/lib/format";
import VarMenu from "./VarMenu";
import { FlexChart, ComboAnalisa, PALETTE } from "./charts";
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";

const MS = 86400000;
const pad = (x: number) => String(x).padStart(2, "0");
const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

const wib = (iso: string) => new Date(new Date(iso).getTime() + 7 * 3600 * 1000);
const dayKey = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
const monKey = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}`;
const yrKey = (d: Date) => `${d.getUTCFullYear()}`;
const mondayOf = (d: Date) => new Date(d.getTime() - ((d.getUTCDay() + 6) % 7) * MS);

function LocalPeriodePicker({
  options,
  g,
  a,
  b,
  onChange,
}: {
  options: Options;
  g: string;
  a: string;
  b: string;
  onChange: (d: string, s: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);

  const vals = useMemo(
    () => (options.periodsByGran[g] ?? []).map((p) => p.value).sort((a, b) => (a < b ? -1 : 1)),
    [options, g]
  );

  const map = useMemo(() => {
    const m = new Map<string, string>();
    for (const v of vals) {
      const w = wib(v);
      const key = g === "harian" ? dayKey(w) : g === "mingguan" ? dayKey(w) : g === "bulanan" ? monKey(w) : yrKey(w);
      m.set(key, v);
    }
    return m;
  }, [vals, g]);

  const lastW = wib(b || vals[vals.length - 1] || new Date().toISOString());
  const [vy, setVy] = useState(lastW.getUTCFullYear());
  const [vm, setVm] = useState(lastW.getUTCMonth());

  useEffect(() => {
    if (b) {
      const w = wib(b);
      setVy(w.getUTCFullYear());
      setVm(w.getUTCMonth());
    }
  }, [b]);

  function apply(d: string, s: string) {
    if (new Date(d) > new Date(s)) [d, s] = [s, d];
    onChange(d, s);
    setOpen(false);
    setPending(null);
  }

  function click(v?: string) {
    if (!v) return;
    if (!pending) setPending(v);
    else apply(pending, v);
  }

  const isSameDayWib = (d1: string | Date, d2: string | Date) => {
    const w1 = new Date(new Date(d1).getTime() + 7 * 3600 * 1000);
    const w2 = new Date(new Date(d2).getTime() + 7 * 3600 * 1000);
    return (
      w1.getUTCFullYear() === w2.getUTCFullYear() &&
      w1.getUTCMonth() === w2.getUTCMonth() &&
      w1.getUTCDate() === w2.getUTCDate()
    );
  };

  function preset(val: number | string) {
    if (!vals.length) return;
    if (val === "kemarin") {
      const idx = Math.max(0, vals.length - 2);
      apply(vals[idx], vals[idx]);
    } else if (typeof val === "number") {
      if (val === 1) {
        apply(vals[vals.length - 1], vals[vals.length - 1]);
      } else {
        const hasToday = isSameDayWib(vals[vals.length - 1], new Date());
        if (g === "harian" && hasToday && vals.length > 1) {
          const endIdx = Math.max(0, vals.length - 2);
          const startIdx = Math.max(0, vals.length - 1 - val);
          apply(vals[startIdx], vals[endIdx]);
        } else {
          apply(vals[Math.max(0, vals.length - val)], vals[vals.length - 1]);
        }
      }
    }
  }

  const cls = (v?: string) => {
    if (!v) return "text-[#c4c8d4] cursor-default";
    if (v === pending) return "bg-[#ee4d2d] text-white ring-2 ring-[#ee4d2d]";
    const inR = !pending && v >= a && v <= b;
    const edge = v === a || v === b;
    if (edge && !pending) return "bg-[#ee4d2d] text-white";
    if (inR) return "bg-[#fff1ed] text-[#ee4d2d]";
    return "hover:bg-[#f4f6fb] text-[#3a3f4d]";
  };

  function Kalender() {
    const first = new Date(Date.UTC(vy, vm, 1));
    const start = (first.getUTCDay() + 6) % 7;
    const cells = Array.from({ length: 42 }, (_, i) => new Date(Date.UTC(vy, vm, i - start + 1)));
    function navMonth(delta: number) {
      const d = new Date(Date.UTC(vy, vm + delta, 1));
      setVy(d.getUTCFullYear());
      setVm(d.getUTCMonth());
    }
    return (
      <>
        <div className="flex items-center justify-between mb-2">
          <button onClick={() => navMonth(-1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180] cursor-pointer">‹</button>
          <div className="font-bold text-[13px]">{BULAN[vm]} {vy}</div>
          <button onClick={() => navMonth(1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180] cursor-pointer">›</button>
        </div>
        <div className="grid grid-cols-7 gap-0.5 text-center text-[10px] text-[#9aa0b2] mb-1">
          {HARI.map((h) => <div key={h}>{h}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-0.5">
          {cells.map((dt, i) => {
            const inMonth = dt.getUTCMonth() === vm;
            const v = g === "harian" ? map.get(dayKey(dt)) : map.get(dayKey(mondayOf(dt)));
            return (
              <button
                key={i}
                disabled={!v}
                onClick={() => click(v)}
                className={`h-7 rounded-lg text-[11px] cursor-pointer ${inMonth ? "" : "opacity-30"} ${cls(v)}`}
              >
                {dt.getUTCDate()}
              </button>
            );
          })}
        </div>
      </>
    );
  }

  function GridBulan() {
    return (
      <>
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => setVy(vy - 1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180] cursor-pointer">‹</button>
          <div className="font-bold text-[13px]">{vy}</div>
          <button onClick={() => setVy(vy + 1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180] cursor-pointer">›</button>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {BULAN.map((bName, mIndex) => {
            const v = map.get(`${vy}-${pad(mIndex + 1)}`);
            return (
              <button key={bName} disabled={!v} onClick={() => click(v)} className={`py-1.5 rounded-lg text-[12px] font-medium cursor-pointer ${cls(v)}`}>{bName}</button>
            );
          })}
        </div>
      </>
    );
  }

  function GridTahun() {
    const years = Array.from(new Set(vals.map((v) => yrKey(wib(v))))).sort();
    return (
      <div className="grid grid-cols-3 gap-1.5">
        {years.map((y) => {
          const v = map.get(y);
          return (
            <button key={y} disabled={!v} onClick={() => click(v)} className={`py-2 rounded-lg text-[13px] font-semibold cursor-pointer ${cls(v)}`}>{y}</button>
          );
        })}
      </div>
    );
  }

  const presets: [string, number | string][] =
    g === "harian"
      ? [["Hari ini", 1], ["Kemarin", "kemarin"], ["7 hari", 7], ["30 hari", 30]]
      : g === "mingguan"
      ? [["Minggu ini", 1], ["4 minggu", 4], ["12 minggu", 12]]
      : g === "bulanan"
      ? [["Bulan ini", 1], ["3 bulan", 3], ["6 bulan", 6], ["12 bulan", 12]]
      : [["Tahun ini", 1], ["Semua", vals.length]];

  return (
    <div className="relative">
      <button
        onClick={() => { setOpen(!open); setPending(null); }}
        className="flex items-center gap-2 border border-[#e6e9f0] rounded-xl px-3 py-1.5 bg-white text-[12px] font-semibold hover:border-[#ee4d2d] transition cursor-pointer"
      >
        <span>📅</span>
        <span>{caption({ periode: g, a, b, toko: [] })}</span>
        <span className="text-[#9aa0b2]">▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => { setOpen(false); setPending(null); }} />
          <div className="absolute z-50 mt-2 left-0 w-[280px] bg-white rounded-2xl border border-slate-100 shadow-2xl p-4">
            <div className="flex flex-wrap gap-1.5 mb-3">
              {presets.map(([lbl, val]) => (
                <button key={lbl} onClick={() => preset(val)} className="px-2.5 py-1 rounded-full text-[10px] font-semibold bg-[#f4f6fb] text-[#6b7180] hover:bg-[#fff1ed] hover:text-[#ee4d2d] cursor-pointer">{lbl}</button>
              ))}
            </div>
            {pending && (
              <div className="text-[10px] text-[#ee4d2d] mb-2 font-semibold">Pilih {g === "tahunan" ? "tahun" : g === "bulanan" ? "bulan" : "tanggal"} akhir…</div>
            )}
            {(g === "harian" || g === "mingguan") && <Kalender />}
            {g === "bulanan" && <GridBulan />}
            {g === "tahunan" && <GridTahun />}
          </div>
        </>
      )}
    </div>
  );
}

const VARS_ANALISA: VarDef[] = [
  { key: "omzet", label: "Omzet", fmt: "rp", ikon: "💰" },
  { key: "biaya", label: "Biaya Iklan", fmt: "rp", ikon: "💸" },
  { key: "omzetIklan", label: "Omzet Iklan", fmt: "rp", ikon: "💵" },
  { key: "roas", label: "ROAS", fmt: "ratio", ikon: "📈" },
  { key: "acos", label: "ACOS", fmt: "pct", ikon: "📊" },
];

const SHOP_ID_BY_NAME: Record<string, string> = {
  "Kimmioshop": "1772452045",
  "lollysweet": "1770737480",
  "Ravella Shop": "1482379795",
  "Topikece Store": "1086654958",
  "Alialia Store": "1083692044",
  "OLIOLIO.ID": "552378634",
  "NOMIDE STORE": "416053468",
  "YARRA STORE": "144416606",
  "ZIOSCARF SUPPLIER HIJAB IMPORT": "93819147",
  "BEVERRA OFFICIAL STORE": "13556329"
};

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
  trendKind,
  options,
}: {
  kind: "jual" | "iklan";
  filter: { g: string; d: string; s: string; t: string };
  columns: SCol[];
  defaultSort: string;
  pageSize?: number;
  downloadName?: string;
  editKey?: string;
  trendKind?: "jual" | "iklan" | "analisa";
  options: Options;
}) {
  const [edits, setEdits] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState(false);
  const [pageSizeState, setPageSizeState] = useState(pageSize);

  useEffect(() => {
    setPageSizeState(pageSize);
  }, [pageSize]);

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
      // Bandingkan dgn nilai asli dari DB. Kalau diubah balik ke angka semula
      // (mis. 50 -> 49 -> 50), edit-nya dibuang biar tombol Simpan ikut hilang.
      const origRaw = rows.find((r) => String(r.kode) === kode)?.[key];
      const origStr = origRaw === null || origRaw === undefined || origRaw === "" ? "" : String(origRaw);
      const isRevert = val === origStr || (val !== "" && origStr !== "" && Number(val) === Number(origStr));

      const rowEdits = { ...(prev[kode] || {}) };
      if (isRevert) delete rowEdits[key];
      else rowEdits[key] = val;

      const next = { ...prev };
      if (Object.keys(rowEdits).length === 0) delete next[kode];
      else next[kode] = rowEdits;

      if (editKey) {
        try { localStorage.setItem("edits:" + editKey, JSON.stringify(next)); } catch {}
      }
      return next;
    });
  }

  function discardEdits() {
    setEdits({});
    if (editKey) {
      try { localStorage.removeItem("edits:" + editKey); } catch {}
    }
  }

  function cellNum(r: Record<string, unknown>, key: string): number {
    const e = edits[String(r.kode)]?.[key];
    const v = e !== undefined && e !== "" ? Number(e) : Number(r[key] ?? 0);
    return Number.isFinite(v) ? v : 0;
  }

  const [modal, setModal] = useState<{ title: string; message: string; success: boolean } | null>(null);

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
        const r = await fetch(`/api/produk?${params({ page: "1", size: String(pageSizeState) })}`);
        const j = await r.json();
        setRows(j.rows || []);
        setModal({
          title: "Perubahan Disimpan",
          message: "Data setting iklan manual dan rekomendasi baru telah berhasil disinkronkan ke database Supabase.",
          success: true
        });
      } else {
        setModal({
          title: "Penyimpanan Gagal",
          message: "Server menolak permintaan penyimpanan. Silakan periksa koneksi Anda dan coba lagi.",
          success: false
        });
      }
    } catch (e) {
      console.error(e);
      setModal({
        title: "Sistem Error",
        message: "Gagal terhubung ke server API. Pastikan server lokal/Vercel berjalan dengan benar.",
        success: false
      });
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

  // States for product trend chart modal
  const [selectedProductTrend, setSelectedProductTrend] = useState<any | null>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendChartSel, setTrendChartSel] = useState<string[]>([]);
  
  // Local time & shop variables inside the modal
  const [localG, setLocalG] = useState("harian");
  const [localD, setLocalD] = useState("");
  const [localS, setLocalS] = useState("");
  const [localToko, setLocalToko] = useState<string[]>([]);
  const [trendStores, setTrendStores] = useState<string[]>([]);

  // Derived compareMode: automatically true if only 1 variable selected, and has skuInduk
  const compareMode = trendChartSel.length === 1 && !!selectedProductTrend?.skuInduk;
  const selectedCompareMetric = trendChartSel[0] || "omzet";

  // Reset/Initialize modal local filters when product is selected
  useEffect(() => {
    if (selectedProductTrend) {
      setLocalG(filter.g);
      setLocalD(filter.d);
      setLocalS(filter.s);
      setLocalToko(filter.t ? filter.t.split(",") : []);

      // Initialize default metrics
      if (trendKind === "iklan") {
        setTrendChartSel(["omzetIklan", "biayaIklan", "roas"]);
      } else if (trendKind === "analisa") {
        setTrendChartSel(["omzet", "biaya", "omzetIklan", "roas", "acos"]);
      } else {
        setTrendChartSel(["omzet", "pesanan"]);
      }
    }
  }, [selectedProductTrend, trendKind]);

  // Adjust date range when local granularity changes
  useEffect(() => {
    if (!options || !options.periodsByGran || !selectedProductTrend) return;
    const dates = options.periodsByGran[localG] || [];
    if (dates.length === 0) return;
    
    const WIN_LOCAL: Record<string, number> = { harian: 14, mingguan: 12, bulanan: 12, tahunan: 6 };
    const dateVals = dates.map(d => d.value);
    const win = WIN_LOCAL[localG] || 12;
    
    let defaultB = dateVals[0] || "";
    let defaultA = dateVals[Math.min(win - 1, dateVals.length - 1)] || "";
    if (defaultA && defaultB && new Date(defaultA) > new Date(defaultB)) {
      [defaultA, defaultB] = [defaultB, defaultA];
    }
    
    setLocalD(defaultA);
    setLocalS(defaultB);
  }, [localG, options, selectedProductTrend]);

  // Fetch trend data based on local filters
  useEffect(() => {
    if (!selectedProductTrend || !trendKind) {
      setTrendData([]);
      setTrendStores([]);
      return;
    }
    
    setTrendLoading(true);
    const params = new URLSearchParams({
      trend_kode: selectedProductTrend.kode,
      trend_kind: trendKind,
      g: localG,
      d: localD,
      s: localS,
      t: localToko.join(","),
    });
    
    if (compareMode && selectedProductTrend.skuInduk) {
      params.append("compare_stores", "1");
      params.append("metric", selectedCompareMetric);
      params.append("sku_induk", selectedProductTrend.skuInduk);
    }
    
    fetch(`/api/produk?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        setTrendData(data.trend || []);
        setTrendStores(data.stores || []);
      })
      .catch((err) => {
        console.error("Gagal mengambil data tren produk:", err);
        setTrendData([]);
        setTrendStores([]);
      })
      .finally(() => {
        setTrendLoading(false);
      });
  }, [selectedProductTrend, trendKind, localG, localD, localS, localToko, compareMode, selectedCompareMetric]);

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
    fetch(`/api/produk?${params({ page: String(page), size: String(pageSizeState) })}`)
      .then((r) => r.json())
      .then((j) => { if (alive) { setRows(j.rows || []); setTotal(j.total || 0); } })
      .catch(() => { if (alive) { setRows([]); setTotal(0); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [params, page, pageSizeState]);

  const pages = Math.max(1, Math.ceil(total / pageSizeState));
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
          <div className="flex items-center gap-1.5">
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-[13px] font-semibold text-white px-3 py-2 rounded-lg disabled:opacity-50 transition-all duration-150 shadow-md flex items-center gap-1.5 hover:brightness-105"
              style={{ background: "linear-gradient(135deg,#f43f5e,#e11d48)" }}
            >
              {saving ? "⏳ Menyimpan..." : `💾 Simpan ${numEdits} Perubahan`}
            </button>
            <button
              onClick={discardEdits}
              disabled={saving}
              title="Batalkan semua perubahan"
              className="text-[13px] font-semibold text-slate-500 w-9 h-9 grid place-items-center rounded-lg border border-[#e6e9f0] bg-white disabled:opacity-50 transition-all duration-150 hover:bg-slate-50 hover:text-rose-500 hover:border-rose-200"
            >
              ✕
            </button>
          </div>
        )}
        <span className="text-[12px] text-[#9aa0b2] ml-auto">{total.toLocaleString("id-ID")} produk</span>
      </div>

      <div className="card p-0 overflow-auto relative max-h-[75vh]">
        {loading && (
          <div className="absolute inset-0 bg-white/60 grid place-items-center z-20 text-[13px] text-[#8a90a2]">Memuat…</div>
        )}
        <table className="text-[12px] border-collapse">
          <thead className="sticky top-0 bg-white z-10">
            <tr className="text-[#8a90a2] text-left">
              <th className="px-3 py-2.5 font-semibold border-b border-[#eef0f6]">No</th>
              {columns.map((c) => {
                const active = c.sort && sort === c.sort;
                const canWrap = ["produk", "ketRating", "ketRoas", "ketBudget", "action"].includes(c.key);
                return (
                  <th
                    key={c.key}
                    onClick={() => clickSort(c)}
                    className={"px-3 py-2.5 font-semibold border-b border-[#eef0f6] " + 
                      (canWrap ? "" : "whitespace-nowrap ") + 
                      (c.sort ? "cursor-pointer select-none hover:text-[#ee4d2d]" : "")}
                    style={c.w ? { minWidth: c.w, maxWidth: c.w } : undefined}
                  >
                    <div style={canWrap ? { whiteSpace: "normal", wordBreak: "break-word", lineHeight: "1.2" } : undefined}>
                      {c.label}
                      {c.sort ? <span className={"ml-1 " + (active ? "text-[#ee4d2d]" : "text-[#cfd3de]")}>{active ? (dir === "asc" ? "▲" : "▼") : "↕"}</span> : null}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-[#f3f4f8] hover:bg-[#fafbfd]">
                <td className="px-3 py-2 text-[#9aa0b2]">{(page - 1) * pageSizeState + i + 1}</td>
                {columns.map((c) => {
                  if (c.key === "gambar") {
                    const url = r.gambar ? String(r.gambar) : "";
                    const shopId = r.toko ? (SHOP_ID_BY_NAME[String(r.toko)] || "") : "";
                    const itemId = r.kode ? String(r.kode) : "";
                    const shopeeUrl = shopId && itemId ? `https://shopee.co.id/product/${shopId}/${itemId}` : "#";

                    return (
                      <td key={c.key} className="px-2 py-1.5">
                        {url ? (
                          <a
                            href={shopeeUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block hover:opacity-85 transition-opacity"
                            title="Buka di Shopee"
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={url} alt="" loading="lazy" referrerPolicy="no-referrer"
                              className="w-12 h-12 rounded-md object-cover border border-[#eef0f6] bg-[#fafbfd] cursor-pointer" />
                          </a>
                        ) : (
                          <div className="w-12 h-12 rounded-md bg-[#f3f4f8] grid place-items-center text-[#c4c8d4] text-[14px]">🖼️</div>
                        )}
                      </td>
                    );
                  }
                  if (c.key === "skuInduk") {
                    const sku = r.skuInduk ? String(r.skuInduk) : "";
                    const itemId = r.kode ? String(r.kode) : "";
                    return (
                      <td
                        key={c.key}
                        className="px-3 py-2 text-slate-700 font-medium text-[12px]"
                        style={{
                          width: c.w ? c.w : 120,
                          minWidth: c.w ? c.w : 120,
                          maxWidth: c.w ? c.w : 120,
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                          lineHeight: "1.35",
                        }}
                      >
                        <div className="font-semibold text-slate-700">{sku || <span className="text-[#c4c8d4]">—</span>}</div>
                        {itemId && <div className="text-[#8a90a2] text-[11px] font-normal mt-0.5">{itemId}</div>}
                      </td>
                    );
                  }
                  if (c.key === "produk") {
                    const raw = r[c.key];
                    const empty = raw === undefined || raw === null || raw === "";
                    return (
                      <td
                        key={c.key}
                        onClick={() => trendKind && setSelectedProductTrend(r)}
                        className={"px-3 py-2 text-slate-700 font-medium " + (trendKind ? "cursor-pointer hover:text-[#ee4d2d] transition-colors" : "")}
                        style={{
                          width: c.w ? c.w : 180,
                          minWidth: c.w ? c.w : 180,
                          maxWidth: c.w ? c.w : 180,
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                        }}
                      >
                        <div
                          style={{
                            display: "-webkit-box",
                            WebkitLineClamp: "2",
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                            lineHeight: "1.35",
                          }}
                          title={String(raw)}
                        >
                          {empty ? <span className="text-[#c4c8d4]">—</span> : String(raw)}
                        </div>
                      </td>
                    );
                  }
                  if (c.key.startsWith("ket")) {
                    const raw = r[c.key];
                    const text = String(raw || "");
                    const parts = text.split("|");
                    let line1 = text;
                    let line2 = "";
                    
                    if (parts.length >= 3) {
                      line1 = parts[0].trim() + " | " + parts[1].trim();
                      line2 = parts.slice(2).join(" | ").trim();
                    } else if (parts.length === 2) {
                      line1 = parts[0].trim();
                      line2 = parts[1].trim();
                    }

                    return (
                      <td
                        key={c.key}
                        className="px-3 py-2 text-slate-500 text-[11px]"
                        style={{
                          width: c.w ? c.w : 130,
                          minWidth: c.w ? c.w : 130,
                          maxWidth: c.w ? c.w : 130,
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                          lineHeight: "1.35",
                        }}
                      >
                        <div className="font-semibold text-slate-600">{line1}</div>
                        {line2 && <div className="text-slate-400 font-normal mt-0.5">{line2}</div>}
                      </td>
                    );
                  }
                  if (c.key === "action") {
                    const raw = r[c.key];
                    const text = String(raw || "");
                    const parts = text.split("&");
                    
                    return (
                      <td
                        key={c.key}
                        className="px-3 py-2 text-slate-700 font-medium text-[11px]"
                        style={{
                          width: c.w ? c.w : 150,
                          minWidth: c.w ? c.w : 150,
                          maxWidth: c.w ? c.w : 150,
                          whiteSpace: "normal",
                          wordBreak: "break-word",
                          lineHeight: "1.35",
                        }}
                      >
                        {parts.map((p, idx) => (
                          <div key={idx} className={idx > 0 ? "mt-1.5" : ""}>
                            {p.trim()}
                          </div>
                        ))}
                      </td>
                    );
                  }
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

      <div className="flex items-center justify-between mt-3 text-[12px] flex-wrap gap-3">
        <div className="flex items-center gap-4">
          <span className="text-[#9aa0b2]">Halaman {page} dari {pages}</span>
          <div className="flex items-center gap-1.5 text-slate-500">
            <span>Tampilkan:</span>
            <select
              value={pageSizeState}
              onChange={(e) => {
                setPageSizeState(Number(e.target.value));
                setPage(1);
              }}
              className="bg-white border border-[#e6e9f0] rounded px-2 py-1 text-[12px] font-semibold outline-none focus:border-[#ee4d2d] cursor-pointer"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <span>produk</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => setPage(1)} disabled={page <= 1} className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40 hover:bg-slate-50 cursor-pointer">⏮</button>
          <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="px-3 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40 hover:bg-slate-50 cursor-pointer">‹ Prev</button>
          <button onClick={() => setPage(page + 1)} disabled={page >= pages} className="px-3 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40 hover:bg-slate-50 cursor-pointer">Next ›</button>
          <button onClick={() => setPage(pages)} disabled={page >= pages} className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] disabled:opacity-40 hover:bg-slate-50 cursor-pointer">⏭</button>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        .animate-fade-in {
          animation: fadeIn 0.18s ease-out forwards;
        }
        .animate-scale-up {
          animation: scaleUp 0.22s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
      `}} />

      {modal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl p-7 max-w-sm w-full mx-4 flex flex-col items-center text-center border border-slate-100 animate-scale-up">
            <div className="mb-4">
              <img src="/syntra-logo.png" alt="SYNTRA" className="h-9 object-contain" />
            </div>
            
            <div className={`w-14 h-14 rounded-full flex items-center justify-center mb-4 ${modal.success ? 'bg-emerald-50 text-emerald-500 border border-emerald-100' : 'bg-rose-50 text-rose-500 border border-rose-100'}`}>
              {modal.success ? (
                <svg className="w-7 h-7 stroke-current" fill="none" strokeWidth="3.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <svg className="w-7 h-7 stroke-current" fill="none" strokeWidth="3.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
            </div>

            <h3 className="text-[15px] font-bold text-slate-800 mb-1">{modal.title}</h3>
            <p className="text-[12.5px] text-slate-500 mb-5 leading-relaxed px-1">{modal.message}</p>

            <button
              onClick={() => setModal(null)}
              className="w-full py-2.5 px-4 rounded-xl text-white font-semibold text-[13px] transition-all duration-150 active:scale-97 shadow-md hover:brightness-105 cursor-pointer outline-none"
              style={{ background: modal.success ? "linear-gradient(135deg,#16b8a6,#0ea596)" : "linear-gradient(135deg,#f43f5e,#e11d48)" }}
            >
              OK
            </button>
          </div>
        </div>
      )}
      {selectedProductTrend && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-40 animate-fade-in p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 max-w-3xl w-full mx-auto border border-slate-100 animate-scale-up flex flex-col max-h-[90vh]">
            
            {/* Header Modal */}
            <div className="flex items-start justify-between border-b pb-4 mb-4 shrink-0">
              <div className="flex items-center gap-3.5">
                {selectedProductTrend.gambar ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={selectedProductTrend.gambar}
                    alt=""
                    className="w-12 h-12 rounded-lg object-cover border border-[#eef0f6]"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-lg bg-[#f3f4f8] grid place-items-center text-[#c4c8d4] text-[16px]">
                    🖼️
                  </div>
                )}
                <div className="max-w-[500px] text-left">
                  <h3 className="text-[14px] font-bold text-slate-800 line-clamp-1">
                    {selectedProductTrend.produk}
                  </h3>
                  <p className="text-[11px] text-[#8a90a2] mt-0.5 font-medium">
                    SKU Induk: <span className="text-[#3a3f4d] font-bold">{selectedProductTrend.skuInduk || "—"}</span>
                    {"  ·  "}
                    Toko Asal: <span className="text-[#3a3f4d] font-bold">{selectedProductTrend.toko}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedProductTrend(null)}
                className="text-slate-400 hover:text-slate-600 text-2xl leading-none font-normal px-2 py-1 cursor-pointer"
              >
                &times;
              </button>
            </div>

            {/* Modal Filters (Time & Store Selection) */}
            <div className="bg-[#f8fafc] border border-slate-100 rounded-xl p-3.5 mb-4 shrink-0 flex flex-col gap-3 text-left">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2.5">
                
                {/* Granularity */}
                <div className="flex items-center gap-1 bg-slate-200/60 rounded-lg p-0.5">
                  {options.grans.map((g) => (
                    <button
                      key={g}
                      onClick={() => setLocalG(g)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition cursor-pointer ${g === localG ? "bg-white text-[#ee4d2d] shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
                    >
                      {g === "harian" ? "Hari" : g === "mingguan" ? "Minggu" : g === "bulanan" ? "Bulan" : "Tahun"}
                    </button>
                  ))}
                </div>

                <LocalPeriodePicker
                  options={options}
                  g={localG}
                  a={localD}
                  b={localS}
                  onChange={(d, s) => {
                    setLocalD(d);
                    setLocalS(s);
                  }}
                />

              </div>

              {/* Toko Selector */}
              <div className="flex flex-wrap items-center gap-1.5 pt-2.5 border-t border-slate-100">
                <span className="text-[11px] text-slate-400 font-semibold mr-1">Toko dibanding:</span>
                <button
                  onClick={() => setLocalToko([])}
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition cursor-pointer ${localToko.length === 0 ? "bg-[#ee4d2d] text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                >
                  Semua
                </button>
                {options.toko.map((t) => {
                  const on = localToko.includes(t);
                  return (
                    <button
                      key={t}
                      onClick={() => {
                        if (localToko.includes(t)) {
                          setLocalToko(localToko.filter((x) => x !== t));
                        } else {
                          setLocalToko([...localToko, t]);
                        }
                      }}
                      className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition cursor-pointer ${on ? "bg-[#fff1ed] text-[#ee4d2d] ring-1 ring-[#ee4d2d]" : "bg-slate-100 text-slate-500 hover:bg-slate-200"}`}
                    >
                      {t}
                    </button>
                  );
                })}
              </div>

            </div>

            {/* Content & Grafik */}
            <div className="flex-1 overflow-y-auto">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h4 className="text-[13px] font-bold text-slate-700 text-left">
                  {compareMode ? `Perbandingan Toko (${selectedProductTrend.skuInduk})` : "Tren Performa Produk"}
                </h4>
                
                <div>
                  <VarMenu
                    all={trendKind === "jual" ? VARS_JUAL : trendKind === "iklan" ? VARS_IKLAN : VARS_ANALISA}
                    selected={trendChartSel}
                    onChange={setTrendChartSel}
                    max={trendKind === "analisa" ? 5 : 4}
                    label="Atur Grafik"
                  />
                </div>
              </div>

              <div className="bg-[#fafbfd] border border-slate-100 rounded-xl p-4 min-h-[300px] flex items-center justify-center relative">
                {trendLoading ? (
                  <div className="text-[13px] text-slate-400 font-medium">Memuat data grafik tren...</div>
                ) : trendData.length === 0 ? (
                  <div className="text-[13px] text-slate-400 font-medium">Tidak ada data tren performa untuk rentang waktu ini.</div>
                ) : compareMode ? (
                  <ResponsiveContainer width="100%" height={320}>
                    <LineChart data={trendData} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
                      <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} />
                      <YAxis
                        tick={{ fontSize: 11, fill: "#9aa0b2" }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => {
                          const vdef = (trendKind === "jual" ? VARS_JUAL : trendKind === "iklan" ? VARS_IKLAN : VARS_ANALISA).find((x) => x.key === selectedCompareMetric);
                          return fmtVal(Number(v), (vdef?.fmt || "num") as Fmt);
                        }}
                        width={58}
                      />
                      <Tooltip
                        itemSorter={(item) => -Number(item.value)}
                        contentStyle={{
                          borderRadius: 12,
                          border: "1px solid #eef1f6",
                          boxShadow: "0 6px 20px rgba(20,23,40,.08)",
                          fontSize: 12,
                        }}
                        cursor={{ fill: "#f6f7fb" }}
                        formatter={(v, name) => {
                          const vdef = (trendKind === "jual" ? VARS_JUAL : trendKind === "iklan" ? VARS_IKLAN : VARS_ANALISA).find((x) => x.key === selectedCompareMetric);
                          return [fmtVal(Number(v), (vdef?.fmt || "num") as Fmt), name];
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      {trendStores.map((store, i) => (
                        <Line
                          key={store}
                          type="monotone"
                          dataKey={store}
                          name={store}
                          stroke={PALETTE[i % PALETTE.length]}
                          strokeWidth={2.5}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                ) : trendKind === "analisa" ? (
                  <ComboAnalisa data={trendData} isShopComparison={false} />
                ) : (
                  <FlexChart
                    data={trendData}
                    series={trendChartSel.map((k) => (trendKind === "jual" ? VARS_JUAL : VARS_IKLAN).find((x) => x.key === k)).filter(Boolean) as VarDef[]}
                    isShopComparison={false}
                  />
                )}
              </div>
            </div>

            {/* Footer Modal */}
            <div className="border-t pt-4 mt-4 flex justify-end shrink-0">
              <button
                onClick={() => setSelectedProductTrend(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-xl text-[13px] font-semibold transition cursor-pointer"
              >
                Tutup
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}
