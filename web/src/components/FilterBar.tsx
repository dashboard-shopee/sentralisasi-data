"use client";

import { useRouter } from "next/navigation";
import type { Filter, Options } from "@/lib/filters";
import PeriodePicker from "./PeriodePicker";

const GRAN_LABEL: Record<string, string> = {
  harian: "Per Hari",
  mingguan: "Per Minggu",
  bulanan: "Per Bulan",
  tahunan: "Per Tahun",
};

export default function FilterBar({ options, filter }: { options: Options; filter: Filter }) {
  const router = useRouter();
  const allToko = options.toko;
  const semua = filter.toko.length === 0;

  function go(over: { g?: string; d?: string | null; s?: string | null; t?: string | null }) {
    const changedGran = over.g !== undefined && over.g !== filter.periode;
    const g = over.g ?? filter.periode;
    const d = over.d !== undefined ? over.d : changedGran ? null : filter.a;
    const s = over.s !== undefined ? over.s : changedGran ? null : filter.b;
    const t = over.t !== undefined ? over.t : filter.toko.length ? filter.toko.join(",") : null;
    const p = new URLSearchParams();
    p.set("g", g);
    if (d) p.set("d", d);
    if (s) p.set("s", s);
    if (t) p.set("t", t);
    router.replace(`?${p.toString()}`, { scroll: false });
  }



  const sel = "px-3 py-1.5 rounded-lg text-[13px] font-semibold transition";
  return (
    <div className="card p-4 mb-5">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        {/* Granularitas */}
        <div className="flex items-center gap-1 bg-[#f4f6fb] rounded-xl p-1">
          {options.grans.map((g) => (
            <button
              key={g}
              onClick={() => go({ g })}
              className={sel + (g === filter.periode ? " bg-white text-[#ee4d2d] shadow-sm" : " text-[#6b7180]")}
            >
              {GRAN_LABEL[g]}
            </button>
          ))}
        </div>

        {/* Rentang periode (pop-up kalender / grid) */}
        <PeriodePicker options={options} filter={filter} />
      </div>

      {/* Toko */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[#f0f2f7]">
        <span className="text-[12px] text-[#8a90a2] mr-1">Toko:</span>
        <div className="relative">
          <select
            value={semua ? "" : filter.toko[0] || ""}
            onChange={(e) => go({ t: e.target.value ? e.target.value : null })}
            className="appearance-none bg-white border border-[#eef0f6] pl-3.5 pr-9 py-1.5 rounded-xl text-[13px] font-semibold text-[#3a3f4d] outline-none focus:border-[#ee4d2d] focus:ring-2 focus:ring-[#ee4d2d]/10 transition-all hover:border-[#ee4d2d]/30 cursor-pointer"
          >
            <option value="">Semua Toko</option>
            {allToko.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <span className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[10px] text-[#8a90a2]">
            ▼
          </span>
        </div>
      </div>
    </div>
  );
}
