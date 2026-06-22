"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { ikon: "🏠", label: "Ringkasan", href: "/" },
  { ikon: "📊", label: "Analisa", href: "/analisa" },
  { ikon: "📦", label: "Penjualan & Pesanan", href: "/penjualan" },
  { ikon: "📢", label: "Iklan", href: "/iklan" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden md:flex w-[240px] shrink-0 flex-col bg-white border-r border-[#eef0f6] px-4 py-6 sticky top-0 h-screen">
      <div className="flex items-center gap-3 px-2 mb-8">
        <div
          className="w-10 h-10 rounded-xl grid place-items-center text-white text-lg"
          style={{ background: "linear-gradient(135deg,#ee4d2d,#ff8a65)" }}
        >
          🛍️
        </div>
        <div>
          <div className="font-extrabold text-[15px] leading-tight">Shopee Data</div>
          <div className="text-[11px] text-[#9aa0b2]">10 Toko</div>
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((n) => {
          const active = path === n.href;
          return (
            <Link
              key={n.href}
              href={n.href}
              className={
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-[14px] font-medium transition " +
                (active ? "bg-[#fff1ed] text-[#ee4d2d]" : "text-[#6b7180] hover:bg-[#f6f7fb]")
              }
            >
              <span className="text-[16px]">{n.ikon}</span>
              {n.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto px-3 pt-6">
        <div
          className="rounded-2xl p-4 text-white text-[12px] leading-relaxed"
          style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
        >
          <div className="font-bold mb-1">Data real-time</div>
          Sumber tunggal Supabase · update harian.
        </div>
      </div>
    </aside>
  );
}
