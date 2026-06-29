"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import MobileNav from "./MobileNav";

export default function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const [minimized, setMinimized] = useState(false);
  const [mounted, setMounted] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    setMounted(true);
    try {
      const val = localStorage.getItem("sidebar-minimized");
      if (val === "true") {
        setMinimized(true);
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const handleToggle = () => {
    const nextVal = !minimized;
    setMinimized(nextVal);
    try {
      localStorage.setItem("sidebar-minimized", String(nextVal));
    } catch (e) {
      console.error(e);
    }
  };

  const isLoginPage = pathname === "/login";

  if (isLoginPage) {
    return (
      <div className="min-h-screen w-full">
        {children}
      </div>
    );
  }

  // Prevent layout jump on mount by using smooth class bindings
  return (
    <div className="flex min-h-screen w-full relative">
      <Sidebar minimized={mounted ? minimized : false} onToggle={handleToggle} />
      <div className="flex-1 flex flex-col min-w-0 transition-all duration-300 ease-in-out">
        <main className="flex-1 min-w-0 px-4 py-5 sm:px-6 sm:py-6 lg:px-8 pb-24 md:pb-8">
          {children}
        </main>
        <MobileNav />
      </div>
    </div>
  );
}

