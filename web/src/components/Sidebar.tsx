"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { ikon: "🏠", label: "Ringkasan", href: "/" },
  { ikon: "📊", label: "Analisa", href: "/analisa" },
  { ikon: "📦", label: "Penjualan & Pesanan", href: "/penjualan" },
  { ikon: "📢", label: "Iklan", href: "/iklan" },
];

export default function Sidebar({
  minimized,
  onToggle,
}: {
  minimized: boolean;
  onToggle: () => void;
}) {
  const path = usePathname();
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
            <div className="text-[10px] text-[#9aa0b2] mt-1">System Centralized</div>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-1.5">
        {NAV.map((n) => {
          const active = path === n.href;
          return (
            <Link
              key={n.href}
              href={n.href}
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


