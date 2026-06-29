import { getIklanData } from "@/lib/data";
import { getOptions, resolveFilter } from "@/lib/filters";
import { caption } from "@/lib/format";
import { VARS_IKLAN } from "@/lib/variables";
import FilterBar from "@/components/FilterBar";
import MetricView from "@/components/MetricView";
import ServerTable from "@/components/ServerTable";
import type { SCol } from "@/components/ServerTable";

export const dynamic = "force-dynamic";
type SP = Promise<Record<string, string | string[] | undefined>>;

const COLS: SCol[] = [
  { key: "toko", label: "Nama Toko", w: 120, sort: "toko" },
  { key: "gambar", label: "Foto", w: 64 },
  { key: "produk", label: "Nama Produk", w: 180, sort: "produk" },
  { key: "kode", label: "Kode Produk", w: 110, sort: "kode" },
  { key: "skuInduk", label: "SKU", w: 90, sort: "skuInduk" },
  { key: "targetRoas", label: "Target ROAS", w: 100 },
  { key: "dilihat", label: "Dilihat", fmt: "num", sort: "dilihat" },
  { key: "klik", label: "Klik", fmt: "num", sort: "klik" },
  { key: "ctr", label: "CTR %", fmt: "pct", sort: "ctr" },
  { key: "cr", label: "CR %", fmt: "pct", sort: "cr" },
  { key: "cpc", label: "CPC", fmt: "rp", sort: "cpc" },
  { key: "konversi", label: "Konversi", fmt: "num", sort: "konversi" },
  { key: "omzetIklan", label: "Omzet Iklan", fmt: "rp", sort: "omzetIklan" },
  { key: "biayaIklan", label: "Biaya Iklan", fmt: "rp", sort: "biayaIklan" },
  { key: "roas", label: "ROAS", fmt: "ratio", sort: "roas" },
  // kolom disiapkan untuk fitur rekomendasi otomasi (diisi menyusul)
  { key: "ratingIklan", label: "Rating Iklan", w: 110 },
  { key: "rekomRoas", label: "Rekomendasi ROAS", w: 140 },
  { key: "rekomBudget", label: "Rekomendasi Budget", w: 150 },
  { key: "ketRating", label: "Keterangan Rating", w: 130 },
  { key: "ketRoas", label: "Keterangan ROAS", w: 130 },
  { key: "ketBudget", label: "Keterangan Budget", w: 130 },
  { key: "action", label: "Action", w: 150 },
];

export default async function Page({ searchParams }: { searchParams: SP }) {
  const options = await getOptions();
  const filter = resolveFilter(await searchParams, options, { g: "harian", win: 7 });
  const d = await getIklanData(filter);
  const ft = { g: filter.periode, d: filter.a, s: filter.b, t: filter.toko.join(",") };

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto">
      <div className="mb-5">
        <h1 className="text-[22px] font-extrabold tracking-tight">📢 Performa Iklan</h1>
        <p className="text-[13px] text-[#8a90a2] mt-0.5">
          {caption(filter)} · {filter.toko.length ? `${filter.toko.length} toko` : "semua toko"}
        </p>
      </div>

      <FilterBar options={options} filter={filter} />

      <MetricView
        catalog={VARS_IKLAN}
        kpi={d.kpi}
        trend={d.trend}
        perToko={d.perToko}
        storageKey="iklan"
        defaultKpi={["omzetIklan", "biayaIklan", "roas", "konversi"]}
        defaultChart={["omzetIklan", "biayaIklan", "roas"]}
      />

      <h2 className="text-[14px] font-bold mt-7 mb-1">📋 Semua Produk Diiklankan</h2>
      <p className="text-[12px] text-[#9aa0b2] mb-3">
        Klik judul kolom untuk urutkan · kolom Rating & Rekomendasi disiapkan untuk fitur otomasi (diisi menyusul).
      </p>
      <ServerTable kind="iklan" filter={ft} columns={COLS} defaultSort="omzetIklan" pageSize={50} downloadName="iklan" trendKind="iklan" />
    </div>
  );
}
