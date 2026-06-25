"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { ikon: "🏠", label: "Ringkasan", href: "/" },
  { ikon: "📊", label: "Analisa", href: "/analisa" },
  { ikon: "📦", label: "Penjualan", href: "/penjualan" },
  { ikon: "📢", label: "Iklan", href: "/iklan" },
];

export default function MobileNav() {
  const path = usePathname();
  const [minimized, setMinimized] = useState(false);
  const [mounted, setMounted] = useState(false);

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

  return (
    <>
      {/* Floating Restore Button when Minimized */}
      <button
        onClick={handleRestore}
        className={`fixed bottom-4 right-4 z-50 w-12 h-12 rounded-full text-white shadow-xl flex items-center justify-center cursor-pointer hover:scale-105 active:scale-95 transition-all duration-300 md:hidden ${
          minimized ? "translate-y-0 opacity-100 scale-100" : "translate-y-10 opacity-0 scale-90 pointer-events-none"
        }`}
        style={{ background: "linear-gradient(135deg, #ee4d2d, #ff7043)" }}
        aria-label="Tampilkan Menu"
        title="Tampilkan Menu"
      >
        <span className="text-[20px]">🧭</span>
      </button>

      {/* Mobile Bottom Navigation Bar */}
      <div
        className={`fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-[#eef0f6] px-4 py-2 shadow-2xl md:hidden transition-all duration-300 ease-in-out ${
          minimized ? "translate-y-full opacity-0 pointer-events-none" : "translate-y-0 opacity-100"
        }`}
      >
        <div className="flex items-center justify-between max-w-md mx-auto">
          {/* Emojis navigation */}
          <div className="flex-1 flex justify-around items-center gap-1">
            {NAV.map((n) => {
              const active = path === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`flex flex-col items-center justify-center p-2 rounded-xl transition-all duration-200 ${
                    active ? "bg-[#fff1ed] text-[#ee4d2d] scale-105" : "text-[#6b7180] hover:bg-[#f6f7fb]"
                  }`}
                  style={{ minWidth: "50px" }}
                >
                  <span className="text-[22px]">{n.ikon}</span>
                  <span className={`text-[9px] mt-0.5 font-bold ${active ? "text-[#ee4d2d]" : "text-[#9aa0b2]"}`}>
                    {n.label.split(" ")[0]}
                  </span>
                </Link>
              );
            })}
          </div>

          {/* Minimize / Close Button */}
          <div className="pl-2 border-l border-[#eef0f6] ml-2">
            <button
              onClick={handleMinimize}
              className="w-10 h-10 rounded-xl bg-[#f4f6fb] text-[#8a90a2] hover:text-[#ee4d2d] hover:bg-[#fff1ed] transition flex items-center justify-center cursor-pointer"
              title="Minimize Menu"
              aria-label="Minimize Menu"
            >
              <span className="text-[14px]">▼</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
