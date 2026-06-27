"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";

interface ProductAcuan {
  id: number;
  market: string;
  sku: string;
  nama_produk: string;
  tgl_upload: string;
  gambar_produk: string;
  harga: string;
  link_produk: string;
  skip_itemid: string;
  tanggal_update: string | null;
  product_category: string;
  total_stock_parent_sku: number;
  total_stock_available_po_parent_sku: number;
  sales_per_toko: Record<string, number>;
  total_sales_shopee: number;
  total_sales_parent_sku: number;
}

interface CompetitorDetail {
  id: number;
  tipe: "manual" | "similar";
  rank: number;
  url: string;
  nama_toko: string;
  harga: string;
  terjual: number;
  gambar: string;
  diambil_pada: string;
}

interface DatabaseLink {
  sku: string;
  status: string;
  total_sales_parent_sku: number;
  links: Record<string, { item_id: string; url: string; search_similar_url: string }>;
  diperbarui_pada: string;
}

export default function RisetKompetitorPage() {
  const router = useRouter();
  
  // State lists
  const [products, setProducts] = useState<ProductAcuan[]>([]);
  const [pagination, setPagination] = useState({ total: 0, page: 1, limit: 15, pages: 1 });
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [search, setSearch] = useState("");
  const [market, setMarket] = useState("");
  const [page, setPage] = useState(1);
  
  // Selected detail
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailProduct, setDetailProduct] = useState<ProductAcuan | null>(null);
  const [competitors, setCompetitors] = useState<CompetitorDetail[]>([]);
  const [dbLink, setDbLink] = useState<DatabaseLink | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [activeDetailTab, setActiveDetailTab] = useState<"similar" | "manual">("similar");
  
  // Modal Edit Manual Links
  const [showEditModal, setShowEditModal] = useState(false);
  const [manualLinksInput, setManualLinksInput] = useState("");
  const [savingManual, setSavingManual] = useState(false);

  // Fetch product list
  useEffect(() => {
    async function fetchList() {
      setLoading(true);
      try {
        const query = new URLSearchParams({
          market,
          search,
          page: String(page),
          limit: "15"
        });
        const res = await fetch(`/api/riset-kompetitor?${query.toString()}`);
        const json = await res.json();
        if (json.success) {
          setProducts(json.data);
          setPagination(json.pagination);
        }
      } catch (err) {
        console.error("Gagal memuat list riset:", err);
      } finally {
        setLoading(false);
      }
    }

    const timer = setTimeout(() => {
      fetchList();
    }, 300); // debounce search input

    return () => clearTimeout(timer);
  }, [market, search, page]);

  // Fetch product details on selection
  useEffect(() => {
    if (!selectedId) {
      setDetailProduct(null);
      setCompetitors([]);
      setDbLink(null);
      return;
    }

    async function fetchDetails() {
      setLoadingDetails(true);
      try {
        const res = await fetch(`/api/riset-kompetitor/${selectedId}`);
        const json = await res.json();
        if (json.success) {
          setDetailProduct(json.data.product);
          setCompetitors(json.data.competitors);
          setDbLink(json.data.databaseLink);
          
          // Set default edit text input
          const manualCompetitors = json.data.competitors.filter((c: any) => c.tipe === "manual");
          const urls = manualCompetitors.map((c: any) => c.url).filter(Boolean).join("\n");
          setManualLinksInput(urls);
        }
      } catch (err) {
        console.error("Gagal memuat detail kompetitor:", err);
      } finally {
        setLoadingDetails(false);
      }
    }

    fetchDetails();
  }, [selectedId]);

  // Handle Save Manual Links
  const handleSaveManualLinks = async () => {
    if (!selectedId) return;
    setSavingManual(true);
    try {
      const urls = manualLinksInput.split("\n").map(u => u.trim()).filter(Boolean);
      const res = await fetch(`/api/riset-kompetitor/${selectedId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ manualUrls: urls })
      });
      const json = await res.json();
      if (json.success) {
        alert(json.message || "Link manual berhasil disimpan!");
        setShowEditModal(false);
        // Refresh details
        const detailsRes = await fetch(`/api/riset-kompetitor/${selectedId}`);
        const detailsJson = await detailsRes.json();
        if (detailsJson.success) {
          setDetailProduct(detailsJson.data.product);
          setCompetitors(detailsJson.data.competitors);
        }
      } else {
        alert(json.error || "Gagal menyimpan link");
      }
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setSavingManual(false);
    }
  };

  const activeCompetitors = competitors.filter(c => c.tipe === activeDetailTab);

  // Formatting utils
  const formatRp = (val: string | number) => {
    if (typeof val === "number") {
      return `Rp${val.toLocaleString("id-ID")}`;
    }
    return String(val || "Rp0");
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Belum di-scrape";
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
    } catch (e) {
      return String(dateStr);
    }
  };

  // Helper to get image from formula or string
  const getImageUrl = (url: string) => {
    if (!url) return "/no-image.png";
    return url;
  };

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto p-1 text-[#3a3f4d]">
      
      {/* Title Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight">Riset Kompetitor 🔍</h1>
          <p className="text-[13px] text-[#8a90a2] mt-0.5">
            Analisis dan perbandingan produk toko kita dengan kompetitor Shopee (WP, Best Seller, & PL Market).
          </p>
        </div>
      </div>

      {/* Main Grid Content */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Side: Product List Table */}
        <div className={`card bg-white border border-[#eef0f6] rounded-2xl shadow-sm p-5 transition-all ${selectedId ? "lg:col-span-6 xl:col-span-5" : "lg:col-span-12"}`}>
          
          {/* Filters Area */}
          <div className="flex flex-col sm:flex-row gap-3 mb-5 justify-between items-stretch">
            {/* Search input */}
            <div className="relative flex-1">
              <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                🔍
              </span>
              <input
                type="text"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                placeholder="Cari SKU atau nama produk..."
                className="w-full pl-9 pr-4 py-2 border border-[#eef0f6] rounded-xl text-[13px] bg-[#f8f9fc] focus:outline-none focus:border-[#ee4d2d] focus:bg-white transition-colors"
              />
            </div>
            
            {/* Market Tabs */}
            <div className="flex gap-1 bg-[#f0f2f7] p-1 rounded-xl text-[12px] font-bold shrink-0">
              {[
                { label: "Semua", value: "" },
                { label: "WP", value: "WP" },
                { label: "Best Seller", value: "Best Seller" },
                { label: "PL", value: "PL" }
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => { setMarket(opt.value); setPage(1); }}
                  className={`px-3.5 py-1.5 rounded-lg cursor-pointer transition-all ${
                    market === opt.value 
                      ? "bg-white text-[#ee4d2d] shadow-sm" 
                      : "text-[#6b7180] hover:text-[#3a3f4d]"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto min-w-0">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-[#f0f2f7] text-[#8a90a2] font-semibold">
                  <th className="py-3 px-2 w-[80px]">Gambar</th>
                  <th className="py-3 px-2">Info SKU</th>
                  <th className="py-3 px-2 text-right">Sales</th>
                  <th className="py-3 px-2 text-center">Status Update</th>
                  <th className="py-3 px-2 w-[70px] text-center">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-[#8a90a2]">
                      <div className="flex flex-col items-center gap-2">
                        <span className="w-8 h-8 rounded-full border-3 border-[#fff1ed] border-t-[#ee4d2d] animate-spin" />
                        <span>Memuat data riset...</span>
                      </div>
                    </td>
                  </tr>
                ) : products.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-[#8a90a2]">
                      Tidak ada produk riset yang cocok.
                    </td>
                  </tr>
                ) : (
                  products.map((p) => {
                    const isSelected = selectedId === p.id;
                    const dateOld = p.tanggal_update 
                      ? (new Date().getTime() - new Date(p.tanggal_update).getTime()) / (1000 * 3600 * 24) >= 10
                      : true;
                    
                    return (
                      <tr 
                        key={p.id}
                        onClick={() => setSelectedId(p.id)}
                        className={`border-b border-[#f8f9fc] hover:bg-[#fff1ed]/20 transition-all cursor-pointer ${
                          isSelected ? "bg-[#fff1ed]/40 hover:bg-[#fff1ed]/40" : ""
                        }`}
                      >
                        {/* Image */}
                        <td className="py-3.5 px-2">
                          <div className="w-[54px] h-[54px] rounded-xl overflow-hidden bg-gray-50 border border-[#eef0f6] shrink-0">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img 
                              src={getImageUrl(p.gambar_produk)} 
                              alt={p.sku} 
                              className="w-full h-full object-cover"
                              onError={(e) => { (e.target as any).src = '/no-image.png'; }}
                            />
                          </div>
                        </td>
                        
                        {/* SKU Info */}
                        <td className="py-3.5 px-2 min-w-0">
                          <div className="font-extrabold text-[14px] text-[#161a27] flex items-center gap-1.5 truncate">
                            {p.sku || "Tanpa SKU"}
                            <span className={`text-[9px] px-2 py-0.5 rounded-full font-extrabold tracking-wider ${
                              p.market === "WP" 
                                ? "bg-emerald-50 text-emerald-600 border border-emerald-100" 
                                : p.market === "Best Seller" 
                                ? "bg-blue-50 text-blue-600 border border-blue-100" 
                                : "bg-purple-50 text-purple-600 border border-purple-100"
                            }`}>
                              {p.market}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#8a90a2] mt-0.5 truncate max-w-[200px]" title={p.nama_produk}>
                            {p.nama_produk !== p.sku ? p.nama_produk : "Menunggu scrape nama..."}
                          </div>
                          <div className="text-[11px] text-[#9b9fb1] font-semibold mt-0.5">
                            {formatRp(p.harga)}
                          </div>
                        </td>
                        
                        {/* Sales */}
                        <td className="py-3.5 px-2 text-right">
                          <div className="font-bold text-[#161a27]">{p.total_sales_shopee.toLocaleString("id-ID")} pcs</div>
                          <div className="text-[10px] text-[#8a90a2] mt-0.5">Induk: {p.total_sales_parent_sku.toLocaleString("id-ID")}</div>
                        </td>
                        
                        {/* Status Update */}
                        <td className="py-3.5 px-2 text-center">
                          <span className={`inline-flex items-center text-[10px] font-bold px-2.5 py-1 rounded-full ${
                            !p.tanggal_update 
                              ? "bg-red-50 text-red-600 border border-red-100"
                              : dateOld 
                              ? "bg-amber-50 text-amber-600 border border-amber-100"
                              : "bg-emerald-50 text-emerald-600 border border-emerald-100"
                          }`}>
                            <span className="w-1.5 h-1.5 rounded-full mr-1.5 animate-pulse" style={{
                              background: !p.tanggal_update ? "#ef4444" : dateOld ? "#f59e0b" : "#10b981"
                            }} />
                            {p.tanggal_update ? formatDate(p.tanggal_update) : "Antrean"}
                          </span>
                        </td>
                        
                        {/* Action Icon */}
                        <td className="py-3.5 px-2 text-center">
                          <div className="w-8 h-8 rounded-full hover:bg-gray-100 grid place-items-center mx-auto text-[#6b7180]">
                            {isSelected ? "▶" : "👁️"}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && pagination.pages > 1 && (
            <div className="flex items-center justify-between mt-5 pt-3 border-t border-[#f8f9fc] text-[12px] font-semibold text-[#6b7180]">
              <div>Total: {pagination.total} produk</div>
              <div className="flex gap-2">
                <button
                  disabled={page === 1}
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  className="px-3 py-1.5 border border-[#eef0f6] rounded-lg bg-white disabled:opacity-40 hover:bg-gray-50 cursor-pointer disabled:cursor-not-allowed"
                >
                  ◀ Prev
                </button>
                <span className="px-3 py-1.5">
                  Page {page} of {pagination.pages}
                </span>
                <button
                  disabled={page === pagination.pages}
                  onClick={() => setPage((prev) => Math.min(prev + 1, pagination.pages))}
                  className="px-3 py-1.5 border border-[#eef0f6] rounded-lg bg-white disabled:opacity-40 hover:bg-gray-50 cursor-pointer disabled:cursor-not-allowed"
                >
                  Next ▶
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Competitor Details Panel */}
        <div className={`lg:col-span-6 xl:col-span-7 ${selectedId ? "block" : "hidden lg:block lg:opacity-40 lg:pointer-events-none"}`}>
          {selectedId ? (
            <div className="card bg-white border border-[#eef0f6] rounded-2xl shadow-sm p-6 relative">
              {loadingDetails ? (
                <div className="py-24 text-center text-[#8a90a2] flex flex-col items-center justify-center gap-2">
                  <span className="w-10 h-10 rounded-full border-4 border-[#fff1ed] border-t-[#ee4d2d] animate-spin" />
                  <span>Mengambil data kompetitor...</span>
                </div>
              ) : detailProduct ? (
                <div>
                  
                  {/* Close button for mobile / narrow views */}
                  <button 
                    onClick={() => setSelectedId(null)}
                    className="absolute top-4 right-4 w-7 h-7 hover:bg-gray-100 rounded-full flex items-center justify-center lg:hidden cursor-pointer"
                  >
                    ✕
                  </button>

                  {/* Product Acuan Summary Header */}
                  <div className="flex flex-col md:flex-row gap-5 pb-5 border-b border-[#f0f2f7] mb-5">
                    <div className="w-[84px] h-[84px] rounded-2xl overflow-hidden bg-gray-50 border border-[#eef0f6] shrink-0">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img 
                        src={getImageUrl(detailProduct.gambar_produk)} 
                        alt={detailProduct.sku} 
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as any).src = '/no-image.png'; }}
                      />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] font-bold text-[#8a90a2] uppercase tracking-wider">
                        PRODUK ACUAN KITA
                      </div>
                      <h2 className="text-[17px] font-extrabold text-[#161a27] mt-0.5 truncate" title={detailProduct.nama_produk}>
                        {detailProduct.nama_produk}
                      </h2>
                      <div className="flex flex-wrap gap-2 items-center mt-2">
                        <span className="text-[12px] font-extrabold bg-[#fff1ed] text-[#ee4d2d] px-2.5 py-0.5 rounded-lg border border-[#ffd3c4]">
                          SKU: {detailProduct.sku}
                        </span>
                        {detailProduct.product_category && (
                          <span className="text-[11px] font-bold bg-[#f3f4f6] text-[#4b5563] px-2.5 py-0.5 rounded-lg">
                            Kategori: {detailProduct.product_category}
                          </span>
                        )}
                        <span className="text-[11px] font-bold bg-amber-50 text-amber-700 px-2 py-0.5 rounded-lg border border-amber-100">
                          Stok Parent: {detailProduct.total_stock_parent_sku} pcs
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Store Link Switched List (Our own store listings) */}
                  <div className="mb-6 bg-[#f8f9fc] p-4 rounded-xl border border-[#eef0f6]">
                    <div className="text-[11.5px] font-bold text-[#8a90a2] mb-2 uppercase tracking-wide">
                      🔗 Link Produk Toko Kita Sendiri (Shopee)
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {/* 1. Alialia primary link */}
                      <a 
                        href={detailProduct.link_produk} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="px-3.5 py-2 bg-white hover:bg-[#fff1ed]/20 border border-[#eef0f6] rounded-xl text-[12px] font-bold inline-flex items-center gap-1.5 transition-colors cursor-pointer hover:border-[#ee4d2d] hover:text-[#ee4d2d]"
                      >
                        🟠 ALIALIA (Utama)
                      </a>

                      {/* 2. Database links for other stores */}
                      {dbLink && dbLink.links && Object.entries(dbLink.links).map(([storeName, info]: [string, any]) => {
                        if (!info.url || storeName.toUpperCase() === "ALIALIA") return null;
                        
                        // Map store icon prefix
                        let prefix = "⭐";
                        if (storeName.toLowerCase().includes("beverra")) prefix = "🔵";
                        else if (storeName.toLowerCase().includes("oliolio")) prefix = "🟢";
                        else if (storeName.toLowerCase().includes("ravella")) prefix = "🟣";
                        else if (storeName.toLowerCase().includes("nomide")) prefix = "🟤";
                        else if (storeName.toLowerCase().includes("topikece")) prefix = "🟡";
                        else if (storeName.toLowerCase().includes("yarra")) prefix = "🔴";
                        else if (storeName.toLowerCase().includes("zioscarf")) prefix = "⚪";

                        return (
                          <a 
                            key={storeName}
                            href={info.url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="px-3.5 py-2 bg-white hover:bg-[#fff1ed]/20 border border-[#eef0f6] rounded-xl text-[12px] font-bold inline-flex items-center gap-1.5 transition-colors cursor-pointer hover:border-[#ee4d2d] hover:text-[#ee4d2d]"
                          >
                            {prefix} {storeName.replace(" OFFICIAL STORE", "").replace(" SUPPLIER HIJAB IMPORT", "")}
                          </a>
                        );
                      })}
                      
                      {/* Mention other stores */}
                      {(!dbLink || !dbLink.links || Object.keys(dbLink.links).length === 0) && (
                        <div className="text-[12px] text-gray-500 italic mt-1 pl-1">
                          (Untuk toko Kimio dan Lolly belum dipetakan di DB Link, silakan cari di Shopee langsung)
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Sales Breakdown by Store */}
                  {detailProduct.sales_per_toko && Object.keys(detailProduct.sales_per_toko).length > 0 && (
                    <div className="mb-6">
                      <div className="text-[11.5px] font-bold text-[#8a90a2] mb-2.5 uppercase tracking-wide">
                        📊 Detail Penjualan per Toko Kita (Sheet Source)
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
                        {Object.entries(detailProduct.sales_per_toko).map(([storeName, salesCount]) => (
                          <div key={storeName} className="bg-white border border-[#eef0f6] rounded-xl p-2.5 text-center shadow-2xs">
                            <div className="text-[10px] text-[#8a90a2] truncate font-medium" title={storeName}>{storeName}</div>
                            <div className="text-[14px] font-extrabold text-[#161a27] mt-0.5">{salesCount.toLocaleString("id-ID")} <span className="text-[10px] font-normal text-[#8a90a2]">pcs</span></div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Competitor Listings Section */}
                  <div>
                    {/* Header Tabs for Competitors */}
                    <div className="flex items-center justify-between border-b border-[#f0f2f7] mb-4">
                      <div className="flex gap-4 text-[13px] font-bold">
                        <button
                          onClick={() => setActiveDetailTab("similar")}
                          className={`pb-2.5 border-b-2 cursor-pointer transition-colors ${
                            activeDetailTab === "similar" 
                              ? "border-[#ee4d2d] text-[#ee4d2d]" 
                              : "border-transparent text-[#6b7180] hover:text-[#3a3f4d]"
                          }`}
                        >
                          Riset Otomatis ({competitors.filter(c => c.tipe === "similar").length})
                        </button>
                        <button
                          onClick={() => setActiveDetailTab("manual")}
                          className={`pb-2.5 border-b-2 cursor-pointer transition-colors ${
                            activeDetailTab === "manual" 
                              ? "border-[#ee4d2d] text-[#ee4d2d]" 
                              : "border-transparent text-[#6b7180] hover:text-[#3a3f4d]"
                          }`}
                        >
                          Manual Input ({competitors.filter(c => c.tipe === "manual").length})
                        </button>
                      </div>
                      
                      {activeDetailTab === "manual" && (
                        <button
                          onClick={() => setShowEditModal(true)}
                          className="text-[12px] bg-[#ee4d2d]/10 hover:bg-[#ee4d2d]/25 text-[#ee4d2d] font-bold px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                        >
                          ✏️ Edit Link Manual
                        </button>
                      )}
                    </div>

                    {/* Competitors List */}
                    <div className="max-h-[450px] overflow-y-auto pr-1">
                      {activeCompetitors.length === 0 ? (
                        <div className="py-12 text-center text-[#8a90a2] text-[13px]">
                          {activeDetailTab === "manual" 
                            ? "Belum ada link kompetitor manual yang di-input untuk produk ini." 
                            : "Tidak ada produk serupa yang dideteksi oleh scraper."}
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {activeCompetitors.map((comp) => (
                            <a
                              key={comp.id}
                              href={comp.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-3 p-3 bg-white hover:bg-[#f8f9fc] border border-[#eef0f6] hover:border-orange-200 rounded-xl transition-all block text-left group cursor-pointer"
                            >
                              {/* Competitor Image */}
                              <div className="w-[50px] h-[50px] rounded-lg overflow-hidden bg-gray-50 border border-[#eef0f6] shrink-0">
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img 
                                  src={getImageUrl(comp.gambar)} 
                                  alt={comp.nama_toko} 
                                  className="w-full h-full object-cover"
                                  onError={(e) => { (e.target as any).src = '/no-image.png'; }}
                                />
                              </div>

                              {/* Competitor Details */}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between">
                                  <div className="font-extrabold text-[12.5px] text-[#161a27] truncate group-hover:text-[#ee4d2d]">
                                    🏪 {comp.nama_toko || "Toko Kompetitor"}
                                  </div>
                                  <div className="text-[11px] bg-orange-50 text-orange-600 font-bold px-2 py-0.5 rounded-md">
                                    Rank #{comp.rank}
                                  </div>
                                </div>
                                
                                <div className="flex items-center gap-3 mt-1.5 text-[11.5px] text-[#8a90a2]">
                                  <span className="font-bold text-[#161a27]">{formatRp(comp.harga)}</span>
                                  <span>•</span>
                                  <span className="bg-[#e7f7f4] text-[#16b8a6] px-1.5 py-0.5 rounded-md font-bold">
                                    🛒 {comp.terjual.toLocaleString("id-ID")} terjual / bln
                                  </span>
                                </div>
                              </div>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                </div>
              ) : (
                <div className="py-24 text-center text-[#8a90a2]">
                  Gagal memuat produk.
                </div>
              )}
            </div>
          ) : (
            <div className="card bg-white border border-[#eef0f6] rounded-2xl shadow-sm p-12 text-center text-[#8a90a2] min-h-[350px] flex flex-col justify-center items-center">
              <span className="text-[44px] mb-2">👁️</span>
              <h3 className="font-bold text-[15px] text-[#161a27]">Pilih Produk Acuan</h3>
              <p className="text-[12.5px] max-w-xs mt-1">
                Klik salah satu produk acuan di tabel sebelah kiri untuk menganalisis dan membandingkan detail kompetitornya.
              </p>
            </div>
          )}
        </div>

      </div>

      {/* Modal Edit Manual Links */}
      {showEditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg shadow-2xl border border-[#eef0f6] overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-5 py-4 border-b border-[#f0f2f7] flex items-center justify-between">
              <h3 className="font-extrabold text-[15px] text-[#161a27]">
                ✏️ Edit Link Kompetitor Manual - {detailProduct?.sku}
              </h3>
              <button 
                onClick={() => setShowEditModal(false)}
                className="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center cursor-pointer text-gray-500"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5">
              <p className="text-[12.5px] text-[#8a90a2] mb-3 leading-relaxed">
                Masukkan link produk kompetitor Shopee (maksimal 10 link, satu link per baris). Link ini akan diproses oleh scraper otomatis pada siklus berikutnya.
              </p>
              
              <textarea
                value={manualLinksInput}
                onChange={(e) => setManualLinksInput(e.target.value)}
                placeholder="Contoh:&#10;https://shopee.co.id/product/12345/67890&#10;https://shopee.co.id/product/11111/22222"
                rows={10}
                className="w-full border border-[#eef0f6] rounded-xl p-3 text-[12px] focus:outline-none focus:border-[#ee4d2d] font-mono bg-gray-50 focus:bg-white transition-colors resize-none"
              />
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3.5 bg-gray-50 border-t border-[#f0f2f7] flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowEditModal(false)}
                disabled={savingManual}
                className="px-4 py-2 border border-gray-200 rounded-xl text-[12.5px] hover:bg-white text-gray-600 cursor-pointer disabled:opacity-50"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleSaveManualLinks}
                disabled={savingManual}
                className="px-4 py-2 bg-[#ee4d2d] hover:bg-[#ee4d2d]/90 text-white font-bold rounded-xl text-[12.5px] cursor-pointer disabled:opacity-50 inline-flex items-center gap-1.5"
              >
                {savingManual ? (
                  <>
                    <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    Menyimpan...
                  </>
                ) : (
                  "💾 Simpan Perubahan"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
