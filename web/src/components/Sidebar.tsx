"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { ikon: "🏠", label: "Ringkasan", href: "/" },
  { ikon: "📊", label: "Analisa", href: "/analisa" },
  { ikon: "📦", label: "Penjualan & Pesanan", href: "/penjualan" },
  { ikon: "📢", label: "Iklan", href: "/iklan" },
  {
    ikon: "🏷️",
    label: "Produk",
    sub: [
      { label: "Harga & Komisi", href: "/produk/harga" },
      { label: "Pusat Promosi", href: "/produk/pusat-promosi" },
      { label: "Stok Katalog", href: "/produk/stok" },
      { label: "Kalkulator", href: "/produk/kalkulator" },
    ],
  },
  { ikon: "🔍", label: "Riset Kompetitor", href: "/riset-kompetitor" },
  { ikon: "🧾", label: "Log", href: "/log" },
];

export default function Sidebar({
  minimized,
  onToggle,
}: {
  minimized: boolean;
  onToggle: () => void;
}) {
  const path = usePathname();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ "Produk": true });
  const [profile, setProfile] = useState<{ role: string; username: string; allowedMenus: string[]; avatarEmoji?: string | null } | null>(null);
  
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  useEffect(() => {
    async function getProfile() {
      try {
        const r = await fetch("/api/me", { cache: "no-store" });
        if (r.ok) {
          const data = await r.json();
          setProfile(data.user);
        }
      } catch (e) {
        console.error("Failed to load user profile:", e);
      }
    }
    getProfile();
  }, []);

  const toggleExpand = (label: string) => {
    setExpanded((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const allowedMenus = profile?.allowedMenus || [];
  const role = profile?.role || "";

  // Filter Navigasi Dinamis
  const filteredNav = NAV.map((n) => {
    if (n.sub) {
      const allowedSub = n.sub.filter((s) => role === "owner" || allowedMenus.includes(s.href));
      if (allowedSub.length === 0) return null;
      return { ...n, sub: allowedSub };
    }
    const hasAccess = role === "owner" || allowedMenus.includes(n.href || "");
    if (!hasAccess) return null;
    return n;
  }).filter((n): n is Exclude<typeof n, null> => n !== null);

  // Akses Kontrol lama dihapus dari filteredNav karena dipindahkan ke menu Setting di bagian profile bawah

  async function handleLogout() {
    try {
      const r = await fetch("/api/logout", { method: "POST" });
      if (r.ok) {
        window.location.href = "/login";
      }
    } catch (e) {
      console.error("Failed to logout:", e);
    }
  }

  return (
    <aside
      className={
        "z-30 relative hidden md:flex shrink-0 flex-col bg-white border-r border-[#eef0f6] py-6 sticky top-0 h-screen transition-all duration-300 ease-in-out " +
        (minimized ? "w-[76px] px-2.5" : "w-[240px] px-4")
      }
    >
      {/* Toggle button overlapping right border */}
      <button
        onClick={onToggle}
        className="absolute top-[32px] -right-[13px] z-50 w-[26px] h-[26px] bg-white text-[#ee4d2d] rounded-full border border-[#eef0f6] shadow-md flex items-center justify-center cursor-pointer hover:scale-110 active:scale-95 transition-all"
        title={minimized ? "Expand Menu" : "Minimize Menu"}
      >
        <span className="text-[10px] font-bold">
          {minimized ? "▶" : "◀"}
        </span>
      </button>

      <div className={"flex items-center gap-2.5 px-1 mb-8 overflow-hidden " + (minimized ? "justify-center" : "")}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/syntra-mark.png" alt="SYNTRA" className="h-9 w-auto shrink-0" />
        {!minimized && (
          <div className="transition-opacity duration-300 opacity-100 whitespace-nowrap">
            <div className="font-extrabold text-[17px] leading-none tracking-[0.18em] text-[#3a3f4d]">SYNTRA</div>
          </div>
        )}
      </div>

      <nav className={`flex-1 flex flex-col gap-1.5 min-h-0 py-2 -mx-1 px-1 ${minimized ? "overflow-visible" : "overflow-y-auto"}`}>
        {filteredNav.map((n) => {
          if (n.sub) {
            const isExpanded = expanded[n.label];
            const isSubActive = n.sub.some((s) => path === s.href);
            
            return (
              <div key={n.label} className="flex flex-col gap-1">
                {minimized ? (
                  // Minimized representation of nested menu
                  <div
                    className={
                      "flex items-center rounded-xl transition-all duration-200 relative group justify-center p-3 text-[18px] cursor-pointer " +
                      (isSubActive ? "bg-[#fff1ed] text-[#ee4d2d]" : "text-[#6b7180] hover:bg-[#f6f7fb]")
                    }
                  >
                    <span className="text-[16px] shrink-0">{n.ikon}</span>
                    
                    {/* Floating sub-menu */}
                    <div 
                      className="absolute left-[52px] top-1/2 -translate-y-1/2 z-50 bg-white/95 backdrop-blur-md border border-[#eef0f6] rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.08)] p-1.5 min-w-[155px] flex flex-col gap-0.5 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-all duration-200 origin-left scale-95 group-hover:scale-100"
                    >
                      {/* Sub-menu title */}
                      <div className="px-2.5 py-1 text-[10px] font-bold text-[#ee4d2d] uppercase tracking-wider border-b border-[#eef0f6] mb-1">
                        {n.label}
                      </div>
                      
                      {/* Sub-menu items */}
                      {n.sub.map((s) => {
                        const active = path === s.href;
                        return (
                          <Link
                            key={s.href}
                            href={s.href}
                            className={
                              "px-2.5 py-1.5 text-[12px] rounded-lg font-medium transition-all duration-150 text-left block w-full " +
                              (active ? "text-[#ee4d2d] bg-[#fff1ed]" : "text-[#6b7180] hover:bg-[#f6f7fb] hover:text-[#ee4d2d]")
                            }
                          >
                            {s.label}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  // Expanded / Normal nested menu representation
                  <>
                    <button
                      onClick={() => toggleExpand(n.label)}
                      className={
                        "flex items-center rounded-xl transition-all duration-200 w-full text-left gap-3 px-3 py-2.5 text-[14px] font-medium cursor-pointer " +
                        (isSubActive ? "text-[#ee4d2d] bg-[#fff1ed]/20" : "text-[#6b7180] hover:bg-[#f6f7fb]")
                      }
                    >
                      <span className="text-[16px] shrink-0">{n.ikon}</span>
                      <span className="flex-1 truncate whitespace-nowrap">{n.label}</span>
                      <span className="text-[9px] text-[#9aa0b2] mr-0.5 select-none font-bold">
                        {isExpanded ? "▼" : "▶"}
                      </span>
                    </button>
                    {isExpanded && (
                      <div className="pl-8 flex flex-col gap-1 transition-all duration-300">
                        {n.sub.map((s) => {
                          const active = path === s.href;
                          return (
                            <Link
                              key={s.href}
                              href={s.href}
                              className={
                                "px-3 py-2 text-[12.5px] rounded-lg font-medium transition-all duration-150 " +
                                (active ? "text-[#ee4d2d] bg-[#fff1ed]" : "text-[#6b7180] hover:bg-[#f6f7fb]")
                              }
                            >
                              {s.label}
                            </Link>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          }

          const active = path === n.href;
          return (
            <Link
              key={n.href}
              href={n.href!}
              className={
                "flex items-center rounded-xl transition-all duration-200 relative group " +
                (minimized ? "justify-center p-3 text-[18px]" : "gap-3 px-3 py-2.5 text-[14px] font-medium") +
                " " +
                (active ? "bg-[#fff1ed] text-[#ee4d2d]" : "text-[#6b7180] hover:bg-[#f6f7fb]")
              }
            >
              <span className="text-[16px] shrink-0">{n.ikon}</span>
              {!minimized && <span className="truncate whitespace-nowrap">{n.label}</span>}
              
              {minimized && (
                <div className="absolute left-14 z-50 bg-[#161a27] text-white text-[11px] px-2.5 py-1.5 rounded-lg shadow-lg font-medium opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap">
                  {n.label}
                </div>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto flex flex-col gap-4 shrink-0">
        {/* Real-time Info Card */}
        {!minimized && (
          <div className="px-3 transition-opacity duration-300">
            <div
              className="rounded-2xl p-4 text-white text-[12px] leading-relaxed"
              style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
            >
              <div className="font-bold mb-1">Data real-time</div>
              Sumber tunggal Supabase · update harian.
            </div>
          </div>
        )}

        {/* User Profile Card (Setting & Logout) */}
        <div className={`relative ${minimized ? 'px-1' : 'px-3'}`} ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className={
              "flex items-center rounded-xl transition-all duration-200 cursor-pointer w-full text-left " +
              (minimized ? "justify-center p-2 hover:bg-[#f6f7fb]" : "gap-3 p-3 bg-gray-50 hover:bg-[#fff1ed]/40 border border-[#eef0f6] hover:border-[#ee4d2d]/30")
            }
            title={profile ? `${profile.username} (${role})` : "Profile"}
          >
            {/* Avatar Circle */}
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-[#ee4d2d] to-[#ff7043] flex items-center justify-center text-white font-bold text-lg shrink-0 shadow-xs">
              {profile?.avatarEmoji ? profile.avatarEmoji : (profile ? profile.username.charAt(0).toUpperCase() : "U")}
            </div>
            
            {/* User Info (Visible only when not minimized) */}
            {!minimized && (
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-800 truncate leading-tight">
                  {profile ? profile.username : "Loading..."}
                </div>
                <div className="text-[11px] text-gray-400 capitalize truncate mt-0.5">
                  {profile ? profile.role : "Please wait"}
                </div>
              </div>
            )}

            {/* Chevron/Dropdown Indicator (Visible only when not minimized) */}
            {!minimized && (
              <span className={`text-[10px] text-gray-400 transition-transform duration-200 ${dropdownOpen ? 'rotate-180' : ''}`}>
                ▲
              </span>
            )}
          </button>

          {/* Dropdown Menu */}
          {dropdownOpen && (
            <div
              className={
                "absolute z-50 bg-white border border-[#eef0f6] rounded-2xl shadow-[0_8px_30px_rgb(0,0,0,0.08)] py-2 transition-all duration-200 " +
                (minimized
                  ? "left-14 bottom-0 w-[180px]"
                  : "left-3 right-3 bottom-[60px]")
              }
            >
              {/* Profile Header (especially for minimized where details are hidden) */}
              {minimized && (
                <div className="px-4 py-2 border-b border-[#eef0f6] mb-1">
                  <div className="font-semibold text-sm text-gray-800 truncate">{profile?.username || "User"}</div>
                  <div className="text-xs text-gray-400 capitalize truncate">{profile?.role || "Role"}</div>
                </div>
              )}

              {/* Setting Link (for Owner) */}
              {role === "owner" && (
                <Link
                  href="/pengaturan-akses"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-2.5 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-[#fff1ed] hover:text-[#ee4d2d] transition-colors"
                >
                  <span className="text-[15px]">⚙️</span>
                  <span>Setting</span>
                </Link>
              )}

              {/* Logout Button */}
              <button
                onClick={() => {
                  setDropdownOpen(false);
                  handleLogout();
                }}
                className="flex items-center gap-2.5 w-full text-left px-4 py-2 text-sm font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors cursor-pointer"
              >
                <span className="text-[15px]">🚪</span>
                <span>Log Out</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
