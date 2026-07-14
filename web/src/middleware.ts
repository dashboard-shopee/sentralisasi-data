import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifySession } from "./lib/auth";

export async function middleware(req: NextRequest) {
  const token = req.cookies.get("dash_auth")?.value;
  const { pathname } = req.nextUrl;

  // 1. Izinkan file statis langsung tanpa perlu login
  if (/\.[a-zA-Z0-9]+$/.test(pathname)) {
    return NextResponse.next();
  }

  // 2. Izinkan API logout/login/me secara langsung
  if (pathname.startsWith("/api/login") || pathname.startsWith("/api/logout")) {
    return NextResponse.next();
  }

  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const user = token ? await verifySession(token, secret) : null;

  // 3. Skenario Pengguna SUDAH Login
  if (user) {
    // Jika sudah login, jangan bolehkan masuk ke halaman login lagi
    if (pathname === "/login") {
      return NextResponse.redirect(new URL("/", req.url));
    }

    const role = user.role as string;
    const allowedMenus = (user.allowed_menus || []) as string[];
    const canViewMargin = role === "owner" || user.can_view_margin !== false;

    // Kalkulator = full-page HPP/margin -> tutup total kalau data sensitif dikunci,
    // walau menu ini masih tercentang di allowed_menus (izin lama sebelum toggle ada).
    if (pathname.startsWith("/produk/kalkulator") && !canViewMargin) {
      return NextResponse.redirect(new URL("/", req.url));
    }

    // Proteksi halaman manajemen akses admin (hanya Owner yang boleh)
    if (pathname.startsWith("/pengaturan-akses") || pathname.startsWith("/api/users")) {
      if (role !== "owner") {
        // API -> 403 JSON; halaman -> redirect ke beranda
        if (pathname.startsWith("/api/")) {
          return NextResponse.json({ ok: false, error: "Forbidden" }, { status: 403 });
        }
        return NextResponse.redirect(new URL("/", req.url));
      }
      return NextResponse.next();
    }

    // Route API lain (mis. /api/me, /api/produk) dilayani untuk semua user yang sudah
    // login — tiap route punya logika auth sendiri. JANGAN kena gating menu di bawah,
    // karena path "/api/..." tak cocok menu manapun -> ke-redirect -> Sidebar gagal
    // baca profil & menu staff hilang.
    if (pathname.startsWith("/api/")) {
      return NextResponse.next();
    }

    // Proteksi Halaman Berdasarkan Menu Izin
    if (pathname === "/") {
      if (role === "owner" || allowedMenus.includes("/")) {
        return NextResponse.next();
      }
      // Jika tidak boleh akses home, arahkan ke menu pertama yang diizinkan
      if (allowedMenus.length > 0) {
        return NextResponse.redirect(new URL(allowedMenus[0], req.url));
      }
      // Jika kosong sama sekali (tidak ada izin), paksa logout
      const res = NextResponse.redirect(new URL("/login", req.url));
      res.cookies.delete("dash_auth");
      return res;
    }

    // Cek kecocokan path dinamis
    const isAllowed = role === "owner" || allowedMenus.some(menu => {
      if (menu === "/") return false;
      return pathname.startsWith(menu);
    });

    if (!isAllowed) {
      // Tidak diizinkan, kembalikan ke halaman utama yang boleh diakses
      const defaultPath = allowedMenus.includes("/") ? "/" : (allowedMenus[0] || "/login");
      if (defaultPath === "/login") {
        const res = NextResponse.redirect(new URL("/login", req.url));
        res.cookies.delete("dash_auth");
        return res;
      }
      return NextResponse.redirect(new URL(defaultPath, req.url));
    }

    return NextResponse.next();
  }

  // 4. Skenario Pengguna BELUM Login
  if (pathname === "/login") {
    return NextResponse.next();
  }

  // Semua halaman internal lainnya wajib login
  return NextResponse.redirect(new URL("/login", req.url));
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
