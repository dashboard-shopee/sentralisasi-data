import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";
import { q } from "@/lib/db";

// Cek live dari DB (bukan cuma JWT) apakah user boleh lihat data sensitif
// (Margin / HPP / Net Price). Owner selalu true. Tanpa sesi valid -> false (aman).
export async function getCanViewMargin(): Promise<boolean> {
  const cookieStore = await cookies();
  const token = cookieStore.get("dash_auth")?.value;
  if (!token) return false;

  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const user = await verifySession(token, secret);
  if (!user) return false;
  if (user.role === "owner") return true;

  const rows = await q<any>("select can_view_margin from dashboard_user where id = $1", [user.id]);
  return rows.length > 0 ? rows[0].can_view_margin !== false : true;
}
