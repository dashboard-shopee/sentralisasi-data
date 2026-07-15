"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";

interface SkuRow {
  sku: string;
  parentSku: string | null;
  productName: string | null;
  category: string | null;
  stock: number;
  inbound: number;
  ttosDate: string | null;
  poNo: string | null;
  orderedAt: string | null;
  forecast: number;
}

interface SkuDetail {
  sales: { toko: string; qty: number }[];
  weekly: { w0: number; w1: number; w2: number; w3: number; w4: number } | null;
  shopee: {
    totalQty: number;
    totalOrders: number;
    singleOrders: number;
    multiOrders: number;
    multiQty: number;
  } | null;
  bounds: { key: number; start: string; end: string }[];
}

export default function StokPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const [sortCol, setSortCol] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const [rows, setRows] = useState<SkuRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Accordion state
  const [expandedSku, setExpandedSku] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<Record<string, SkuDetail>>({});
  const [loadingDetail, setLoadingDetail] = useState(false);

  const formatRp = (n: number | null | undefined) => {
    if (n === null || n === undefined) return "-";
    return "Rp" + Math.round(n).toLocaleString("id-ID");
  };

  const formatDate = (ds: string | null | undefined, includeTime = false) => {
    if (!ds) return "-";
    try {
      const d = new Date(ds);
      return d.toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: includeTime ? "2-digit" : undefined,
        minute: includeTime ? "2-digit" : undefined
      }).replace(",", "");
    } catch {
      return ds;
    }
  };

  const formatWeekBound = (bound: { start: string; end: string }) => {
    const s = new Date(bound.start);
    const e = new Date(bound.end);
    return `${s.getDate()}/${s.getMonth() + 1} - ${e.getDate()}/${e.getMonth() + 1}`;
  };

  // Guard race: search cepat-cepat (debounce beririsan) -> respons lama bisa nimpa hasil baru.
  const reqId = useRef(0);

  const fetchData = useCallback(async () => {
    const myReq = ++reqId.current;
    setLoading(true);
    try {
      const params = new URLSearchParams({
        q,
        page: String(page),
        size: String(size),
        sort: sortCol,
        dir: sortDir
      });

      const res = await fetch(`/api/produk/stok?${params.toString()}`, { cache: "no-store" });
      if (myReq !== reqId.current) return;
      if (res.ok) {
        const d = await res.json();
        if (myReq !== reqId.current) return;
        setRows(d.rows || []);
        setTotal(d.total || 0);
      }
    } catch (e) {
      if (myReq !== reqId.current) return;
      console.error("Gagal mengambil data stok ERP:", e);
    } finally {
      if (myReq === reqId.current) setLoading(false);
    }
  }, [q, page, size, sortCol, sortDir]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQ(e.target.value);
    setPage(1);
    setExpandedSku(null);
  };

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(1);
    setExpandedSku(null);
  };

  const toggleRow = async (sku: string) => {
    if (expandedSku === sku) {
      setExpandedSku(null);
      return;
    }
    setExpandedSku(sku);

    if (!detailData[sku]) {
      setLoadingDetail(true);
      try {
        const res = await fetch(`/api/produk/stok?sku=${encodeURIComponent(sku)}`);
        if (res.ok) {
          const detail = await res.json();
          setDetailData((prev) => ({ ...prev, [sku]: detail }));
        }
      } catch (e) {
        console.error("Gagal mengambil detail stok SKU:", e);
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  const getStockStatus = (r: SkuRow) => {
    if (r.stock <= 0) return { label: "Kritis (Habis)", color: "bg-[#ffe4e6] text-[#e11d48] border border-[#fecdd3]" };
    if (r.stock <= (r.forecast * 7)) return { label: "Reorder (Tipis)", color: "bg-[#fffbeb] text-[#d97706] border border-[#fef3c7]" };
    return { label: "Aman", color: "bg-[#ecfdf5] text-[#059669] border border-[#d1fae5]" };
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <div className="max-w-[1400px] xl:max-w-[1650px] w-full mx-auto">
      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight flex items-center gap-2 text-[#3a3f4d]">
            <span>📦</span> Stok & Purchase Data (ERP)
          </h1>
          <p className="text-[13px] text-[#8a90a2] mt-0.5">
            Pantau level inventori fisik gudang, PO aktif, outbound velocity, dan metrik order detail per master SKU.
          </p>
        </div>
        
        {/* Search */}
        <div className="relative w-full md:w-[320px] shrink-0">
          <input
            type="text"
            placeholder="Cari SKU, nama produk, PO..."
            value={q}
            onChange={handleSearchChange}
            className="w-full bg-white border border-[#eef0f6] rounded-xl pl-9 pr-4 py-2 text-[13px] outline-none focus:border-[#ee4d2d] transition-all text-[#161a27]"
          />
          <span className="absolute left-3 top-[11px] text-[13px] text-[#9aa0b2]">🔍</span>
        </div>
      </div>

      {/* Table Card */}
      <div className="card w-full overflow-hidden">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-t-transparent border-[#ee4d2d] animate-spin"></div>
            <span className="text-[12px] text-[#8a90a2] font-semibold">Memuat katalog stok...</span>
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <span className="text-3xl mb-2">📥</span>
            <div className="font-bold text-[#161a27]">Tidak Ada Data</div>
            <p className="text-xs text-[#8a90a2] mt-1 max-w-[280px]">
              {q ? "Kata kunci pencarian tidak mencocokkan SKU apa pun." : "Katalog stok ERP saat ini kosong."}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse" style={{ minWidth: "1200px" }}>
                <thead>
                  <tr className="border-b border-[#eef0f6] bg-[#f6f7fb]">
                    <th className="p-3.5 w-[40px]"></th>
                    <th className="p-3.5 w-[55px] text-center text-[12px] font-bold text-[#6b7180] tracking-wider">No</th>
                    <th onClick={() => handleSort("sku")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px]">
                      SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("parent_sku")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[120px]">
                      Parent SKU {sortCol === "parent_sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("product_name")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[260px]">
                      Nama Produk & Kategori {sortCol === "product_name" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("total_stock")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px] text-right font-bold text-[#16b8a6]">
                      Stok Fisik {sortCol === "total_stock" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("total_inbound")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right font-bold text-[#42a5f5]">
                      Inbound {sortCol === "total_inbound" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider w-[120px] text-center">
                      Status Stok
                    </th>
                    <th onClick={() => handleSort("ttos_date")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[120px] text-center">
                      TTOS Date {sortCol === "ttos_date" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("forecast_val")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                      Forecast {sortCol === "forecast_val" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                    <th onClick={() => handleSort("po_no")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px]">
                      PO Terkini {sortCol === "po_no" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#eef0f6] text-[13px]">
                  {rows.map((r, index) => {
                    const isOpen = expandedSku === r.sku;
                    const st = getStockStatus(r);
                    return (
                      <React.Fragment key={r.sku}>
                        {/* Main row */}
                        <tr
                          onClick={() => toggleRow(r.sku)}
                          className={`cursor-pointer transition-colors ${isOpen ? "bg-[#fff1ed]/20" : "hover:bg-[#fcfdfe]"}`}
                        >
                          <td className="p-3.5 text-center text-[#8a90a2] font-bold text-[10px] select-none">
                            {isOpen ? "▼" : "▶"}
                          </td>
                          <td className="p-3.5 text-center text-[#9aa0b2] font-semibold">
                            {(page - 1) * size + index + 1}
                          </td>
                          <td className="p-3.5 font-bold text-[#161a27]">{r.sku}</td>
                          <td className="p-3.5"><span className="px-2 py-0.5 bg-[#f0f2f5] text-[#4b5563] text-[11px] font-medium rounded">{r.parentSku || "-"}</span></td>
                          <td className="p-3.5 text-xs max-w-[260px]">
                            <div className="font-semibold text-[#161a27] truncate" title={r.productName || ""}>{r.productName || "-"}</div>
                            {r.category && <div className="text-[10px] text-[#8a90a2] mt-0.5 font-medium">{r.category}</div>}
                          </td>
                          <td className="p-3.5 text-right font-bold text-[#16b8a6]">{r.stock?.toLocaleString("id-ID")}</td>
                          <td className="p-3.5 text-right font-bold text-[#42a5f5]">{r.inbound?.toLocaleString("id-ID") || "0"}</td>
                          <td className="p-3.5 text-center">
                            <span className={`px-2 py-1 text-[10px] font-bold rounded-full ${st.color}`}>
                              {st.label}
                            </span>
                          </td>
                          <td className="p-3.5 text-center font-medium text-[#ef4444] bg-[#fff1ed]/10">
                            {formatDate(r.ttosDate)}
                          </td>
                          <td className="p-3.5 text-right text-[#4b5563] font-semibold">{r.forecast?.toFixed(1) || "0.0"}</td>
                          <td className="p-3.5 text-xs text-[#6b7180] max-w-[150px] truncate">
                            {r.poNo ? (
                              <div>
                                <span className="font-semibold text-[#374151]">{r.poNo}</span>
                                <div className="text-[10px] text-[#9aa0b2] mt-0.5">Tgl PO: {formatDate(r.orderedAt)}</div>
                              </div>
                            ) : "-"}
                          </td>
                        </tr>

                        {/* Expandable detailed drawer */}
                        {isOpen && (
                          <tr className="bg-[#fafbfc] border-t border-b border-[#eef0f6]">
                            <td colSpan={11} className="p-5">
                              {loadingDetail ? (
                                <div className="flex items-center justify-center py-6 gap-2">
                                  <div className="w-5 h-5 rounded-full border-2 border-t-transparent border-[#ee4d2d] animate-spin"></div>
                                  <span className="text-[11px] text-[#8a90a2] font-semibold">Mengambil detail SKU...</span>
                                </div>
                              ) : detailData[r.sku] ? (
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-[#161a27]">
                                  {/* 1. Sales per Group */}
                                  <div className="bg-white p-4 rounded-2xl border border-[#eef0f6] shadow-sm">
                                    <h4 className="text-[12px] font-bold text-[#4b5563] mb-3 flex items-center gap-1.5 border-b border-[#f3f4f6] pb-1.5">
                                      <span>🏬</span> Kontribusi Penjualan Toko (Sales Group)
                                    </h4>
                                    {detailData[r.sku].sales.length === 0 ? (
                                      <div className="text-center py-6 text-xs text-[#8a90a2]">Belum ada data penjualan toko.</div>
                                    ) : (
                                      <div className="flex flex-col gap-2.5 max-h-[180px] overflow-y-auto pr-1">
                                        {detailData[r.sku].sales.map((sl) => (
                                          <div key={sl.toko} className="text-xs">
                                            <div className="flex justify-between font-semibold text-[#4b5563] mb-1">
                                              <span>{sl.toko}</span>
                                              <span>{sl.qty} Unit</span>
                                            </div>
                                            <div className="w-full bg-[#f3f4f6] h-1.5 rounded-full overflow-hidden">
                                              <div
                                                className="bg-[#ee4d2d] h-full rounded-full"
                                                style={{
                                                  width: `${Math.min(100, (sl.qty / Math.max(...detailData[r.sku].sales.map(s => s.qty), 1)) * 100)}%`
                                                }}
                                              ></div>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>

                                  {/* 2. 5-Week Trend */}
                                  <div className="bg-white p-4 rounded-2xl border border-[#eef0f6] shadow-sm">
                                    <h4 className="text-[12px] font-bold text-[#4b5563] mb-3 flex items-center gap-1.5 border-b border-[#f3f4f6] pb-1.5">
                                      <span>📈</span> Tren Penjualan Mingguan (w0 s.d w4)
                                    </h4>
                                    {detailData[r.sku].weekly ? (
                                      <div className="grid grid-cols-5 gap-2 mt-4 text-center">
                                        {[
                                          { k: "w4", label: "W-4" },
                                          { k: "w3", label: "W-3" },
                                          { k: "w2", label: "W-2" },
                                          { k: "w1", label: "W-1" },
                                          { k: "w0", label: "W-0", highlight: true }
                                        ].map((wk) => {
                                          const val = (detailData[r.sku].weekly as any)[wk.k] || 0;
                                          const bound = detailData[r.sku].bounds.find(b => b.key === Number(wk.k.slice(1)));
                                          return (
                                            <div key={wk.k} className={`p-2 rounded-xl border ${wk.highlight ? "bg-[#fff1ed] border-[#ffddcc]" : "bg-[#f9fafb] border-[#eef0f6]"}`}>
                                              <div className={`text-[10px] font-bold ${wk.highlight ? "text-[#ee4d2d]" : "text-[#8a90a2]"}`}>{wk.label}</div>
                                              <div className="text-[14px] font-bold mt-1 text-[#161a27]">{val}</div>
                                              {bound && <div className="text-[8px] text-[#9aa0b2] mt-1 font-medium">{formatWeekBound(bound)}</div>}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <div className="text-center py-6 text-xs text-[#8a90a2]">Tren mingguan tidak tersedia.</div>
                                    )}
                                  </div>

                                  {/* 3. Shopee Metrics */}
                                  <div className="bg-white p-4 rounded-2xl border border-[#eef0f6] shadow-sm">
                                    <h4 className="text-[12px] font-bold text-[#4b5563] mb-3 flex items-center gap-1.5 border-b border-[#f3f4f6] pb-1.5">
                                      <span>📊</span> Analisa Order Shopee (30 Hari)
                                    </h4>
                                    {detailData[r.sku].shopee ? (
                                      <div className="flex flex-col gap-2.5 mt-2 text-xs">
                                        <div className="flex justify-between items-center bg-[#f9fafb] p-2 rounded-xl">
                                          <span className="font-semibold text-[#6b7180]">Total Order Shopee:</span>
                                          <span className="font-bold text-[#161a27]">{detailData[r.sku].shopee?.totalOrders} pesanan ({detailData[r.sku].shopee?.totalQty} pcs)</span>
                                        </div>
                                        <div className="flex justify-between items-center">
                                          <span className="text-[#6b7180]">Single SKU Orders:</span>
                                          <span className="font-semibold text-[#4b5563]">{detailData[r.sku].shopee?.singleOrders} order</span>
                                        </div>
                                        <div className="flex justify-between items-center">
                                          <span className="text-[#6b7180]">Multi SKU Orders:</span>
                                          <span className="font-semibold text-[#4b5563]">{detailData[r.sku].shopee?.multiOrders} order ({detailData[r.sku].shopee?.multiQty} pcs)</span>
                                        </div>
                                      </div>
                                    ) : (
                                      <div className="text-center py-6 text-xs text-[#8a90a2]">Metrik order Shopee tidak tersedia.</div>
                                    )}
                                  </div>
                                </div>
                              ) : (
                                <div className="text-center py-4 text-xs text-[#ef4444]">Gagal memuat detail data SKU.</div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between p-4 border-t border-[#eef0f6] bg-[#fafbfc] flex-wrap gap-3">
              <div className="flex items-center gap-4">
                <span className="text-[12px] text-[#8a90a2]">
                  Menampilkan <span className="font-bold text-[#4b5563]">{rows.length}</span> dari <span className="font-bold text-[#4b5563]">{total.toLocaleString("id-ID")}</span> master SKU
                </span>
                <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
                  <span>Tampilkan:</span>
                  <select
                    value={size}
                    onChange={(e) => {
                      setSize(Number(e.target.value));
                      setPage(1);
                    }}
                    className="bg-white border border-[#eef0f6] rounded px-2 py-1 text-[12px] font-semibold outline-none focus:border-[#ee4d2d] cursor-pointer"
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                  <span>produk</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                  className="px-3.5 py-1.5 text-[12px] font-bold rounded-lg border border-[#eef0f6] bg-white cursor-pointer hover:bg-[#f6f7fb] active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all"
                >
                  ◀ Prev
                </button>
                <span className="text-[12px] font-bold text-[#4b5563] px-1">
                  Halaman {page} / {totalPages}
                </span>
                <button
                  disabled={page === totalPages}
                  onClick={() => setPage(page + 1)}
                  className="px-3.5 py-1.5 text-[12px] font-bold rounded-lg border border-[#eef0f6] bg-white cursor-pointer hover:bg-[#f6f7fb] active:scale-95 disabled:opacity-40 disabled:pointer-events-none transition-all"
                >
                  Next ▶
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
