"use client";

import React, { useState, useEffect, useCallback } from "react";

interface AllProdukRow {
  sku: string;
  sku_induk: string | null;
  nama_produk: string | null;
  category: string | null;
  net_price_awal: number | null;
  net_price_detail: number | null;
  harga_awal: number | null;
  harga_diskon: number | null;
  custom_harga_diskon: number | null;
  margin_persen: number | null;
  harga_pancing: number | null;
  catalogs: any[];
  diperbarui_pada: string;
}

interface OlahDataRow {
  toko: string;
  itemId: string;
  modelId: string;
  ptag: string | null;
  sku: string | null;
  namaVariasi: string | null;
  namaProduk: string | null;
  hargaAwal: number;
  hargaDiskonDb: number;
  hargaPancing: number;
  hargaAkhirTarget: number;
  hargaTampil: number;
  selisih: number;
  sumberHarga: string | null;
  alasan: string | null;
  diperbaruiPada: string;
}

interface KomisiRow {
  sku: string;
  parentSku: string | null;
  category: string | null;
  totalSales: number;
  netPrice: number;
  diperbaruiPada: string;
  tokos: Record<string, {
    hargaSaatIni: number;
    komisiPersen: number;
    hargaJual: number;
  }>;
}

interface TokoInfo {
  username: string;
  nama: string;
}

export default function HargaPage() {
  const [tab, setTab] = useState<"all" | "olah" | "komisi">("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [size] = useState(50);
  const [sortCol, setSortCol] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  
  // Tab-specific filters
  const [selectedToko, setSelectedToko] = useState("");
  const [selectedSumber, setSelectedSumber] = useState("");
  
  // Data states
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [tokos, setTokos] = useState<TokoInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Inline edit state for Custom Harga Diskon
  const [editingDiskonSku, setEditingDiskonSku] = useState<string | null>(null);
  const [editDiskonVal, setEditDiskonVal] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const formatRp = (n: number | null | undefined) => {
    if (n === null || n === undefined) return "-";
    return "Rp" + Math.round(n).toLocaleString("id-ID");
  };

  const formatDate = (ds: string | null | undefined) => {
    if (!ds) return "-";
    try {
      const d = new Date(ds);
      return d.toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
      }).replace(",", "");
    } catch {
      return ds;
    }
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        tab,
        q,
        page: String(page),
        size: String(size),
        sort: sortCol,
        dir: sortDir
      });

      if (tab === "olah") {
        if (selectedToko) params.append("toko", selectedToko);
        if (selectedSumber) params.append("sumber", selectedSumber);
      }

      const res = await fetch(`/api/produk/harga?${params.toString()}`);
      if (res.ok) {
        const d = await res.json();
        setRows(d.rows || []);
        setTotal(d.total || 0);
        if (d.tokos) setTokos(d.tokos);
      }
    } catch (e) {
      console.error("Gagal mengambil data monitoring harga:", e);
    } finally {
      setLoading(false);
    }
  }, [tab, q, page, size, sortCol, sortDir, selectedToko, selectedSumber]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const saveCustomDiskon = async (sku: string) => {
    try {
      setIsSaving(true);
      const res = await fetch("/api/produk/harga", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "update-custom-diskon",
          sku,
          custom_harga_diskon: editDiskonVal
        })
      });
      if (res.ok) {
        setEditingDiskonSku(null);
        fetchData();
      } else {
        alert("Gagal menyimpan harga diskon");
      }
    } catch (e) {
      console.error(e);
      alert("Terjadi kesalahan.");
    } finally {
      setIsSaving(false);
    }
  };

  // Reset pagination on search / tab change
  const handleTabChange = (t: "all" | "olah" | "komisi") => {
    setTab(t);
    setRows([]);
    setQ("");
    setPage(1);
    setSortCol("");
    setSortDir("desc");
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQ(e.target.value);
    setPage(1);
  };

  const handleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
    setPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  const renderAllProdukTable = () => {
    const list = rows as AllProdukRow[];
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" style={{ minWidth: "1900px" }}>
          <thead>
            <tr className="border-b border-[#eef0f6] bg-[#f6f7fb]">
              <th onClick={() => handleSort("sku")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px]">
                SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("sku_induk")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px]">
                SKU Induk {sortCol === "sku_induk" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("nama_produk")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[230px]">
                Nama Produk {sortCol === "nama_produk" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("category")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[90px]">
                Category {sortCol === "category" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("net_price_awal")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px] text-right">
                Net Price Awal {sortCol === "net_price_awal" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("net_price_detail")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px] text-right text-[#0369a1] bg-[#e0f2fe]/40">
                Net Detail {sortCol === "net_price_detail" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("margin_persen")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[80px] text-right">
                Margin {sortCol === "margin_persen" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_awal")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Harga Awal {sortCol === "harga_awal" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_diskon")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px] text-right text-[#ee4d2d] bg-[#fff1ed]/40">
                Harga Diskon {sortCol === "harga_diskon" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_pancing")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Harga Pancing {sortCol === "harga_pancing" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              {/* Dynamic Store Headers */}
              {tokos.map((tk) => (
                <th key={tk.username} className="px-2 py-2 text-[10px] text-[#4b5563] border-l border-[#eef0f6] text-center w-[100px] bg-[#fdfdfd] font-bold">
                  <div className="truncate max-w-[90px] mx-auto text-[#ee4d2d]" title={tk.nama}>{tk.nama.replace(" Store", "").replace(" OFFICIAL STORE", "")}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f6] text-[12px]">
            {list.map((r, i) => (
              <tr key={r.sku} className="hover:bg-[#fcfdfe] transition-colors">
                <td className="px-2 py-2 font-bold text-[#161a27] align-middle">{r.sku}</td>
                <td className="px-2 py-2 align-middle">
                  <span className="px-2 py-0.5 bg-[#f0f2f5] text-[#4b5563] text-[10px] font-semibold rounded">
                    {r.sku_induk || "-"}
                  </span>
                </td>
                <td className="px-2 py-2 text-[#4b5563] truncate max-w-[230px] align-middle" title={r.nama_produk || ""}>
                  {r.nama_produk || "-"}
                </td>
                <td className="px-2 py-2 text-[#6b7180] align-middle">{r.category || "-"}</td>
                <td className="px-2 py-2 text-right text-[#4b5563] align-middle">{r.net_price_awal !== null && r.net_price_awal !== undefined ? formatRp(r.net_price_awal) : "-"}</td>
                <td className="px-2 py-2 text-right font-medium text-[#0369a1] bg-[#e0f2fe]/10 align-middle">{r.net_price_detail !== null && r.net_price_detail !== undefined ? formatRp(r.net_price_detail) : "-"}</td>
                
                {/* Margin Persen */}
                <td className="px-2 py-2 text-right font-bold align-middle">
                  {r.margin_persen !== null && r.margin_persen !== undefined ? (
                    <span className={r.margin_persen >= 0.12 ? "text-[#047857]" : r.margin_persen >= 0 ? "text-[#eab308]" : "text-[#e11d48]"}>
                      {(r.margin_persen * 100).toFixed(1)}%
                    </span>
                  ) : "-"}
                </td>

                <td className="px-2 py-2 text-right text-[#6b7180] align-middle">{r.harga_awal !== null && r.harga_awal !== undefined ? formatRp(r.harga_awal) : "-"}</td>
                
                {/* Editable Harga Diskon */}
                <td className="px-2 py-2 text-right align-middle bg-[#fff1ed]/10">
                  {editingDiskonSku === r.sku ? (
                    <div className="flex items-center justify-end gap-1">
                      <input 
                        autoFocus
                        type="number" 
                        value={editDiskonVal}
                        onChange={(e) => setEditDiskonVal(e.target.value)}
                        className="w-[70px] border border-[#ee4d2d] rounded px-1 py-0.5 text-[11px] text-right outline-none bg-white"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveCustomDiskon(r.sku);
                          if (e.key === "Escape") setEditingDiskonSku(null);
                        }}
                      />
                      <button onClick={() => saveCustomDiskon(r.sku)} disabled={isSaving} className="text-[#ee4d2d] hover:text-[#c4361e] cursor-pointer" title="Simpan">
                        {isSaving ? "⏳" : "✔️"}
                      </button>
                    </div>
                  ) : (
                    <div 
                      className="cursor-pointer group flex items-center justify-end gap-1 hover:bg-[#fff1ed] hover:text-[#ee4d2d] rounded px-1 -mx-1 transition-colors"
                      onClick={() => { setEditingDiskonSku(r.sku); setEditDiskonVal(r.custom_harga_diskon !== null ? String(r.custom_harga_diskon) : ""); }}
                      title={r.custom_harga_diskon !== null ? "Harga kustom aktif. Klik untuk mengubah" : "Harga default. Klik untuk menimpa"}
                    >
                      <span className={r.custom_harga_diskon !== null ? "text-[#ee4d2d] font-bold" : "text-[#161a27] font-semibold"}>
                        {r.harga_diskon !== null && r.harga_diskon !== undefined ? formatRp(r.harga_diskon) : "-"}
                      </span>
                      <span className="text-[9px] opacity-0 group-hover:opacity-100 transition-opacity">✏️</span>
                    </div>
                  )}
                </td>

                <td className="px-2 py-2 text-right text-[#6b7180] align-middle">{r.harga_pancing !== null && r.harga_pancing !== undefined ? formatRp(r.harga_pancing) : "-"}</td>
                
                {/* Dynamic Store Cells (Multiple Catalogs per Store) */}
                {tokos.map((tk) => {
                  const storeCats = (r.catalogs || []).filter((c: any) => c.toko === tk.nama);
                  return (
                    <td key={tk.username} className="px-2 py-1.5 border-l border-[#eef0f6] text-center text-[11px] align-middle">
                      {storeCats.length > 0 ? (
                        <div className="flex flex-col gap-1 items-center justify-center">
                          {storeCats.map((c: any, idx: number) => {
                            const price = c.harga;
                            const isRugi = r.harga_diskon !== null && r.harga_diskon > 0 && price > 0 && price < r.harga_diskon;
                            return (
                              <div 
                                key={idx} 
                                className={`px-1.5 py-0.5 rounded font-bold w-max ${isRugi ? 'bg-[#fff1ed] text-[#ee4d2d]' : 'bg-[#f8f9fa] text-[#4b5563]'} border ${isRugi ? 'border-[#ffddcc]' : 'border-transparent'}`}
                                title={`Item ID: ${c.itemId}`}
                              >
                                {formatRp(price)}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <span className="text-[#e2e4ea]">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderOlahDataTable = () => {
    const list = rows as OlahDataRow[];
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" style={{ minWidth: "1500px" }}>
          <thead>
            <tr className="border-b border-[#eef0f6] bg-[#f6f7fb]">
              <th onClick={() => handleSort("toko")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px]">
                Toko {sortCol === "toko" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("sku")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[120px]">
                SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider w-[120px]">
                Item & Model ID
              </th>
              <th onClick={() => handleSort("nama_produk")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[220px]">
                Nama Produk & Varian {sortCol === "nama_produk" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_awal")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Harga Awal {sortCol === "harga_awal" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_diskon_db")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Harga DB {sortCol === "harga_diskon_db" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_pancing")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Pancingan {sortCol === "harga_pancing" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_akhir_target")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right font-bold text-[#ee4d2d]">
                Target {sortCol === "harga_akhir_target" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_tampil")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right font-bold text-[#16b8a6]">
                Harga Real {sortCol === "harga_tampil" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("selisih")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[80px] text-right">
                Selisih {sortCol === "selisih" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("sumber_harga")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[120px]">
                Sumber {sortCol === "sumber_harga" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider w-[180px]">
                Alasan / Keterangan
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f6] text-[13px]">
            {list.map((r, i) => {
              const absSelisih = Math.abs(r.selisih);
              const hasDiff = absSelisih > 10; // abaikan rounding kecil
              
              // Badge color for Promo Label
              let badgeColor = "bg-[#f0f2f5] text-[#4b5563]";
              if (r.sumberHarga === "Promo Toko") badgeColor = "bg-[#fff1ed] text-[#ee4d2d] border border-[#ffddcc]";
              else if (r.sumberHarga === "Paket Diskon") badgeColor = "bg-[#e0f2fe] text-[#0369a1] border border-[#bae6fd]";
              else if (r.sumberHarga === "Garansi Harga Terbaik") badgeColor = "bg-[#ecfdf5] text-[#047857] border border-[#a7f3d0]";
              else if (r.sumberHarga === "Komisi Aktif") badgeColor = "bg-[#f3e8ff] text-[#6b21a8] border border-[#e9d5ff]";

              return (
                <tr key={`${r.toko}-${r.itemId}-${r.modelId}`} className="hover:bg-[#fcfdfe] transition-colors">
                  <td className="p-3.5 font-semibold text-[#161a27]">{r.toko}</td>
                  <td className="p-3.5 font-bold text-[#4b5563]">{r.sku || "-"}</td>
                  <td className="p-3.5 text-xs text-[#8a90a2]">
                    <div>{r.itemId}</div>
                    <div className="mt-0.5 text-[10px]">{r.modelId}</div>
                  </td>
                  <td className="p-3.5 text-xs max-w-[220px]">
                    <div className="font-semibold text-[#161a27] truncate" title={r.namaProduk || ""}>{r.namaProduk}</div>
                    {r.namaVariasi && <div className="text-[10px] text-[#8a90a2] mt-0.5 font-medium bg-[#f3f4f6] px-1.5 py-0.5 rounded w-max">{r.namaVariasi}</div>}
                  </td>
                  <td className="p-3.5 text-right text-[#6b7180]">{formatRp(r.hargaAwal)}</td>
                  <td className="p-3.5 text-right text-[#6b7180]">{formatRp(r.hargaDiskonDb)}</td>
                  <td className="p-3.5 text-right text-[#6b7180]">{formatRp(r.hargaPancing)}</td>
                  <td className="p-3.5 text-right font-bold text-[#ee4d2d] bg-[#fff1ed]/20">{formatRp(r.hargaAkhirTarget)}</td>
                  <td className="p-3.5 text-right font-bold text-[#16b8a6] bg-[#e7f7f4]/20">{formatRp(r.hargaTampil)}</td>
                  <td className={`p-3.5 text-right font-semibold ${hasDiff ? "text-[#e11d48]" : "text-[#8a90a2]"}`}>
                    {hasDiff ? `-${formatRp(absSelisih)}` : "0"}
                  </td>
                  <td className="p-3.5">
                    <span className={`px-2 py-1 text-[10px] font-bold rounded-full ${badgeColor}`}>
                      {r.sumberHarga || "Harga Awal"}
                    </span>
                  </td>
                  <td className="p-3.5 text-xs text-[#8a90a2] truncate max-w-[180px]" title={r.alasan || ""}>
                    {r.alasan || "-"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  };

  const renderKomisiTable = () => {
    const list = rows as KomisiRow[];
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" style={{ minWidth: "1400px" }}>
          <thead>
            <tr className="border-b border-[#eef0f6] bg-[#f6f7fb]">
              <th onClick={() => handleSort("sku")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px]">
                SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("parent_sku")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px]">
                Parent SKU {sortCol === "parent_sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("category")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[110px]">
                Category {sortCol === "category" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("total_sales")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Total Sales {sortCol === "total_sales" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("net_price")} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right">
                Net Price {sortCol === "net_price" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              
              {/* Dynamic headers for Active Tokos */}
              {tokos.map((tk) => (
                <th key={tk.username} className="p-3.5 text-[11px] text-[#4b5563] border-l border-[#eef0f6] text-center w-[160px] bg-[#fdfdfd]">
                  <div className="font-bold text-[#ee4d2d] truncate max-w-[140px] mx-auto">{tk.nama}</div>
                  <div className="text-[9px] text-[#8a90a2] mt-0.5">Saat ini | % | Jual</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f6] text-[13px]">
            {list.map((r, i) => (
              <tr key={r.sku} className="hover:bg-[#fcfdfe] transition-colors">
                <td className="p-3.5 font-bold text-[#161a27]">{r.sku}</td>
                <td className="p-3.5"><span className="px-2 py-0.5 bg-[#f0f2f5] text-[#4b5563] text-[11px] font-medium rounded">{r.parentSku || "-"}</span></td>
                <td className="p-3.5 text-[#6b7180]">{r.category || "-"}</td>
                <td className="p-3.5 text-right font-medium text-[#4b5563]">{formatRp(r.totalSales)}</td>
                <td className="p-3.5 text-right font-semibold text-[#161a27]">{formatRp(r.netPrice)}</td>
                
                {tokos.map((tk) => {
                  const tkData = r.tokos?.[tk.username];
                  return (
                    <td key={tk.username} className="p-3.5 border-l border-[#eef0f6] text-center text-xs">
                      {tkData ? (
                        <div className="flex items-center justify-between gap-1 w-full font-medium">
                          <span className="text-[#6b7180]">{Math.round(tkData.hargaSaatIni / 1000)}k</span>
                          <span className="px-1.5 py-0.5 bg-[#f3e8ff] text-[#6b21a8] text-[10px] font-bold rounded">{tkData.komisiPersen}%</span>
                          <span className="text-[#ee4d2d] font-bold">{Math.round(tkData.hargaJual / 1000)}k</span>
                        </div>
                      ) : (
                        <span className="text-[#c3c6d1]">-</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="max-w-[1400px] xl:max-w-[1650px] w-full mx-auto">
      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight flex items-center gap-2 text-[#3a3f4d]">
            <span>🏷️</span> Monitoring Harga & Komisi
          </h1>
          <div className="flex flex-col md:flex-row md:items-center gap-1 md:gap-3 mt-0.5">
            <p className="text-[13px] text-[#8a90a2]">
              Kelola data master SKU, performa diskon promo shopee, dan rate komisi affiliate.
            </p>
            {tab === "all" && rows.length > 0 && (
              <span className="text-[11px] px-2 py-0.5 bg-[#f0f2f5] text-[#6b7180] rounded-md font-medium whitespace-nowrap">
                Terakhir Sinkron: {formatDate(rows[0]?.diperbarui_pada)}
              </span>
            )}
          </div>
        </div>
        
        {/* Search */}
        <div className="relative w-full md:w-[320px] shrink-0">
          <input
            type="text"
            placeholder={
              tab === "all"
                ? "Cari SKU, SKU induk..."
                : tab === "olah"
                ? "Cari SKU, nama produk, ID..."
                : "Cari SKU, category..."
            }
            value={q}
            onChange={handleSearchChange}
            className="w-full bg-white border border-[#eef0f6] rounded-xl pl-9 pr-4 py-2 text-[13px] outline-none focus:border-[#ee4d2d] transition-all text-[#161a27]"
          />
          <span className="absolute left-3 top-[11px] text-[13px] text-[#9aa0b2]">🔍</span>
        </div>
      </div>

      {/* Tabs Row */}
      <div className="flex border-b border-[#eef0f6] mb-5 overflow-x-auto gap-6 text-[14px]">
        <button
          onClick={() => handleTabChange("all")}
          className={`pb-2.5 font-bold cursor-pointer transition-all border-b-2 whitespace-nowrap ${
            tab === "all" ? "border-[#ee4d2d] text-[#ee4d2d]" : "border-transparent text-[#6b7180] hover:text-[#161a27]"
          }`}
        >
          🗂️ All Produk (Katalog)
        </button>
        <button
          onClick={() => handleTabChange("olah")}
          className={`pb-2.5 font-bold cursor-pointer transition-all border-b-2 whitespace-nowrap ${
            tab === "olah" ? "border-[#ee4d2d] text-[#ee4d2d]" : "border-transparent text-[#6b7180] hover:text-[#161a27]"
          }`}
        >
          ⚖️ Olah Data (Price Monitor)
        </button>
        <button
          onClick={() => handleTabChange("komisi")}
          className={`pb-2.5 font-bold cursor-pointer transition-all border-b-2 whitespace-nowrap ${
            tab === "komisi" ? "border-[#ee4d2d] text-[#ee4d2d]" : "border-transparent text-[#6b7180] hover:text-[#161a27]"
          }`}
        >
          🤝 Komisi Affiliate
        </button>
      </div>

      {/* Specific Filters for Olah Data */}
      {tab === "olah" && (
        <div className="flex flex-wrap gap-3 mb-5 items-center bg-[#fdfdfd] p-3 rounded-xl border border-[#eef0f6]">
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] font-bold text-[#6b7180]">Toko:</span>
            <select
              value={selectedToko}
              onChange={(e) => { setSelectedToko(e.target.value); setPage(1); }}
              className="bg-white border border-[#eef0f6] text-[12px] rounded-lg px-2.5 py-1 text-[#4b5563] outline-none focus:border-[#ee4d2d]"
            >
              <option value="">Semua Toko</option>
              {tokos.map((tk) => (
                <option key={tk.username} value={tk.nama}>{tk.nama}</option>
              ))}
            </select>
          </div>
          
          <div className="flex items-center gap-1.5">
            <span className="text-[12px] font-bold text-[#6b7180]">Sumber Harga:</span>
            <select
              value={selectedSumber}
              onChange={(e) => { setSelectedSumber(e.target.value); setPage(1); }}
              className="bg-white border border-[#eef0f6] text-[12px] rounded-lg px-2.5 py-1 text-[#4b5563] outline-none focus:border-[#ee4d2d]"
            >
              <option value="">Semua Sumber</option>
              <option value="Harga Awal">Harga Awal</option>
              <option value="Promo Toko">Promo Toko</option>
              <option value="Paket Diskon">Paket Diskon</option>
              <option value="Garansi Harga Terbaik">Garansi Harga Terbaik</option>
              <option value="Komisi Aktif">Komisi Aktif</option>
            </select>
          </div>
        </div>
      )}

      {/* Main Card */}
      <div className="card w-full overflow-hidden">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-t-transparent border-[#ee4d2d] animate-spin"></div>
            <span className="text-[12px] text-[#8a90a2] font-semibold">Memuat data produk...</span>
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <span className="text-3xl mb-2">📥</span>
            <div className="font-bold text-[#161a27]">Tidak Ada Data</div>
            <p className="text-xs text-[#8a90a2] mt-1 max-w-[280px]">
              {q ? "Kata kunci pencarian tidak mencocokkan produk apa pun." : "Database kosong atau filter menyembunyikan semua data."}
            </p>
          </div>
        ) : (
          <>
            {tab === "all" && renderAllProdukTable()}
            {tab === "olah" && renderOlahDataTable()}
            {tab === "komisi" && renderKomisiTable()}
            
            {/* Pagination Row */}
            <div className="flex items-center justify-between p-4 border-t border-[#eef0f6] bg-[#fafbfc]">
              <span className="text-[12px] text-[#8a90a2]">
                Menampilkan <span className="font-bold text-[#4b5563]">{rows.length}</span> dari <span className="font-bold text-[#4b5563]">{total.toLocaleString("id-ID")}</span> produk
              </span>
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
