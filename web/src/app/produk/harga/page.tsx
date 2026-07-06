"use client";

import React, { useState, useEffect, useCallback } from "react";
import { tsWIB } from "@/lib/format";

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
  custom_harga_pancing: number | null;
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
  diprosesPada: string | null;
  diperbaruiPada: string;
}

interface KomisiRow {
  sku: string;
  parentSku: string | null;
  category: string | null;
  netPrice: number;
  hargaDiskon: number;
  diperbaruiPada: string;
  tokos: Record<string, {
    hargaSaatIni: number;
    komisiPersen: number;
    hargaJual: number;
    manualHargaJual: number;
  }>;
}

interface TokoInfo {
  username: string;
  nama: string;
}

interface RiwayatRow {
  id: number;
  waktu_update: string;
  sku: string;
  aksi: string;
  nilai_lama: number | null;
  nilai_baru: number | null;
  username: string;
  avatar_emoji?: string | null;
}

export default function HargaPage() {
  const [tab, setTab] = useState<"all" | "olah" | "komisi" | "riwayat">("all");
  const [jejakHarga, setJejakHarga] = useState<{ dataTerakhir: string | null; fase: Record<string, string | null> } | null>(null);
  useEffect(() => {
    fetch("/api/produk/harga/jejak", { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => setJejakHarga(j))
      .catch(() => {});
  }, []);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
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
  // Inline edit state for Custom Harga Pancing
  const [editingPancingSku, setEditingPancingSku] = useState<string | null>(null);
  const [editPancingVal, setEditPancingVal] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // Inline edit state for Komisi
  const [editingKomisi, setEditingKomisi] = useState<{sku: string, toko: string, field: 'persen'|'jual'} | null>(null);
  const [editKomisiVal, setEditKomisiVal] = useState("");

  // Mass Update State
  const [showMassModal, setShowMassModal] = useState(false);
  const [massSkuInduk, setMassSkuInduk] = useState("");
  const [massSkus, setMassSkus] = useState<any[]>([]);
  const [massSelectedSkus, setMassSelectedSkus] = useState<string[]>([]);
  const [massDiskon, setMassDiskon] = useState("");
  const [massPancing, setMassPancing] = useState("");
  const [isMassSaving, setIsMassSaving] = useState(false);
  const [isMassLoading, setIsMassLoading] = useState(false);

  // Jual settings modal states
  const [showJualModal, setShowJualModal] = useState(false);
  const [selectedJualToko, setSelectedJualToko] = useState<TokoInfo | null>(null);
  const [jualParentSku, setJualParentSku] = useState("");
  const [jualParentPrice, setJualParentPrice] = useState("");
  const [isJualSaving, setIsJualSaving] = useState(false);

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

  const saveCustomPancing = async (sku: string) => {
    try {
      setIsSaving(true);
      const res = await fetch("/api/produk/harga", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "update-custom-pancing",
          sku,
          custom_harga_pancing: editPancingVal
        })
      });
      if (res.ok) {
        setEditingPancingSku(null);
        fetchData();
      } else {
        alert("Gagal menyimpan harga pancing");
      }
    } catch (e) {
      console.error(e);
      alert("Terjadi kesalahan.");
    } finally {
      setIsSaving(false);
    }
  };

  const saveKomisiUpdate = async (sku: string, toko: string, field: 'persen'|'jual') => {
    try {
      setIsSaving(true);
      const payload: any = { action: "update-komisi-toko", sku, toko };
      if (field === 'persen') payload.komisi_persen = parseFloat(editKomisiVal);
      if (field === 'jual') payload.harga_jual = parseFloat(editKomisiVal);

      const res = await fetch("/api/produk/harga", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setEditingKomisi(null);
        fetchData();
      } else {
        alert("Gagal menyimpan data komisi");
      }
    } catch (e) {
      console.error(e);
      alert("Terjadi kesalahan.");
    } finally {
      setIsSaving(false);
    }
  };
  
  const handleMassKomisi = async (toko: string) => {
    const val = prompt(`Masukkan nilai persentase komisi massal untuk toko ${toko}:`);
    if (val === null || val.trim() === '') return;
    try {
      const res = await fetch("/api/produk/harga", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "mass-update-komisi-toko", toko, komisi_persen: val })
      });
      const d = await res.json();
      if (res.ok) { alert(d.message); fetchData(); }
      else alert(d.error);
    } catch (err: any) { alert(err.message); }
  };

  const handleMassJual = async (toko: string) => {
    const skipHigher = confirm(`Lewati (jangan turunkan harga) jika Harga Real Saat Ini sudah lebih mahal dari Harga Rekomendasi?`);
    const updates: any[] = [];
    rows.forEach((r: any) => {
      const tkData = r.tokos?.[toko];
      if (tkData) {
        const rec = Math.ceil(r.netPrice / (1 - tkData.komisiPersen / 100));
        let finalJual = rec;
        if (skipHigher && tkData.hargaSaatIni > rec) {
          finalJual = tkData.hargaSaatIni;
        }
        updates.push({ sku: r.sku, harga_jual: finalJual });
      }
    });

    try {
      const res = await fetch("/api/produk/harga", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "batch-update-jual", toko, updates })
      });
      const d = await res.json();
      if (res.ok) { alert(d.message); fetchData(); }
      else alert(d.error);
    } catch (err: any) { alert(err.message); }
  };

  const handleAddParentSku = async () => {
    const parentSku = prompt("Masukkan Parent SKU untuk ditambahkan ke Komisi:");
    if (!parentSku) return;
    try {
      const res = await fetch("/api/produk/harga", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "add-komisi-produk", parent_sku: parentSku })
      });
      const d = await res.json();
      if (res.ok) { alert(d.message); fetchData(); }
      else alert(d.error);
    } catch (err: any) { alert(err.message); }
  };

  const handleDeleteParentSku = async () => {
    const parentSku = prompt("Masukkan Parent SKU yang ingin dihapus dari Komisi:");
    if (!parentSku) return;
    try {
      const res = await fetch("/api/produk/harga", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete-komisi-produk", parent_sku: parentSku })
      });
      const d = await res.json();
      if (res.ok) { alert(d.message); fetchData(); }
      else alert(d.error);
    } catch (err: any) { alert(err.message); }
  };

  const fetchMassSkus = useCallback(async (induk: string) => {
    if (!induk) return;
    setIsMassLoading(true);
    try {
      const res = await fetch(`/api/produk/harga?tab=all&q=${encodeURIComponent(induk)}&size=1000`);
      if (res.ok) {
        const d = await res.json();
        // filter exact match
        const exact = (d.rows || []).filter((r: any) => (r.sku_induk || "").toLowerCase() === induk.toLowerCase());
        setMassSkus(exact);
        setMassSelectedSkus(exact.map((r: any) => r.sku));
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsMassLoading(false);
    }
  }, []);

  useEffect(() => {
    if (massSkuInduk) {
      const delay = setTimeout(() => fetchMassSkus(massSkuInduk), 500);
      return () => clearTimeout(delay);
    } else {
      setMassSkus([]);
      setMassSelectedSkus([]);
    }
  }, [massSkuInduk, fetchMassSkus]);

  const saveMassUpdate = async () => {
    if (massSelectedSkus.length === 0) return alert("Pilih minimal 1 SKU");
    try {
      setIsMassSaving(true);
      const payload: any = { action: "mass-update-harga", skus: massSelectedSkus };
      if (massDiskon !== "") payload.custom_harga_diskon = massDiskon;
      if (massPancing !== "") payload.custom_harga_pancing = massPancing;

      const res = await fetch("/api/produk/harga", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        setShowMassModal(false);
        fetchData();
        setMassDiskon("");
        setMassPancing("");
        setMassSkuInduk("");
      } else {
        alert("Gagal melakukan update massal");
      }
    } catch (e) {
      console.error(e);
      alert("Terjadi kesalahan.");
    } finally {
      setIsMassSaving(false);
    }
  };

  // Reset pagination on search / tab change
  const handleTabChange = (t: "all" | "olah" | "komisi" | "riwayat") => {
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
              <th onClick={() => handleSort("harga_pancing")} className="px-2 py-2 text-[11px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[100px] text-right bg-[#f0f9ff]/40">
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

                {/* Editable Harga Pancing */}
                <td className="px-2 py-2 text-right align-middle bg-[#f0f9ff]/20">
                  {editingPancingSku === r.sku ? (
                    <div className="flex items-center justify-end gap-1">
                      <input 
                        autoFocus
                        type="number" 
                        value={editPancingVal}
                        onChange={(e) => setEditPancingVal(e.target.value)}
                        className="w-[70px] border border-[#0ea5e9] rounded px-1 py-0.5 text-[11px] text-right outline-none bg-white"
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveCustomPancing(r.sku);
                          if (e.key === "Escape") setEditingPancingSku(null);
                        }}
                      />
                      <button onClick={() => saveCustomPancing(r.sku)} disabled={isSaving} className="text-[#0ea5e9] hover:text-[#0284c7] cursor-pointer" title="Simpan">
                        {isSaving ? "⏳" : "✔️"}
                      </button>
                    </div>
                  ) : (
                    <div 
                      className="cursor-pointer group flex items-center justify-end gap-1 hover:bg-[#f0f9ff] hover:text-[#0ea5e9] rounded px-1 -mx-1 transition-colors"
                      onClick={() => { setEditingPancingSku(r.sku); setEditPancingVal(r.custom_harga_pancing !== null ? String(r.custom_harga_pancing) : ""); }}
                      title={r.custom_harga_pancing !== null ? "Pancing kustom aktif. Klik untuk mengubah" : "Pancing default. Klik untuk menimpa"}
                    >
                      <span className={r.custom_harga_pancing !== null ? "text-[#0ea5e9] font-bold" : "text-[#6b7180] font-medium"}>
                        {r.harga_pancing !== null && r.harga_pancing !== undefined ? formatRp(r.harga_pancing) : "-"}
                      </span>
                      <span className="text-[9px] opacity-0 group-hover:opacity-100 transition-opacity">✏️</span>
                    </div>
                  )}
                </td>
                
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
              <th className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider w-[140px]">
                Terakhir Diproses
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
                  <td className="p-3.5 text-xs text-[#8a90a2] whitespace-nowrap">
                    {r.diprosesPada
                      ? new Date(r.diprosesPada).toLocaleString("id-ID", {
                          day: "2-digit", month: "short", year: "2-digit",
                          hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta",
                        }) + " WIB"
                      : "-"}
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
              <th onClick={() => handleSort("sku")} style={{ left: 0, width: 170, minWidth: 170 }} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors sticky z-20 bg-[#f6f7fb]">
                SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("parent_sku")} style={{ left: 170, width: 110, minWidth: 110 }} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors sticky z-20 bg-[#f6f7fb]">
                Parent {sortCol === "parent_sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("category")} style={{ left: 280, width: 90, minWidth: 90 }} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors sticky z-20 bg-[#f6f7fb]">
                Category {sortCol === "category" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("net_price")} style={{ left: 370, width: 100, minWidth: 100 }} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors sticky z-20 bg-[#f6f7fb] text-right">
                Net Price {sortCol === "net_price" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("harga_diskon")} style={{ left: 470, width: 110, minWidth: 110 }} className="p-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors sticky z-20 bg-[#f6f7fb] text-right shadow-[inset_-2px_0_0_#eef0f6]">
                Harga Diskon {sortCol === "harga_diskon" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              
              {/* Dynamic headers for Active Tokos */}
              {tokos.map((tk) => (
                <th key={tk.username} className="p-3.5 text-[11px] text-[#4b5563] border-l border-[#eef0f6] text-center w-[160px] bg-[#fdfdfd] relative group">
                  <div className="font-bold text-[#ee4d2d] truncate max-w-[140px] mx-auto">{tk.nama}</div>
                  <div className="text-[9px] text-[#8a90a2] mt-0.5 flex flex-col justify-center gap-1 items-center">
                     <div className="flex gap-2.5">
                       <span title="Harga Real Saat Ini (dari Olah Data)">Saat ini</span> 
                       <span className="cursor-pointer hover:text-[#6b21a8] text-[#6b21a8] font-bold transition-colors" onClick={() => handleMassKomisi(tk.username)} title={`Set Komisi Massal ${tk.nama}`}>⚙️ Rkm (%)</span> 
                       <span className="cursor-pointer hover:text-[#ee4d2d] text-[#ee4d2d] font-bold transition-colors" onClick={() => { setSelectedJualToko(tk); setShowJualModal(true); }} title={`Pengaturan Jual Massal ${tk.nama}`}>⚙️ Jual</span>
                     </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f6] text-[13px]">
            {list.map((r, i) => (
              <tr key={r.sku} className="hover:bg-[#fcfdfe] transition-colors">
                <td style={{ left: 0 }} className="p-3.5 font-bold text-[#161a27] sticky z-10 bg-white group-hover:bg-[#fcfdfe]">{r.sku}</td>
                <td style={{ left: 170 }} className="p-3.5 sticky z-10 bg-white group-hover:bg-[#fcfdfe]"><span className="px-2 py-0.5 bg-[#f0f2f5] text-[#4b5563] text-[11px] font-medium rounded">{r.parentSku || "-"}</span></td>
                <td style={{ left: 280 }} className="p-3.5 text-[#6b7180] sticky z-10 bg-white group-hover:bg-[#fcfdfe]">{r.category || "-"}</td>
                <td style={{ left: 370 }} className="p-3.5 text-right font-semibold text-[#161a27] sticky z-10 bg-white group-hover:bg-[#fcfdfe]">{formatRp(r.netPrice)}</td>
                <td style={{ left: 470 }} className="p-3.5 text-right font-semibold text-[#ee4d2d] sticky z-10 bg-white group-hover:bg-[#fcfdfe] shadow-[inset_-2px_0_0_#eef0f6]">{formatRp(r.hargaDiskon)}</td>
                
                {tokos.map((tk) => {
                  const tkData = r.tokos?.[tk.username];
                  return (
                    <td key={tk.username} className="p-3.5 border-l border-[#eef0f6] text-center text-xs align-middle">
                      {tkData ? (
                        <div className="flex items-center justify-between gap-1 w-full font-medium">
                          <span className="text-[#6b7180]">{tkData.hargaSaatIni > 0 ? formatRp(tkData.hargaSaatIni) : '-'}</span>
                          
                          {/* Komisi % Inline Edit */}
                          {editingKomisi?.sku === r.sku && editingKomisi?.toko === tk.username && editingKomisi?.field === 'persen' ? (
                            <div className="flex items-center gap-0.5">
                              <input 
                                autoFocus type="number" value={editKomisiVal} 
                                onChange={(e) => setEditKomisiVal(e.target.value)}
                                onKeyDown={(e) => { if(e.key==='Enter') saveKomisiUpdate(r.sku, tk.username, 'persen'); if(e.key==='Escape') setEditingKomisi(null); }}
                                className="w-[35px] border border-[#6b21a8] rounded px-0.5 py-0.5 text-[9px] text-center outline-none bg-white"
                              />
                            </div>
                          ) : (
                            <span 
                              onClick={() => { setEditingKomisi({sku: r.sku, toko: tk.username, field: 'persen'}); setEditKomisiVal(String(tkData.komisiPersen)); }}
                              className="px-1.5 py-0.5 bg-[#f3e8ff] text-[#6b21a8] hover:bg-[#e9d5ff] cursor-pointer transition-colors text-[10px] font-bold rounded whitespace-nowrap"
                              title={`Edit persentase komisi (Saat ini: ${tkData.komisiPersen}%)`}
                            >
                              {formatRp(Math.ceil(r.netPrice / (1 - tkData.komisiPersen / 100)))} ({tkData.komisiPersen}%)
                            </span>
                          )}

                          {/* Harga Jual Inline Edit */}
                          {editingKomisi?.sku === r.sku && editingKomisi?.toko === tk.username && editingKomisi?.field === 'jual' ? (
                            <div className="flex items-center gap-0.5">
                              <input 
                                autoFocus type="number" value={editKomisiVal} 
                                onChange={(e) => setEditKomisiVal(e.target.value)}
                                onKeyDown={(e) => { if(e.key==='Enter') saveKomisiUpdate(r.sku, tk.username, 'jual'); if(e.key==='Escape') setEditingKomisi(null); }}
                                className="w-[55px] border border-[#ee4d2d] rounded px-0.5 py-0.5 text-[10px] text-right outline-none bg-white"
                              />
                            </div>
                          ) : (
                            <span 
                              onClick={() => { setEditingKomisi({sku: r.sku, toko: tk.username, field: 'jual'}); setEditKomisiVal(tkData.manualHargaJual > 0 ? String(tkData.manualHargaJual) : String(Math.ceil(r.netPrice / (1 - tkData.komisiPersen / 100)))); }}
                              className={`font-bold cursor-pointer whitespace-nowrap ${tkData.manualHargaJual > 0 ? 'text-[#0ea5e9] hover:underline' : 'text-[#c3c6d1] hover:text-[#0ea5e9]'}`}
                              title={tkData.manualHargaJual > 0 ? "Harga manual. Klik untuk edit" : "Belum diset manual. Klik untuk set"}
                            >
                              {tkData.manualHargaJual > 0 ? formatRp(tkData.manualHargaJual) : '-'}
                            </span>
                          )}
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

  const renderRiwayatTable = () => {
    const list = rows as RiwayatRow[];
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse" style={{ minWidth: "1000px" }}>
          <thead>
            <tr className="border-b border-[#eef0f6] bg-[#f6f7fb]">
              <th onClick={() => handleSort("waktu_update")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[180px]">
                Waktu {sortCol === "waktu_update" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("username")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px]">
                Pengguna {sortCol === "username" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("aksi")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[180px]">
                Aksi {sortCol === "aksi" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("sku")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px]">
                SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("nilai_lama")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px] text-right">
                Nilai Lama {sortCol === "nilai_lama" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
              <th onClick={() => handleSort("nilai_baru")} className="px-4 py-3.5 text-[12px] font-bold text-[#6b7180] tracking-wider cursor-pointer hover:bg-[#eaecef] transition-colors w-[150px] text-right">
                Nilai Baru {sortCol === "nilai_baru" ? (sortDir === "asc" ? "▲" : "▼") : ""}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eef0f6] text-[13px]">
            {list.map((r, i) => (
              <tr key={r.id || i} className="hover:bg-[#fcfdfe] transition-colors">
                <td className="px-4 py-3 text-[#8a90a2] font-medium align-middle">{formatDate(r.waktu_update)}</td>
                <td className="px-4 py-3 align-middle">
                  <div className="flex items-center gap-1.5">
                    {r.avatar_emoji ? (
                      <span className="text-[14px] w-5 h-5 flex items-center justify-center">
                        {r.avatar_emoji}
                      </span>
                    ) : (
                      <span className="w-5 h-5 rounded-full bg-[#f3e8ff] flex items-center justify-center text-[10px] font-bold text-[#6b21a8]">
                        {r.username.substring(0, 1).toUpperCase()}
                      </span>
                    )}
                    <span className="font-bold text-[#4b5563]">{r.username}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-[#4b5563] font-semibold align-middle">
                  <span className={`px-2 py-1 rounded-md text-[11px] ${r.aksi.includes('Diskon') ? 'bg-[#fff1ed] text-[#ee4d2d]' : 'bg-[#f0f9ff] text-[#0ea5e9]'}`}>
                    {r.aksi}
                  </span>
                </td>
                <td className="px-4 py-3 font-bold text-[#161a27] align-middle">{r.sku}</td>
                <td className="px-4 py-3 text-right text-[#9aa0b2] line-through align-middle">
                  {r.nilai_lama !== null && r.nilai_lama !== undefined ? formatRp(r.nilai_lama) : "-"}
                </td>
                <td className="px-4 py-3 text-right font-bold text-[#047857] align-middle bg-[#ecfdf5]/20">
                  {r.nilai_baru !== null && r.nilai_baru !== undefined ? formatRp(r.nilai_baru) : "-"}
                </td>
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
          {jejakHarga && (
            <p className="text-[11px] text-[#b4b9c6] mt-1 leading-relaxed">
              🔄 Data terakhir: <span className="text-[#8a90a2] font-medium">{tsWIB(jejakHarga.dataTerakhir)}</span>
              {"  ·  "}Grab: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.grab)}</span>
              {"  ·  "}HPP: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.hpp)}</span>
              {"  ·  "}Rubah Harga: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.rubah_harga)}</span>
              {"  ·  "}Verifikasi: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.verifikasi)}</span>
              {"  ·  "}Duplikat Promo: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.duplikat_promo)}</span>
              {"  ·  "}Kampanye: <span className="text-[#8a90a2]">{tsWIB(jejakHarga.fase.kampanye)}</span>
            </p>
          )}
          <div className="flex flex-col md:flex-row md:items-center gap-1 md:gap-3 mt-0.5">
            <p className="text-[13px] text-[#8a90a2]">
              Kelola data master SKU, performa diskon promo shopee, dan rate komisi affiliate.
            </p>
            {tab === "komisi" && (
            <div className="flex gap-2">
              <button
                onClick={handleAddParentSku}
                className="px-3.5 py-1.5 text-xs font-semibold bg-[#8b5cf6] text-white rounded hover:bg-[#7c3aed] transition-colors shadow-sm flex items-center gap-1.5"
              >
                <span>➕ Tambah by Parent SKU</span>
              </button>
              <button
                onClick={handleDeleteParentSku}
                className="px-3.5 py-1.5 text-xs font-semibold bg-white border border-[#e11d48] text-[#e11d48] rounded hover:bg-[#fff1f2] transition-colors shadow-sm flex items-center gap-1.5"
              >
                <span>🗑️ Hapus by Parent SKU</span>
              </button>
            </div>
          )}
          
          {tab === "all" && rows.length > 0 && (
              <span className="text-[11px] px-2 py-0.5 bg-[#f0f2f5] text-[#6b7180] rounded-md font-medium whitespace-nowrap">
                Terakhir Sinkron: {formatDate(rows[0]?.diperbarui_pada)}
              </span>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-3 w-full md:w-auto shrink-0">
          {tab === "all" && (
            <button 
              onClick={() => setShowMassModal(true)}
              className="bg-[#161a27] text-white px-4 py-2 rounded-xl text-[13px] font-bold hover:bg-[#2c3245] transition-colors whitespace-nowrap shadow-sm flex items-center gap-2"
            >
              <span>✏️</span> Update Massal
            </button>
          )}
          
          {/* Search */}
          <div className="relative w-full md:w-[280px]">
            <input
              type="text"
              placeholder={
                tab === "all"
                ? "Cari SKU, SKU induk..."
                : tab === "olah"
                ? "Cari SKU, nama produk, ID..."
                : tab === "komisi"
                ? "Cari SKU, category..."
                : "Cari SKU, pengguna, aksi..."
              }
              value={q}
              onChange={handleSearchChange}
              className="w-full bg-white border border-[#eef0f6] rounded-xl pl-9 pr-4 py-2 text-[13px] outline-none focus:border-[#ee4d2d] transition-all text-[#161a27]"
            />
            <span className="absolute left-3 top-[11px] text-[13px] text-[#9aa0b2]">🔍</span>
          </div>
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
        <button
          onClick={() => handleTabChange("riwayat")}
          className={`pb-2.5 font-bold cursor-pointer transition-all border-b-2 whitespace-nowrap ${
            tab === "riwayat" ? "border-[#ee4d2d] text-[#ee4d2d]" : "border-transparent text-[#6b7180] hover:text-[#161a27]"
          }`}
        >
          📜 Riwayat Update
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
            {tab === "riwayat" && renderRiwayatTable()}
            
            {/* Pagination Row */}
            <div className="flex items-center justify-between p-4 border-t border-[#eef0f6] bg-[#fafbfc] flex-wrap gap-3">
              <div className="flex items-center gap-4">
                <span className="text-[12px] text-[#8a90a2]">
                  Menampilkan <span className="font-bold text-[#4b5563]">{rows.length}</span> dari <span className="font-bold text-[#4b5563]">{total.toLocaleString("id-ID")}</span> produk
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

      {/* Mass Update Modal */}
      {showMassModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl w-full max-w-[600px] shadow-2xl flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-200">
            <div className="p-5 border-b border-[#eef0f6] flex justify-between items-center bg-[#fcfdfe] rounded-t-2xl">
              <h2 className="text-[16px] font-extrabold text-[#161a27] flex items-center gap-2">
                <span>✏️</span> Update Massal Harga
              </h2>
              <button onClick={() => setShowMassModal(false)} className="text-[#8a90a2] hover:bg-[#f0f2f5] rounded-full w-8 h-8 flex items-center justify-center font-bold text-xl leading-none transition-colors">&times;</button>
            </div>
            
            <div className="p-5 flex-1 overflow-y-auto">
              <div className="mb-5">
                <label className="block text-[12px] font-bold text-[#4b5563] mb-1.5">1. Filter SKU Induk</label>
                <input 
                  type="text" 
                  value={massSkuInduk} 
                  onChange={e => setMassSkuInduk(e.target.value)} 
                  placeholder="Ketik SKU Induk untuk mencari varian..." 
                  className="w-full border border-[#eef0f6] bg-[#f8f9fa] rounded-xl px-4 py-2.5 text-[13px] font-medium outline-none focus:border-[#ee4d2d] focus:bg-white transition-all" 
                />
              </div>
              
              {massSkuInduk && (
                <div className="mb-6">
                  <div className="flex justify-between items-center mb-2">
                    <label className="text-[12px] font-bold text-[#4b5563]">2. Pilih SKU yang Akan Diupdate ({massSelectedSkus.length}/{massSkus.length})</label>
                    {massSkus.length > 0 && (
                      <button 
                        onClick={() => setMassSelectedSkus(massSelectedSkus.length === massSkus.length ? [] : massSkus.map(r=>r.sku))} 
                        className="text-[11px] text-[#0369a1] hover:underline font-bold px-2 py-0.5 bg-[#e0f2fe]/50 rounded"
                      >
                        {massSelectedSkus.length === massSkus.length ? "Deselect All" : "Select All"}
                      </button>
                    )}
                  </div>
                  
                  {isMassLoading ? (
                    <div className="text-[12px] text-[#8a90a2] py-8 text-center flex flex-col items-center gap-2">
                      <div className="w-5 h-5 rounded-full border-2 border-t-transparent border-[#0369a1] animate-spin"></div>
                      Mencari SKU...
                    </div>
                  ) : massSkus.length === 0 ? (
                    <div className="text-[12px] text-[#8a90a2] py-6 text-center border-2 border-dashed border-[#eef0f6] rounded-xl bg-[#fafbfc]">
                      Tidak ada produk varian dengan SKU Induk "<span className="font-bold text-[#4b5563]">{massSkuInduk}</span>"
                    </div>
                  ) : (
                    <div className="border border-[#eef0f6] rounded-xl max-h-[180px] overflow-y-auto divide-y divide-[#eef0f6]">
                      {massSkus.map((r) => (
                        <label key={r.sku} className="flex items-center gap-3 px-3 py-2.5 hover:bg-[#fcfdfe] cursor-pointer text-[12px] transition-colors">
                          <input 
                            type="checkbox" 
                            checked={massSelectedSkus.includes(r.sku)} 
                            onChange={(e) => {
                              if(e.target.checked) setMassSelectedSkus([...massSelectedSkus, r.sku]);
                              else setMassSelectedSkus(massSelectedSkus.filter(s => s !== r.sku));
                            }} 
                            className="accent-[#ee4d2d] w-[18px] h-[18px] cursor-pointer rounded-sm" 
                          />
                          <div className="flex flex-col flex-1 truncate">
                            <span className="font-bold text-[#161a27]">{r.sku}</span>
                            <span className="text-[#8a90a2] text-[10px] truncate" title={r.nama_produk}>{r.nama_produk}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-4">
                <div className="flex-1 bg-[#fff1ed]/30 p-3.5 rounded-xl border border-[#ffddcc]/50">
                  <label className="block text-[12px] font-bold text-[#ee4d2d] mb-1.5">3. Harga Diskon Baru</label>
                  <input 
                    type="number" 
                    value={massDiskon} 
                    onChange={e => setMassDiskon(e.target.value)} 
                    placeholder="Biarkan kosong jika tetap" 
                    className="w-full border border-[#ffddcc] bg-white rounded-lg px-3 py-2 text-[13px] outline-none focus:border-[#ee4d2d] focus:ring-1 focus:ring-[#ee4d2d]" 
                  />
                </div>
                <div className="flex-1 bg-[#f0f9ff]/50 p-3.5 rounded-xl border border-[#bae6fd]/50">
                  <label className="block text-[12px] font-bold text-[#0ea5e9] mb-1.5">Harga Pancing Baru</label>
                  <input 
                    type="number" 
                    value={massPancing} 
                    onChange={e => setMassPancing(e.target.value)} 
                    placeholder="Biarkan kosong jika tetap" 
                    className="w-full border border-[#bae6fd] bg-white rounded-lg px-3 py-2 text-[13px] outline-none focus:border-[#0ea5e9] focus:ring-1 focus:ring-[#0ea5e9]" 
                  />
                </div>
              </div>
            </div>
            
            <div className="p-4 border-t border-[#eef0f6] flex justify-end gap-3 bg-[#fdfdfd] rounded-b-2xl">
              <button 
                onClick={() => setShowMassModal(false)} 
                className="px-5 py-2.5 text-[13px] font-bold text-[#6b7180] hover:bg-[#eaecef] hover:text-[#161a27] rounded-xl transition-colors cursor-pointer"
              >
                Batal
              </button>
              <button 
                onClick={saveMassUpdate} 
                disabled={isMassSaving || massSelectedSkus.length === 0} 
                className="px-5 py-2.5 text-[13px] font-bold bg-[#ee4d2d] text-white hover:bg-[#d73f22] rounded-xl shadow-md shadow-[#ee4d2d]/20 transition-all disabled:opacity-50 disabled:shadow-none cursor-pointer flex items-center gap-2"
              >
                {isMassSaving ? "Menyimpan..." : "✓ Terapkan Massal"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Jual Settings Modal */}
      {showJualModal && selectedJualToko && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl w-full max-w-[500px] shadow-2xl flex flex-col max-h-[90vh] animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="p-5 border-b border-[#eef0f6] flex justify-between items-center bg-[#fcfdfe] rounded-t-2xl">
              <h2 className="text-[16px] font-extrabold text-[#161a27] flex items-center gap-2">
                <span>⚙️</span> Pengaturan Jual - {selectedJualToko.nama}
              </h2>
              <button 
                onClick={() => { setShowJualModal(false); setJualParentSku(""); setJualParentPrice(""); }} 
                className="text-[#8a90a2] hover:bg-[#f0f2f5] rounded-full w-8 h-8 flex items-center justify-center font-bold text-xl leading-none transition-colors"
              >
                &times;
              </button>
            </div>
            
            {/* Body */}
            <div className="p-5 flex-1 overflow-y-auto space-y-6">
              {/* Option 1: Tambah Massal (ikut rekomendasi) */}
              <div className="bg-[#fff1ed]/30 p-4 rounded-xl border border-[#ffddcc]/50">
                <h3 className="text-xs font-bold text-[#ee4d2d] mb-1">1. Tambah Massal (Ikuti Rekomendasi)</h3>
                <p className="text-[11px] text-[#6b7180] mb-3">Set harga jual massal untuk semua produk di toko ini mengikuti harga rekomendasi (Net Price / (1 - Komisi%)).</p>
                <button
                  onClick={async () => {
                    setShowJualModal(false);
                    await handleMassJual(selectedJualToko.username);
                  }}
                  className="w-full py-2 bg-[#ee4d2d] hover:bg-[#d73f22] text-white font-bold text-[12px] rounded-lg transition-colors cursor-pointer text-center"
                >
                  🚀 Terapkan Tambah Massal
                </button>
              </div>

              {/* Option 2: Edit Harga per SKU Induk */}
              <div className="bg-[#f3e8ff]/30 p-4 rounded-xl border border-[#e9d5ff]/50">
                <h3 className="text-xs font-bold text-[#6b21a8] mb-1">2. Edit Harga per SKU Induk</h3>
                <p className="text-[11px] text-[#6b7180] mb-3">Set harga jual manual untuk semua varian SKU yang memiliki SKU Induk yang sama.</p>
                
                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-semibold text-[#4b5563] mb-1">SKU Induk / Parent SKU</label>
                    <input 
                      type="text" 
                      value={jualParentSku} 
                      onChange={e => setJualParentSku(e.target.value)} 
                      placeholder="Contoh: BSCR, BSCT, TRC..." 
                      className="w-full border border-[#eef0f6] bg-white rounded-lg px-3 py-2 text-[12px] font-medium outline-none focus:border-[#6b21a8] transition-all" 
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-[#4b5563] mb-1">Harga Jual Baru (Rp)</label>
                    <input 
                      type="number" 
                      value={jualParentPrice} 
                      onChange={e => setJualParentPrice(e.target.value)} 
                      placeholder="Masukkan nominal harga jual..." 
                      className="w-full border border-[#eef0f6] bg-white rounded-lg px-3 py-2 text-[12px] font-medium outline-none focus:border-[#6b21a8] transition-all" 
                    />
                  </div>
                  <button
                    onClick={async () => {
                      if (!jualParentSku.trim()) return alert("SKU Induk wajib diisi");
                      if (!jualParentPrice.trim()) return alert("Harga Jual wajib diisi");
                      
                      try {
                        setIsJualSaving(true);
                        const res = await fetch("/api/produk/harga", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            action: "update-jual-parent-sku",
                            toko: selectedJualToko.username,
                            parent_sku: jualParentSku,
                            harga_jual: jualParentPrice
                          })
                        });
                        const d = await res.json();
                        if (res.ok) {
                          alert(d.message);
                          setShowJualModal(false);
                          setJualParentSku("");
                          setJualParentPrice("");
                          fetchData();
                        } else {
                          alert(d.error || "Gagal mengupdate harga per SKU Induk");
                        }
                      } catch (err: any) {
                        alert(err.message);
                      } finally {
                        setIsJualSaving(false);
                      }
                    }}
                    disabled={isJualSaving}
                    className="w-full py-2 bg-[#6b21a8] hover:bg-[#581c87] text-white font-bold text-[12px] rounded-lg transition-colors cursor-pointer disabled:opacity-50 text-center"
                  >
                    {isJualSaving ? "Memproses..." : "✏️ Update Harga SKU Induk"}
                  </button>
                </div>
              </div>

              {/* Option 3: Hapus Massal */}
              <div className="bg-[#fff1f2]/50 p-4 rounded-xl border border-[#ffe4e6]/50">
                <h3 className="text-xs font-bold text-[#e11d48] mb-1">3. Hapus Massal Harga Jual</h3>
                <p className="text-[11px] text-[#6b7180] mb-3">Hapus semua harga jual manual di toko ini. Harga akan otomatis kembali mengikuti Harga Rekomendasi.</p>
                <button
                  onClick={async () => {
                    const confirmDelete = confirm(`Apakah Anda yakin ingin menghapus SEMUA harga jual manual untuk toko ${selectedJualToko.nama}? Harga akan kembali ke rekomendasi.`);
                    if (!confirmDelete) return;
                    
                    try {
                      setIsJualSaving(true);
                      const res = await fetch("/api/produk/harga", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          action: "mass-delete-jual-toko",
                          toko: selectedJualToko.username
                        })
                      });
                      const d = await res.json();
                      if (res.ok) {
                        alert(d.message);
                        setShowJualModal(false);
                        fetchData();
                      } else {
                        alert(d.error || "Gagal menghapus harga massal");
                      }
                    } catch (err: any) {
                      alert(err.message);
                    } finally {
                      setIsJualSaving(false);
                    }
                  }}
                  disabled={isJualSaving}
                  className="w-full py-2 bg-white border border-[#e11d48] text-[#e11d48] hover:bg-[#fff1f2] font-bold text-[12px] rounded-lg transition-colors cursor-pointer disabled:opacity-50 text-center"
                >
                  {isJualSaving ? "Memproses..." : "🗑️ Hapus Semua Harga Jual Manual"}
                </button>
              </div>
            </div>
            
            {/* Footer */}
            <div className="p-4 border-t border-[#eef0f6] flex justify-end bg-[#fdfdfd] rounded-b-2xl">
              <button 
                onClick={() => { setShowJualModal(false); setJualParentSku(""); setJualParentPrice(""); }} 
                className="px-5 py-2.5 text-[13px] font-bold text-[#6b7180] hover:bg-[#eaecef] hover:text-[#161a27] rounded-xl transition-colors cursor-pointer"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
