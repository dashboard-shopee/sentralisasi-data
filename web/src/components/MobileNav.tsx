"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const BOTTOM_NAV_ITEMS = [
  { ikon: "🏠", label: "Ringkasan", href: "/" },
  { ikon: "📊", label: "Analisa", href: "/analisa" },
  { ikon: "📦", label: "Penjualan", href: "/penjualan" },
  { ikon: "📢", label: "Iklan", href: "/iklan" },
];

const SHEET_NAV_ITEMS = [
  { ikon: "🏷️", label: "Harga & Komisi", href: "/produk/harga" },
  { ikon: "🎯", label: "Pusat Promosi", href: "/produk/pusat-promosi" },
  { ikon: "📦", label: "Stok Katalog", href: "/produk/stok" },
  { ikon: "🧮", label: "Kalkulator", href: "/produk/kalkulator" },
  { ikon: "🔍", label: "Riset Kompetitor", href: "/riset-kompetitor" },
];

export default function MobileNav() {
  const path = usePathname();
  const [minimized, setMinimized] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [profile, setProfile] = useState<{ role: string; username: string; allowedMenus: string[]; avatarEmoji?: string | null } | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const val = localStorage.getItem("mobile-nav-minimized");
      if (val === "true") {
        setMinimized(true);
      }
    } catch (e) {
      console.error(e);
    }

    async function getProfile() {
      try {
        const r = await fetch("/api/me");
        if (r.ok) {
          const data = await r.json();
          setProfile(data.user);
        }
      } catch (e) {
        console.error("Failed to load mobile nav user profile:", e);
      }
    }
    getProfile();
  }, []);

  const handleMinimize = () => {
    setMinimized(true);
    try {
      localStorage.setItem("mobile-nav-minimized", "true");
    } catch (e) {
      console.error(e);
    }
  };

  const handleRestore = () => {
    setMinimized(false);
    try {
      localStorage.setItem("mobile-nav-minimized", "false");
    } catch (e) {
      console.error(e);
    }
  };

  if (!mounted) return null;

  const allowedMenus = profile?.allowedMenus || [];
  const role = profile?.role || "";

  // Filter item navigasi utama bawah berdasarkan akses
  const filteredBottomNav = BOTTOM_NAV_ITEMS.filter(
    (n) => role === "owner" || allowedMenus.includes(n.href)
  );

  // Filter item menu sekunder bottom sheet berdasarkan akses
  const filteredSheetNav = SHEET_NAV_ITEMS.filter(
    (n) => role === "owner" || allowedMenus.includes(n.href)
  );

  // Gabungkan dengan tombol Setting
  const finalBottomNav = [
    ...filteredBottomNav,
    {
      ikon: "⚙️",
      label: "Setting",
      href: "#setting"
    }
  ];

  async function handleLogout() {
    try {
      const r = await fetch("/api/logout", { method: "POST" });
      if (r.ok) {
        window.location.href = "/login";
      }
    } catch (e) {
      console.error("Failed to logout on mobile:", e);
    }
  }

  return (
    <>
      {/* Floating Restore Button when Minimized */}
      <button
        onClick={handleRestore}
        className={`fixed bottom-4 right-4 z-50 w-12 h-12 rounded-full bg-white border border-[#eef0f6] shadow-xl flex items-center justify-center cursor-pointer hover:scale-105 active:scale-95 transition-all duration-300 md:hidden ${
          minimized ? "translate-y-0 opacity-100 scale-100" : "translate-y-10 opacity-0 scale-90 pointer-events-none"
        }`}
        aria-label="Tampilkan Menu"
        title="Tampilkan Menu"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/syntra-mark.png" alt="SYNTRA" className="w-7 h-7 object-contain animate-pulse" />
      </button>

      {/* Mobile Bottom Navigation Bar */}
      <div
        className={`fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-[#eef0f6] px-4 py-2 shadow-2xl md:hidden transition-all duration-300 ease-in-out ${
          minimized ? "translate-y-full opacity-0 pointer-events-none" : "translate-y-0 opacity-100"
        }`}
      >
        {/* Minimize Button overlapping the top border */}
        <button
          onClick={handleMinimize}
          className="absolute -top-[13px] right-6 z-50 w-[26px] h-[26px] bg-white text-[#ee4d2d] rounded-full border border-[#eef0f6] shadow-md flex items-center justify-center cursor-pointer hover:scale-110 active:scale-95 transition-all"
          title="Minimize Menu"
          aria-label="Minimize Menu"
        >
          <span className="text-[10px] font-bold">▼</span>
        </button>

        <div className="flex items-center justify-center max-w-md mx-auto">
          {/* Emojis navigation */}
          <div className="flex-1 flex justify-around items-center gap-1 py-1">
            {finalBottomNav.map((n) => {
              const active = path === n.href;
              const isSetting = n.href === "#setting";

              if (isSetting) {
                return (
                  <button
                    key={n.href}
                    onClick={() => setMenuOpen(true)}
                    className={`flex flex-col items-center justify-center p-1.5 rounded-xl transition-all duration-200 cursor-pointer ${
                      menuOpen ? "bg-[#fff1ed] text-[#ee4d2d] scale-105" : "text-[#6b7180] hover:bg-[#f6f7fb]"
                    }`}
                    style={{ minWidth: "42px" }}
                  >
                    <span className="text-[20px]">{n.ikon}</span>
                    <span className={`text-[9px] mt-0.5 font-bold ${menuOpen ? "text-[#ee4d2d]" : "text-[#9aa0b2]"}`}>
                      {n.label}
                    </span>
                  </button>
                );
              }

              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex flex-col items-center justify-center p-1.5 rounded-xl transition-all duration-200 ${
                    active ? "bg-[#fff1ed] text-[#ee4d2d] scale-105" : "text-[#6b7180] hover:bg-[#f6f7fb]"
                  }`}
                  style={{ minWidth: "42px" }}
                >
                  <span className="text-[20px]">{n.ikon}</span>
                  <span className={`text-[9px] mt-0.5 font-bold ${active ? "text-[#ee4d2d]" : "text-[#9aa0b2]"}`}>
                    {n.label.split(" ")[0]}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      {/* Mobile Account Bottom Sheet */}
      {menuOpen && (
        <div 
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-end justify-center md:hidden"
          onClick={() => setMenuOpen(false)}
        >
          <div 
            className="bg-white w-full rounded-t-3xl p-6 pb-8 shadow-2xl flex flex-col gap-4 animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Handle Bar */}
            <div className="w-12 h-1.5 bg-gray-200 rounded-full mx-auto mb-2" />
            
            {/* Profile Info */}
            <div className="flex items-center gap-3 border-b border-[#eef0f6] pb-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-[#ee4d2d] to-[#ff7043] flex items-center justify-center text-white font-bold text-lg shadow-xs">
                {profile?.avatarEmoji ? profile.avatarEmoji : (profile?.username ? profile.username.charAt(0).toUpperCase() : "U")}
              </div>
              <div>
                <div className="font-bold text-gray-800 text-base">{profile?.username || "Loading..."}</div>
                <div className="text-xs text-gray-400 capitalize mt-0.5">{role || "Please wait"}</div>
              </div>
            </div>
            
            {/* Menu Options */}
            <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto pr-1">
              {/* Secondary Navigation Options */}
              {filteredSheetNav.map((s) => (
                <Link
                  key={s.href}
                  href={s.href}
                  onClick={() => setMenuOpen(false)}
                  className={`flex items-center gap-3 p-3 rounded-xl transition-colors font-medium text-sm ${
                    path === s.href ? "bg-[#fff1ed] text-[#ee4d2d]" : "bg-gray-50 text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <span className="text-[16px]">{s.ikon}</span>
                  <span>{s.label}</span>
                </Link>
              ))}

              <div className="border-t border-[#eef0f6] my-1" />

              {/* Administrative Options */}
              {role === "owner" && (
                <Link
                  href="/pengaturan-akses"
                  onClick={() => setMenuOpen(false)}
                  className={`flex items-center gap-3 p-3 rounded-xl transition-colors font-medium text-sm ${
                    path === "/pengaturan-akses" ? "bg-[#fff1ed] text-[#ee4d2d]" : "bg-gray-50 text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  <span className="text-[16px]">⚙️</span>
                  <span>Setting Akses</span>
                </Link>
              )}
              
              <button
                onClick={() => {
                  setMenuOpen(false);
                  handleLogout();
                }}
                className="flex items-center gap-3 p-3 rounded-xl bg-red-50 text-red-600 font-medium text-sm hover:bg-red-100 transition-colors w-full text-left cursor-pointer"
              >
                <span className="text-[16px]">🚪</span>
                <span>Log Out</span>
              </button>
            </div>
            
            {/* Close Button */}
            <button 
              onClick={() => setMenuOpen(false)}
              className="mt-2 py-3 rounded-xl border border-gray-200 text-gray-500 font-medium text-center hover:bg-gray-50 cursor-pointer"
            >
              Tutup
            </button>
          </div>
        </div>
      )}
    </>
  );
}
