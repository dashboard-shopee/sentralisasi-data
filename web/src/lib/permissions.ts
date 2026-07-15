import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";
import { q } from "@/lib/db";

// Daftar tab per halaman yang punya navigasi tab internal. Dipakai sebagai
// default "semua boleh" kalau field allowed_tabs user belum diisi/null
// (backward compatible utk user lama), dan sebagai validasi input di API users.
export const TABS_BY_PAGE: Record<string, string[]> = {
  harga: ["all", "olah", "komisi", "riwayat"],
  promosi: ["promo_toko", "garansi", "campaign", "flash", "voucher", "paket", "komisi"],
  kalkulator: ["single", "batch"],
};

export interface ViewPerms {
  netPrice: boolean;
  margin: boolean;
  hpp: boolean;
  hargaJualKomisi: boolean;
  allowedTabs: Record<string, string[]>; // { harga: [...], promosi: [...], kalkulator: [...] }
}

const FULL_TABS: Record<string, string[]> = TABS_BY_PAGE;

function normalizeAllowedTabs(raw: unknown): Record<string, string[]> {
  let parsed: Record<string, unknown> | null = null;
  if (typeof raw === "string") {
    try { parsed = JSON.parse(raw); } catch { parsed = null; }
  } else if (raw && typeof raw === "object") {
    parsed = raw as Record<string, unknown>;
  }
  const out: Record<string, string[]> = {};
  for (const page of Object.keys(TABS_BY_PAGE)) {
    const val = parsed && Array.isArray(parsed[page]) ? (parsed[page] as string[]) : null;
    out[page] = val && val.length > 0 ? val.filter((t: string) => TABS_BY_PAGE[page].includes(t)) : TABS_BY_PAGE[page];
  }
  return out;
}

interface DashboardUserRow {
  can_view_net_price: boolean | null;
  can_view_margin: boolean | null;
  can_view_hpp: boolean | null;
  can_view_harga_jual_komisi: boolean | null;
  allowed_tabs: unknown;
}

// Ambil izin lihat (field sensitif + tab per halaman) live dari DB (bukan cache JWT).
// Owner / tanpa sesi valid -> owner full akses, tanpa sesi -> semua false/kosong (aman).
export async function getViewPerms(): Promise<ViewPerms> {
  const cookieStore = await cookies();
  const token = cookieStore.get("dash_auth")?.value;
  if (!token) return { netPrice: false, margin: false, hpp: false, hargaJualKomisi: false, allowedTabs: { harga: [], promosi: [], kalkulator: [] } };

  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const user = await verifySession(token, secret);
  if (!user) return { netPrice: false, margin: false, hpp: false, hargaJualKomisi: false, allowedTabs: { harga: [], promosi: [], kalkulator: [] } };

  if (user.role === "owner") {
    return { netPrice: true, margin: true, hpp: true, hargaJualKomisi: true, allowedTabs: { ...FULL_TABS } };
  }

  const rows = await q<DashboardUserRow>(
    "select can_view_net_price, can_view_margin, can_view_hpp, can_view_harga_jual_komisi, allowed_tabs from dashboard_user where id = $1",
    [user.id]
  );
  if (rows.length === 0) {
    return { netPrice: false, margin: false, hpp: false, hargaJualKomisi: false, allowedTabs: { harga: [], promosi: [], kalkulator: [] } };
  }
  const r = rows[0];
  return {
    netPrice: r.can_view_net_price !== false,
    margin: r.can_view_margin !== false,
    hpp: r.can_view_hpp !== false,
    hargaJualKomisi: r.can_view_harga_jual_komisi !== false,
    allowedTabs: normalizeAllowedTabs(r.allowed_tabs),
  };
}

export function isTabAllowed(perms: ViewPerms, page: keyof typeof TABS_BY_PAGE, tabKey: string): boolean {
  return perms.allowedTabs[page]?.includes(tabKey) ?? false;
}
