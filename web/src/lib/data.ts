import { q } from "./db";
import type { Filter } from "./filters";
import { labelPeriode, labelHari, n } from "./format";

// Jejak "terakhir diperbarui": laporan & analisa dari siklus_log (kapan trigger jalan),
// purchase data dari erp_sku_list.diperbarui_pada (data real). Aman-gagal -> null.
export async function getJejakUpdate() {
  const out: { laporan: string | null; analisa: string | null; purchase: string | null } = {
    laporan: null, analisa: null, purchase: null,
  };
  try {
    const rows = await q<{ pemicu: string; waktu: string }>(
      `select distinct on (pemicu) pemicu, waktu
         from siklus_log where program='iklan' and pemicu in ('laporan','analisa')
        order by pemicu, waktu desc`
    );
    for (const r of rows) {
      if (r.pemicu === "laporan") out.laporan = r.waktu;
      else if (r.pemicu === "analisa") out.analisa = r.waktu;
    }
  } catch {}
  try {
    const e = await q<{ mx: string | null }>(`select max(diperbarui_pada) as mx from erp_sku_list`);
    out.purchase = e[0]?.mx ?? null;
  } catch {}
  return out;
}

// Bangun kondisi WHERE bersama (periode + rentang + toko). params di-isi sekali, dipakai semua query.
function build(f: Filter) {
  const params: unknown[] = [f.periode, f.a, f.b];
  let tc = "";
  if (f.toko.length) {
    params.push(f.toko);
    tc = ` and t.nama = any($${params.length})`;
  }
  const W = `f.periode=$1 and f.periode_mulai between $2 and $3${tc}`;
  return { params, W };
}

// ── PENJUALAN (Ringkasan / Penjualan) ─────────────────────────────
export async function getOverview(f: Filter) {
  const { params, W } = build(f);
  const k = (
    await q<Record<string, number>>(
      `select coalesce(sum(f.penjualan),0)::float omzet, coalesce(sum(f.unit_pesanan),0)::float unit,
              coalesce(sum(f.pesanan),0)::float pesanan, coalesce(sum(f.pengunjung),0)::float pengunjung,
              count(distinct f.produk_id)::int produk
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W}`,
      params
    )
  )[0];
  const trend = (
    await q<{ waktu: Date; omzet: number; pesanan: number }>(
      `select f.periode_mulai waktu, sum(f.penjualan)::float omzet, sum(f.pesanan)::float pesanan
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W}
       group by f.periode_mulai order by f.periode_mulai`,
      params
    )
  ).map((r) => ({ label: labelPeriode(f.periode, r.waktu), omzet: n(r.omzet), pesanan: n(r.pesanan) }));
  const perToko = (
    await q<{ toko: string; omzet: number; pesanan: number }>(
      `select t.nama toko, sum(f.penjualan)::float omzet, sum(f.pesanan)::float pesanan
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W}
       group by t.nama order by omzet desc nulls last`,
      params
    )
  ).map((r) => ({ toko: r.toko, omzet: n(r.omzet), pesanan: n(r.pesanan) }));
  const top = (
    await q<{ produk: string; toko: string; omzet: number; unit: number; pesanan: number }>(
      `select dp.nama_produk produk, t.nama toko, sum(f.penjualan)::float omzet,
              sum(f.unit_pesanan)::int unit, sum(f.pesanan)::int pesanan
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
       where ${W} group by dp.nama_produk, t.nama order by omzet desc nulls last limit 8`,
      params
    )
  ).map((r) => ({ produk: r.produk, toko: r.toko, omzet: n(r.omzet), unit: n(r.unit), pesanan: n(r.pesanan) }));

  const omzet = n(k.omzet);
  return {
    kpi: {
      omzet,
      unit: n(k.unit),
      pesanan: n(k.pesanan),
      pengunjung: n(k.pengunjung),
      produk: n(k.produk),
      konversi: k.pengunjung ? (n(k.unit) / n(k.pengunjung)) * 100 : 0,
    },
    trend,
    perToko,
    top,
  };
}

// ── ANALISA (penjualan vs iklan) ──────────────────────────────────
export async function getAnalisa(f: Filter) {
  const { params, W } = build(f);
  const rows = await q<{ waktu: Date; omzet: number; biaya: number; oik: number }>(
    `select p.pm waktu, p.omzet, coalesce(i.biaya,0)::float biaya, coalesce(i.oik,0)::float oik
     from (select f.periode_mulai pm, sum(f.penjualan)::float omzet
           from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by f.periode_mulai) p
     left join (select f.periode_mulai pm, sum(f.biaya_iklan)::float biaya, sum(f.omzet_iklan)::float oik
                from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by f.periode_mulai) i
       on i.pm = p.pm order by p.pm`,
    params
  );
  const trend = rows.map((r) => ({
    label: labelPeriode(f.periode, r.waktu),
    omzet: n(r.omzet),
    biaya: n(r.biaya),
    omzetIklan: n(r.oik),
    roas: r.biaya ? n(r.oik) / n(r.biaya) : 0,
    acos: r.omzet ? (n(r.biaya) / n(r.omzet)) * 100 : 0,
  }));
  const t = rows.reduce(
    (a, r) => ({ omzet: a.omzet + n(r.omzet), biaya: a.biaya + n(r.biaya), oik: a.oik + n(r.oik) }),
    { omzet: 0, biaya: 0, oik: 0 }
  );
  const perToko = (await q<{ toko: string; omzet: number; biaya: number; oik: number }>(
    `select coalesce(p.toko, i.toko) toko, coalesce(p.omzet,0)::float omzet, coalesce(i.biaya,0)::float biaya, coalesce(i.oik,0)::float oik
     from (select t.nama toko, sum(f.penjualan)::float omzet
           from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by t.nama) p
     full outer join (select t.nama toko, sum(f.biaya_iklan)::float biaya, sum(f.omzet_iklan)::float oik
                      from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by t.nama) i
       on i.toko = p.toko order by omzet desc nulls last`,
    params
  )).map((r) => ({
    label: r.toko,
    toko: r.toko,
    omzet: n(r.omzet),
    biaya: n(r.biaya),
    omzetIklan: n(r.oik),
    roas: r.biaya ? n(r.oik) / n(r.biaya) : 0,
    acos: r.omzet ? (n(r.biaya) / n(r.omzet)) * 100 : 0,
  }));
  return {
    trend,
    perToko,
    total: {
      omzet: t.omzet,
      biaya: t.biaya,
      omzetIklan: t.oik,
      roas: t.biaya ? t.oik / t.biaya : 0,
      acos: t.omzet ? (t.biaya / t.omzet) * 100 : 0,
    },
  };
}

// ── IKLAN ─────────────────────────────────────────────────────────
export async function getIklan(f: Filter) {
  const { params, W } = build(f);
  const k = (
    await q<Record<string, number>>(
      `select coalesce(sum(f.biaya_iklan),0)::float biaya, coalesce(sum(f.omzet_iklan),0)::float omzet,
              coalesce(sum(f.dilihat),0)::float dilihat, coalesce(sum(f.klik),0)::float klik,
              coalesce(sum(f.konversi),0)::float konversi
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W}`,
      params
    )
  )[0];
  const perToko = (
    await q<{ toko: string; biaya: number; omzet: number; roas: number }>(
      `select t.nama toko, sum(f.biaya_iklan)::float biaya, sum(f.omzet_iklan)::float omzet,
              (case when sum(f.biaya_iklan)>0 then sum(f.omzet_iklan)/sum(f.biaya_iklan) else 0 end)::float roas
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W}
       group by t.nama order by biaya desc nulls last`,
      params
    )
  ).map((r) => ({ toko: r.toko, biaya: n(r.biaya), omzet: n(r.omzet), roas: n(r.roas) }));
  const produk = (
    await q<{ produk: string; toko: string; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number; roas: number }>(
      `select dp.nama_produk produk, t.nama toko, sum(f.dilihat)::int dilihat, sum(f.klik)::int klik,
              sum(f.konversi)::int konversi, sum(f.omzet_iklan)::float omzet, sum(f.biaya_iklan)::float biaya,
              (case when sum(f.biaya_iklan)>0 then sum(f.omzet_iklan)/sum(f.biaya_iklan) else 0 end)::float roas
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
       where ${W} group by dp.nama_produk, t.nama order by biaya desc nulls last limit 40`,
      params
    )
  ).map((r) => ({ produk: r.produk, toko: r.toko, dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya), roas: n(r.roas) }));
  const biaya = n(k.biaya), omzet = n(k.omzet);
  return {
    kpi: { biaya, omzet, dilihat: n(k.dilihat), klik: n(k.klik), konversi: n(k.konversi), roas: biaya ? omzet / biaya : 0, ctr: k.dilihat ? (n(k.klik) / n(k.dilihat)) * 100 : 0 },
    perToko,
    produk,
  };
}

// ── PESANAN (per toko dari fact_pesanan + per produk dari fact_penjualan) ──
export async function getPesanan(f: Filter) {
  const { params, W } = build(f);
  const perToko = (
    await q<{ toko: string; pesanan: number; batal: number; omzet: number }>(
      `select t.nama toko, coalesce(sum(f.jumlah_pesanan),0)::int pesanan,
              coalesce(sum(f.pesanan_batal),0)::int batal, coalesce(sum(f.omzet_pesanan),0)::float omzet
       from fact_pesanan f join dim_toko t on t.toko_id=f.toko_id where ${W}
       group by t.nama order by pesanan desc nulls last`,
      params
    )
  ).map((r) => ({ toko: r.toko, pesanan: n(r.pesanan), batal: n(r.batal), omzet: n(r.omzet) }));
  const produk = (
    await q<{ produk: string; toko: string; pesanan: number; unit: number; omzet: number }>(
      `select dp.nama_produk produk, t.nama toko, sum(f.pesanan)::int pesanan,
              sum(f.unit_pesanan)::int unit, sum(f.penjualan)::float omzet
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
       where ${W} and f.pesanan is not null group by dp.nama_produk, t.nama order by sum(f.pesanan) desc nulls last limit 20`,
      params
    )
  ).map((r) => ({ produk: r.produk, toko: r.toko, pesanan: n(r.pesanan), unit: n(r.unit), omzet: n(r.omzet) }));
  return { perToko, produk };
}

// ── GABUNGAN Penjualan + Pesanan (KPI/grafik custom + tabel produk) ──
export async function getCombined(f: Filter) {
  const { params, W } = build(f);
  const pk = (
    await q<Record<string, number>>(
      `select coalesce(sum(penjualan),0)::float omzet, coalesce(sum(pesanan),0)::float pesanan,
              coalesce(sum(unit_pesanan),0)::float unit, coalesce(sum(pembeli),0)::float pembeli,
              coalesce(sum(pengunjung),0)::float pengunjung, coalesce(sum(keranjang),0)::float keranjang
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W}`,
      params
    )
  )[0];
  const ok = (
    await q<Record<string, number>>(
      `select coalesce(sum(omzet_pesanan),0)::float op, coalesce(sum(pesanan_batal),0)::float batal
       from fact_pesanan f join dim_toko t on t.toko_id=f.toko_id where ${W}`,
      params
    )
  )[0];
  const kpi: Record<string, number> = {
    omzet: n(pk.omzet), pesanan: n(pk.pesanan), unit: n(pk.unit), pembeli: n(pk.pembeli),
    pengunjung: n(pk.pengunjung), keranjang: n(pk.keranjang),
    omzetPesanan: n(ok.op), pesananBatal: n(ok.batal),
    konversi: pk.pengunjung ? (n(pk.pesanan) / n(pk.pengunjung)) * 100 : 0,
    aov: pk.pesanan ? n(pk.omzet) / n(pk.pesanan) : 0,
  };

  const tp = await q<{ w: Date; omzet: number; pesanan: number; unit: number; pembeli: number; pengunjung: number; keranjang: number }>(
    `select periode_mulai w, sum(penjualan)::float omzet, sum(pesanan)::float pesanan, sum(unit_pesanan)::float unit,
            sum(pembeli)::float pembeli, sum(pengunjung)::float pengunjung, sum(keranjang)::float keranjang
     from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by periode_mulai`,
    params
  );
  const to = await q<{ w: Date; op: number; batal: number }>(
    `select periode_mulai w, coalesce(sum(omzet_pesanan),0)::float op, coalesce(sum(pesanan_batal),0)::float batal
     from fact_pesanan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by periode_mulai`,
    params
  );
  const m = new Map<string, Record<string, number | string>>();
  for (const r of tp) {
    m.set(r.w.toISOString(), {
      label: labelPeriode(f.periode, r.w), omzet: n(r.omzet), pesanan: n(r.pesanan), unit: n(r.unit),
      pembeli: n(r.pembeli), pengunjung: n(r.pengunjung), keranjang: n(r.keranjang), omzetPesanan: 0, pesananBatal: 0,
    });
  }
  for (const r of to) {
    const k = r.w.toISOString();
    const e = m.get(k) ?? { label: labelPeriode(f.periode, r.w), omzet: 0, pesanan: 0, unit: 0, pembeli: 0, pengunjung: 0, keranjang: 0, omzetPesanan: 0, pesananBatal: 0 };
    e.omzetPesanan = n(r.op); e.pesananBatal = n(r.batal); m.set(k, e);
  }
  const trend = [...m.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([, v]) => {
    v.konversi = (v.pengunjung as number) ? ((v.pesanan as number) / (v.pengunjung as number)) * 100 : 0;
    v.aov = (v.pesanan as number) ? (v.omzet as number) / (v.pesanan as number) : 0;
    return v;
  });

  const pr = await q<{ kode: string; sku: string | null; sku_induk: string | null; produk: string; toko: string; omzet: number; pesanan: number; unit: number; pembeli: number; pengunjung: number; keranjang: number }>(
    `select dp.produk_id kode, dp.sku, dp.sku_induk, dp.nama_produk produk, t.nama toko,
            sum(f.penjualan)::float omzet, sum(f.pesanan)::int pesanan, sum(f.unit_pesanan)::int unit,
            sum(f.pembeli)::int pembeli, sum(f.pengunjung)::int pengunjung, sum(f.keranjang)::int keranjang
     from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
     where ${W} group by dp.produk_id, dp.sku, dp.sku_induk, dp.nama_produk, t.nama
     order by omzet desc nulls last limit 20`,
    params
  );
  const produk = pr.map((r) => ({
    kode: String(r.kode), sku: r.sku ?? "", skuInduk: r.sku_induk ?? "", produk: r.produk, toko: r.toko,
    omzet: n(r.omzet), pesanan: n(r.pesanan), unit: n(r.unit), pembeli: n(r.pembeli),
    pengunjung: n(r.pengunjung), keranjang: n(r.keranjang),
    konversi: r.pengunjung ? (n(r.unit) / n(r.pengunjung)) * 100 : 0,
    aov: r.pesanan ? n(r.omzet) / n(r.pesanan) : 0,
  }));
  const tpToko = await q<{ toko: string; omzet: number; pesanan: number; unit: number; pembeli: number; pengunjung: number; keranjang: number }>(
    `select t.nama toko, sum(penjualan)::float omzet, sum(pesanan)::float pesanan, sum(unit_pesanan)::float unit,
            sum(pembeli)::float pembeli, sum(pengunjung)::float pengunjung, sum(keranjang)::float keranjang
     from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by t.nama`,
    params
  );
  const toToko = await q<{ toko: string; op: number; batal: number }>(
    `select t.nama toko, coalesce(sum(omzet_pesanan),0)::float op, coalesce(sum(pesanan_batal),0)::float batal
     from fact_pesanan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by t.nama`,
    params
  );
  const mToko = new Map<string, Record<string, number | string>>();
  for (const r of tpToko) {
    mToko.set(r.toko, {
      toko: r.toko, omzet: n(r.omzet), pesanan: n(r.pesanan), unit: n(r.unit),
      pembeli: n(r.pembeli), pengunjung: n(r.pengunjung), keranjang: n(r.keranjang), omzetPesanan: 0, pesananBatal: 0,
    });
  }
  for (const r of toToko) {
    const k = r.toko;
    const e = mToko.get(k) ?? { toko: r.toko, omzet: 0, pesanan: 0, unit: 0, pembeli: 0, pengunjung: 0, keranjang: 0, omzetPesanan: 0, pesananBatal: 0 };
    e.omzetPesanan = n(r.op); e.pesananBatal = n(r.batal); mToko.set(k, e);
  }
  const perToko = [...mToko.values()].sort((a, b) => ((b.omzet as number) - (a.omzet as number))).map(v => {
    v.konversi = (v.pengunjung as number) ? ((v.pesanan as number) / (v.pengunjung as number)) * 100 : 0;
    v.aov = (v.pesanan as number) ? (v.omzet as number) / (v.pesanan as number) : 0;
    return v;
  });

  return { kpi, trend, perToko, produk };
}

// ── IKLAN (KPI/grafik custom + tabel produk + kolom rekomendasi disiapkan) ──
function deriveIklan(d: { dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }) {
  return {
    dilihat: d.dilihat, klik: d.klik, konversi: d.konversi, omzetIklan: d.omzet, biayaIklan: d.biaya,
    ctr: d.dilihat ? (d.klik / d.dilihat) * 100 : 0,
    cr: d.klik ? (d.konversi / d.klik) * 100 : 0,
    cpc: d.klik ? d.biaya / d.klik : 0,
    roas: d.biaya ? d.omzet / d.biaya : 0,
  };
}
export async function getIklanData(f: Filter) {
  const { params, W } = build(f);
  const ik = (
    await q<Record<string, number>>(
      `select coalesce(sum(dilihat),0)::float dilihat, coalesce(sum(klik),0)::float klik,
              coalesce(sum(konversi),0)::float konversi, coalesce(sum(omzet_iklan),0)::float omzet,
              coalesce(sum(biaya_iklan),0)::float biaya
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W}`,
      params
    )
  )[0];
  const kpi = deriveIklan({ dilihat: n(ik.dilihat), klik: n(ik.klik), konversi: n(ik.konversi), omzet: n(ik.omzet), biaya: n(ik.biaya) });

  const tt = await q<{ w: Date; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }>(
    `select periode_mulai w, coalesce(sum(dilihat),0)::float dilihat, coalesce(sum(klik),0)::float klik,
            coalesce(sum(konversi),0)::float konversi, coalesce(sum(omzet_iklan),0)::float omzet,
            coalesce(sum(biaya_iklan),0)::float biaya
     from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by periode_mulai order by periode_mulai`,
    params
  );
  const trend = tt.map((r) => ({
    label: labelPeriode(f.periode, r.w),
    ...deriveIklan({ dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya) }),
  }));

  const pr = await q<{ kode: string; sku: string | null; toko: string; produk: string; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }>(
    `select dp.produk_id kode, dp.sku, t.nama toko, dp.nama_produk produk,
            sum(f.dilihat)::float dilihat, sum(f.klik)::float klik, sum(f.konversi)::float konversi,
            sum(f.omzet_iklan)::float omzet, sum(f.biaya_iklan)::float biaya
     from fact_iklan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
     where ${W} group by dp.produk_id, dp.sku, t.nama, dp.nama_produk order by biaya desc nulls last limit 50`,
    params
  );
  const produk = pr.map((r) => ({
    kode: String(r.kode), sku: r.sku ?? "", toko: r.toko, produk: r.produk, targetRoas: "",
    ...deriveIklan({ dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya) }),
  }));
  const ttToko = await q<{ toko: string; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }>(
    `select t.nama toko, coalesce(sum(dilihat),0)::float dilihat, coalesce(sum(klik),0)::float klik,
            coalesce(sum(konversi),0)::float konversi, coalesce(sum(omzet_iklan),0)::float omzet,
            coalesce(sum(biaya_iklan),0)::float biaya
     from fact_iklan f join dim_toko t on t.toko_id=f.toko_id where ${W} group by t.nama order by omzet desc nulls last`,
    params
  );
  const perToko = ttToko.map((r) => ({
    toko: r.toko,
    ...deriveIklan({ dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya) }),
  }));

  return { kpi, trend, perToko, produk };
}

// ── TABEL PRODUK server-side: pagination + sort + search (skala 20rb+) ──
export type TableOpts = { page: number; size: number; sort: string; dir: string; q: string; all?: boolean };

const SORT_JUAL: Record<string, string> = {
  kode: "dp.produk_id", produk: "dp.nama_produk", toko: "t.nama", skuInduk: "dp.sku_induk",
  omzet: "sum(f.penjualan)", pesanan: "sum(f.pesanan)", unit: "sum(f.unit_pesanan)",
  pembeli: "sum(f.pembeli)", pengunjung: "sum(f.pengunjung)", keranjang: "sum(f.keranjang)",
  konversi: "case when sum(f.pengunjung)>0 then sum(f.pesanan)::float/sum(f.pengunjung) else 0 end",
  aov: "case when sum(f.pesanan)>0 then sum(f.penjualan)/sum(f.pesanan) else 0 end",
};
const SORT_IKLAN: Record<string, string> = {
  kode: "dp.produk_id", produk: "dp.nama_produk", toko: "t.nama", skuInduk: "dp.sku_induk",
  dilihat: "sum(f.dilihat)", klik: "sum(f.klik)", konversi: "sum(f.konversi)",
  omzetIklan: "sum(f.omzet_iklan)", biayaIklan: "sum(f.biaya_iklan)",
  roas: "case when sum(f.biaya_iklan)>0 then sum(f.omzet_iklan)/sum(f.biaya_iklan) else 0 end",
  ctr: "case when sum(f.dilihat)>0 then sum(f.klik)::float/sum(f.dilihat) else 0 end",
  cr: "case when sum(f.klik)>0 then sum(f.konversi)::float/sum(f.klik) else 0 end",
  cpc: "case when sum(f.klik)>0 then sum(f.biaya_iklan)/sum(f.klik) else 0 end",
};

function paging(o: TableOpts) {
  const dir = o.dir === "asc" ? "asc" : "desc";
  const lim = o.all ? 100000 : Math.min(200, Math.max(1, o.size || 50));
  const off = o.all ? 0 : (Math.max(1, o.page) - 1) * lim;
  return { dir, lim, off };
}

export async function getProdukJual(f: Filter, o: TableOpts) {
  if (!f.a || !f.b) return { total: 0, rows: [] as Record<string, unknown>[] };
  const { params, W } = build(f);
  let where = W;
  const qq = o.q.trim();
  if (qq) {
    params.push("%" + qq + "%"); const a = params.length;
    params.push(qq + "%"); const b = params.length;
    where += ` and (dp.nama_produk ilike $${a} or dp.sku_induk ilike $${a} or dp.produk_id::text like $${b})`;
  }
  const sortExpr = SORT_JUAL[o.sort] ?? SORT_JUAL.omzet;
  const { dir, lim, off } = paging(o);
  const total = n(
    (await q<{ c: number }>(
      `select count(*)::int c from (select dp.produk_id from fact_penjualan f
        join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
        where ${where} group by dp.produk_id) z`,
      params
    ))[0]?.c
  );
  const rows = await q<Record<string, unknown>>(
    `select dp.produk_id kode, dp.sku_induk "skuInduk", dp.nama_produk produk, dp.gambar, t.nama toko,
       sum(f.penjualan)::float omzet, sum(f.pesanan)::int pesanan, sum(f.unit_pesanan)::int unit,
       sum(f.pembeli)::int pembeli, sum(f.pengunjung)::int pengunjung, sum(f.keranjang)::int keranjang,
       (case when sum(f.pengunjung)>0 then sum(f.pesanan)::float/sum(f.pengunjung)*100 else 0 end) konversi,
       (case when sum(f.pesanan)>0 then sum(f.penjualan)/sum(f.pesanan) else 0 end) aov
     from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
     where ${where} group by dp.produk_id, dp.sku_induk, dp.nama_produk, dp.gambar, t.nama
     order by ${sortExpr} ${dir} nulls last limit ${lim} offset ${off}`,
    params
  );
  return {
    total,
    rows: rows.map((r) => ({
      kode: String(r.kode), skuInduk: r.skuInduk ?? "", produk: r.produk, gambar: r.gambar ?? null, toko: r.toko,
      omzet: n(r.omzet), pesanan: n(r.pesanan), unit: n(r.unit), pembeli: n(r.pembeli),
      pengunjung: n(r.pengunjung), keranjang: n(r.keranjang), konversi: n(r.konversi), aov: n(r.aov),
    })),
  };
}

export async function getProdukIklan(f: Filter, o: TableOpts) {
  if (!f.a || !f.b) return { total: 0, rows: [] as Record<string, unknown>[] };
  const { params, W } = build(f);
  let where = W;
  const qq = o.q.trim();
  if (qq) {
    params.push("%" + qq + "%"); const a = params.length;
    params.push(qq + "%"); const b = params.length;
    where += ` and (dp.nama_produk ilike $${a} or dp.sku_induk ilike $${a} or dp.produk_id::text like $${b})`;
  }
  const sortExpr = SORT_IKLAN[o.sort] ?? SORT_IKLAN.omzetIklan;
  const { dir, lim, off } = paging(o);
  const total = n(
    (await q<{ c: number }>(
      `select count(*)::int c from (select dp.produk_id from fact_iklan f
        join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
        where ${where} group by dp.produk_id) z`,
      params
    ))[0]?.c
  );
  const rows = await q<Record<string, unknown>>(
    `select dp.produk_id kode, dp.sku_induk "skuInduk", t.nama toko, dp.nama_produk produk, dp.gambar,
       sum(f.dilihat)::int dilihat, sum(f.klik)::int klik, sum(f.konversi)::int konversi,
       sum(f.omzet_iklan)::float "omzetIklan", sum(f.biaya_iklan)::float "biayaIklan",
       (case when sum(f.dilihat)>0 then sum(f.klik)::float/sum(f.dilihat)*100 else 0 end) ctr,
       (case when sum(f.klik)>0 then sum(f.konversi)::float/sum(f.klik)*100 else 0 end) cr,
       (case when sum(f.klik)>0 then sum(f.biaya_iklan)/sum(f.klik) else 0 end) cpc,
       (case when sum(f.biaya_iklan)>0 then sum(f.omzet_iklan)/sum(f.biaya_iklan) else 0 end) roas,
       max(s.target_roas)::float "targetRoas", max(s.roas_lama)::float "roasLama",
       max(s.rekom_roas)::float "rekomRoas", max(s.rekom_budget)::float "rekomBudget",
       max(s.budget_manual)::float "budgetManual", max(s.rating_iklan) "ratingIklan",
       max(s.ket_rating) "ketRating", max(s.ket_roas) "ketRoas", max(s.ket_budget) "ketBudget",
       max(s.action) "action"
     from fact_iklan f join dim_toko t on t.toko_id=f.toko_id join dim_produk dp on dp.produk_id=f.produk_id
     left join iklan_setting s on s.produk_id=dp.produk_id
     where ${where} group by dp.produk_id, dp.sku_induk, t.nama, dp.nama_produk, dp.gambar
     order by ${sortExpr} ${dir} nulls last limit ${lim} offset ${off}`,
    params
  );
  // setting bisa null (produk belum ada di iklan_setting) -> kirim "" supaya tabel tampil "—", bukan 0
  const v = (x: unknown) => (x === null || x === undefined ? "" : x);
  return {
    total,
    rows: rows.map((r) => ({
      kode: String(r.kode), skuInduk: r.skuInduk ?? "", toko: r.toko, produk: r.produk, gambar: r.gambar ?? null,
      dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi),
      omzetIklan: n(r.omzetIklan), biayaIklan: n(r.biayaIklan),
      ctr: n(r.ctr), cr: n(r.cr), cpc: n(r.cpc), roas: n(r.roas),
      targetRoas: v(r.targetRoas), roasLama: v(r.roasLama), rekomRoas: v(r.rekomRoas),
      rekomBudget: v(r.rekomBudget), budgetManual: v(r.budgetManual), ratingIklan: v(r.ratingIklan),
      ketRating: v(r.ketRating), ketRoas: v(r.ketRoas), ketBudget: v(r.ketBudget), action: v(r.action),
    })),
  };
}

export async function getProdukTrend(kode: string, kind: "jual" | "iklan" | "analisa", f: Filter) {
  const { params, W } = build(f);
  params.push(Number(kode));
  const pidParam = `$${params.length}`;
  
  if (kind === "iklan") {
    const rows = await q<{ w: Date; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }>(
      `select f.periode_mulai w, coalesce(sum(f.dilihat),0)::float dilihat, coalesce(sum(f.klik),0)::float klik,
              coalesce(sum(f.konversi),0)::float konversi, coalesce(sum(f.omzet_iklan),0)::float omzet,
              coalesce(sum(f.biaya_iklan),0)::float biaya
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id
       where ${W} and f.produk_id = ${pidParam}
       group by f.periode_mulai order by f.periode_mulai`,
      params
    );
    return rows.map((r) => ({
      label: labelPeriode(f.periode, r.w),
      ...deriveIklan({ dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya) }),
    }));
  } else if (kind === "analisa") {
    const rows = await q<{ pm: Date; omzet: number; biaya: number; oik: number }>(
      `select p.pm, p.omzet, coalesce(i.biaya,0)::float biaya, coalesce(i.oik,0)::float oik
       from (select f.periode_mulai pm, sum(f.penjualan)::float omzet
             from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
             where ${W} and f.produk_id = ${pidParam} group by f.periode_mulai) p
       left join (select f.periode_mulai pm, sum(f.biaya_iklan)::float biaya, sum(f.omzet_iklan)::float oik
                  from fact_iklan f join dim_toko t on t.toko_id=f.toko_id
                  where ${W} and f.produk_id = ${pidParam} group by f.periode_mulai) i
         on i.pm = p.pm order by p.pm`,
      params
    );
    return rows.map((r) => ({
      label: labelPeriode(f.periode, r.pm),
      omzet: n(r.omzet),
      biaya: n(r.biaya),
      omzetIklan: n(r.oik),
      roas: r.biaya ? n(r.oik) / n(r.biaya) : 0,
      acos: r.omzet ? (n(r.biaya) / n(r.omzet)) * 100 : 0,
    }));
  } else {
    // kind === "jual"
    const rows = await q<{ w: Date; omzet: number; pesanan: number; unit: number; pembeli: number; pengunjung: number; keranjang: number }>(
      `select f.periode_mulai w, coalesce(sum(f.penjualan),0)::float omzet, coalesce(sum(f.pesanan),0)::float pesanan,
              coalesce(sum(f.unit_pesanan),0)::float unit, coalesce(sum(f.pembeli),0)::float pembeli,
              coalesce(sum(f.pengunjung),0)::float pengunjung, coalesce(sum(f.keranjang),0)::float keranjang
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
       where ${W} and f.produk_id = ${pidParam}
       group by f.periode_mulai order by f.periode_mulai`,
      params
    );
    return rows.map((r) => ({
      label: labelPeriode(f.periode, r.w),
      omzet: n(r.omzet),
      pesanan: n(r.pesanan),
      unit: n(r.unit),
      pembeli: n(r.pembeli),
      pengunjung: n(r.pengunjung),
      keranjang: n(r.keranjang),
      konversi: r.pengunjung ? (n(r.pesanan) / n(r.pengunjung)) * 100 : 0,
      aov: r.pesanan ? n(r.omzet) / n(r.pesanan) : 0,
    }));
  }
}

async function getBestProductPerStore(skuInduk: string, kind: "jual" | "iklan" | "analisa", metric: string, f: Filter) {
  const { params, W } = build(f);
  params.push(skuInduk);
  const skuParam = `$${params.length}`;
  
  let query = "";
  if (kind === "iklan") {
    let orderExpr = "total_omzetIklan";
    if (metric === "biayaIklan") orderExpr = "total_biayaIklan";
    else if (metric === "klik") orderExpr = "total_klik";
    else if (metric === "dilihat") orderExpr = "total_dilihat";
    else if (metric === "konversi") orderExpr = "total_konversi";
    else if (metric === "roas") orderExpr = "case when total_biayaIklan > 0 then total_omzetIklan / total_biayaIklan else 0 end";
    else if (metric === "ctr") orderExpr = "case when total_dilihat > 0 then total_klik / total_dilihat else 0 end";
    else if (metric === "cr") orderExpr = "case when total_klik > 0 then total_konversi / total_klik else 0 end";
    else if (metric === "cpc") orderExpr = "case when total_klik > 0 then total_biayaIklan / total_klik else 0 end";

    query = `
      with product_totals as (
        select 
          f.produk_id,
          dp.toko_id,
          sum(f.omzet_iklan)::float as total_omzetIklan,
          sum(f.biaya_iklan)::float as total_biayaIklan,
          sum(f.klik)::float as total_klik,
          sum(f.dilihat)::float as total_dilihat,
          sum(f.konversi)::float as total_konversi
        from fact_iklan f
        join dim_produk dp on dp.produk_id = f.produk_id
        join dim_toko t on t.toko_id = dp.toko_id
        where ${W} and dp.sku_induk = ${skuParam}
        group by f.produk_id, dp.toko_id
      ),
      ranked as (
        select 
          produk_id,
          toko_id,
          row_number() over (partition by toko_id order by ${orderExpr} desc) as rn
        from product_totals
      )
      select r.produk_id, t.nama as toko
      from ranked r
      join dim_toko t on t.toko_id = r.toko_id
      where r.rn = 1
    `;
  } else if (kind === "analisa") {
    let orderExpr = "total_omzet";
    if (metric === "biaya") orderExpr = "total_biaya";
    else if (metric === "omzetIklan") orderExpr = "total_oik";
    else if (metric === "roas") orderExpr = "case when total_biaya > 0 then total_oik / total_biaya else 0 end";
    else if (metric === "acos") orderExpr = "case when total_omzet > 0 then total_biaya / total_omzet else 0 end";

    query = `
      with product_totals as (
        select 
          dp.produk_id,
          dp.toko_id,
          coalesce(sum(f.penjualan), 0)::float as total_omzet,
          coalesce(max(i.biaya), 0)::float as total_biaya,
          coalesce(max(i.oik), 0)::float as total_oik
        from dim_produk dp
        join dim_toko t on t.toko_id = dp.toko_id
        left join fact_penjualan f on f.produk_id = dp.produk_id and f.periode = $1 and f.periode_mulai between $2 and $3
        left join (
          select produk_id, sum(biaya_iklan) as biaya, sum(omzet_iklan) as oik
          from fact_iklan
          where periode = $1 and periode_mulai between $2 and $3
          group by produk_id
        ) i on i.produk_id = dp.produk_id
        where dp.sku_induk = ${skuParam}
        group by dp.produk_id, dp.toko_id
      ),
      ranked as (
        select 
          produk_id,
          toko_id,
          row_number() over (partition by toko_id order by ${orderExpr} desc) as rn
        from product_totals
      )
      select r.produk_id, t.nama as toko
      from ranked r
      join dim_toko t on t.toko_id = r.toko_id
      where r.rn = 1
    `;
  } else {
    let orderExpr = "total_omzet";
    if (metric === "pesanan") orderExpr = "total_pesanan";
    else if (metric === "unit") orderExpr = "total_unit";
    else if (metric === "pembeli") orderExpr = "total_pembeli";
    else if (metric === "pengunjung") orderExpr = "total_pengunjung";
    else if (metric === "keranjang") orderExpr = "total_keranjang";
    else if (metric === "konversi") orderExpr = "case when total_pengunjung > 0 then total_pesanan / total_pengunjung else 0 end";
    else if (metric === "aov") orderExpr = "case when total_pesanan > 0 then total_omzet / total_pesanan else 0 end";

    query = `
      with product_totals as (
        select 
          f.produk_id,
          dp.toko_id,
          sum(f.penjualan)::float as total_omzet,
          sum(f.pesanan)::float as total_pesanan,
          sum(f.unit_pesanan)::float as total_unit,
          sum(f.pembeli)::float as total_pembeli,
          sum(f.pengunjung)::float as total_pengunjung,
          sum(f.keranjang)::float as total_keranjang
        from fact_penjualan f
        join dim_produk dp on dp.produk_id = f.produk_id
        join dim_toko t on t.toko_id = dp.toko_id
        where ${W} and dp.sku_induk = ${skuParam}
        group by f.produk_id, dp.toko_id
      ),
      ranked as (
        select 
          produk_id,
          toko_id,
          row_number() over (partition by toko_id order by ${orderExpr} desc) as rn
        from product_totals
      )
      select r.produk_id, t.nama as toko
      from ranked r
      join dim_toko t on t.toko_id = r.toko_id
      where r.rn = 1
    `;
  }

  return q<{ produk_id: number; toko: string }>(query, params);
}

export async function getProdukComparisonTrend(
  skuInduk: string,
  kind: "jual" | "iklan" | "analisa",
  metric: string,
  f: Filter
) {
  const bestProducts = await getBestProductPerStore(skuInduk, kind, metric, f);
  if (bestProducts.length === 0) return [];
  
  const productIds = bestProducts.map((p) => p.produk_id);
  const storeMap = new Map<number, string>();
  bestProducts.forEach((p) => storeMap.set(Number(p.produk_id), p.toko));
  
  const { params, W } = build(f);
  params.push(productIds);
  const idsParam = `$${params.length}`;
  
  const dateMap = new Map<string, Record<string, number | string>>();
  
  if (kind === "iklan") {
    const rows = await q<{ w: Date; produk_id: number; dilihat: number; klik: number; konversi: number; omzet: number; biaya: number }>(
      `select f.periode_mulai w, f.produk_id, coalesce(sum(f.dilihat),0)::float dilihat, coalesce(sum(f.klik),0)::float klik,
              coalesce(sum(f.konversi),0)::float konversi, coalesce(sum(f.omzet_iklan),0)::float omzet,
              coalesce(sum(f.biaya_iklan),0)::float biaya
       from fact_iklan f join dim_toko t on t.toko_id=f.toko_id
       where ${W} and f.produk_id = any(${idsParam})
       group by f.periode_mulai, f.produk_id order by f.periode_mulai`,
      params
    );
    
    rows.forEach((r) => {
      const label = labelPeriode(f.periode, r.w);
      const storeName = storeMap.get(Number(r.produk_id)) || "Unknown";
      const metrics = deriveIklan({ dilihat: n(r.dilihat), klik: n(r.klik), konversi: n(r.konversi), omzet: n(r.omzet), biaya: n(r.biaya) });
      const val = metrics[metric as keyof typeof metrics] ?? 0;
      
      if (!dateMap.has(label)) {
        dateMap.set(label, { label });
      }
      dateMap.get(label)![storeName] = n(val);
    });
  } else if (kind === "analisa") {
    const rows = await q<{ pm: Date; produk_id: number; omzet: number; biaya: number; oik: number }>(
      `select p.pm, p.produk_id, p.omzet, coalesce(i.biaya,0)::float biaya, coalesce(i.oik,0)::float oik
       from (select f.periode_mulai pm, f.produk_id, sum(f.penjualan)::float omzet
             from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
             where ${W} and f.produk_id = any(${idsParam}) group by f.periode_mulai, f.produk_id) p
       left join (select f.periode_mulai pm, f.produk_id, sum(f.biaya_iklan)::float biaya, sum(f.omzet_iklan)::float oik
                  from fact_iklan f join dim_toko t on t.toko_id=f.toko_id
                  where ${W} and f.produk_id = any(${idsParam}) group by f.periode_mulai, f.produk_id) i
         on i.pm = p.pm and i.produk_id = p.produk_id order by p.pm`,
      params
    );
    
    rows.forEach((r) => {
      const label = labelPeriode(f.periode, r.pm);
      const storeName = storeMap.get(Number(r.produk_id)) || "Unknown";
      
      let val = 0;
      if (metric === "omzet") val = n(r.omzet);
      else if (metric === "biaya") val = n(r.biaya);
      else if (metric === "omzetIklan") val = n(r.oik);
      else if (metric === "roas") val = r.biaya ? n(r.oik) / n(r.biaya) : 0;
      else if (metric === "acos") val = r.omzet ? (n(r.biaya) / n(r.omzet)) * 100 : 0;
      
      if (!dateMap.has(label)) {
        dateMap.set(label, { label });
      }
      dateMap.get(label)![storeName] = val;
    });
  } else {
    const rows = await q<{ w: Date; produk_id: number; omzet: number; pesanan: number; unit: number; pembeli: number; pengunjung: number; keranjang: number }>(
      `select f.periode_mulai w, f.produk_id, coalesce(sum(f.penjualan),0)::float omzet, coalesce(sum(f.pesanan),0)::float pesanan,
              coalesce(sum(f.unit_pesanan),0)::float unit, coalesce(sum(f.pembeli),0)::float pembeli,
              coalesce(sum(f.pengunjung),0)::float pengunjung, coalesce(sum(f.keranjang),0)::float keranjang
       from fact_penjualan f join dim_toko t on t.toko_id=f.toko_id
       where ${W} and f.produk_id = any(${idsParam})
       group by f.periode_mulai, f.produk_id order by f.periode_mulai`,
      params
    );
    
    rows.forEach((r) => {
      const label = labelPeriode(f.periode, r.w);
      const storeName = storeMap.get(Number(r.produk_id)) || "Unknown";
      
      let val = 0;
      if (metric === "omzet") val = n(r.omzet);
      else if (metric === "pesanan") val = n(r.pesanan);
      else if (metric === "unit") val = n(r.unit);
      else if (metric === "pembeli") val = n(r.pembeli);
      else if (metric === "pengunjung") val = n(r.pengunjung);
      else if (metric === "keranjang") val = n(r.keranjang);
      else if (metric === "konversi") val = r.pengunjung ? (n(r.pesanan) / n(r.pengunjung)) * 100 : 0;
      else if (metric === "aov") val = r.pesanan ? n(r.omzet) / n(r.pesanan) : 0;
      
      if (!dateMap.has(label)) {
        dateMap.set(label, { label });
      }
      dateMap.get(label)![storeName] = val;
    });
  }
  
  return Array.from(dateMap.values());
}

export { labelHari };
