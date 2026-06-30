import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const market = searchParams.get("market") || "";
  const search = searchParams.get("search") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = parseInt(searchParams.get("limit") || "15", 10);
  const offset = (page - 1) * limit;

  let whereClauses: string[] = [];
  let params: any[] = [];

  if (market) {
    whereClauses.push(`market = $${whereClauses.length + 1}`);
    params.push(market);
  }

  if (search) {
    whereClauses.push(`(sku iLike $${whereClauses.length + 1} or nama_produk iLike $${whereClauses.length + 1})`);
    params.push(`%${search}%`);
  }

  const whereStr = whereClauses.length > 0 ? "where " + whereClauses.join(" and ") : "";

  const countSql = `select count(*) as total from riset_produk_acuan ${whereStr}`;
  const dataSql = `
    select id, market, sku, nama_produk, tgl_upload, gambar_produk, harga, link_produk, skip_itemid, tanggal_update, product_category, total_stock_parent_sku, total_stock_available_po_parent_sku, sales_per_toko, total_sales_shopee, total_sales_parent_sku
    from riset_produk_acuan
    ${whereStr}
    order by total_sales_shopee desc, sku asc
    limit $${params.length + 1} offset $${params.length + 2}
  `;

  try {
    const [totalRes, dataRes] = await Promise.all([
      q<{ total: string }>(countSql, params),
      q<any>(dataSql, [...params, limit, offset])
    ]);

    const total = parseInt(totalRes[0]?.total || "0", 10);

    return NextResponse.json({
      success: true,
      data: dataRes,
      pagination: {
        total,
        page,
        limit,
        pages: Math.ceil(total / limit)
      }
    });
  } catch (err: any) {
    console.error("API Riset List Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get("dash_auth")?.value;
    const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
    const user = token ? await verifySession(token, secret) : null;
    const role = user?.role || "staff";

    if (role !== "owner" && !user?.can_edit_competitor) {
      return NextResponse.json(
        { success: false, error: "Akses ditolak: Anda tidak memiliki izin untuk mengedit riset kompetitor." },
        { status: 403 }
      );
    }

    const body = await request.json();
    const { sku, market, link_produk, product_category } = body;

    if (!sku || !market || !link_produk) {
      return NextResponse.json(
        { success: false, error: "SKU, Market, dan Link Produk wajib diisi." },
        { status: 400 }
      );
    }

    await q(
      `insert into riset_produk_acuan (market, sku, link_produk, product_category, nama_produk, tgl_upload, gambar_produk, harga, skip_itemid, tanggal_update)
       values ($1, $2, $3, $4, $2, null, null, null, null, null)`,
      [market.trim(), sku.trim(), link_produk.trim(), (product_category || "").trim()]
    );

    return NextResponse.json({
      success: true,
      message: "Produk acuan berhasil ditambahkan ke dalam antrean riset."
    });
  } catch (err: any) {
    console.error("API Riset Add Product Error:", err);
    if (err.code === "23505") {
      return NextResponse.json(
        { success: false, error: "Produk dengan link ini sudah terdaftar di market tersebut." },
        { status: 400 }
      );
    }
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

