"use client";

import { useState, useEffect, useCallback } from "react";

type Row = Record<string, unknown>;
type Toko = { username: string; nama: string };

const TABS = [
  { key: "promo_toko", label: "Promo Toko" },
  { key: "paket", label: "Paket Diskon" },
  { key: "voucher", label: "Voucher" },
  { key: "campaign", label: "Campaign" },
  { key: "garansi", label: "Garansi" },
  { key: "flash", label: "Flash Sale" },
  { key: "komisi", label: "Komisi" },
];

// Kolom per tab: [key, judul, tipe]. tipe: text | rp | dt | num | status
type Col = { k: string; t: string; f?: "rp" | "dt" | "num" | "status" };
const COLS: Record<string, Col[]> = {
  promo_toko: [
    { k: "toko", t: "Toko" }, { k: "sku", t: "SKU" }, { k: "namaProduk", t: "Produk" },
    { k: "namaVariasi", t: "Variasi" }, { k: "hargaPromo", t: "Harga Promo", f: "rp" },
    { k: "status", t: "Status", f: "status" }, { k: "stok", t: "Stok", f: "num" },
    { k: "berakhir", t: "Berakhir", f: "dt" },
  ],
  paket: [
    { k: "toko", t: "Toko" }, { k: "bundleDealId", t: "ID" }, { k: "name", t: "Nama" },
    { k: "status", t: "Status", f: "status" }, { k: "startTime", t: "Mulai", f: "dt" },
    { k: "endTime", t: "Berakhir", f: "dt" },
  ],
  voucher: [
    { k: "toko", t: "Toko" }, { k: "code", t: "Kode" }, { k: "name", t: "Nama" },
    { k: "discount", t: "Diskon %", f: "num" }, { k: "minPrice", t: "Min Belanja", f: "rp" },
    { k: "tipe", t: "Tipe" }, { k: "endTime", t: "Berakhir", f: "dt" },
  ],
  campaign: [
    { k: "toko", t: "Toko" }, { k: "campaignName", t: "Campaign" }, { k: "sessionName", t: "Sesi" },
    { k: "nominated", t: "Produk Ternominasi", f: "num" }, { k: "sessionStart", t: "Mulai Sesi", f: "dt" },
    { k: "nominationEnd", t: "Tutup Nominasi", f: "dt" },
  ],
  garansi: [
    { k: "toko", t: "Toko" }, { k: "sku", t: "SKU" }, { k: "namaProduk", t: "Produk" },
    { k: "namaVariasi", t: "Variasi" }, { k: "currentPrice", t: "Harga Kini", f: "rp" },
    { k: "bestPrice", t: "Harga Terbaik", f: "rp" }, { k: "bidPrice", t: "Harga Program", f: "rp" },
    { k: "stok", t: "Stok", f: "num" },
  ],
  flash: [
    { k: "toko", t: "Toko" }, { k: "flashSaleId", t: "ID Sesi" }, { k: "status", t: "Status", f: "status" },
    { k: "itemCount", t: "Jml Item", f: "num" }, { k: "startTime", t: "Mulai", f: "dt" },
    { k: "endTime", t: "Berakhir", f: "dt" },
  ],
  komisi: [
    { k: "toko", t: "Toko" }, { k: "sku", t: "SKU" }, { k: "parentSku", t: "Parent SKU" },
    { k: "category", t: "Kategori" }, { k: "komisiPersen", t: "Komisi %", f: "num" },
    { k: "hargaJual", t: "Harga Jual", f: "rp" },
  ],
};

const rp = (v: unknown) => {
  const n = Number(v);
  if (!n) return "-";
  return "Rp " + Math.round(n).toLocaleString("id-ID");
};
const dt = (v: unknown) => {
  if (!v) return "-";
  const d = new Date(String(v));
  if (isNaN(d.getTime())) return "-";
  return d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
};
const fmt = (v: unknown, f?: string) => {
  if (f === "rp") return rp(v);
  if (f === "dt") return dt(v);
  if (f === "num") return v === null || v === undefined || v === "" ? "-" : Number(v).toLocaleString("id-ID");
  if (v === null || v === undefined || v === "") return "-";
  return String(v);
};

export default function PusatPromosiPage() {
  const [tab, setTab] = useState("promo_toko");
  const [rows, setRows] = useState<Row[]>([]);
  const [tokos, setTokos] = useState<Toko[]>([]);
  const [total, setTotal] = useState(0);
  const [toko, setToko] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const size = 50;

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const u = new URL("/api/produk/pusat-promosi", window.location.origin);
      u.searchParams.set("tab", tab);
      u.searchParams.set("page", String(page));
      u.searchParams.set("size", String(size));
      if (toko) u.searchParams.set("toko", toko);
      if (search) u.searchParams.set("q", search);
      const r = await fetch(u.toString(), { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "Gagal memuat");
      setRows(d.rows || []);
      setTotal(d.total || 0);
      if (d.tokos) setTokos(d.tokos);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [tab, page, toko, search]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  const cols = COLS[tab] || [];
  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="p-5 md:p-8 max-w-[1600px] mx-auto">
      <div className="mb-5">
        <h1 className="text-[22px] font-extrabold text-[#3a3f4d] tracking-tight">🎯 Pusat Promosi</h1>
        <p className="text-[13px] text-[#6b7180] mt-1">
          Fakta keikutsertaan promo semua produk per program — dikumpulkan otomatis oleh bot (Fase 1).
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setPage(1); }}
            className={
              "px-3.5 py-2 rounded-xl text-[13px] font-semibold transition-all " +
              (tab === t.key
                ? "bg-[#ee4d2d] text-white shadow-sm"
                : "bg-white text-[#6b7180] border border-[#eef0f6] hover:bg-[#fff1ed]")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <select
          value={toko}
          onChange={(e) => { setToko(e.target.value); setPage(1); }}
          className="px-3 py-2 rounded-lg border border-[#eef0f6] text-[13px] bg-white text-[#3a3f4d] outline-none focus:border-[#ee4d2d]"
        >
          <option value="">Semua Toko</option>
          {tokos.map((t) => (
            <option key={t.username} value={t.nama}>{t.nama}</option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="Cari SKU / nama / kode…"
          className="px-3 py-2 rounded-lg border border-[#eef0f6] text-[13px] bg-white text-[#3a3f4d] outline-none focus:border-[#ee4d2d] min-w-[220px] flex-1 max-w-[320px]"
        />
        <span className="text-[12px] text-[#9aa0b2] ml-auto">{total.toLocaleString("id-ID")} baris</span>
      </div>

      {/* Tabel */}
      <div className="bg-white rounded-2xl border border-[#eef0f6] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="bg-[#f6f7fb] text-[#6b7180] text-left">
                {cols.map((c) => (
                  <th key={c.k} className="px-3 py-2.5 font-semibold whitespace-nowrap">{c.t}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={cols.length} className="px-3 py-8 text-center text-[#9aa0b2]">Memuat…</td></tr>
              ) : err ? (
                <tr><td colSpan={cols.length} className="px-3 py-8 text-center text-red-500">{err}</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={cols.length} className="px-3 py-8 text-center text-[#9aa0b2]">Belum ada data. Bot Fase 1 mengisi tab ini otomatis (harian/mingguan).</td></tr>
              ) : (
                rows.map((row, i) => (
                  <tr key={i} className="border-t border-[#f2f3f8] hover:bg-[#fafbfe]">
                    {cols.map((c) => (
                      <td key={c.k} className="px-3 py-2 whitespace-nowrap text-[#3a3f4d]">
                        {c.f === "status" ? (
                          <span className={
                            "px-2 py-0.5 rounded-full text-[11px] font-semibold " +
                            (String(row[c.k]).toLowerCase().includes("aktif") || Number(row[c.k]) === 1
                              ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-500")
                          }>
                            {fmt(row[c.k])}
                          </span>
                        ) : (
                          <span className={c.k === "namaProduk" ? "block max-w-[240px] truncate" : ""} title={c.k === "namaProduk" ? String(row[c.k] ?? "") : undefined}>
                            {fmt(row[c.k], c.f)}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg border border-[#eef0f6] text-[13px] bg-white text-[#6b7180] disabled:opacity-40 hover:bg-[#fff1ed]"
          >
            ← Sebelumnya
          </button>
          <span className="text-[13px] text-[#6b7180]">Hal {page} / {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1.5 rounded-lg border border-[#eef0f6] text-[13px] bg-white text-[#6b7180] disabled:opacity-40 hover:bg-[#fff1ed]"
          >
            Berikutnya →
          </button>
        </div>
      )}
    </div>
  );
}
