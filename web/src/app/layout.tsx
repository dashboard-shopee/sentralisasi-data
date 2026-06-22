import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Dashboard Shopee Multi-Toko",
  description: "Pusat data penjualan, pesanan & iklan 10 toko",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className={`${inter.variable} h-full`}>
      <body
        className="min-h-full"
        style={{ fontFamily: "var(--font-inter), system-ui, sans-serif" }}
      >
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 min-w-0 px-5 py-6 lg:px-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
