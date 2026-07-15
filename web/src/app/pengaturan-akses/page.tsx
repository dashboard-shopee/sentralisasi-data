"use client";

import { useEffect, useState } from "react";

interface UserAccount {
  id: number;
  username: string;
  password: string;
  allowed_menus: string[];
  can_edit_ads: boolean;
  can_edit_competitor: boolean;
  can_edit_harga: boolean;
  can_edit_komisi: boolean;
  can_edit_kalkulator: boolean;
  can_view_net_price: boolean;
  can_view_margin: boolean;
  can_view_hpp: boolean;
  can_view_harga_jual_komisi: boolean;
  allowed_tabs: Record<string, string[]>;
  avatar_emoji: string | null;
  session_duration_days: number;
}

const MENU_LIST = [
  { path: "/", label: "🏠 Ringkasan" },
  { path: "/analisa", label: "📊 Analisa" },
  { path: "/penjualan", label: "📦 Penjualan & Pesanan" },
  { path: "/iklan", label: "📢 Performa Iklan" },
  { path: "/produk/harga", label: "🏷️ Harga & Komisi" },
  { path: "/produk/pusat-promosi", label: "🎯 Pusat Promosi" },
  { path: "/produk/stok", label: "📦 Stok Katalog" },
  { path: "/produk/kalkulator", label: "🧮 Kalkulator" },
  { path: "/riset-kompetitor", label: "🔍 Riset Kompetitor" },
  { path: "/log", label: "🧾 Log Otomatisasi" }
];

// Tab internal per halaman (page key -> path menu + daftar tab). Cuma dipakai
// utk halaman yg punya navigasi tab beneran (bukan modal drill-down).
const TAB_DEFS: Record<string, { menuPath: string; label: string; tabs: { key: string; label: string }[] }> = {
  harga: {
    menuPath: "/produk/harga",
    label: "🏷️ Harga & Komisi",
    tabs: [
      { key: "all", label: "All Produk (Katalog)" },
      { key: "olah", label: "Olah Data (Price Monitor)" },
      { key: "komisi", label: "Komisi Affiliate" },
      { key: "riwayat", label: "Riwayat Update" },
    ],
  },
  promosi: {
    menuPath: "/produk/pusat-promosi",
    label: "🎯 Pusat Promosi",
    tabs: [
      { key: "promo_toko", label: "Promo Toko" },
      { key: "garansi", label: "Garansi (3 sub-tab jadi 1)" },
      { key: "campaign", label: "Campaign" },
      { key: "flash", label: "Flash Sale" },
      { key: "voucher", label: "Voucher" },
      { key: "paket", label: "Paket Diskon" },
      { key: "komisi", label: "Komisi" },
    ],
  },
  kalkulator: {
    menuPath: "/produk/kalkulator",
    label: "🧮 Kalkulator",
    tabs: [
      { key: "single", label: "Simulasi Produk Baru (Single)" },
      { key: "batch", label: "Katalog Produk (Batch)" },
    ],
  },
};
const ALL_TABS_DEFAULT: Record<string, string[]> = Object.fromEntries(
  Object.entries(TAB_DEFS).map(([page, def]) => [page, def.tabs.map((t) => t.key)])
);

export default function PengaturanAkses() {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // Modals state
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState<UserAccount | null>(null);

  // Form state
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [durationInput, setDurationInput] = useState(7);
  const [selectedMenus, setSelectedMenus] = useState<string[]>([]);
  const [allowedTabsInput, setAllowedTabsInput] = useState<Record<string, string[]>>({ ...ALL_TABS_DEFAULT });
  const [canEditAdsInput, setCanEditAdsInput] = useState(false);
  const [canEditCompInput, setCanEditCompInput] = useState(false);
  const [canEditHargaInput, setCanEditHargaInput] = useState(false);
  const [canEditKomisiInput, setCanEditKomisiInput] = useState(false);
  const [canEditKalkulatorInput, setCanEditKalkulatorInput] = useState(false);
  const [canViewNetPriceInput, setCanViewNetPriceInput] = useState(true);
  const [canViewMarginInput, setCanViewMarginInput] = useState(true);
  const [canViewHppInput, setCanViewHppInput] = useState(true);
  const [canViewHargaJualKomisiInput, setCanViewHargaJualKomisiInput] = useState(true);
  const [avatarEmojiInput, setAvatarEmojiInput] = useState("");
  const [saving, setSaving] = useState(false);

  // Load user list
  async function fetchUsers() {
    setLoading(true);
    setErr("");
    try {
      const r = await fetch("/api/users", { cache: "no-store" });
      const data = await r.json();
      if (r.ok) {
        setUsers(data.users || []);
      } else {
        setErr(data.error || "Gagal memuat pengguna");
      }
    } catch (e) {
      setErr("Gagal memuat data pengguna, coba lagi nanti.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchUsers();
  }, []);

  // Open modal for add
  function openAddModal() {
    setEditingUser(null);
    setUsernameInput("");
    setPasswordInput("");
    setDurationInput(7);
    setSelectedMenus(["/"]); // default view Ringkasan
    setAllowedTabsInput({ ...ALL_TABS_DEFAULT });
    setCanEditAdsInput(false);
    setCanEditCompInput(false);
    setCanEditHargaInput(false);
    setCanEditKomisiInput(false);
    setCanEditKalkulatorInput(false);
    setCanViewNetPriceInput(true);
    setCanViewMarginInput(true);
    setCanViewHppInput(true);
    setCanViewHargaJualKomisiInput(true);
    setAvatarEmojiInput("");
    setShowModal(true);
  }

  // Open modal for edit
  function openEditModal(u: UserAccount) {
    setEditingUser(u);
    setUsernameInput(u.username);
    setPasswordInput(u.password);
    setDurationInput(u.session_duration_days);
    setSelectedMenus(u.allowed_menus || []);
    setAllowedTabsInput(u.allowed_tabs && Object.keys(u.allowed_tabs).length > 0 ? u.allowed_tabs : { ...ALL_TABS_DEFAULT });
    setCanEditAdsInput(u.can_edit_ads);
    setCanEditCompInput(u.can_edit_competitor);
    setCanEditHargaInput(u.can_edit_harga || false);
    setCanEditKomisiInput(u.can_edit_komisi || false);
    setCanEditKalkulatorInput(u.can_edit_kalkulator || false);
    setCanViewNetPriceInput(u.can_view_net_price !== false);
    setCanViewMarginInput(u.can_view_margin !== false);
    setCanViewHppInput(u.can_view_hpp !== false);
    setCanViewHargaJualKomisiInput(u.can_view_harga_jual_komisi !== false);
    setAvatarEmojiInput(u.avatar_emoji || "");
    setShowModal(true);
  }

  // Handle Save (Create / Update)
  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!usernameInput || !passwordInput) return;
    setSaving(true);

    const payload = {
      id: editingUser?.id,
      username: usernameInput,
      password: passwordInput,
      allowed_menus: selectedMenus,
      allowed_tabs: allowedTabsInput,
      can_edit_ads: canEditAdsInput,
      can_edit_competitor: canEditCompInput,
      can_edit_harga: canEditHargaInput,
      can_edit_komisi: canEditKomisiInput,
      can_edit_kalkulator: canEditKalkulatorInput,
      can_view_net_price: canViewNetPriceInput,
      can_view_margin: canViewMarginInput,
      can_view_hpp: canViewHppInput,
      can_view_harga_jual_komisi: canViewHargaJualKomisiInput,
      avatar_emoji: avatarEmojiInput,
      session_duration_days: Number(durationInput)
    };

    try {
      const method = editingUser ? "PUT" : "POST";
      const res = await fetch("/api/users", {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok) {
        setShowModal(false);
        fetchUsers();
      } else {
        alert(data.error || "Terjadi kesalahan.");
      }
    } catch (ex: any) {
      alert("Error: " + ex.message);
    } finally {
      setSaving(false);
    }
  }

  // Handle Delete
  async function handleDelete(id: number, username: string) {
    if (username === "Owner") {
      alert("Akun Owner tidak dapat dihapus!");
      return;
    }
    if (!confirm(`Apakah Anda yakin ingin menghapus akun '${username}'?`)) return;

    try {
      const res = await fetch(`/api/users?id=${id}`, { method: "DELETE" });
      const data = await res.json();
      if (res.ok) {
        fetchUsers();
      } else {
        alert(data.error || "Gagal menghapus user.");
      }
    } catch (ex: any) {
      alert("Error: " + ex.message);
    }
  }

  // Toggle checkbox view menus
  function handleMenuToggle(path: string) {
    setSelectedMenus(prev => {
      if (prev.includes(path)) {
        return prev.filter(p => p !== path);
      } else {
        return [...prev, path];
      }
    });
  }

  // Toggle checkbox tab dalam 1 halaman (page key: harga | promosi | kalkulator)
  function handleTabToggle(page: string, tabKey: string) {
    setAllowedTabsInput(prev => {
      const cur = prev[page] || [];
      const next = cur.includes(tabKey) ? cur.filter(t => t !== tabKey) : [...cur, tabKey];
      return { ...prev, [page]: next };
    });
  }

  return (
    <div className="max-w-[1400px] xl:max-w-[1600px] w-full mx-auto p-1 text-[#3a3f4d]">

      {/* Header */}
      <div className="mb-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight">⚙️ Pengaturan Akses Dashboard</h1>
          <p className="text-[13px] text-[#8a90a2] mt-0.5">
            Kelola hak akses menu, tab, data sensitif, izin edit, dan masa berlaku cookie login per pengguna.
          </p>
        </div>

        <button
          onClick={openAddModal}
          className="px-4 py-2 text-[13px] font-bold text-white rounded-xl shadow-md transition-all duration-200 cursor-pointer hover:scale-102 flex items-center gap-1.5 align-middle"
          style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
        >
          ➕ Tambah Pengguna Baru
        </button>
      </div>

      {err && (
        <div className="bg-rose-50 border border-rose-100 rounded-2xl p-4 text-[13px] text-rose-700 mb-5">
          ⚠️ {err}
        </div>
      )}

      {/* User Accounts List Table */}
      <div className="card p-0 overflow-auto">
        {loading ? (
          <div className="py-20 text-center text-[13px] text-[#8a90a2]">Memuat data pengguna…</div>
        ) : (
          <table className="text-[12px] border-collapse min-w-full">
            <thead>
              <tr className="text-[#8a90a2] text-left border-b border-[#eef0f6]">
                <th className="px-4 py-3 font-semibold w-[60px]">No</th>
                <th className="px-4 py-3 font-semibold w-[150px]">Nama Akun</th>
                <th className="px-4 py-3 font-semibold w-[150px]">Password Masuk</th>
                <th className="px-4 py-3 font-semibold">Izin Akses Menu (Lihat)</th>
                <th className="px-4 py-3 font-semibold w-[150px]">Data Sensitif</th>
                <th className="px-4 py-3 font-semibold w-[150px]">Izin Edit Data</th>
                <th className="px-4 py-3 font-semibold w-[120px]">Durasi Sesi</th>
                <th className="px-4 py-3 font-semibold text-center w-[120px]">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u, index) => {
                const isOwner = u.username === "Owner";
                return (
                  <tr key={u.id} className="border-t border-[#f3f4f8] hover:bg-[#fafbfd] transition-all">
                    <td className="px-4 py-3.5 text-[#9aa0b2]">{index + 1}</td>
                    <td className="px-4 py-3.5 font-bold text-[#161a27]">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-[#ee4d2d] to-[#ff7043] flex items-center justify-center text-white font-bold text-[11px] shrink-0">
                          {u.avatar_emoji ? u.avatar_emoji : u.username.charAt(0).toUpperCase()}
                        </div>
                        <span>{u.username}</span>
                        {isOwner && (
                          <span className="ml-1.5 px-2 py-0.5 text-[9px] font-extrabold bg-[#fff1ed] text-[#ee4d2d] rounded-md border border-[#ffccbc]">
                            Owner
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[#6b7180] tracking-wider select-all">
                      {isOwner ? "Restu_99 (Masked)" : u.password}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-wrap gap-1 max-w-[450px]">
                        {isOwner ? (
                          <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-100 font-semibold text-[10px]">
                            Semua Menu (Full View)
                          </span>
                        ) : u.allowed_menus && u.allowed_menus.length > 0 ? (
                          u.allowed_menus.map(path => {
                            const name = MENU_LIST.find(m => m.path === path)?.label || path;
                            return (
                              <span key={path} className="px-2 py-0.5 rounded bg-[#f6f7fb] text-[#6b7180] border border-[#eef0f6] text-[10.5px]">
                                {name.replace(/[🏠📊📦📢🏷️🎯🔍🧮🧾]/g, "").trim()}
                              </span>
                            );
                          })
                        ) : (
                          <span className="text-[#c4c8d4] italic">Tidak ada akses menu</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col gap-1 text-[11px] font-medium">
                        {isOwner ? (
                          <span className="text-emerald-700 font-semibold flex items-center gap-1">✅ Semua Data</span>
                        ) : (
                          <>
                            <span className={u.can_view_net_price !== false ? "text-emerald-700" : "text-rose-500"}>
                              {u.can_view_net_price !== false ? "✅ Net Price" : "🔒 Net Price"}
                            </span>
                            <span className={u.can_view_margin !== false ? "text-emerald-700" : "text-rose-500"}>
                              {u.can_view_margin !== false ? "✅ Margin" : "🔒 Margin"}
                            </span>
                            <span className={u.can_view_hpp !== false ? "text-emerald-700" : "text-rose-500"}>
                              {u.can_view_hpp !== false ? "✅ HPP" : "🔒 HPP"}
                            </span>
                            <span className={u.can_view_harga_jual_komisi !== false ? "text-emerald-700" : "text-rose-500"}>
                              {u.can_view_harga_jual_komisi !== false ? "✅ Harga Jual Komisi" : "🔒 Harga Jual Komisi"}
                            </span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col gap-1 text-[11px] font-medium">
                        {isOwner ? (
                          <span className="text-emerald-700 font-semibold flex items-center gap-1">✅ Semua Akses Edit</span>
                        ) : (
                          <>
                            <span className={u.can_edit_ads ? "text-emerald-700" : "text-gray-400"}>
                              {u.can_edit_ads ? "✅ Edit Iklan" : "❌ Edit Iklan"}
                            </span>
                            <span className={u.can_edit_competitor ? "text-emerald-700" : "text-gray-400"}>
                              {u.can_edit_competitor ? "✅ Edit Riset" : "❌ Edit Riset"}
                            </span>
                            <span className={u.can_edit_harga ? "text-emerald-700" : "text-gray-400"}>
                              {u.can_edit_harga ? "✅ Edit Katalog" : "❌ Edit Katalog"}
                            </span>
                            <span className={u.can_edit_komisi ? "text-emerald-700" : "text-gray-400"}>
                              {u.can_edit_komisi ? "✅ Edit Komisi" : "❌ Edit Komisi"}
                            </span>
                            <span className={u.can_edit_kalkulator ? "text-emerald-700" : "text-gray-400"}>
                              {u.can_edit_kalkulator ? "✅ Edit Kalkulator" : "❌ Edit Kalkulator"}
                            </span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-[#3a3f4d] font-semibold">
                      {u.session_duration_days} hari
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => openEditModal(u)}
                          className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] hover:border-[#ee4d2d] hover:text-[#ee4d2d] transition-all cursor-pointer font-bold"
                          title="Edit Akses"
                        >
                          ✏️ Edit
                        </button>
                        {!isOwner && (
                          <button
                            onClick={() => handleDelete(u.id, u.username)}
                            className="px-2.5 py-1.5 rounded-lg border border-[#e6e9f0] hover:border-[#f43f5e] hover:text-[#f43f5e] transition-all cursor-pointer font-bold"
                            title="Hapus Akun"
                          >
                            🗑️ Hapus
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* CREATE / EDIT MODAL POPUP */}
      {showModal && (
        <div className="fixed inset-0 bg-[#161a27]/50 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-fade-in">
          <form
            onSubmit={handleSave}
            className="bg-white rounded-2xl border border-[#eef0f6] shadow-2xl p-6 w-full max-w-[560px] max-h-[90vh] overflow-y-auto animate-scale-up text-[#3a3f4d]"
          >
            <h2 className="font-extrabold text-[16px] mb-4 text-[#161a27]">
              {editingUser ? `✏️ Edit Pengguna: ${editingUser.username}` : "➕ Tambah Pengguna Baru"}
            </h2>

            <div className="flex flex-col gap-4">
              {/* Username */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180]">Nama Akun / Nickname</label>
                <input
                  type="text"
                  required
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  disabled={editingUser?.username === "Owner"}
                  placeholder="Contoh: Staff Iklan, Staff Riset"
                  className="w-full border border-[#e6e9f0] rounded-xl px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none mt-1.5"
                />
              </div>

              {/* Avatar Emoticon / Character */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180] block mb-1.5">Karakter / Emoticon Logo (Avatar)</label>
                <div className="flex gap-2 items-center flex-wrap">
                  <input
                    type="text"
                    maxLength={2}
                    value={avatarEmojiInput}
                    onChange={(e) => setAvatarEmojiInput(e.target.value)}
                    placeholder="Inisial / Emoji (cth: 🦊)"
                    className="w-[140px] border border-[#e6e9f0] rounded-xl px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none bg-white"
                  />
                  <div className="flex flex-wrap gap-1">
                    {["🦊", "🦁", "🐨", "🐼", "🤖", "💻", "📈", "🚀", "🔥"].map(emoji => (
                      <button
                        key={emoji}
                        type="button"
                        onClick={() => setAvatarEmojiInput(emoji)}
                        className={`w-8 h-8 rounded-lg border text-sm flex items-center justify-center cursor-pointer transition-colors ${avatarEmojiInput === emoji ? 'border-[#ee4d2d] bg-[#fff1ed]' : 'border-[#e6e9f0] hover:bg-gray-50'}`}
                      >
                        {emoji}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setAvatarEmojiInput("")}
                      className="px-2 h-8 rounded-lg border text-[11px] font-bold text-gray-500 cursor-pointer border-[#e6e9f0] hover:bg-gray-50"
                    >
                      Batal
                    </button>
                  </div>
                </div>
                <p className="text-[11px] text-[#8a90a2] mt-1">Kosongkan untuk menggunakan inisial huruf pertama nama akun.</p>
              </div>

              {/* Password */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180]">Password Masuk</label>
                <input
                  type="text"
                  required
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  placeholder="Password masuk unik akun ini"
                  className="w-full border border-[#e6e9f0] rounded-xl px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none mt-1 mt-1.5"
                />
              </div>

              {/* Cookie Expiry */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180]">Masa Berlaku Cookie Sesi (Login Ulang)</label>
                <select
                  value={durationInput}
                  onChange={(e) => setDurationInput(Number(e.target.value))}
                  className="w-full border border-[#e6e9f0] rounded-xl px-3 py-2 text-[13px] focus:border-[#ee4d2d] outline-none mt-1.5 bg-white cursor-pointer"
                >
                  <option value={1}>1 hari (Keamanan Ketat)</option>
                  <option value={7}>7 hari (Rekomendasi Standar)</option>
                  <option value={30}>30 hari (Jarang Login Ulang)</option>
                  <option value={90}>90 hari (Tetap Aktif Lama)</option>
                </select>
              </div>

              {/* View Permission check boxes (Only editable if not owner) */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180] block mb-1.5">Hak Akses Menu (Lihat Halaman)</label>
                {editingUser?.username === "Owner" ? (
                  <div className="text-[12px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2 font-medium">
                    Owner memiliki hak melihat semua menu secara otomatis dan tidak bisa dikurangi.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 border border-[#eef0f6] rounded-xl p-3 bg-[#fafbfd]">
                    {MENU_LIST.map((menu) => {
                      const checked = selectedMenus.includes(menu.path);
                      return (
                        <label key={menu.path} className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] transition-all py-0.5">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => handleMenuToggle(menu.path)}
                            className="rounded accent-[#ee4d2d]"
                          />
                          <span>{menu.label}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Tab-level: cuma tampil kalau halamannya dicentang & punya tab internal */}
              {editingUser?.username !== "Owner" && Object.entries(TAB_DEFS).map(([page, def]) => {
                if (!selectedMenus.includes(def.menuPath)) return null;
                const current = allowedTabsInput[page] || [];
                return (
                  <div key={page} className="ml-3 -mt-2">
                    <label className="text-[11.5px] font-bold text-[#8a90a2] block mb-1.5">↳ Tab di {def.label} (Lihat)</label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 border border-[#eef0f6] rounded-xl p-3 bg-[#fafbfd]">
                      {def.tabs.map((t) => (
                        <label key={t.key} className="flex items-center gap-2 text-[11.5px] cursor-pointer hover:text-[#ee4d2d] transition-all py-0.5">
                          <input
                            type="checkbox"
                            checked={current.includes(t.key)}
                            onChange={() => handleTabToggle(page, t.key)}
                            className="rounded accent-[#ee4d2d]"
                          />
                          <span>{t.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Data Sensitif (view-level per-field, terpisah dari izin edit) */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180] block mb-1.5">Data Sensitif (Lihat)</label>
                {editingUser?.username === "Owner" ? (
                  <div className="text-[12px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2 font-medium">
                    Owner selalu bisa lihat semua data sensitif.
                  </div>
                ) : (
                  <div className="border border-[#eef0f6] rounded-xl p-3 bg-[#fafbfd] flex flex-col gap-1">
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input type="checkbox" checked={canViewNetPriceInput} onChange={(e) => setCanViewNetPriceInput(e.target.checked)} className="rounded accent-[#ee4d2d]" />
                      <span>🔒 Net Price <span className="text-[10px] text-[#9aa0b2]">(All Produk, Komisi)</span></span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input type="checkbox" checked={canViewMarginInput} onChange={(e) => setCanViewMarginInput(e.target.checked)} className="rounded accent-[#ee4d2d]" />
                      <span>🔒 Margin % <span className="text-[10px] text-[#9aa0b2]">(All Produk, Olah Data, Garansi, Kalkulator)</span></span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input type="checkbox" checked={canViewHppInput} onChange={(e) => setCanViewHppInput(e.target.checked)} className="rounded accent-[#ee4d2d]" />
                      <span>🔒 HPP <span className="text-[10px] text-[#9aa0b2]">(Kalkulator)</span></span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input type="checkbox" checked={canViewHargaJualKomisiInput} onChange={(e) => setCanViewHargaJualKomisiInput(e.target.checked)} className="rounded accent-[#ee4d2d]" />
                      <span>🔒 Harga Jual Komisi <span className="text-[10px] text-[#9aa0b2]">(tab Komisi Affiliate)</span></span>
                    </label>
                  </div>
                )}
              </div>

              {/* Edit Permission checkboxes */}
              <div>
                <label className="text-[12.5px] font-bold text-[#6b7180] block mb-1.5">Hak Akses Edit Data</label>
                {editingUser?.username === "Owner" ? (
                  <div className="text-[12px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2 font-medium">
                    Owner memiliki izin edit semua data secara otomatis.
                  </div>
                ) : (
                  <div className="flex flex-col gap-2 border border-[#eef0f6] rounded-xl p-3 bg-[#fafbfd]">
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input
                        type="checkbox"
                        checked={canEditAdsInput}
                        onChange={(e) => setCanEditAdsInput(e.target.checked)}
                        className="rounded accent-[#ee4d2d]"
                      />
                      <span>📢 Bisa Edit Target ROAS & Budget Harian Iklan</span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input
                        type="checkbox"
                        checked={canEditCompInput}
                        onChange={(e) => setCanEditCompInput(e.target.checked)}
                        className="rounded accent-[#ee4d2d]"
                      />
                      <span>🔍 Bisa Edit Link Manual Kompetitor Riset</span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input
                        type="checkbox"
                        checked={canEditHargaInput}
                        onChange={(e) => setCanEditHargaInput(e.target.checked)}
                        className="rounded accent-[#ee4d2d]"
                      />
                      <span>🏷️ Bisa Edit Custom Harga Diskon & Pancingan (Katalog)</span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input
                        type="checkbox"
                        checked={canEditKomisiInput}
                        onChange={(e) => setCanEditKomisiInput(e.target.checked)}
                        className="rounded accent-[#ee4d2d]"
                      />
                      <span>🤝 Bisa Edit Rate Komisi & Harga Jual Toko (Komisi)</span>
                    </label>
                    <label className="flex items-center gap-2 text-[12px] cursor-pointer hover:text-[#ee4d2d] py-0.5">
                      <input
                        type="checkbox"
                        checked={canEditKalkulatorInput}
                        onChange={(e) => setCanEditKalkulatorInput(e.target.checked)}
                        className="rounded accent-[#ee4d2d]"
                      />
                      <span>🧮 Bisa Edit Pengaturan Batch Kalkulator</span>
                    </label>
                  </div>
                )}
              </div>
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-end gap-2.5 mt-6 border-t border-[#eef0f6] pt-4">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 border border-[#e6e9f0] rounded-xl text-[13px] text-[#6b7180] hover:bg-[#f6f7fb] cursor-pointer"
              >
                Batal
              </button>
              <button
                type="submit"
                disabled={saving || !usernameInput || !passwordInput}
                className="px-4 py-2 text-[13px] font-bold text-white rounded-xl disabled:opacity-50 cursor-pointer"
                style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
              >
                {saving ? "Menyimpan…" : "Simpan Pengguna"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Dynamic CSS animations */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleUp {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        .animate-fade-in {
          animation: fadeIn 0.15s ease-out forwards;
        }
        .animate-scale-up {
          animation: scaleUp 0.18s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
        }
      `}} />
    </div>
  );
}
