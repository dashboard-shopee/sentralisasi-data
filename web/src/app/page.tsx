import { getOverview, getAnalisa } from "@/lib/data";
import { getOptions, resolveFilter } from "@/lib/filters";
import { rp, rpShort, num, numShort, caption } from "@/lib/format";
import KpiCard from "@/components/KpiCard";
import { FlexChart, DonutToko, BarTokoDuo, PALETTE } from "@/components/charts";

export const dynamic = "force-dynamic";

export default async function Home() {
  const options = await getOptions();
  // Ringkasan = TETAP 7 hari terakhir, semua toko (tanpa pengaturan)
  const filter = resolveFilter({}, options, { g: "harian", win: 7 });
  filter.toko = [];
  const d = await getOverview(filter);
  const an = await getAnalisa(filter);
  const k = d.kpi;
  const totalToko = d.perToko.reduce((a, b) => a + b.omzet, 0) || 1;

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto">
      <div className="mb-5">
        <h1 className="text-[22px] font-extrabold tracking-tight">Ringkasan Toko 👋</h1>
        <p className="text-[13px] text-[#8a90a2] mt-0.5">7 hari terakhir ({caption(filter)}) · semua toko</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
        <KpiCard ikon="💰" label="Omzet" value={rpShort(k.omzet)} sub={rp(k.omzet)} color="#8a90a2" />
        <KpiCard ikon="🛒" label="Pesanan" value={numShort(k.pesanan)} sub={`${num(k.unit)} unit`} tint="#e7f7f4" color="#16b8a6" />
        <KpiCard ikon="💸" label="Biaya Iklan" value={rpShort(an.total.biaya)} sub={`ACOS ${an.total.acos.toFixed(1)}%`} tint="#fdeaf1" color="#ec407a" />
        <KpiCard ikon="📈" label="ROAS Iklan" value={an.total.roas.toFixed(2)} sub={`omzet iklan ${rpShort(an.total.omzetIklan)}`} tint="#eaf2fe" color="#42a5f5" />
      </div>

      <div className="card p-5 mb-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold text-[15px]">Tren Omzet, Biaya Iklan & ACOS</h2>
          <span className="text-[12px] text-[#8a90a2]">harian</span>
        </div>
        <FlexChart
          data={an.trend}
          series={[
            { key: "omzet", label: "Omzet", fmt: "rp", ikon: "💰" },
            { key: "biaya", label: "Biaya Iklan", fmt: "rp", ikon: "💸" },
            { key: "acos", label: "ACOS %", fmt: "pct", ikon: "📊" },
          ]}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-5">
        <div className="card p-5 lg:col-span-2">
          <h2 className="font-bold text-[15px] mb-2">Pesanan & Omzet per Toko</h2>
          <BarTokoDuo data={d.perToko} />
        </div>
        <div className="card p-5">
          <h2 className="font-bold text-[15px] mb-2">Komposisi Omzet</h2>
          <DonutToko data={d.perToko} />
          <div className="mt-2 space-y-1.5">
            {d.perToko.slice(0, 5).map((t, i) => (
              <div key={t.toko} className="flex items-center justify-between text-[12px] min-w-0">
                <span className="flex items-center gap-2 text-[#6b7180] truncate min-w-0">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: PALETTE[i % PALETTE.length] }} />
                  <span className="truncate" title={t.toko}>{t.toko}</span>
                </span>
                <span className="font-semibold shrink-0">{((t.omzet / totalToko) * 100).toFixed(0)}%</span>
              </div>
            ))}

          </div>
        </div>
      </div>

      <div className="card p-5">
        <h2 className="font-bold text-[15px] mb-3">Produk Terlaris</h2>
        <div className="grid md:grid-cols-2 gap-x-8 gap-y-2.5">
          {d.top.map((p, i) => (
            <div key={i} className="flex items-center gap-3 min-w-0 w-full">
              <div className="w-7 h-7 rounded-lg grid place-items-center text-[12px] font-bold shrink-0" style={{ background: "#fff1ed", color: "#ee4d2d" }}>{i + 1}</div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-medium truncate" title={p.produk}>{p.produk}</div>
                <div className="text-[11px] text-[#9aa0b2] truncate" title={`${p.toko} · ${num(p.pesanan)} pesanan · ${num(p.unit)} pcs`}>
                  {p.toko} · {num(p.pesanan)} pesanan · {num(p.unit)} pcs
                </div>
              </div>
              <div className="text-[13px] font-bold shrink-0">{rpShort(p.omzet)}</div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
