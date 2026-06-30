import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { verifySession } from "@/lib/auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get("dash_auth")?.value;

  if (!token) {
    return NextResponse.json({ ok: false, error: "Not authenticated" }, { status: 401 });
  }

  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const payload = await verifySession(token, secret);

  if (!payload) {
    return NextResponse.json({ ok: false, error: "Session invalid or expired" }, { status: 401 });
  }

  // Kembalikan data profil user
  return NextResponse.json({
    ok: true,
    user: {
      username: payload.username,
      role: payload.role,
      allowedMenus: payload.allowed_menus || [],
      canEditAds: !!payload.can_edit_ads,
      canEditCompetitor: !!payload.can_edit_competitor,
      canEditHarga: !!payload.can_edit_harga,
      canEditKomisi: !!payload.can_edit_komisi,
      canEditKalkulator: !!payload.can_edit_kalkulator,
      avatarEmoji: payload.avatar_emoji || null
    }
  });
}
