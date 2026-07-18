"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";

interface ProductRow {
  sku: string;
  status: string;
  nama_produk: string;
  hpp: number;
  override_net: number;
  harga_jual_net: number;
  net_rounded_100: number;
  actual_margin: number;
  margin_status: string;
}

interface CostSettings {
  admin_fee_pct: number;
  discount_ads_pct: number;
  salary_pct: number;
  commission_pct: number;
  packing_fee: number;
  service_fee: number;
  service_fee_min_hpp: number;
}

export default function KalkulatorPage() {
  const [activeTab, setActiveTab] = useState<"single" | "batch">("single");
  const ALL_TABS_KALKULATOR = ["single", "batch"];
  const [allowedTabs, setAllowedTabs] = useState<string[]>([...ALL_TABS_KALKULATOR]);
  const [perm, setPerm] = useState({ netPrice: true, margin: true, hpp: true, hargaJualKomisi: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [batchErr, setBatchErr] = useState("");

  // Settings states
  const [singleSettings, setSingleSettings] = useState<CostSettings>({
    admin_fee_pct: 0.16,
    discount_ads_pct: 0.06,
    salary_pct: 0.08,
    commission_pct: 0.00,
    packing_fee: 400,
    service_fee: 1250,
    service_fee_min_hpp: 600,
  });

  const [batchSettings, setBatchSettings] = useState<CostSettings>({
    admin_fee_pct: 0.16,
    discount_ads_pct: 0.06,
    salary_pct: 0.08,
    commission_pct: 0.00,
    packing_fee: 400,
    service_fee: 1250,
    service_fee_min_hpp: 600,
  });

  const settings = activeTab === "single" ? singleSettings : batchSettings;

  // Modal Settings state
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [tempSettings, setTempSettings] = useState<CostSettings>({ ...singleSettings });

  // ────────────────────────────────────────────────────────
  //  TAB 1: SINGLE INTERACTIVE CALCULATOR STATE & MATH
  // ────────────────────────────────────────────────────────
  const [singleHpp, setSingleHpp] = useState<number>(0);
  const [singleOverride, setSingleOverride] = useState<number>(0);
  const [customMargin, setCustomMargin] = useState<string>(""); // state for manual target margin override in Target Mode

  // Helper auto margin rule
  const getAutoMarginPct = (hpp: number) => {
    if (hpp < 500) return 0.25;
    if (hpp < 1000) return 0.20;
    if (hpp < 3000) return 0.15;
    return 0.12;
  };

  // Math calculations for Tab 1 (Single)
  const totalPctBiaya = settings.admin_fee_pct + settings.discount_ads_pct + settings.salary_pct + settings.commission_pct;
  const isLayananApplied = singleHpp >= settings.service_fee_min_hpp;
  const biayaLayananActual = isLayananApplied ? settings.service_fee : 0;
  const biayaTetap = settings.packing_fee + biayaLayananActual;
  
  // Target Mode Target Margin
  const targetMarginPct = customMargin !== "" ? parseFloat(customMargin) / 100 : getAutoMarginPct(singleHpp);

  // 1. Target Mode Jual Net
  const targetJualNetCalculated = (singleHpp + biayaTetap) / (1 - totalPctBiaya - targetMarginPct);
  const targetJualNet = singleOverride > 0 ? singleOverride : targetJualNetCalculated;
  const targetBulat100 = Math.ceil(targetJualNet / 100) * 100;
  const targetBulat500 = Math.ceil(targetJualNet / 500) * 500;

  // Target Mode Rincian
  const targetAdminFeeRp = settings.admin_fee_pct * targetJualNet;
  const targetAdsFeeRp = settings.discount_ads_pct * targetJualNet;
  const targetSalaryFeeRp = settings.salary_pct * targetJualNet;
  const targetCommFeeRp = settings.commission_pct * targetJualNet;
  const targetNetMarginRp = targetJualNet - targetAdminFeeRp - targetAdsFeeRp - targetSalaryFeeRp - targetCommFeeRp - biayaTetap - singleHpp;
  const targetMarginActualPct = targetJualNet > 0 ? targetNetMarginRp / targetJualNet : 0;

  // 2. Real Mode Jual Net (percentages are calculated on net price excluding fixed costs)
  const realJualNetCalculated = (singleHpp / (1 - totalPctBiaya - targetMarginPct)) + biayaTetap;
  const realJualNet = singleOverride > 0 ? singleOverride : realJualNetCalculated;
  const realBulat100 = Math.ceil(realJualNet / 100) * 100;
  const realBulat500 = Math.ceil(realJualNet / 500) * 500;

  // Real Mode Rincian
  const realAdminFeeRp = settings.admin_fee_pct * (realJualNet - biayaTetap);
  const realAdsFeeRp = settings.discount_ads_pct * (realJualNet - biayaTetap);
  const realSalaryFeeRp = settings.salary_pct * (realJualNet - biayaTetap);
  const realCommFeeRp = settings.commission_pct * (realJualNet - biayaTetap);
  const realNetMarginRp = realJualNet - realAdminFeeRp - realAdsFeeRp - realSalaryFeeRp - realCommFeeRp - biayaTetap - singleHpp;
  const realMarginActualPct = realJualNet > 0 ? realNetMarginRp / realJualNet : 0;

  const getStatusLabel = (margin: number) => {
    if (margin >= 0.12) return { text: "Good", bg: "bg-emerald-50 text-emerald-700 border-emerald-200" };
    if (margin > 0.08) return { text: "Average", bg: "bg-amber-50 text-amber-700 border-amber-200" };
    if (margin > 0) return { text: "Bad", bg: "bg-rose-50 text-rose-700 border-rose-200" };
    return { text: "Rugi", bg: "bg-red-100 text-red-800 border-red-300 font-bold" };
  };

  // ────────────────────────────────────────────────────────
  //  TAB 2: BATCH BROWSER STATE & DATA FETCHING
  // ────────────────────────────────────────────────────────
  const [rows, setRows] = useState<ProductRow[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [marginFilter, setMarginFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sortCol, setSortCol] = useState("");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  // Product editing state
  const [editingProduct, setEditingProduct] = useState<{
    sku: string;
    nama: string;
    hpp: number;
    override_net: number;
  } | null>(null);

  // Drawer detail product state
  const [selectedProductDetail, setSelectedProductDetail] = useState<ProductRow | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch("/api/produk/kalkulator?tab=settings", { cache: "no-store" });
      const data = await res.json();
      if (data.allowedTabs) setAllowedTabs(data.allowedTabs);
      if (res.status === 403) {
        const allowed: string[] = data.allowedTabs || [];
        if (allowed.length > 0 && !allowed.includes(activeTab)) setActiveTab(allowed[0] as "single" | "batch");
        return;
      }
      if (res.ok) {
        if (data.perm) setPerm(data.perm);
        if (data.single && data.batch) {
          setSingleSettings(data.single);
          setBatchSettings(data.batch);
          setTempSettings(activeTab === "single" ? data.single : data.batch);
        }
      }
    } catch (e) {
      console.error("Gagal mengambil settings kalkulator:", e);
    }
  }, [activeTab]);

  // Guard race: ganti filter/search cepat-cepat -> respons lama bisa nimpa hasil baru.
  const reqId = useRef(0);

  const fetchProducts = useCallback(async () => {
    const myReq = ++reqId.current;
    setLoading(true);
    setBatchErr("");
    try {
      const params = new URLSearchParams({
        tab: "batch",
        q: search,
        status: statusFilter,
        margin_status: marginFilter,
        page: String(page),
        sort: sortCol,
        dir: sortDir,
      });
      const res = await fetch(`/api/produk/kalkulator?${params.toString()}`, { cache: "no-store" });
      const data = await res.json();
      if (myReq !== reqId.current) return;
      // JANGAN setAllowedTabs di sini biarpun respons bawa itu (fetchSettings udah nyimpennya).
      // AKAR BUG: allowedTabs adalah dependency useEffect yg MANGGIL fetchProducts ini — kalau
      // di-set ulang tiap fetch sukses (array baru walau ISI SAMA, beda reference), React nganggep
      // berubah -> effect nembak lagi -> fetch lagi -> LOOP TANPA HENTI (kebukti: puluhan request
      // identik di Network tab, UI kelihatan "Memuat data katalog..." nyangkut selamanya).
      if (res.status === 403) { setRows([]); setTotal(0); return; }
      if (res.ok) {
        if (data.perm) setPerm(data.perm);
        setRows(data.rows || []);
        setTotal(data.total || 0);
        if (data.single) setSingleSettings(data.single);
        if (data.batch) setBatchSettings(data.batch);
      } else {
        // dulu: error di sini cuma console.error, tabel tampil "Tidak ada produk" seolah
        // kosong padahal gagal — sekarang ketauan (dan data lama TIDAK dihapus diam-diam).
        setBatchErr(data.error || `Gagal memuat data (HTTP ${res.status})`);
      }
    } catch (e) {
      if (myReq !== reqId.current) return;
      setBatchErr(e instanceof Error ? e.message : "Gagal memuat data katalog batch");
      console.error("Gagal memuat batch data kalkulator:", e);
    } finally {
      if (myReq === reqId.current) setLoading(false);
    }
  }, [search, statusFilter, marginFilter, page, sortCol, sortDir]);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  useEffect(() => {
    if (activeTab === "batch" && allowedTabs.includes("batch")) {
      fetchProducts();
    } else if (activeTab === "batch") {
      // tab batch aktif tapi allowedTabs BELUM/GA include "batch" (mis. permission sync
      // belum sampe) -> dulu loading nyangkut true selamanya (fetchProducts ga pernah
      // dipanggil, ga ada yg nge-set false). Sekarang di-reset biar ga stuck spinner.
      setLoading(false);
    }
  }, [activeTab, fetchProducts, allowedTabs]);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("/api/produk/kalkulator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "update-settings",
          type: activeTab,
          settings: tempSettings,
        }),
      });
      if (res.ok) {
        if (activeTab === "single") {
          setSingleSettings(tempSettings);
        } else {
          setBatchSettings(tempSettings);
        }
        setIsSettingsModalOpen(false);
        if (activeTab === "batch") {
          fetchProducts();
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveProductEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingProduct) return;
    setSaving(true);
    try {
      const res = await fetch("/api/produk/kalkulator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "update-product",
          sku: editingProduct.sku,
          hpp: editingProduct.hpp,
          override_net: editingProduct.override_net,
        }),
      });
      if (res.ok) {
        setEditingProduct(null);
        fetchProducts();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const formatRp = (n: number | null | undefined) => {
    if (n === null || n === undefined) return "Rp0";
    return "Rp" + Math.round(n).toLocaleString("id-ID");
  };

  const formatPct = (n: number | null | undefined) => {
    if (n === null || n === undefined) return "0,0%";
    return (n * 100).toFixed(1).replace(".", ",") + "%";
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

  // Safe variables for detail rendering
  const detailBiayaLayanan = selectedProductDetail && selectedProductDetail.hpp >= settings.service_fee_min_hpp ? settings.service_fee : 0;
  const detailBiayaTetap = selectedProductDetail ? (settings.packing_fee + detailBiayaLayanan) : 0;
  const detailAdminFeeRp = selectedProductDetail ? (settings.admin_fee_pct * selectedProductDetail.harga_jual_net) : 0;
  const detailAdsFeeRp = selectedProductDetail ? (settings.discount_ads_pct * selectedProductDetail.harga_jual_net) : 0;
  const detailSalaryFeeRp = selectedProductDetail ? (settings.salary_pct * selectedProductDetail.harga_jual_net) : 0;
  const detailCommFeeRp = selectedProductDetail ? (settings.commission_pct * selectedProductDetail.harga_jual_net) : 0;
  const detailMarginRp = selectedProductDetail ? (selectedProductDetail.harga_jual_net - detailAdminFeeRp - detailAdsFeeRp - detailSalaryFeeRp - detailCommFeeRp - detailBiayaTetap - selectedProductDetail.hpp) : 0;

  if (allowedTabs.length === 0) {
    return (
      <div className="min-h-screen bg-[#f8fafc] p-4 md:p-8 flex items-center justify-center">
        <div className="max-w-[420px] text-center bg-white border border-[#eef0f6] rounded-2xl p-8 shadow-sm">
          <div className="text-4xl mb-3">🔒</div>
          <h1 className="text-lg font-extrabold text-[#161a27] mb-2">Akses Ditolak</h1>
          <p className="text-[13px] text-[#8a90a2]">
            Anda tidak memiliki izin melihat tab manapun di halaman Kalkulator. Hubungi Owner kalau Anda merasa harus punya akses ke halaman ini.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] p-4 md:p-8">
      {/* Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0f172a] tracking-tight">
            🧮 Kalkulator Net Price & Margin
          </h1>
          <p className="text-sm text-[#64748b] mt-1">
            Hitung harga jual optimal, simulasikan margin, dan kelola setelan biaya Shopee secara real-time.
          </p>
        </div>
        <button
          onClick={() => {
            setTempSettings({ ...settings });
            setIsSettingsModalOpen(true);
          }}
          className="mt-4 md:mt-0 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium shadow-sm transition flex items-center gap-2 self-start md:self-auto"
        >
          <span>⚙️</span> Setelan Biaya {activeTab === "single" ? "Single" : "Batch"}
        </button>
      </div>

      {/* Tabs Menu */}
      <div className="flex border-b border-[#e2e8f0] mb-6">
        {allowedTabs.includes("single") && (
          <button
            onClick={() => setActiveTab("single")}
            className={`px-6 py-3 font-semibold text-sm transition-all border-b-2 -mb-[2px] ${
              activeTab === "single"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Simulasi Produk Baru (Single)
          </button>
        )}
        {allowedTabs.includes("batch") && (
          <button
            onClick={() => setActiveTab("batch")}
            className={`px-6 py-3 font-semibold text-sm transition-all border-b-2 -mb-[2px] ${
              activeTab === "batch"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            Katalog Produk (Batch)
          </button>
        )}
      </div>

      {/* ────────────────────────────────────────────────────────
         TAB 1: SINGLE INTERACTIVE CALCULATOR
         ──────────────────────────────────────────────────────── */}
      {activeTab === "single" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Inputs Section */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm h-fit">
            <h2 className="text-lg font-bold text-slate-800 border-b pb-3 mb-4">
              📥 Input Parameter Simulasi
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Harga Pokok Produksi (HPP)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-medium">Rp</span>
                  <input
                    type="number"
                    value={singleHpp || ""}
                    onChange={(e) => setSingleHpp(parseFloat(e.target.value) || 0)}
                    placeholder="0"
                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5">
                  Masukkan biaya modal barang untuk menghitung target harga jual.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Target Margin % (Custom)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={customMargin}
                    onChange={(e) => setCustomMargin(e.target.value)}
                    placeholder={`Otomatis (${formatPct(getAutoMarginPct(singleHpp))})`}
                    className="w-full pr-8 pl-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 text-sm font-medium">%</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5">
                  Biarkan kosong untuk menggunakan aturan margin otomatis berdasarkan HPP.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                  Override Harga Jual Net (Rp)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-medium">Rp</span>
                  <input
                    type="number"
                    value={singleOverride || ""}
                    onChange={(e) => setSingleOverride(parseFloat(e.target.value) || 0)}
                    placeholder="Gunakan target margin"
                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-medium"
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1.5">
                  Isi jika ingin mematok harga jual net secara manual.
                </p>
              </div>
            </div>

            {/* Quick Rules Box */}
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mt-6">
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Aturan & Parameter Aktif
              </h3>
              <div className="space-y-1 text-xs text-slate-500">
                <div className="flex justify-between">
                  <span>Aturan Margin:</span>
                  <span className="font-semibold text-slate-700">HPP &lt; 500 → 25%</span>
                </div>
                <div className="flex justify-between pl-4">
                  <span></span>
                  <span className="font-semibold text-slate-700">500 - 999 → 20%</span>
                </div>
                <div className="flex justify-between pl-4">
                  <span></span>
                  <span className="font-semibold text-slate-700">1.000 - 2.999 → 15%</span>
                </div>
                <div className="flex justify-between pl-4">
                  <span></span>
                  <span className="font-semibold text-slate-700">≥ 3.000 → 12%</span>
                </div>
                <div className="flex justify-between border-t pt-1.5 mt-1.5">
                  <span>Admin Shopee:</span>
                  <span className="font-semibold text-slate-700">{formatPct(settings.admin_fee_pct)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Diskon & Iklan:</span>
                  <span className="font-semibold text-slate-700">{formatPct(settings.discount_ads_pct)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Gaji Karyawan:</span>
                  <span className="font-semibold text-slate-700">{formatPct(settings.salary_pct)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Komisi Toko:</span>
                  <span className="font-semibold text-slate-700">{formatPct(settings.commission_pct)}</span>
                </div>
                <div className="flex justify-between border-t pt-1.5 mt-1.5">
                  <span>Biaya Packing (tetap):</span>
                  <span className="font-semibold text-slate-700">{formatRp(settings.packing_fee)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Biaya Layanan (&ge;{settings.service_fee_min_hpp}):</span>
                  <span className="font-semibold text-slate-700">{formatRp(settings.service_fee)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Outputs Section */}
          <div className="lg:col-span-2 space-y-8">
            {/* TARGET MODE */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-4">
                <h3 className="font-bold text-lg">Hasil Perhitungan Harga Jual Net</h3>
                <p className="text-xs opacity-90 mt-0.5">Semua biaya % dihitung dari Harga Net Jual secara penuh.</p>
              </div>
              <div className="p-6">
                {/* Harga Net Utama */}
                <div className="bg-slate-50 border p-4 rounded-xl text-center mb-6">
                  <span className="text-xs text-slate-500 font-medium">HARGA JUAL NET IDEAL</span>
                  <div className="text-3xl font-extrabold text-indigo-600 mt-1">
                    {formatRp(targetJualNet)}
                  </div>
                  {/* Status Badge */}
                  <span className={`inline-block px-2 py-0.5 border text-xs font-semibold rounded-full mt-2 ${getStatusLabel(targetMarginActualPct).bg}`}>
                    Margin: {getStatusLabel(targetMarginActualPct).text} ({formatPct(targetMarginActualPct)})
                  </span>
                </div>

                {/* Pembulatan */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="border border-slate-200 rounded-lg p-2.5 text-center">
                    <span className="text-[10px] text-slate-400 font-semibold block">Bulat 100 Terdekat</span>
                    <span className="font-bold text-slate-700 text-sm">{formatRp(targetBulat100)}</span>
                  </div>
                  <div className="border border-slate-200 rounded-lg p-2.5 text-center">
                    <span className="text-[10px] text-slate-400 font-semibold block">Bulat 500 Terdekat</span>
                    <span className="font-bold text-slate-700 text-sm">{formatRp(targetBulat500)}</span>
                  </div>
                </div>

                {/* Rincian Potongan */}
                <h4 className="text-xs font-bold text-slate-600 uppercase tracking-wider border-b pb-2 mb-3">
                  Rincian Potongan
                </h4>
                <div className="space-y-2 text-sm text-slate-600">
                  <div className="flex justify-between font-semibold">
                    <span>Harga Jual Net</span>
                    <span>{formatRp(targetJualNet)}</span>
                  </div>
                  <div className="flex justify-between text-rose-500">
                    <span>(-) HPP</span>
                    <span>-{formatRp(singleHpp)}</span>
                  </div>
                  <div className="flex justify-between text-rose-500">
                    <span>(-) Biaya Admin Shopee ({formatPct(settings.admin_fee_pct)})</span>
                    <span>-{formatRp(targetAdminFeeRp)}</span>
                  </div>
                  <div className="flex justify-between text-rose-500">
                    <span>(-) Diskon & Iklan ({formatPct(settings.discount_ads_pct)})</span>
                    <span>-{formatRp(targetAdsFeeRp)}</span>
                  </div>
                  <div className="flex justify-between text-rose-500">
                    <span>(-) Gaji ({formatPct(settings.salary_pct)})</span>
                    <span>-{formatRp(targetSalaryFeeRp)}</span>
                  </div>
                  {settings.commission_pct > 0 && (
                    <div className="flex justify-between text-rose-500">
                      <span>(-) Komisi ({formatPct(settings.commission_pct)})</span>
                      <span>-{formatRp(targetCommFeeRp)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-rose-500">
                    <span>(-) Biaya Packing (tetap)</span>
                    <span>-{formatRp(settings.packing_fee)}</span>
                  </div>
                  <div className="flex justify-between text-rose-500">
                    <span>(-) Biaya Layanan ({isLayananApplied ? "Dikenakan" : "0"})</span>
                    <span>-{formatRp(biayaLayananActual)}</span>
                  </div>
                  <div className="flex justify-between font-bold text-emerald-600 border-t pt-2 mt-2">
                    <span>Margin Profit Aktual</span>
                    <span>{formatRp(targetNetMarginRp)} ({formatPct(targetMarginActualPct)})</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
         TAB 2: BATCH BROWSER
         ──────────────────────────────────────────────────────── */}
      {activeTab === "batch" && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          {/* Header & Filters */}
          <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 flex flex-col sm:flex-row gap-4">
              <input
                type="text"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Cari SKU atau Nama Produk..."
                className="w-full sm:w-64 px-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 border rounded-lg text-sm focus:outline-none"
              >
                <option value="">Semua Status</option>
                <option value="EOL">EOL</option>
                <option value="NEW PD">NEW PD</option>
                <option value="BS-100">BS-100</option>
              </select>

              <select
                value={marginFilter}
                onChange={(e) => {
                  setMarginFilter(e.target.value);
                  setPage(1);
                }}
                className="px-3 py-2 border rounded-lg text-sm focus:outline-none"
              >
                <option value="">Semua Margin Status</option>
                <option value="Good">Good (&ge; 12%)</option>
                <option value="Average">Average (8% - 12%)</option>
                <option value="Bad">Bad (0% - 8%)</option>
                <option value="Rugi">Rugi (&le; 0%)</option>
              </select>
            </div>

            <div className="text-sm font-semibold text-slate-500">
              Total: <span className="text-slate-800 font-bold">{total}</span> produk
            </div>
          </div>

          {/* Table */}
          <div className="overflow-auto max-h-[75vh]">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 z-10 bg-white">
                <tr className="bg-slate-50 border-b border-slate-200 text-xs font-bold text-slate-500 uppercase tracking-wider">
                  <th className="px-6 py-4 cursor-pointer hover:bg-slate-100" onClick={() => handleSort("status")}>
                    Status {sortCol === "status" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:bg-slate-100" onClick={() => handleSort("sku")}>
                    SKU {sortCol === "sku" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 cursor-pointer hover:bg-slate-100" onClick={() => handleSort("nama_produk")}>
                    Nama Produk {sortCol === "nama_produk" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-right cursor-pointer hover:bg-slate-100" onClick={() => handleSort("hpp")}>
                    HPP {sortCol === "hpp" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-right cursor-pointer hover:bg-slate-100" onClick={() => handleSort("override_net")}>
                    Override Net {sortCol === "override_net" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-right cursor-pointer hover:bg-slate-100" onClick={() => handleSort("harga_jual_net")}>
                    Jual Net {sortCol === "harga_jual_net" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-right cursor-pointer hover:bg-slate-100" onClick={() => handleSort("actual_margin")}>
                    Margin % {sortCol === "actual_margin" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-center cursor-pointer hover:bg-slate-100" onClick={() => handleSort("margin_status")}>
                    Status Profit {sortCol === "margin_status" ? (sortDir === "asc" ? "▲" : "▼") : ""}
                  </th>
                  <th className="px-6 py-4 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan={9} className="text-center py-10 text-slate-400 font-medium">
                      Memuat data katalog...
                    </td>
                  </tr>
                ) : batchErr ? (
                  <tr>
                    <td colSpan={9} className="text-center py-10 text-red-500 font-medium">
                      ⚠️ {batchErr} — coba refresh halaman.
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-10 text-slate-400 font-medium">
                      Tidak ada produk ditemukan.
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.sku} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-3.5">
                        {row.status && (
                          <span className={`px-2 py-0.5 text-xs font-bold rounded-md ${
                            row.status === "EOL" ? "bg-slate-100 text-slate-700" : "bg-blue-50 text-blue-700"
                          }`}>
                            {row.status}
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-3.5 font-semibold text-slate-900">{row.sku}</td>
                      <td className="px-6 py-3.5 max-w-xs truncate" title={row.nama_produk}>
                        {row.nama_produk}
                      </td>
                      <td className="px-6 py-3.5 text-right font-medium">{perm.hpp ? formatRp(row.hpp) : <span className="text-slate-300">🔒</span>}</td>
                      <td className="px-6 py-3.5 text-right font-medium text-slate-500">
                        {row.override_net > 0 ? formatRp(row.override_net) : "-"}
                      </td>
                      <td className="px-6 py-3.5 text-right font-bold text-indigo-600">{formatRp(row.harga_jual_net)}</td>
                      <td className="px-6 py-3.5 text-right font-semibold">
                        {perm.margin ? formatPct(row.actual_margin) : <span className="text-slate-300">🔒</span>}
                      </td>
                      <td className="px-6 py-3.5 text-center">
                        {perm.margin ? (
                          <span className={`inline-block px-2.5 py-0.5 border text-xs font-bold rounded-full ${
                            getStatusLabel(row.actual_margin).bg
                          }`}>
                            {row.margin_status}
                          </span>
                        ) : <span className="text-slate-300">🔒</span>}
                      </td>
                      <td className="px-6 py-3.5 text-center flex items-center justify-center gap-2">
                        {perm.hpp && (
                          <button
                            onClick={() => setEditingProduct({
                              sku: row.sku,
                              nama: row.nama_produk,
                              hpp: row.hpp,
                              override_net: row.override_net,
                            })}
                            className="px-2 py-1 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 rounded-md transition"
                          >
                            Edit
                          </button>
                        )}
                        <button
                          onClick={() => setSelectedProductDetail(row)}
                          className="px-2 py-1 text-xs font-medium text-slate-600 bg-slate-100 border border-slate-200 hover:bg-slate-200 rounded-md transition"
                        >
                          Detail
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && rows.length > 0 && (
            <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 text-xs font-semibold border rounded-lg bg-white shadow-sm hover:bg-slate-50 transition disabled:opacity-50"
              >
                Sebelumnya
              </button>
              <span className="text-xs font-medium text-slate-500">
                Halaman <span className="font-bold text-slate-800">{page}</span> dari{" "}
                <span className="font-bold text-slate-800">{Math.ceil(total / 50)}</span>
              </span>
              <button
                disabled={page >= Math.ceil(total / 50)}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 text-xs font-semibold border rounded-lg bg-white shadow-sm hover:bg-slate-50 transition disabled:opacity-50"
              >
                Selanjutnya
              </button>
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
         MODAL SETELAN BIAYA GLOBAL
         ──────────────────────────────────────────────────────── */}
      {isSettingsModalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <form onSubmit={handleSaveSettings} className="bg-white w-full max-w-md rounded-xl shadow-lg border overflow-hidden">
            <div className="px-6 py-4 border-b bg-slate-50 font-bold text-slate-800 text-lg flex justify-between items-center">
              <span>⚙️ Setelan Parameter Biaya {activeTab === "single" ? "Simulasi Single" : "Katalog Batch"}</span>
              <button
                type="button"
                onClick={() => setIsSettingsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 text-xl font-normal"
              >
                &times;
              </button>
            </div>
            
            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  % Admin Shopee
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    value={tempSettings.admin_fee_pct * 100}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      admin_fee_pct: parseFloat(e.target.value) / 100 || 0,
                    })}
                    className="w-full pr-8 pl-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-bold text-sm">%</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  % Diskon & Iklan
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    value={tempSettings.discount_ads_pct * 100}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      discount_ads_pct: parseFloat(e.target.value) / 100 || 0,
                    })}
                    className="w-full pr-8 pl-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-bold text-sm">%</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  % Gaji
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    value={tempSettings.salary_pct * 100}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      salary_pct: parseFloat(e.target.value) / 100 || 0,
                    })}
                    className="w-full pr-8 pl-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-bold text-sm">%</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  % Komisi Toko
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="0.01"
                    value={tempSettings.commission_pct * 100}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      commission_pct: parseFloat(e.target.value) / 100 || 0,
                    })}
                    className="w-full pr-8 pl-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-400 font-bold text-sm">%</span>
                </div>
              </div>

              <div className="border-t pt-4">
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Biaya Packing Tetap (Rp)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-semibold">Rp</span>
                  <input
                    type="number"
                    value={tempSettings.packing_fee}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      packing_fee: parseInt(e.target.value) || 0,
                    })}
                    className="w-full pl-9 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Biaya Layanan Tetap (Rp)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-semibold">Rp</span>
                  <input
                    type="number"
                    value={tempSettings.service_fee}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      service_fee: parseInt(e.target.value) || 0,
                    })}
                    className="w-full pl-9 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Batas HPP Min (untuk Biaya Layanan)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-semibold">Rp</span>
                  <input
                    type="number"
                    value={tempSettings.service_fee_min_hpp}
                    onChange={(e) => setTempSettings({
                      ...tempSettings,
                      service_fee_min_hpp: parseInt(e.target.value) || 0,
                    })}
                    className="w-full pl-9 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>
            </div>

            <div className="px-6 py-4 bg-slate-50 border-t flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsSettingsModalOpen(false)}
                className="px-4 py-2 border text-slate-600 rounded-lg hover:bg-slate-100 transition text-sm font-semibold"
              >
                Batal
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition text-sm font-semibold disabled:opacity-50"
              >
                {saving ? "Menyimpan..." : "Simpan Setelan"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
         MODAL EDIT PRODUK HPP & OVERRIDE
         ──────────────────────────────────────────────────────── */}
      {editingProduct && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <form onSubmit={handleSaveProductEdit} className="bg-white w-full max-w-md rounded-xl shadow-lg border overflow-hidden">
            <div className="px-6 py-4 border-b bg-slate-50 font-bold text-slate-800 text-lg flex justify-between items-center">
              <span>Edit Produk - {editingProduct.sku}</span>
              <button
                type="button"
                onClick={() => setEditingProduct(null)}
                className="text-slate-400 hover:text-slate-600 text-xl font-normal"
              >
                &times;
              </button>
            </div>
            
            <div className="p-6 space-y-4">
              <p className="text-xs text-slate-500 font-semibold italic border-b pb-2 mb-2">
                {editingProduct.nama}
              </p>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Harga Pokok Produksi (HPP)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-semibold">Rp</span>
                  <input
                    type="number"
                    value={editingProduct.hpp || ""}
                    onChange={(e) => setEditingProduct({
                      ...editingProduct,
                      hpp: parseFloat(e.target.value) || 0,
                    })}
                    className="w-full pl-9 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">
                  Override Net Price (Rp)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-400 text-sm font-semibold">Rp</span>
                  <input
                    type="number"
                    value={editingProduct.override_net || ""}
                    onChange={(e) => setEditingProduct({
                      ...editingProduct,
                      override_net: parseFloat(e.target.value) || 0,
                    })}
                    className="w-full pl-9 pr-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 font-semibold"
                  />
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  Biarkan 0 untuk menggunakan perhitungan target margin standar.
                </p>
              </div>
            </div>

            <div className="px-6 py-4 bg-slate-50 border-t flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingProduct(null)}
                className="px-4 py-2 border text-slate-600 rounded-lg hover:bg-slate-100 transition text-sm font-semibold"
              >
                Batal
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition text-sm font-semibold disabled:opacity-50"
              >
                {saving ? "Menyimpan..." : "Simpan Perubahan"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ────────────────────────────────────────────────────────
         MODAL / DRAWER DETAIL PRODUCT
         ──────────────────────────────────────────────────────── */}
      {selectedProductDetail && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-end">
          <div className="bg-white w-full max-w-md h-full shadow-2xl flex flex-col">
            
            {/* Header */}
            <div className="px-6 py-5 border-b bg-slate-50 flex justify-between items-center shrink-0">
              <div>
                <h3 className="font-extrabold text-slate-900 text-lg">Detail Margin & Harga</h3>
                <span className="text-xs text-indigo-600 font-semibold">{selectedProductDetail.sku}</span>
              </div>
              <button
                onClick={() => setSelectedProductDetail(null)}
                className="text-slate-400 hover:text-slate-600 text-2xl font-normal"
              >
                &times;
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              <div>
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  Nama Produk
                </span>
                <p className="text-sm font-semibold text-slate-700 leading-relaxed border-b pb-3 mb-3">
                  {selectedProductDetail.nama_produk}
                </p>
              </div>

              {/* Status Section */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] text-slate-400 font-bold block mb-1 uppercase tracking-wider">
                    Status Produk
                  </span>
                  <span className={`inline-block px-2 py-0.5 text-xs font-bold rounded-md ${
                    selectedProductDetail.status === "EOL" ? "bg-slate-100 text-slate-700" : "bg-blue-50 text-blue-700"
                  }`}>
                    {selectedProductDetail.status || "N/A"}
                  </span>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-center">
                  <span className="text-[10px] text-slate-400 font-bold block mb-1 uppercase tracking-wider">
                    Status Profit
                  </span>
                  {perm.margin ? (
                    <span className={`inline-block px-2 py-0.5 border text-xs font-bold rounded-full ${
                      getStatusLabel(selectedProductDetail.actual_margin).bg
                    }`}>
                      {selectedProductDetail.margin_status}
                    </span>
                  ) : <span className="text-slate-300 text-xs font-bold">🔒</span>}
                </div>
              </div>

              {/* Jual Net & HPP Box */}
              <div className="bg-gradient-to-br from-indigo-50 to-blue-50 rounded-xl border border-indigo-100 p-4">
                <div className="flex justify-between border-b border-indigo-100/50 pb-2.5 mb-2.5 text-sm">
                  <span className="text-slate-500 font-semibold">Harga Jual Net</span>
                  <span className="font-extrabold text-indigo-700">{formatRp(selectedProductDetail.harga_jual_net)}</span>
                </div>
                <div className="flex justify-between border-b border-indigo-100/50 pb-2.5 mb-2.5 text-sm">
                  <span className="text-slate-500 font-semibold">Net Bulat 100</span>
                  <span className="font-extrabold text-slate-700">{formatRp(selectedProductDetail.net_rounded_100)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500 font-semibold">Harga Pokok Produksi (HPP)</span>
                  <span className="font-bold text-slate-700">{perm.hpp ? formatRp(selectedProductDetail.hpp) : "🔒"}</span>
                </div>
              </div>

              {/* Rincian Rinci */}
              <div>
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider border-b pb-2 mb-3">
                  Rincian Komponen Biaya
                </h4>
                <div className="space-y-2.5 text-sm text-slate-600">
                  <div className="flex justify-between text-slate-500">
                    <span>Biaya Admin Shopee ({formatPct(settings.admin_fee_pct)})</span>
                    <span>-{formatRp(detailAdminFeeRp)}</span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>Diskon & Iklan ({formatPct(settings.discount_ads_pct)})</span>
                    <span>-{formatRp(detailAdsFeeRp)}</span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>Gaji Karyawan ({formatPct(settings.salary_pct)})</span>
                    <span>-{formatRp(detailSalaryFeeRp)}</span>
                  </div>
                  {settings.commission_pct > 0 && (
                    <div className="flex justify-between text-slate-500">
                      <span>Komisi ({formatPct(settings.commission_pct)})</span>
                      <span>-{formatRp(detailCommFeeRp)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-slate-500">
                    <span>Biaya Packing Tetap</span>
                    <span>-{formatRp(settings.packing_fee)}</span>
                  </div>
                  <div className="flex justify-between text-slate-500">
                    <span>Biaya Layanan Tetap</span>
                    <span>-{formatRp(detailBiayaLayanan)}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-3 font-bold text-slate-800 text-base">
                    <span>Margin Aktual (Rp)</span>
                    {perm.margin ? (
                      <span className={detailMarginRp >= 0 ? "text-emerald-600" : "text-rose-600"}>
                        {formatRp(detailMarginRp)} ({formatPct(selectedProductDetail.actual_margin)})
                      </span>
                    ) : <span className="text-slate-300">🔒</span>}
                  </div>
                </div>
              </div>

            </div>

            {/* Footer */}
            <div className="px-6 py-4 bg-slate-50 border-t shrink-0 flex justify-end">
              <button
                onClick={() => setSelectedProductDetail(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-sm font-semibold transition"
              >
                Tutup Detail
              </button>
            </div>
            
          </div>
        </div>
      )}

    </div>
  );
}
