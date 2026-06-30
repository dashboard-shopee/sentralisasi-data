import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { verifySession } from "@/lib/auth";
import { q } from "@/lib/db";

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

  try {
    const userRes = await q<any>(
      "select username, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, avatar_emoji from dashboard_user where id = $1",
      [payload.id]
    );
    if (userRes && userRes.length > 0) {
      const dbUser = userRes[0];
      return NextResponse.json({
        ok: true,
        user: {
          username: dbUser.username,
          role: payload.role,
          allowedMenus: typeof dbUser.allowed_menus === "string" ? JSON.parse(dbUser.allowed_menus) : (dbUser.allowed_menus || []),
          canEditAds: !!dbUser.can_edit_ads,
          canEditCompetitor: !!dbUser.can_edit_competitor,
          canEditHarga: !!dbUser.can_edit_harga,
          canEditKomisi: !!dbUser.can_edit_komisi,
          canEditKalkulator: !!dbUser.can_edit_kalkulator,
          avatarEmoji: dbUser.avatar_emoji || null
        }
      });
    }
  } catch (err) {
    console.error("me API database query error:", err);
  }

  // Fallback ke data JWT jika database bermasalah
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
