import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const pass = process.env.DASH_PASSWORD || "";
  const body = (await req.json().catch(() => ({}))) as { password?: string };
  if (pass && body.password === pass) {
    const res = NextResponse.json({ ok: true });
    res.cookies.set("dash_auth", pass, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 hari
      secure: process.env.NODE_ENV === "production",
    });
    return res;
  }
  return NextResponse.json({ ok: false }, { status: 401 });
}
