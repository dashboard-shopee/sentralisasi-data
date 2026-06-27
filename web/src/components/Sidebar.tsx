"use client";

import { useState, useEffect } from "react";
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
      { label: "Stok Katalog", href: "/produk/stok" },
    ],
  },
  { ikon: "🔍", label: "Riset Kompetitor", href: "/riset-kompetitor" },
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
  const [profile, setProfile] = useState<{ role: string; username: string; allowedMenus: string[] } | null>(null);

  useEffect(() => {
    async function getProfile() {
      try {
        const r = await fetch("/api/me");
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

  // Jika owner, tambahkan menu Akses Kontrol
  if (role === "owner") {
    filteredNav.push({
      ikon: "⚙️",
      label: "Akses Kontrol",
      href: "/pengaturan-akses"
    });
  }

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
        "relative hidden md:flex shrink-0 flex-col bg-white border-r border-[#eef0f6] py-6 sticky top-0 h-screen transition-all duration-300 ease-in-out " +
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
            <div className="text-[10px] text-[#9aa0b2] mt-1">
              {profile ? `${profile.username} (${role})` : "System Centralized"}
            </div>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-1.5">
        {filteredNav.map((n) => {
          if (n.sub) {
            const isExpanded = expanded[n.label];
            const isSubActive = n.sub.some((s) => path === s.href);
            
            return (
              <div key={n.label} className="flex flex-col gap-1">
                {minimized ? (
                  // Minimized representation of nested menu
                  <Link
                    href={n.sub[0].href}
                    className={
                      "flex items-center rounded-xl transition-all duration-200 relative group justify-center p-3 text-[18px] " +
                      (isSubActive ? "bg-[#fff1ed] text-[#ee4d2d]" : "text-[#6b7180] hover:bg-[#f6f7fb]")
                    }
                  >
                    <span className="text-[16px] shrink-0">{n.ikon}</span>
                    <div className="absolute left-14 z-50 bg-[#161a27] text-white text-[11px] px-2.5 py-1.5 rounded-lg shadow-lg font-medium opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap flex flex-col gap-1">
                      <div className="font-bold text-[#ee4d2d] border-b border-white/20 pb-0.5 mb-0.5">{n.label}</div>
                      {n.sub.map((s) => (
                        <div key={s.href} className={path === s.href ? "text-[#ff7043]" : "text-white/80"}>{s.label}</div>
                      ))}
                    </div>
                  </Link>
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

      {/* Logout Button */}
      <div className="mt-4 border-t border-[#eef0f6] pt-4">
        <button
          onClick={handleLogout}
          className={
            "flex items-center rounded-xl transition-all duration-200 cursor-pointer w-full " +
            (minimized ? "justify-center p-3 text-[18px]" : "gap-3 px-3 py-2.5 text-[14px] font-medium") +
            " text-[#9aa0b2] hover:bg-[#fff1ed]/20 hover:text-[#ee4d2d]"
          }
          title="Log Out dari Sistem"
        >
          <span className="text-[16px] shrink-0">🚪</span>
          {!minimized && <span>Log Out</span>}
        </button>
      </div>

      {/* Real-time Info Card */}
      {!minimized && (
        <div className="mt-auto px-3 pt-6 transition-opacity duration-300">
          <div
            className="rounded-2xl p-4 text-white text-[12px] leading-relaxed"
            style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
          >
            <div className="font-bold mb-1">Data real-time</div>
            Sumber tunggal Supabase · update harian.
          </div>
        </div>
      )}
    </aside>
  );
}
