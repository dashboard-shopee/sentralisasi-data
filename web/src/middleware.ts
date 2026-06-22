import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Penjaga: semua halaman butuh cookie auth, kecuali halaman/login API.
export function middleware(req: NextRequest) {
  const pass = process.env.DASH_PASSWORD || "";
  const auth = req.cookies.get("dash_auth")?.value;
  const ok = pass && auth === pass;
  const { pathname } = req.nextUrl;

  if (ok || pathname.startsWith("/login") || pathname.startsWith("/api/login")) {
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
