import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { signSession } from "@/lib/auth";
import { sendOtpEmail } from "@/lib/email";

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as { password?: string };
  const inputPassword = (body.password || "").trim();

  if (!inputPassword) {
    return NextResponse.json({ ok: false, error: "Password wajib diisi" }, { status: 400 });
  }

  // 1. Cek Skenario Owner (password: Restu_99)
  if (inputPassword === "Restu_99") {
    // Generate 6 digit OTP
    const otp = Math.floor(100000 + Math.random() * 900000).toString();
    
    try {
      // Simpan OTP ke database dengan masa berlaku 5 menit
      await q(
        "insert into owner_otp_session (otp_code, expired_at) values ($1, now() + interval '5 minutes')",
        [otp]
      );

      // Kirim ke Email
      const emailTarget = (process.env.EMAIL_TO || "beverramarketing@gmail.com").trim();
      
      // Kirim secara async
      await sendOtpEmail(emailTarget, otp);

      return NextResponse.json({
        requiresOtp: true,
        email: emailTarget,
        message: "Kode OTP telah dikirim ke Email Anda."
      });
    } catch (err: any) {
      console.error("Owner Login Error:", err);
      return NextResponse.json({ ok: false, error: "Terjadi kesalahan internal" }, { status: 500 });
    }
  }

  // 2. Cek Skenario Staf biasa (password dicocokkan ke database_user)
  try {
    const userRes = await q<any>(
      "select id, username, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_margin, avatar_emoji, session_duration_days from dashboard_user where password = $1",
      [inputPassword]
    );

    if (userRes && userRes.length > 0) {
      const user = userRes[0];
      const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
      const durationSeconds = (user.session_duration_days || 7) * 24 * 3600;

      // Buat token session
      const tokenPayload = {
        id: user.id,
        username: user.username,
        role: user.username === "Owner" ? "owner" : "staff",
        allowed_menus: typeof user.allowed_menus === "string" ? JSON.parse(user.allowed_menus) : user.allowed_menus,
        can_edit_ads: !!user.can_edit_ads,
        can_edit_competitor: !!user.can_edit_competitor,
        can_edit_harga: !!user.can_edit_harga,
        can_edit_komisi: !!user.can_edit_komisi,
        can_edit_kalkulator: !!user.can_edit_kalkulator,
        can_view_margin: user.can_view_margin !== false,
        avatar_emoji: user.avatar_emoji || null
      };

      const sessionToken = await signSession(tokenPayload, secret, durationSeconds);

      const res = NextResponse.json({ ok: true });
      res.cookies.set("dash_auth", sessionToken, {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        maxAge: durationSeconds,
        secure: process.env.NODE_ENV === "production",
      });
      return res;
    }

    return NextResponse.json({ ok: false, error: "Password salah, coba lagi." }, { status: 401 });
  } catch (err: any) {
    console.error("Login Query Error:", err);
    return NextResponse.json({ ok: false, error: "Database error" }, { status: 500 });
  }
}
