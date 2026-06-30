import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const skuDetail = p.get("sku") || "";

  try {
    if (skuDetail) {
      // Get detailed metrics for one SKU
      const sales = await q<any>(
        `select grup_toko "toko", total_qty "qty" from erp_sales_data where sku = $1 order by total_qty desc`,
        [skuDetail]
      );
      const weekly = await q<any>(
        `select w0, w1, w2, w3, w4 from erp_weekly_sales where sku = $1`,
        [skuDetail]
      );
      const shopee = await q<any>(
        `select total_qty "totalQty", total_orders "totalOrders", single_sku_orders "singleOrders", multi_sku_orders "multiOrders", multi_sku_qty "multiQty" 
         from erp_shopee_metrics where sku = $1`,
        [skuDetail]
      );
      const bounds = await q<any>(
        `select week_key "key", start_time "start", end_time "end" from erp_week_bounds order by week_key asc`
      );

      return NextResponse.json({
        sales,
        weekly: weekly[0] || null,
        shopee: shopee[0] || null,
        bounds
      });
    }

    // Default: paginated catalog list
    const search = p.get("q") || "";
    const page = parseInt(p.get("page") || "1") || 1;
    const size = parseInt(p.get("size") || "50") || 50;
    const offset = (page - 1) * size;
    
    // Sort
    const sortCol = p.get("sort") || "";
    const sortDir = p.get("dir") || "desc";

    let W = "1=1";
    const params: unknown[] = [];
    if (search) {
      params.push(`%${search}%`);
      W += ` and (sku ilike $1 or parent_sku ilike $1 or product_name ilike $1 or current_category ilike $1 or po_no ilike $1)`;
    }

    let order = "coalesce(ps.parent_qty, 0) desc, parent_sku asc, sku asc";
    if (sortCol) {
      const allowed = ["sku", "parent_sku", "product_name", "current_category", "total_stock", "total_inbound", "ttos_date", "po_no", "ordered_at", "forecast_val"];
      if (allowed.includes(sortCol)) {
        const col = sortCol === "parent_sku" ? "parent_sku" : sortCol === "product_name" ? "product_name" : sortCol === "current_category" ? "current_category" : sortCol === "ordered_at" ? "ordered_at" : sortCol;
        order = `${col} ${sortDir === "asc" ? "asc" : "desc"}`;
      }
    }

    params.push(size, offset);
    const rows = await q<any>(
      `with parent_sales as (
         select 
           coalesce(nullif(e2.parent_sku, ''), e2.sku) as parent_group,
           sum(coalesce(sm.total_qty, 0)) as parent_qty
         from erp_sku_list e2
         left join erp_shopee_metrics sm on e2.sku = sm.sku
         group by coalesce(nullif(e2.parent_sku, ''), e2.sku)
       )
       select sku, parent_sku "parentSku", product_name "productName", current_category "category", 
              total_stock "stock", total_inbound "inbound", ttos_date "ttosDate", po_no "poNo", 
              ordered_at "orderedAt", forecast_val "forecast"
       from erp_sku_list
       left join parent_sales ps on coalesce(nullif(parent_sku, ''), sku) = ps.parent_group
       where ${W}
       order by ${order}
       limit $${params.length - 1} offset $${params.length}`,
      params
    );

    const countParams = search ? [`%${search}%`] : [];
    const total = await q<{ count: string }>(
      `select count(*) from erp_sku_list where ${W}`,
      countParams
    );

    return NextResponse.json({
      rows,
      total: parseInt(total[0]?.count || "0")
    });

  } catch (err: any) {
    console.error("GET /api/produk/stok error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
