import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { signSession } from "@/lib/auth";

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as { otp?: string };
    const inputOtp = (body.otp || "").trim();

    if (!inputOtp) {
      return NextResponse.json({ ok: false, error: "Kode OTP wajib diisi" }, { status: 400 });
    }

    // Cari OTP terbaru yang belum terpakai dan belum expired
    const otpRes = await q<any>(
      "select id, otp_code, expired_at from owner_otp_session where is_verified = false and expired_at > now() order by dibuat_pada desc limit 1"
    );

    if (!otpRes || otpRes.length === 0) {
      return NextResponse.json({ ok: false, error: "Kode OTP tidak valid atau telah kadaluwarsa" }, { status: 400 });
    }

    const latestOtp = otpRes[0];

    // Cek kecocokan OTP
    if (latestOtp.otp_code !== inputOtp) {
      return NextResponse.json({ ok: false, error: "Kode OTP salah, silakan coba lagi." }, { status: 400 });
    }

    // OTP Valid -> Tandai sebagai terpakai
    await q("update owner_otp_session set is_verified = true where id = $1", [latestOtp.id]);

    // Ambil data Owner dari database untuk mendapatkan konfigurasi terupdate
    const ownerRes = await q<any>(
      "select id, username, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_margin, avatar_emoji, session_duration_days from dashboard_user where username = 'Owner' limit 1"
    );

    let ownerInfo = {
      id: 1,
      username: "Owner",
      role: "owner",
      allowed_menus: ["/", "/analisa", "/penjualan", "/pesanan", "/produk/harga", "/produk/stok", "/produk/kalkulator", "/riset-kompetitor", "/pengaturan-akses"],
      can_edit_ads: true,
      can_edit_competitor: true,
      session_duration_days: 30
    };

    if (ownerRes && ownerRes.length > 0) {
      const dbOwner = ownerRes[0];
      ownerInfo = {
        id: dbOwner.id,
        username: dbOwner.username,
        role: "owner",
        allowed_menus: typeof dbOwner.allowed_menus === "string" ? JSON.parse(dbOwner.allowed_menus) : dbOwner.allowed_menus,
        can_edit_ads: !!dbOwner.can_edit_ads,
        can_edit_competitor: !!dbOwner.can_edit_competitor,
        can_edit_harga: !!dbOwner.can_edit_harga,
        can_edit_komisi: !!dbOwner.can_edit_komisi,
        can_edit_kalkulator: !!dbOwner.can_edit_kalkulator,
        can_view_margin: true,
        avatar_emoji: dbOwner.avatar_emoji || null,
        session_duration_days: dbOwner.session_duration_days || 30
      } as any;
    }

    const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
    const durationSeconds = ownerInfo.session_duration_days * 24 * 3600;

    // Buat token session
    const tokenPayload = {
      id: ownerInfo.id,
      username: ownerInfo.username,
      role: "owner",
      allowed_menus: ownerInfo.allowed_menus,
      can_edit_ads: ownerInfo.can_edit_ads,
      can_edit_competitor: ownerInfo.can_edit_competitor,
      can_edit_harga: (ownerInfo as any).can_edit_harga ?? true,
      can_edit_komisi: (ownerInfo as any).can_edit_komisi ?? true,
      can_edit_kalkulator: (ownerInfo as any).can_edit_kalkulator ?? true,
      can_view_margin: true,
      avatar_emoji: (ownerInfo as any).avatar_emoji || null
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
  } catch (err: any) {
    console.error("OTP Verification Error:", err);
    return NextResponse.json({ ok: false, error: "Terjadi kesalahan internal" }, { status: 500 });
  }
}
