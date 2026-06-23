import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Penjaga: semua halaman butuh cookie auth, kecuali halaman/login API.
export function middleware(req: NextRequest) {
  const pass = (process.env.DASH_PASSWORD || "").trim();
  const auth = req.cookies.get("dash_auth")?.value;
  const ok = pass && auth === pass;
  const { pathname } = req.nextUrl;

  // izinkan halaman login, API login, dan semua file statis (punya ekstensi: .png/.svg/.ico/.css/.js dst)
  if (ok || pathname.startsWith("/login") || pathname.startsWith("/api/login") || /\.[a-zA-Z0-9]+$/.test(pathname)) {
    return NextResponse.next();
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
