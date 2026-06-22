"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Filter, Options } from "@/lib/filters";
import { caption } from "@/lib/format";

const MS = 86400000;
const pad = (x: number) => String(x).padStart(2, "0");
const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

// value ISO -> Date di "ruang WIB" (geser +7 jam, lalu pakai getUTC*)
const wib = (iso: string) => new Date(new Date(iso).getTime() + 7 * 3600 * 1000);
const dayKey = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
const monKey = (d: Date) => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}`;
const yrKey = (d: Date) => `${d.getUTCFullYear()}`;
const mondayOf = (d: Date) => new Date(d.getTime() - ((d.getUTCDay() + 6) % 7) * MS);

export default function PeriodePicker({ options, filter }: { options: Options; filter: Filter }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const g = filter.periode;
  const vals = useMemo(
    () => (options.periodsByGran[g] ?? []).map((p) => p.value).sort((a, b) => (a < b ? -1 : 1)),
    [options, g]
  );

  // peta key -> value ISO sesuai granularitas
  const map = useMemo(() => {
    const m = new Map<string, string>();
    for (const v of vals) {
      const w = wib(v);
      const key = g === "harian" ? dayKey(w) : g === "mingguan" ? dayKey(w) : g === "bulanan" ? monKey(w) : yrKey(w);
      m.set(key, v);
    }
    return m;
  }, [vals, g]);

  const lastW = wib(filter.b || vals[vals.length - 1] || new Date().toISOString());
  const [vy, setVy] = useState(lastW.getUTCFullYear());
  const [vm, setVm] = useState(lastW.getUTCMonth());

  function apply(d: string, s: string) {
    if (new Date(d) > new Date(s)) [d, s] = [s, d];
    const p = new URLSearchParams();
    p.set("g", g);
    p.set("d", d);
    p.set("s", s);
    if (filter.toko.length) p.set("t", filter.toko.join(","));
    router.replace(`?${p.toString()}`, { scroll: false });
    setOpen(false);
    setPending(null);
  }
  function click(v?: string) {
    if (!v) return;
    if (!pending) setPending(v);
    else apply(pending, v);
  }
  function preset(n: number) {
    if (!vals.length) return;
    apply(vals[Math.max(0, vals.length - n)], vals[vals.length - 1]);
  }
  const cls = (v?: string) => {
    if (!v) return "text-[#c4c8d4] cursor-default";
    if (v === pending) return "bg-[#ee4d2d] text-white ring-2 ring-[#ee4d2d]";
    const inR = !pending && v >= filter.a && v <= filter.b;
    const edge = v === filter.a || v === filter.b;
    if (edge && !pending) return "bg-[#ee4d2d] text-white";
    if (inR) return "bg-[#fff1ed] text-[#ee4d2d]";
    return "hover:bg-[#f4f6fb] text-[#3a3f4d]";
  };

  // ── KALENDER (harian / mingguan) ──
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
          <button onClick={() => navMonth(-1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180]">‹</button>
          <div className="font-bold text-[14px]">{BULAN[vm]} {vy}</div>
          <button onClick={() => navMonth(1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180]">›</button>
        </div>
        <div className="grid grid-cols-7 gap-0.5 text-center text-[11px] text-[#9aa0b2] mb-1">
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
                className={`h-8 rounded-lg text-[12px] ${inMonth ? "" : "opacity-30"} ${cls(v)}`}
              >
                {dt.getUTCDate()}
              </button>
            );
          })}
        </div>
      </>
    );
  }

  // ── GRID BULAN ──
  function GridBulan() {
    return (
      <>
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => setVy(vy - 1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180]">‹</button>
          <div className="font-bold text-[14px]">{vy}</div>
          <button onClick={() => setVy(vy + 1)} className="w-7 h-7 rounded-lg hover:bg-[#f4f6fb] text-[#6b7180]">›</button>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {BULAN.map((b, m) => {
            const v = map.get(`${vy}-${pad(m + 1)}`);
            return (
              <button key={b} disabled={!v} onClick={() => click(v)} className={`py-2.5 rounded-lg text-[13px] font-medium ${cls(v)}`}>{b}</button>
            );
          })}
        </div>
      </>
    );
  }

  // ── GRID TAHUN ──
  function GridTahun() {
    const years = Array.from(new Set(vals.map((v) => yrKey(wib(v))))).sort();
    return (
      <div className="grid grid-cols-3 gap-1.5">
        {years.map((y) => {
          const v = map.get(y);
          return (
            <button key={y} disabled={!v} onClick={() => click(v)} className={`py-3 rounded-lg text-[14px] font-semibold ${cls(v)}`}>{y}</button>
          );
        })}
      </div>
    );
  }

  const presets =
    g === "harian"
      ? [["Hari ini", 1], ["7 hari", 7], ["30 hari", 30]]
      : g === "mingguan"
      ? [["Minggu ini", 1], ["4 minggu", 4], ["12 minggu", 12]]
      : g === "bulanan"
      ? [["Bulan ini", 1], ["3 bulan", 3], ["6 bulan", 6], ["12 bulan", 12]]
      : [["Tahun ini", 1], ["Semua", vals.length]];

  return (
    <div className="relative">
      <button
        onClick={() => { setOpen(!open); setPending(null); }}
        className="flex items-center gap-2 border border-[#e6e9f0] rounded-xl px-3 py-2 bg-white text-[13px] font-medium hover:border-[#ee4d2d] transition"
      >
        <span>📅</span>
        <span>{caption(filter)}</span>
        <span className="text-[#9aa0b2]">▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => { setOpen(false); setPending(null); }} />
          <div className="absolute z-30 mt-2 left-0 w-[300px] card p-4 shadow-xl">
            <div className="flex flex-wrap gap-1.5 mb-3">
              {presets.map(([lbl, n]) => (
                <button key={lbl as string} onClick={() => preset(n as number)} className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[#f4f6fb] text-[#6b7180] hover:bg-[#fff1ed] hover:text-[#ee4d2d]">{lbl}</button>
              ))}
            </div>
            {pending && (
              <div className="text-[11px] text-[#ee4d2d] mb-2 font-medium">Pilih {g === "tahunan" ? "tahun" : g === "bulanan" ? "bulan" : "tanggal"} akhir…</div>
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
