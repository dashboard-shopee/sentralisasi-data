import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";

// GET ga manggil cookies() (cuma POST/DELETE di file ini yg pakai) -> tanpa ini bisa kena
// Full Route Cache Next.js, detail produk basi walau data di DB udah keupdate.
export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    // 1. Fetch acuan product details
    const acuan = await q<any>(
      `select * from riset_produk_acuan where id = $1`,
      [id]
    );
    if (!acuan || acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan" }, { status: 404 });
    }

    const prod = acuan[0];

    // 2. Fetch competitor details
    const competitors = await q<any>(
      `select id, produk_acuan_id, tipe, rank, url, nama_toko, harga, terjual, gambar, diambil_pada
       from riset_kompetitor_detail
       where produk_acuan_id = $1
       order by tipe, rank`,
      [id]
    );

    // 3. Fetch SKU database link matching this product's SKU
    let dbLink = null;
    if (prod.sku) {
      const dbLinkRes = await q<any>(
        `select sku, status, total_sales_parent_sku, links, diperbarui_pada
         from sku_database_link
         where sku = $1`,
        [prod.sku]
      );
      if (dbLinkRes.length > 0) {
        dbLink = dbLinkRes[0];
      }
    }

    // 4. Fetch Kimmio and Lolly items from dim_produk dynamically
    if (prod.sku) {
      const additionalLinks = await q<any>(
        `select p.produk_id, p.toko_id, t.nama as toko_nama
         from dim_produk p
         join dim_toko t on p.toko_id = t.toko_id
         where p.sku_induk = $1 and p.toko_id in (1, 2)`,
        [prod.sku]
      );
      
      if (additionalLinks.length > 0) {
        if (!dbLink) {
          dbLink = {
            sku: prod.sku,
            status: null,
            total_sales_parent_sku: 0,
            links: {}
          };
        } else if (!dbLink.links) {
          dbLink.links = {};
        }
        
        for (const linkItem of additionalLinks) {
          const shopId = linkItem.toko_id === 1 ? "124115456" : "260408542";
          const storeKey = linkItem.toko_id === 1 ? "KIMMIO" : "LOLLYSWEET";
          const itemId = String(linkItem.produk_id);
          dbLink.links[storeKey] = {
            url: `https://shopee.co.id/product/${shopId}/${itemId}`,
            item_id: itemId,
            search_similar_url: `https://shopee.co.id/find_similar_products?itemid=${itemId}&shopid=${shopId}`
          };
        }
      }
    }

    // 5. Fetch excluded competitors
    const excluded = await q<any>(
      `select id, produk_acuan_id, item_id, url, nama_toko, harga, terjual, gambar, diambil_pada
       from riset_kompetitor_excluded
       where produk_acuan_id = $1
       order by diambil_pada desc`,
      [id]
    );

    return NextResponse.json({
      success: true,
      data: {
        product: prod,
        competitors,
        databaseLink: dbLink,
        excluded
      }
    });
  } catch (err: any) {
    console.error("API Riset Detail Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

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
        return NextResponse.json({ success: false, error: "Akses ditolak: Anda tidak memiliki izin untuk mengedit riset kompetitor." }, { status: 403 });
      }
    }

    const body = await request.json();
    const { manualUrls } = body; // Array of strings (URLs)

    if (!Array.isArray(manualUrls)) {
      return NextResponse.json({ success: false, error: "manualUrls harus berupa array string" }, { status: 400 });
    }

    // 1. Check if product acuan exists
    const acuan = await q(
      `select id, sku from riset_produk_acuan where id = $1`,
      [id]
    );
    if (acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan" }, { status: 404 });
    }

    // 2. Truncate existing manual competitors for this acuan
    await q(
      `delete from riset_kompetitor_detail where produk_acuan_id = $1 and tipe = 'manual'`,
      [id]
    );

    // 3. Insert new manual competitor slots
    for (let i = 0; i < Math.min(manualUrls.length, 10); i++) {
      const url = String(manualUrls[i] || "").trim();
      if (url) {
        await q(
          `insert into riset_kompetitor_detail (produk_acuan_id, tipe, rank, url, nama_toko, harga, terjual, gambar, diambil_pada)
           values ($1, 'manual', $2, $3, $4, $5, $6, $7, null)`,
          [id, i + 1, url, url, "Menunggu Scrape...", "Rp0", 0, ""]
        );
      }
    }

    // Reset tanggal_update to null so that the scraper will pick it up on the next run!
    await q(
      `update riset_produk_acuan set tanggal_update = null where id = $1`,
      [id]
    );

    return NextResponse.json({
      success: true,
      message: "Daftar link manual berhasil diperbarui. Antrean riset telah di-reset agar segera di-scrape."
    });
  } catch (err: any) {
    console.error("API Riset Detail POST Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

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
        return NextResponse.json({ success: false, error: "Akses ditolak: Anda tidak memiliki izin untuk mengedit riset kompetitor." }, { status: 403 });
      }
    }

    const acuan = await q(
      `select id from riset_produk_acuan where id = $1`,
      [id]
    );
    if (acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan" }, { status: 404 });
    }

    await q(`delete from riset_produk_acuan where id = $1`, [id]);

    return NextResponse.json({
      success: true,
      message: "Produk acuan beserta seluruh data riset terkait berhasil dihapus."
    });
  } catch (err: any) {
    console.error("API Riset Detail DELETE Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

