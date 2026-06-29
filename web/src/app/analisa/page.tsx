import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";
import { getAnalisa, getJejakUpdate } from "@/lib/data";
import { getOptions, resolveFilter } from "@/lib/filters";
import { rp, rpShort, caption, tsWIB } from "@/lib/format";
import KpiCard from "@/components/KpiCard";
import FilterBar from "@/components/FilterBar";
import { ComboAnalisa } from "@/components/charts";
import ServerTable from "@/components/ServerTable";
import type { SCol } from "@/components/ServerTable";

export const dynamic = "force-dynamic";
type SP = Promise<Record<string, string | string[] | undefined>>;

const COLS: SCol[] = [
  { key: "toko", label: "Nama Toko", w: 120, sort: "toko" },
  { key: "kode", label: "Kode Produk", w: 110, sort: "kode" },
  { key: "produk", label: "Nama Produk", w: 240, sort: "produk" },
  { key: "skuInduk", label: "SKU Induk", w: 100, sort: "skuInduk" },
  { key: "roas", label: "ROAS Saat Ini", fmt: "ratio", sort: "roas" },
  // kolom disiapkan untuk fitur otomasi ROAS/budget (diisi menyusul)
  { key: "targetRoas", label: "Target ROAS", w: 100 },
  { key: "roasLama", label: "ROAS Lama", w: 100 },
  { key: "rekomRoas", label: "Rekomendasi ROAS", w: 140, edit: true },
  { key: "ratingIklan", label: "Rating Iklan", w: 110 },
  { key: "rekomBudget", label: "Rekomendasi Budget", fmt: "rp", w: 150 },
  { key: "budgetManual", label: "Budget Manual", w: 130, edit: true },
  { key: "budgetAkhir", label: "Budget Akhir", fmt: "rp", w: 130, computeMax: ["rekomBudget", "budgetManual"] },
];

export default async function Page({ searchParams }: { searchParams: SP }) {
  const options = await getOptions();
  const filter = resolveFilter(await searchParams, options, { g: "harian", win: 7 });
  const d = await getAnalisa(filter);
  const jejak = await getJejakUpdate();
  const t = d.total;
  const ft = { g: filter.periode, d: filter.a, s: filter.b, t: filter.toko.join(",") };

  // Verifikasi izin edit dari session cookie
  const cookieStore = await cookies();
  const token = cookieStore.get("dash_auth")?.value;
  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const user = token ? await verifySession(token, secret) : null;
  const canEdit = !!(user?.can_edit_ads || user?.role === "owner");

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto">
      <div className="mb-5">
        <h1 className="text-[22px] font-extrabold tracking-tight">📊 Analisa Penjualan vs Iklan</h1>
        <p className="text-[13px] text-[#8a90a2] mt-0.5">
          {caption(filter)} · {filter.toko.length ? `${filter.toko.length} toko` : "semua toko"}
        </p>
        <p className="text-[11px] text-[#b4b9c6] mt-1">
          🔄 Laporan terakhir: <span className="text-[#8a90a2] font-medium">{tsWIB(jejak.laporan)}</span>
          {"  ·  "}Analisa terakhir: <span className="text-[#8a90a2] font-medium">{tsWIB(jejak.analisa)}</span>
        </p>
      </div>

      <FilterBar options={options} filter={filter} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <KpiCard ikon="💰" label="Total Omzet" value={rpShort(t.omzet)} sub={rp(t.omzet)} color="#8a90a2" />
        <KpiCard ikon="💸" label="Total Biaya Iklan" value={rpShort(t.biaya)} sub={`ACOS ${t.acos.toFixed(1)}%`} tint="#fdeaf1" color="#ec407a" />
        <KpiCard ikon="💵" label="Omzet dari Iklan" value={rpShort(t.omzetIklan)} tint="#e7f7f4" color="#16b8a6" />
        <KpiCard ikon="📈" label="ROAS" value={t.roas.toFixed(2)} sub="omzet iklan ÷ biaya" tint="#eaf2fe" color="#42a5f5" />
      </div>

      <div className="card p-5 mb-7">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold text-[15px]">Omzet vs Biaya · ROAS · ACOS</h2>
          <span className="text-[12px] text-[#8a90a2]">batang = Rp · garis = ROAS/ACOS</span>
        </div>
        <ComboAnalisa data={d.trend.length === 1 ? d.perToko : d.trend} isShopComparison={d.trend.length === 1} />
      </div>

      <h2 className="text-[14px] font-bold mb-1">📋 Daftar Produk Diiklankan</h2>
      <p className="text-[12px] text-[#9aa0b2] mb-3">
        Klik judul kolom untuk urutkan · kolom Target/Rekomendasi/Budget disiapkan untuk fitur otomasi (diisi menyusul).
      </p>
      <ServerTable kind="iklan" filter={ft} columns={COLS} defaultSort="omzetIklan" pageSize={50} editKey={canEdit ? "analisa-setting" : undefined} />
    </div>
  );
}
