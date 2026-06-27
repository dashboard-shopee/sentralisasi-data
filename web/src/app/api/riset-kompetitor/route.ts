import { NextResponse } from "next/server";
import { q } from "@/lib/db";

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
