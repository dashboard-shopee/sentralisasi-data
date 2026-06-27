import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { signSession } from "@/lib/auth";

async function sendWhatsapp(target: string, message: string) {
  const gatewayUrl = (process.env.WA_GATEWAY_URL || "http://localhost:5001/send-otp").trim();
  const gatewaySecret = (process.env.WA_GATEWAY_SECRET || "syntra_gateway_secret_2026").trim();
  
  try {
    const res = await fetch(gatewayUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${gatewaySecret}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        target,
        message
      })
    });
    const data = await res.json().catch(() => ({}));
    console.log("[WA OTP SENT] Local Gateway Response:", data);
    return res.ok;
  } catch (err: any) {
    console.warn(`\n==================================================\n[WA OTP GATEWAY OFFLINE] Could not connect to gateway.\nOTP Message: "${message}"\nError: ${err.message}\n==================================================\n`);
    return false;
  }
}

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

      // Kirim ke WhatsApp
      const targetPhone = "082114417314";
      const message = `[SYNTRA OTP] Kode OTP Anda untuk masuk sebagai Owner adalah: *${otp}*. Kode berlaku selama 5 menit.`;
      
      // Kirim secara async, jika gagal token tetap tertulis di log console server
      await sendWhatsapp(targetPhone, message);

      return NextResponse.json({
        requiresOtp: true,
        message: "Kode OTP telah dikirim ke WhatsApp Anda."
      });
    } catch (err: any) {
      console.error("Owner Login Error:", err);
      return NextResponse.json({ ok: false, error: "Terjadi kesalahan internal" }, { status: 500 });
    }
  }

  // 2. Cek Skenario Staf biasa (password dicocokkan ke database_user)
  try {
    const userRes = await q<any>(
      "select id, username, allowed_menus, can_edit_ads, can_edit_competitor, session_duration_days from dashboard_user where password = $1",
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
        can_edit_competitor: !!user.can_edit_competitor
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
