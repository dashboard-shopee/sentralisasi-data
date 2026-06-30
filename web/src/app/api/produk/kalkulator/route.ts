import { NextResponse } from "next/server";
import { q } from "@/lib/db";
import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const tab = p.get("tab") || "batch";

  try {
    // 1. Ambil settings kalkulator dari database
    const dbSettings = await q<{ key: string; value: string }>(
      "select key, value from kalkulator_settings"
    );
    
    // Default fallback values
    const defaultSettings = {
      admin_fee_pct: 0.16,
      discount_ads_pct: 0.06,
      salary_pct: 0.08,
      commission_pct: 0.00,
      packing_fee: 400,
      service_fee: 1250,
      service_fee_min_hpp: 600,
    };

    const singleSettings: Record<string, number> = { ...defaultSettings };
    const batchSettings: Record<string, number> = { ...defaultSettings };

    // Populate from database
    dbSettings.forEach((item) => {
      if (item.key.startsWith("single_")) {
        const cleanKey = item.key.substring("single_".length);
        singleSettings[cleanKey] = parseFloat(item.value);
      } else if (item.key.startsWith("batch_")) {
        const cleanKey = item.key.substring("batch_".length);
        batchSettings[cleanKey] = parseFloat(item.value);
      } else {
        // Fallback for legacy keys (no prefix)
        if (item.key in defaultSettings) {
          singleSettings[item.key] = parseFloat(item.value);
          batchSettings[item.key] = parseFloat(item.value);
        }
      }
    });

    if (tab === "settings") {
      return NextResponse.json({ ok: true, single: singleSettings, batch: batchSettings });
    }

    // 2. Fetch paginated batch list
    const search = p.get("q") || "";
    const statusFilter = p.get("status") || "";
    const marginFilter = p.get("margin_status") || "";
    const page = parseInt(p.get("page") || "1") || 1;
    const size = parseInt(p.get("size") || "50") || 50;
    const offset = (page - 1) * size;
    
    const sortCol = p.get("sort") || "";
    const sortDir = p.get("dir") || "asc";

    // Constants to pass as parameters for dynamic SQL calculation (Batch Settings)
    const packing_fee = batchSettings.packing_fee;
    const service_fee_min_hpp = batchSettings.service_fee_min_hpp;
    const service_fee = batchSettings.service_fee;
    const total_pct_biaya = batchSettings.admin_fee_pct + batchSettings.discount_ads_pct + batchSettings.salary_pct + batchSettings.commission_pct;

    let W = "1=1";
    const params: unknown[] = [packing_fee, service_fee_min_hpp, service_fee, total_pct_biaya];

    if (search) {
      params.push(`%${search}%`);
      W += ` and (sku ilike $${params.length} or nama_produk ilike $${params.length})`;
    }

    if (statusFilter) {
      params.push(statusFilter);
      W += ` and status = $${params.length}`;
    }

    // CTE Query calculating everything dynamically
    const sqlBase = `
      with base as (
        select 
          e.sku,
          coalesce(s.status, '') as status,
          e.product_name as nama_produk,
          coalesce(e.hpp, 0)::float as hpp,
          coalesce(e.override_net, 0)::float as override_net,
          ($1 + (case when coalesce(e.hpp, 0) >= $2 then $3 else 0 end))::float as biaya_tetap,
          (case 
            when coalesce(e.hpp, 0) < 500 then 0.25 
            when coalesce(e.hpp, 0) < 1000 then 0.20 
            when coalesce(e.hpp, 0) < 3000 then 0.15 
            else 0.12 
          end)::float as target_margin
        from erp_sku_list e
        left join sku_database_link s on e.sku = s.sku
      ),
      calc1 as (
        select 
          sku,
          status,
          nama_produk,
          hpp,
          override_net,
          biaya_tetap,
          target_margin,
          (case 
            when override_net > 0 then override_net 
            else (hpp + biaya_tetap) / (1.0 - $4 - target_margin) 
          end)::float as harga_jual_net
        from base
      ),
      calc2 as (
        select 
          sku,
          status,
          nama_produk,
          hpp,
          override_net,
          harga_jual_net,
          ceil(harga_jual_net / 100.0) * 100 as net_rounded_100,
          (case 
            when harga_jual_net > 0 then (1.0 - $4 - (hpp + biaya_tetap) / harga_jual_net) 
            else 0.0 
          end)::float as actual_margin
        from calc1
      ),
      calc3 as (
        select 
          sku,
          status,
          nama_produk,
          hpp,
          override_net,
          harga_jual_net,
          net_rounded_100,
          actual_margin,
          (case 
            when actual_margin >= 0.12 then 'Good' 
            when actual_margin > 0.08 then 'Average' 
            when actual_margin > 0.00 then 'Bad' 
            else 'Rugi' 
          end) as margin_status
        from calc2
      )
    `;

    // Filter margin status di server jika dipilih
    let filterMargin = "";
    if (marginFilter) {
      params.push(marginFilter);
      filterMargin = ` and margin_status = $${params.length}`;
    }

    // Sorting
    let order = "sku asc";
    const allowedSort = ["sku", "status", "nama_produk", "hpp", "override_net", "harga_jual_net", "actual_margin", "margin_status"];
    if (sortCol && allowedSort.includes(sortCol)) {
      order = `${sortCol === "nama_produk" ? "nama_produk" : sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
    }

    // Query untuk hitung total
    const countSql = `${sqlBase} select count(*) from calc3 where ${W} ${filterMargin}`;
    const totalRes = await q<{ count: string }>(countSql, params);
    const total = parseInt(totalRes[0]?.count || "0");

    // Query untuk baris
    params.push(size, offset);
    const rowsSql = `
      ${sqlBase} 
      select * from calc3 
      where ${W} ${filterMargin} 
      order by ${order} 
      limit $${params.length - 1} offset $${params.length}
    `;
    const rows = await q<any>(rowsSql, params);

    return NextResponse.json({
      ok: true,
      rows,
      total,
      single: singleSettings,
      batch: batchSettings
    });

  } catch (err: any) {
    console.error("GET /api/produk/kalkulator error:", err);
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const { action } = body;

    // Ambil info user yang mengubah
    const cookieStore = await cookies();
    const token = cookieStore.get("dash_auth")?.value;
    const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
    const user = token ? await verifySession(token, secret) : null;
    const role = user?.role || "staff";

    // Validasi izin edit berdasarkan role dan permission
    if (role !== "owner" && !user?.can_edit_kalkulator) {
      return NextResponse.json({ ok: false, error: "Akses ditolak: Anda tidak memiliki izin mengedit kalkulator." }, { status: 403 });
    }

    if (action === "update-settings") {
      const { settings, type } = body;
      if (!settings || typeof settings !== "object" || (type !== "single" && type !== "batch")) {
        return NextResponse.json({ ok: false, error: "Settings tidak valid" }, { status: 400 });
      }

      // Simpan settings satu-satu dengan prefix sesuai type
      for (const [key, val] of Object.entries(settings)) {
        const dbKey = `${type}_${key}`;
        await q(
          `insert into kalkulator_settings (key, value, diperbarui_pada) 
           values ($1, $2, now()) 
           on conflict (key) do update set value = excluded.value, diperbarui_pada = now()`,
          [dbKey, parseFloat(val as string)]
        );
      }

      return NextResponse.json({ ok: true, message: `Setelan parameter ${type} berhasil disimpan` });
    }

    if (action === "update-product") {
      const { sku, hpp, override_net } = body;
      if (!sku) {
        return NextResponse.json({ ok: false, error: "SKU wajib diisi" }, { status: 400 });
      }

      await q(
        `update erp_sku_list 
         set hpp = $1, override_net = $2, diperbarui_pada = now() 
         where sku = $3`,
        [parseFloat(hpp || 0), parseFloat(override_net || 0), sku]
      );

      return NextResponse.json({ ok: true, message: `Produk ${sku} berhasil diperbarui` });
    }

    return NextResponse.json({ ok: false, error: "Action tidak dikenal" }, { status: 400 });

  } catch (err: any) {
    console.error("POST /api/produk/kalkulator error:", err);
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
