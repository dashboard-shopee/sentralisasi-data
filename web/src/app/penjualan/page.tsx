import { getCombined } from "@/lib/data";
import { getOptions, resolveFilter } from "@/lib/filters";
import { caption } from "@/lib/format";
import { VARS_JUAL } from "@/lib/variables";
import FilterBar from "@/components/FilterBar";
import MetricView from "@/components/MetricView";
import ServerTable from "@/components/ServerTable";
import type { SCol } from "@/components/ServerTable";

export const dynamic = "force-dynamic";
type SP = Promise<Record<string, string | string[] | undefined>>;

const COLS: SCol[] = [
  { key: "gambar", label: "Foto", w: 52 },
  { key: "kode", label: "Kode Produk", w: 110, sort: "kode" },
  { key: "skuInduk", label: "SKU Induk", w: 100, sort: "skuInduk" },
  { key: "produk", label: "Nama Produk", w: 240, sort: "produk" },
  { key: "toko", label: "Toko", w: 120, sort: "toko" },
  { key: "omzet", label: "Omzet", fmt: "rp", sort: "omzet" },
  { key: "pesanan", label: "Pesanan", fmt: "num", sort: "pesanan" },
  { key: "unit", label: "Unit Terjual", fmt: "num", sort: "unit" },
  { key: "pembeli", label: "Pembeli", fmt: "num", sort: "pembeli" },
  { key: "pengunjung", label: "Pengunjung", fmt: "num", sort: "pengunjung" },
  { key: "konversi", label: "Konversi %", fmt: "pct", sort: "konversi" },
  { key: "aov", label: "Omzet/Pesanan", fmt: "rp", sort: "aov" },
  { key: "keranjang", label: "Masuk Keranjang", fmt: "num", sort: "keranjang" },
];

export default async function Page({ searchParams }: { searchParams: SP }) {
  const options = await getOptions();
  const filter = resolveFilter(await searchParams, options, { g: "harian", win: 7 });
  const d = await getCombined(filter);
  const ft = { g: filter.periode, d: filter.a, s: filter.b, t: filter.toko.join(",") };

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto">
      <div className="mb-5">
        <h1 className="text-[22px] font-extrabold tracking-tight">📦 Penjualan & Pesanan</h1>
        <p className="text-[13px] text-[#8a90a2] mt-0.5">
          {caption(filter)} · {filter.toko.length ? `${filter.toko.length} toko` : "semua toko"}
        </p>
      </div>

      <FilterBar options={options} filter={filter} />

      <MetricView
        catalog={VARS_JUAL}
        kpi={d.kpi}
        trend={d.trend}
        perToko={d.perToko}
        storageKey="jual"
        defaultKpi={["omzet", "pesanan", "unit", "pembeli"]}
        defaultChart={["omzet", "pesanan"]}
      />

      <h2 className="text-[14px] font-bold mt-7 mb-1">📋 Daftar Produk</h2>
      <p className="text-[12px] text-[#9aa0b2] mb-3">Semua produk · klik judul kolom untuk urutkan · cari & pindah halaman.</p>
      <ServerTable kind="jual" filter={ft} columns={COLS} defaultSort="omzet" pageSize={50} downloadName="penjualan" />
    </div>
  );
}
