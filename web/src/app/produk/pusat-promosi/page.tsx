"use client";

import { useState, useEffect, useCallback, Fragment } from "react";
import CustomSelect from "@/components/CustomSelect";

type Row = Record<string, unknown>;
type Toko = { username: string; nama: string };

// Urutan by cadence tarik: jam (Promo Toko) -> harian (Garansi, Campaign) ->
// mingguan (Flash, Voucher, Paket) -> Komisi (dari dashboard).
const TABS = [
  { key: "promo_toko", label: "Promo Toko" },
  { key: "garansi", label: "Garansi" },
  { key: "campaign", label: "Campaign" },
  { key: "flash", label: "Flash Sale" },
  { key: "voucher", label: "Voucher" },
  { key: "paket", label: "Paket Diskon" },
  { key: "komisi", label: "Komisi" },
];

// Kolom per tab: [key, judul, tipe]. tipe: text | rp | dt | num | status
type Col = { k: string; t: string; f?: "rp" | "dt" | "num" | "status" | "margin" | "verdict" };
const COLS: Record<string, Col[]> = {
  promo_toko: [
    { k: "toko", t: "Toko" }, { k: "nama", t: "Nama Promo" },
    { k: "status", t: "Status", f: "status" }, { k: "itemCount", t: "Jml Produk", f: "num" },
    { k: "mulai", t: "Mulai", f: "dt" }, { k: "berakhir", t: "Berakhir", f: "dt" },
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
    { k: "namaVariasi", t: "Variasi" },
    { k: "currentPrice", t: "Harga Kini", f: "rp" }, { k: "marginCurrent", t: "Margin Kini", f: "margin" },
    { k: "bestPrice", t: "Harga Terbaik", f: "rp" }, { k: "marginBest", t: "Margin Terbaik", f: "margin" },
    { k: "bidPrice", t: "Harga Program", f: "rp" }, { k: "marginProgram", t: "Margin Program", f: "margin" },
    { k: "stok", t: "Stok", f: "num" },
  ],
  flash: [
    { k: "toko", t: "Toko" }, { k: "flashSaleId", t: "ID Sesi" }, { k: "status", t: "Status", f: "status" },
    { k: "itemCount", t: "Jml Item", f: "num" }, { k: "startTime", t: "Mulai", f: "dt" },
    { k: "endTime", t: "Berakhir", f: "dt" },
  ],
  komisi: [
    { k: "toko", t: "Toko" }, { k: "itemName", t: "Produk" },
    { k: "verdict", t: "Status Komisi", f: "verdict" },
    { k: "syntraPersen", t: "Komisi Syntra %", f: "num" },
    { k: "shopeePersen", t: "Komisi Shopee %", f: "num" },
    { k: "jmlSku", t: "Jml SKU", f: "num" },
  ],
  garansi_nom: [
    { k: "toko", t: "Toko" }, { k: "itemName", t: "Produk" }, { k: "modelName", t: "Variasi" },
    { k: "hargaReal", t: "Harga Real", f: "rp" }, { k: "marginReal", t: "Margin Real", f: "margin" },
    { k: "floor", t: "Harga Terbaik", f: "rp" }, { k: "marginBest", t: "Margin Terbaik", f: "margin" },
    { k: "ceiling", t: "Harga Program", f: "rp" }, { k: "marginProgram", t: "Margin Program", f: "margin" },
    { k: "stok", t: "Stok", f: "num" },
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

const GARANSI_SUB = [
  { key: "rekomendasi", label: "Belum Didaftar" },
  { key: "terbaik", label: "Terbaik" },
  { key: "perlu_ditinjau", label: "Perlu Ditinjau" },
];

export default function PusatPromosiPage() {
  const [tab, setTab] = useState("promo_toko");
  const [garSub, setGarSub] = useState("terbaik");   // sub-tab Garansi (a/b/c)
  const [rows, setRows] = useState<Row[]>([]);
  const [tokos, setTokos] = useState<Toko[]>([]);
  const [total, setTotal] = useState(0);
  const [toko, setToko] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [perm, setPerm] = useState({ netPrice: true, margin: true, hpp: true, hargaJualKomisi: true });
  const ALL_TABS_PROMOSI = ["promo_toko", "garansi", "campaign", "flash", "voucher", "paket", "komisi"];
  const [allowedTabs, setAllowedTabs] = useState<string[]>([...ALL_TABS_PROMOSI]);
  const size = 50;

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const u = new URL("/api/produk/pusat-promosi", window.location.origin);
      u.searchParams.set("tab", tab === "garansi" ? "garansi_nom" : tab);
      if (tab === "garansi") u.searchParams.set("kat", garSub);
      u.searchParams.set("page", String(page));
      u.searchParams.set("size", String(size));
      if (toko) u.searchParams.set("toko", toko);
      if (search) u.searchParams.set("q", search);
      const r = await fetch(u.toString(), { cache: "no-store" });
      const d = await r.json();
      if (r.status === 403) {
        const allowed: string[] = d.allowedTabs || [];
        setAllowedTabs(allowed);
        if (allowed.length > 0 && !allowed.includes(tab)) {
          setTab(allowed[0]);
          return;
        }
        setErr(allowed.length === 0 ? "Anda tidak memiliki izin lihat tab manapun di halaman ini." : (d.error || "Akses ditolak"));
        setRows([]);
        setTotal(0);
        return;
      }
      if (!r.ok) throw new Error(d.error || "Gagal memuat");
      setRows(d.rows || []);
      setTotal(d.total || 0);
      if (d.tokos) setTokos(d.tokos);
      if (d.perm) setPerm(d.perm);
      if (d.allowedTabs) setAllowedTabs(d.allowedTabs);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setRows([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [tab, garSub, page, toko, search]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  const cols = COLS[tab === "garansi" ? "garansi_nom" : tab] || [];
  const totalPages = Math.max(1, Math.ceil(total / size));

  // Expand-row: klik promo -> produk di dalamnya. Config per tab yg support detail.
  const DETAIL_CFG: Record<string, { idField: string; detailTab: string; idParam: string; priceField: string; judul: string }> = {
    voucher: { idField: "voucherId", detailTab: "voucher_produk", idParam: "voucher_id", priceField: "hargaTampil", judul: "voucher" },
    paket: { idField: "bundleDealId", detailTab: "paket_produk", idParam: "bundle_deal_id", priceField: "hargaTampil", judul: "paket diskon" },
    promo_toko: { idField: "promotionId", detailTab: "promo_toko_produk", idParam: "promotion_id", priceField: "hargaPromo", judul: "promo toko" },
    komisi: { idField: "itemId", detailTab: "komisi_produk", idParam: "item_id", priceField: "hargaJual", judul: "komisi (SKU variasi)" },
  };
  const cfg = DETAIL_CFG[tab];
  const bisaDetail = !!cfg;
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, { shopWide?: boolean; produk?: Row[] }>>({});
  const [detailLoading, setDetailLoading] = useState(false);

  const toggleRow = async (row: Row) => {
    if (!cfg) return;
    const key = String(row[cfg.idField]);
    if (expanded === key) { setExpanded(null); return; }
    setExpanded(key);
    if (!detail[key]) {
      setDetailLoading(true);
      try {
        const u = new URL("/api/produk/pusat-promosi", window.location.origin);
        u.searchParams.set("tab", cfg.detailTab);
        u.searchParams.set(cfg.idParam, String(row[cfg.idField]));
        u.searchParams.set("toko", String(row.toko));
        const r = await fetch(u.toString(), { cache: "no-store" });
        const d = await r.json();
        setDetail((prev) => ({ ...prev, [key]: d }));
      } catch { /* diamkan */ }
      finally { setDetailLoading(false); }
    }
  };

  const renderProdukDetail = (key: string) => {
    const dd = detail[key];
    if (!dd) return <div className="p-3 text-xs text-[#8a90a2]">{detailLoading ? "Memuat produk…" : "—"}</div>;
    if (dd.shopWide) return <div className="p-3 text-[12px] text-[#6b7180]">🏷️ Berlaku untuk <b>semua produk</b> toko.</div>;
    const produk = dd.produk || [];
    const pf = cfg?.priceField || "hargaTampil";
    return (
      <div className="p-3">
        <div className="text-[11px] font-bold text-[#6b7180] uppercase tracking-wider mb-1.5">Produk dalam {cfg?.judul} ({produk.length})</div>
        {produk.length === 0 ? (
          <div className="text-xs text-[#8a90a2]">Tidak ada produk cocok di data olah (mungkin stok 0 saat grab).</div>
        ) : (
          <div className="flex flex-col gap-1">
            {produk.map((pr, i) => (
              <div key={i} className="flex items-center gap-2 text-[12px]">
                <span className="font-semibold text-[#4b5563] w-[130px] truncate">{String(pr.sku ?? "-")}</span>
                <span className="flex-1 min-w-0 truncate text-[#3a3f4d]" title={String(pr.namaProduk ?? "")}>{String(pr.namaProduk ?? "-")}</span>
                <span className="text-[#16b8a6] font-semibold shrink-0">{rp((pr as Record<string, unknown>)[pf])}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

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
        {TABS.filter((t) => allowedTabs.includes(t.key)).map((t) => (
          <button
            key={t.key}
            onClick={() => { setTab(t.key); setPage(1); setExpanded(null); }}
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

      {/* Sub-tab Garansi (a/b/c) */}
      {tab === "garansi" && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {GARANSI_SUB.map((s) => (
            <button
              key={s.key}
              onClick={() => { setGarSub(s.key); setPage(1); }}
              className={
                "px-3 py-1.5 rounded-lg text-[12.5px] font-semibold transition-all border " +
                (garSub === s.key
                  ? "bg-[#fff1ed] text-[#ee4d2d] border-[#ffccbc]"
                  : "bg-white text-[#8a90a2] border-[#eef0f6] hover:bg-[#fafbfe]")
              }
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <CustomSelect
          value={toko}
          onChange={(val) => { setToko(val); setPage(1); }}
          options={tokos.map((t) => ({ value: t.nama, label: t.nama }))}
          placeholder="Semua Toko"
        />
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
                rows.map((row, i) => {
                  const key = cfg ? String(row[cfg.idField]) : String(i);
                  const isOpen = bisaDetail && expanded === key;
                  return (
                  <Fragment key={key}>
                  <tr
                    onClick={() => toggleRow(row)}
                    className={"border-t border-[#f2f3f8] " + (bisaDetail ? "cursor-pointer " : "") + (isOpen ? "bg-[#fff8f6]" : "hover:bg-[#fafbfe]")}
                  >
                    {cols.map((c, ci) => (
                      <td key={c.k} className="px-3 py-2 whitespace-nowrap text-[#3a3f4d]">
                        {ci === 0 && bisaDetail && (
                          <span className="inline-block w-3 text-[#ee4d2d] mr-1 select-none">{isOpen ? "▾" : "▸"}</span>
                        )}
                        {c.f === "status" ? (
                          <span className={
                            "px-2 py-0.5 rounded-full text-[11px] font-semibold " +
                            (/aktif|berjalan/.test(String(row[c.k]).toLowerCase()) || Number(row[c.k]) === 1
                              ? "bg-green-50 text-green-600"
                              : String(row[c.k]).toLowerCase().includes("datang")
                                ? "bg-blue-50 text-blue-600" : "bg-gray-100 text-gray-500")
                          }>
                            {fmt(row[c.k])}
                          </span>
                        ) : c.f === "verdict" ? (
                          <span className={
                            "px-2 py-0.5 rounded-full text-[11px] font-semibold " +
                            (row[c.k] === "sesuai" ? "bg-green-50 text-green-600"
                              : row[c.k] === "belum_dikomisikan" ? "bg-amber-50 text-amber-600"
                              : "bg-red-50 text-red-600")
                          }>
                            {row[c.k] === "sesuai" ? "✅ Sesuai"
                              : row[c.k] === "belum_dikomisikan" ? "⚠️ Belum dikomisikan"
                              : "❌ Harusnya dicabut"}
                          </span>
                        ) : c.f === "margin" ? (
                          !perm.margin ? (
                            <span className="text-[#c3c6d1]" title="Akses data sensitif dikunci">🔒</span>
                          ) : row[c.k] === null || row[c.k] === undefined || row[c.k] === "" ? (
                            <span className="text-[#c3c6d1]">-</span>
                          ) : (
                            <span className={
                              "font-bold " +
                              (Number(row[c.k]) >= 0.12 ? "text-[#047857]" : Number(row[c.k]) >= 0 ? "text-[#eab308]" : "text-[#e11d48]")
                            }>
                              {(Number(row[c.k]) * 100).toFixed(1)}%
                            </span>
                          )
                        ) : (
                          <span className={c.k === "namaProduk" || c.k === "itemName" ? "block max-w-[240px] truncate" : ""} title={c.k === "namaProduk" || c.k === "itemName" ? String(row[c.k] ?? "") : undefined}>
                            {fmt(row[c.k], c.f)}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={cols.length} className="p-0 bg-[#fafbfe] border-b-2 border-[#ffddcc]">
                        {renderProdukDetail(key)}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                  );
                })
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
