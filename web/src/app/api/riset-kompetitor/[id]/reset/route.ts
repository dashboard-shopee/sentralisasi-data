import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const acuanId = parseInt(id, 10);

  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("dash_auth")?.value;
    const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
    const user = token ? await verifySession(token, secret) : null;
    const role = user?.role || "staff";

    if (role !== "owner") {
      const dbUser = user?.id ? await q<any>(
        "select can_edit_competitor from dashboard_user where id = $1",
        [user.id]
      ) : [];
      const perms = dbUser.length > 0 ? dbUser[0] : { can_edit_competitor: false };

      if (!perms.can_edit_competitor) {
        return NextResponse.json(
          { success: false, error: "Akses ditolak: Anda tidak memiliki izin untuk mengedit riset kompetitor." },
          { status: 403 }
        );
      }
    }

    // Verify product acuan exists
    const acuan = await q<any>(
      `select id, sku from riset_produk_acuan where id = $1`,
      [acuanId]
    );
    if (acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan" }, { status: 404 });
    }

    // Reset tanggal_update to null
    await q(
      `update riset_produk_acuan set tanggal_update = null where id = $1`,
      [acuanId]
    );

    return NextResponse.json({
      success: true,
      message: `Status update untuk SKU "${acuan[0].sku}" berhasil di-reset menjadi Antrean.`
    });
  } catch (err: any) {
    console.error("API Riset Reset Date Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
