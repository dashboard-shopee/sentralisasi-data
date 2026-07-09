import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { q } from "@/lib/db";
import { verifySession } from "@/lib/auth";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const tab = p.get("tab") || "all";
  const search = p.get("q") || "";
  const page = parseInt(p.get("page") || "1") || 1;
  const size = parseInt(p.get("size") || "50") || 50;
  const offset = (page - 1) * size;
  const sortCol = p.get("sort") || "";
  const sortDir = p.get("dir") || "desc";

  try {
    const activeTokos = await q<any>(`select username, nama from dim_toko order by shop_index`);

    if (tab === "all") {
      let W = "1=1";
      const params: unknown[] = [];
      if (search) {
        params.push(`%${search}%`);
        W += ` and (h.sku ilike $1 or h.sku_induk ilike $1 or h.nama_produk ilike $1)`;
      }

      let order = "h.sku asc";
      if (sortCol) {
        const allowed = ["sku", "sku_induk", "nama_produk", "category", "net_price_awal", "net_price_detail", "harga_awal", "harga_diskon", "harga_pancing", "margin_persen", "diperbarui_pada"];
        const colMap: Record<string, string> = {
          sku: "h.sku", sku_induk: "h.sku_induk", nama_produk: "h.nama_produk", category: "h.category", 
          harga_awal: "h.harga_awal", harga_pancing: "h.harga_pancing", diperbarui_pada: "h.diperbarui_pada"
        };
        const sqlOrderCol = colMap[sortCol] || sortCol;
        order = `${sqlOrderCol} ${sortDir === "asc" ? "asc" : "desc"}`;
      }

      const sqlBase = `
        with base as (
          select 
            h.sku, h.sku_induk, h.nama_produk, h.category,
            h.harga_awal, h.harga_pancing, h.harga_diskon, h.diperbarui_pada,
            h.custom_harga_diskon, h.custom_harga_pancing,
            coalesce(e.hpp, 0) as hpp, coalesce(e.override_net, 0) as override_net,
            coalesce(sm.total_qty, 0)::numeric as total_qty,
            coalesce(sm.total_orders, 0)::numeric as total_orders,
            sum(coalesce(sm.total_qty, 0)) over (partition by coalesce(nullif(h.sku_induk, ''), h.sku))::numeric as parent_total_qty
          from harga_all_produk h
          left join erp_sku_list e on h.sku = e.sku
          left join erp_shopee_metrics sm on h.sku = sm.sku
          where ${W}
        ),
        kalkulator_settings as (
          select 
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_packing_fee'), 400) as packing_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee_min_hpp'), 600) as min_hpp,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee'), 1250) as service_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_admin_fee_pct'), 0.16) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_discount_ads_pct'), 0.06) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_salary_pct'), 0.08) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_commission_pct'), 0.0) as total_pct_biaya
        ),
        calc1 as (
          select b.*, ks.packing_fee, ks.min_hpp, ks.service_fee, ks.total_pct_biaya,
            (ks.packing_fee + (case when b.hpp >= ks.min_hpp then ks.service_fee else 0 end))::numeric as biaya_tetap,
            (case when b.hpp < 500 then 0.25 when b.hpp < 1000 then 0.20 when b.hpp < 3000 then 0.15 else 0.12 end)::numeric as target_margin
          from base b cross join kalkulator_settings ks
        ),
        calc2 as (
          select c1.*,
            (case when c1.override_net > 0 then c1.override_net else (c1.hpp + c1.biaya_tetap) / nullif((1.0 - c1.total_pct_biaya - c1.target_margin), 0) end)::numeric as net_price_awal
          from calc1 c1
        ),
        calc3 as (
          select c2.*,
            (case when c2.total_qty > 0 then c2.net_price_awal - ((greatest(0, c2.total_qty - c2.total_orders) / c2.total_qty) * c2.service_fee) else c2.net_price_awal end)::numeric as net_price_detail,
            (c2.packing_fee + (case when c2.total_qty > 0 then c2.service_fee * c2.total_orders / c2.total_qty else c2.service_fee end))::numeric as biaya_tetap_adjusted
          from calc2 c2
        ),
        olah_toko as (
          select sku, jsonb_agg(jsonb_build_object('toko', toko, 'itemId', item_id, 'harga', harga_tampil)) as catalogs
          from harga_olah_data group by sku
        ),
        final as (
          select
            c3.sku, c3.sku_induk as "sku_induk", c3.nama_produk as "nama_produk", c3.category, c3.harga_awal as "harga_awal",
            c3.custom_harga_pancing as "custom_harga_pancing",
            (case when c3.custom_harga_pancing is not null then c3.custom_harga_pancing else c3.harga_pancing end)::numeric as "harga_pancing",
            c3.diperbarui_pada as "diperbarui_pada",
            c3.net_price_awal as "net_price_awal", c3.net_price_detail as "net_price_detail",
            c3.custom_harga_diskon as "custom_harga_diskon",
            -- Harga Diskon TERSIMPAN (stabil): custom override -> harga_diskon stored -> net_price_detail (fallback)
            (case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon else coalesce(nullif(c3.harga_diskon, 0), c3.net_price_detail) end)::numeric as harga_diskon,
            (case when (case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon else coalesce(nullif(c3.harga_diskon, 0), c3.net_price_detail) end) > 0
               then 1.0 - c3.total_pct_biaya - ((c3.hpp + c3.biaya_tetap_adjusted) / nullif((case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon else coalesce(nullif(c3.harga_diskon, 0), c3.net_price_detail) end), 0))
               else 0.0 end)::numeric as margin_persen,
            coalesce(ot.catalogs, '[]'::jsonb) as catalogs,
            c3.parent_total_qty
          from calc3 c3
          left join olah_toko ot on c3.sku = ot.sku
        )
      `;

      const rowsSql = `
        ${sqlBase}
        select * from final 
        order by ${sortCol ? (["sku", "sku_induk", "nama_produk", "category", "harga_awal", "harga_pancing", "diperbarui_pada"].includes(sortCol) ? sortCol : `"${sortCol}"`) : 'parent_total_qty'} ${sortCol ? (sortDir === "asc" ? "asc" : "desc") : 'desc'}, sku_induk asc, sku asc 
        limit $${params.length + 1} offset $${params.length + 2}
      `;
      
      const rows = await q<any>(rowsSql, [...params, size, offset]);
      const total = await q<{ count: string }>(`select count(*) from harga_all_produk h where ${W}`, params);

      return NextResponse.json({ rows, total: parseInt(total[0]?.count || "0"), tokos: activeTokos });

    } else if (tab === "olah") {
      let W = "1=1";
      const params: unknown[] = [];
      const filterToko = p.get("toko") || "";
      if (filterToko) { params.push(filterToko); W += ` and toko = $${params.length}`; }
      const filterSumber = p.get("sumber") || "";
      if (filterSumber) { params.push(filterSumber); W += ` and sumber_harga = $${params.length}`; }
      if (search) {
        params.push(`%${search}%`);
        W += ` and (sku ilike $${params.length} or nama_produk ilike $${params.length} or nama_variasi ilike $${params.length} or item_id::text like $${params.length} or model_id::text like $${params.length})`;
      }
      let order = "coalesce(ss.parent_qty, 0) desc, ho.toko asc, ho.item_id asc, ho.model_id asc";
      if (sortCol) {
        const allowed = ["toko", "item_id", "model_id", "ptag", "sku", "nama_variasi", "nama_produk", "harga_awal", "harga_pancing", "harga_akhir_target", "harga_tampil", "selisih", "sumber_harga", "alasan", "diperbarui_pada"];
        if (sortCol === "margin_persen") order = `"marginPersen" ${sortDir === "asc" ? "asc" : "desc"} nulls last`;
        else if (allowed.includes(sortCol)) order = `ho.${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
      }
      params.push(size, offset);
      const rows = await q<any>(`
        with parent_sales as (
          select
            coalesce(nullif(e2.parent_sku, ''), e2.sku) as parent_group,
            sum(coalesce(sm.total_qty, 0)) as parent_qty
          from erp_sku_list e2
          left join erp_shopee_metrics sm on e2.sku = sm.sku
          group by coalesce(nullif(e2.parent_sku, ''), e2.sku)
        ),
        sku_sales as (
          select
            e2.sku as sales_sku,
            coalesce(ps.parent_qty, 0) as parent_qty
          from erp_sku_list e2
          left join parent_sales ps on coalesce(nullif(e2.parent_sku, ''), e2.sku) = ps.parent_group
        ),
        kalk as (
          select
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_packing_fee'), 400) as packing_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee'), 1250) as service_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_admin_fee_pct'), 0.16) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_discount_ads_pct'), 0.06) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_salary_pct'), 0.08) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_commission_pct'), 0.0) as total_pct_biaya
        ),
        sku_cost as (
          select upper(h.sku) as sku_u,
            coalesce(e.hpp, 0)::numeric as hpp,
            k.total_pct_biaya,
            (k.packing_fee + (case when coalesce(sm.total_qty, 0) > 0 then k.service_fee * coalesce(sm.total_orders, 0) / sm.total_qty else k.service_fee end))::numeric as biaya_tetap_adjusted
          from harga_all_produk h
          left join erp_sku_list e on h.sku = e.sku
          left join erp_shopee_metrics sm on h.sku = sm.sku
          cross join kalk k
        )
        select ho.toko, ho.item_id "itemId", ho.model_id "modelId", ho.ptag, ho.sku, ho.nama_variasi "namaVariasi", ho.nama_produk "namaProduk", ho.harga_awal "hargaAwal",
          coalesce(ap.custom_harga_diskon, ap.harga_diskon) "hargaDiskonDb", coalesce(nullif(coalesce(ap.custom_harga_pancing, ap.harga_pancing), 0), 0) "hargaPancing", coalesce(nullif(coalesce(ap.custom_harga_pancing, ap.harga_pancing), 0), nullif(coalesce(ap.custom_harga_diskon, ap.harga_diskon), 0), 0) "hargaAkhirTarget", ho.harga_tampil "hargaTampil", ho.selisih, ho.sumber_harga "sumberHarga", ho.alasan, ho.diproses_pada "diprosesPada", ho.diperbarui_pada "diperbaruiPada",
          (case when ho.harga_tampil > 0 and sc.sku_u is not null then 1.0 - sc.total_pct_biaya - ((sc.hpp + sc.biaya_tetap_adjusted) / nullif(ho.harga_tampil, 0)) else null end)::numeric "marginPersen"
        from harga_olah_data ho
        left join sku_sales ss on ho.sku = ss.sales_sku
        left join harga_all_produk ap on upper(ap.sku) = upper(ho.sku)
        left join sku_cost sc on sc.sku_u = upper(ho.sku)
        where ${W}
        order by ${order}
        limit $${params.length - 1} offset $${params.length}
      `, params);
      const countParams = [...params]; countParams.splice(countParams.length - 2, 2);
      const total = await q<{ count: string }>(`select count(*) from harga_olah_data where ${W}`, countParams);
      return NextResponse.json({ rows, total: parseInt(total[0]?.count || "0"), tokos: activeTokos });

    } else if (tab === "komisi") {
      let W = "1=1";
      const params: unknown[] = [];
      if (search) { params.push(`%${search}%`); W += ` and (p.sku ilike $1 or p.parent_sku ilike $1 or p.category ilike $1)`; }
      let order = "p.total_sales desc, p.parent_sku asc, p.sku asc";
      if (sortCol) {
        const allowed = ["sku", "parent_sku", "category", "total_sales", "net_price"];
        if (allowed.includes(sortCol)) order = `p.${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
      }
      params.push(size, offset);
      // CTE for harga_diskon
      const sqlBase = `
        with base as (
          select h.sku, coalesce(e.hpp, 0) as hpp, coalesce(e.override_net, 0) as override_net, coalesce(sm.total_qty, 0)::numeric as total_qty, coalesce(sm.total_orders, 0)::numeric as total_orders, h.custom_harga_diskon, h.harga_diskon, h.harga_pancing, h.custom_harga_pancing, h.harga_awal, h.sku_induk, h.nama_produk, h.category, h.diperbarui_pada
          from harga_all_produk h
          left join erp_sku_list e on h.sku = e.sku
          left join erp_shopee_metrics sm on h.sku = sm.sku
        ),
        kalkulator_settings as (
          select 
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_packing_fee'), 400) as packing_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee_min_hpp'), 600) as min_hpp,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee'), 1250) as service_fee,
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_admin_fee_pct'), 0.16) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_discount_ads_pct'), 0.06) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_salary_pct'), 0.08) +
            coalesce((select value::numeric from kalkulator_settings where key = 'batch_commission_pct'), 0.0) as total_pct_biaya
        ),
        calc1 as (
          select b.*, ks.packing_fee, ks.min_hpp, ks.service_fee, ks.total_pct_biaya,
            (ks.packing_fee + (case when b.hpp >= ks.min_hpp then ks.service_fee else 0 end))::numeric as biaya_tetap,
            (case when b.hpp < 500 then 0.25 when b.hpp < 1000 then 0.20 when b.hpp < 3000 then 0.15 else 0.12 end)::numeric as target_margin
          from base b cross join kalkulator_settings ks
        ),
        calc2 as (
          select c1.*,
            (case when c1.override_net > 0 then c1.override_net else (c1.hpp + c1.biaya_tetap) / nullif((1.0 - c1.total_pct_biaya - c1.target_margin), 0) end)::numeric as net_price_awal
          from calc1 c1
        ),
        calc3 as (
          select c2.*,
            (case when c2.total_qty > 0 then c2.net_price_awal - ((greatest(0, c2.total_qty - c2.total_orders) / c2.total_qty) * c2.service_fee) else c2.net_price_awal end)::numeric as net_price_detail,
            (c2.packing_fee + (case when c2.total_qty > 0 then c2.service_fee * c2.total_orders / c2.total_qty else c2.service_fee end))::numeric as biaya_tetap_adjusted
          from calc2 c2
        ),
        final_diskon as (
          select c3.sku, (case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon else coalesce(nullif(c3.harga_diskon, 0), c3.net_price_detail) end)::numeric as harga_diskon
          from calc3 c3
        )
      `;

      const prodsSql = `
        ${sqlBase}
        select p.sku, p.parent_sku "parentSku", p.category, p.total_sales "totalSales", p.net_price "netPrice", p.diperbarui_pada "diperbaruiPada", coalesce(fd.harga_diskon, 0) "hargaDiskon" 
        from harga_komisi_produk p 
        left join final_diskon fd on p.sku = fd.sku
        where ${W} 
        order by ${order} 
        limit $${params.length - 1} offset $${params.length}
      `;
      const prods = await q<any>(prodsSql, params);
      const countParams = search ? [`%${search}%`] : [];
      const total = await q<{ count: string }>(`select count(*) from harga_komisi_produk p where ${W}`, countParams);
      if (prods.length === 0) return NextResponse.json({ rows: [], total: 0, tokos: activeTokos });
      const skus = prods.map((pr: any) => pr.sku);
      
      const tokoDetails = await q<any>(`select sku, username_toko "toko", komisi_persen "komisiPersen", harga_jual "hargaJual" from harga_komisi_toko where sku = any($1)`, [skus]);
      
      const olahTokoPrices = await q<any>(`
        select sku, toko, max(harga_tampil) as harga_tampil 
        from harga_olah_data 
        where sku = any($1) 
        group by sku, toko
      `, [skus]);

      const rows = prods.map((pr: any) => {
        const details = tokoDetails.filter((t: any) => t.sku === pr.sku);
        const tokos: Record<string, any> = {};
        
        activeTokos.forEach((tk: any) => {
          const dt = details.find((d: any) => d.toko === tk.username);
          const realPriceRow = olahTokoPrices.find((ot: any) => ot.sku === pr.sku && ot.toko === tk.nama);
          
          const hargaSaatIni = realPriceRow ? Number(realPriceRow.harga_tampil) : 0;
          const komisiPersen = dt ? Number(dt.komisiPersen) : 10;
          
          // Recommended harga jual: Net Price / (1 - komisi_persen / 100)
          const recHargaJual = Math.ceil(pr.netPrice / (1 - komisiPersen / 100));
          const manualHargaJual = dt ? Number(dt.hargaJual) : 0;
          const hargaJual = manualHargaJual > 0 ? manualHargaJual : recHargaJual;
          
          tokos[tk.username] = { 
            hargaSaatIni, 
            komisiPersen, 
            hargaJual,
            manualHargaJual 
          };
        });
        return { ...pr, tokos };
      });
      return NextResponse.json({ rows, total: parseInt(total[0]?.count || "0"), tokos: activeTokos });
    } else if (tab === "riwayat") {
      let W = "1=1";
      const params: unknown[] = [];
      if (search) { 
        params.push(`%${search}%`); 
        W += ` and (r.sku ilike $1 or r.username ilike $1 or u.username ilike $1 or r.aksi ilike $1)`; 
      }
      let order = "r.waktu_update desc";
      if (sortCol) {
        const allowed = ["waktu_update", "sku", "aksi", "nilai_lama", "nilai_baru", "username"];
        if (allowed.includes(sortCol)) {
          if (sortCol === "username") {
            order = `coalesce(u.username, r.username) ${sortDir === "asc" ? "asc" : "desc"}`;
          } else {
            order = `r.${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
          }
        }
      }
      params.push(size, offset);
      const rows = await q<any>(
        `select r.id, r.waktu_update, r.sku, r.aksi, r.nilai_lama, r.nilai_baru, 
                coalesce(u.username, r.username) as username, 
                u.avatar_emoji 
         from harga_riwayat_update r 
         left join dashboard_user u on r.user_id = u.id 
         where ${W} 
         order by ${order} 
         limit $${params.length - 1} offset $${params.length}`, 
        params
      );
      const countParams = search ? [`%${search}%`] : [];
      const total = await q<{ count: string }>(
        `select count(*) 
         from harga_riwayat_update r 
         left join dashboard_user u on r.user_id = u.id 
         where ${W}`, 
        countParams
      );
      return NextResponse.json({ rows, total: parseInt(total[0]?.count || "0") });
    }
    return NextResponse.json({ error: "Invalid tab" }, { status: 400 });
  } catch (err: any) {
    console.error("GET /api/produk/harga error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  const sqlBase = `
    with base as (
      select h.sku, coalesce(e.hpp, 0) as hpp, coalesce(e.override_net, 0) as override_net, coalesce(sm.total_qty, 0)::numeric as total_qty, coalesce(sm.total_orders, 0)::numeric as total_orders, h.custom_harga_diskon, h.harga_pancing, h.custom_harga_pancing, h.harga_awal, h.sku_induk, h.nama_produk, h.category, h.diperbarui_pada
      from harga_all_produk h
      left join erp_sku_list e on h.sku = e.sku
      left join erp_shopee_metrics sm on h.sku = sm.sku
    ),
    kalkulator_settings as (
      select 
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_packing_fee'), 400) as packing_fee,
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee_min_hpp'), 600) as min_hpp,
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_service_fee'), 1250) as service_fee,
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_admin_fee_pct'), 0.16) +
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_discount_ads_pct'), 0.06) +
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_salary_pct'), 0.08) +
        coalesce((select value::numeric from kalkulator_settings where key = 'batch_commission_pct'), 0.0) as total_pct_biaya
    ),
    calc1 as (
      select b.*, ks.packing_fee, ks.min_hpp, ks.service_fee, ks.total_pct_biaya,
        (ks.packing_fee + (case when b.hpp >= ks.min_hpp then ks.service_fee else 0 end))::numeric as biaya_tetap,
        (case when b.hpp < 500 then 0.25 when b.hpp < 1000 then 0.20 when b.hpp < 3000 then 0.15 else 0.12 end)::numeric as target_margin
      from base b cross join kalkulator_settings ks
    ),
    calc2 as (
      select c1.*,
        (case when c1.override_net > 0 then c1.override_net else (c1.hpp + c1.biaya_tetap) / nullif((1.0 - c1.total_pct_biaya - c1.target_margin), 0) end)::numeric as net_price_awal
      from calc1 c1
    ),
    calc3 as (
      select c2.*,
        (case when c2.total_qty > 0 then c2.net_price_awal - ((greatest(0, c2.total_qty - c2.total_orders) / c2.total_qty) * c2.service_fee) else c2.net_price_awal end)::numeric as net_price_detail,
        (c2.packing_fee + (case when c2.total_qty > 0 then c2.service_fee * c2.total_orders / c2.total_qty else c2.service_fee end))::numeric as biaya_tetap_adjusted
      from calc2 c2
    )
  `;

  try {
    const body = await req.json().catch(() => ({}));
    const { action, sku, custom_harga_diskon, custom_harga_pancing, skus } = body;

    // Ambil info user yang mengubah
    const cookieStore = await cookies();
    const token = cookieStore.get("dash_auth")?.value;
    const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
    const user = token ? await verifySession(token, secret) : null;
    const userId = user?.id || null;
    let username = user?.username || "System";
    const role = user?.role || "staff";
    
    // Ambil nama user real-time dari database untuk menghindari nama usang dari JWT session cookie
    if (userId) {
      const dbUser = await q<any>("select username from dashboard_user where id = $1", [userId]);
      if (dbUser.length > 0) {
        username = dbUser[0].username;
      }
    }

    // Validasi izin edit berdasarkan role dan permission
    // Ambil langsung dari DB agar perubahan hak akses langsung berlaku tanpa re-login
    if (role !== "owner") {
      const isCatalogEdit = ["update-custom-diskon", "update-custom-pancing", "mass-update-harga"].includes(action);
      const isKomisiEdit = [
        "update-komisi-toko", 
        "update-harga-jual-toko", 
        "mass-update-komisi-toko", 
        "add-komisi-produk", 
        "delete-komisi-produk", 
        "batch-update-jual",
        "mass-delete-jual-toko",
        "update-jual-parent-sku"
      ].includes(action);
      
      if (isCatalogEdit || isKomisiEdit) {
        // Cek langsung dari database untuk memastikan data selalu up-to-date
        const dbUser = user?.id ? await q<any>(
          "select can_edit_harga, can_edit_komisi from dashboard_user where id = $1",
          [user.id]
        ) : [];
        const perms = dbUser.length > 0 ? dbUser[0] : { can_edit_harga: false, can_edit_komisi: false };
        
        if (isCatalogEdit && !perms.can_edit_harga) {
          return NextResponse.json({ ok: false, error: "Akses ditolak: Anda tidak memiliki izin mengedit harga katalog." }, { status: 403 });
        }
        if (isKomisiEdit && !perms.can_edit_komisi) {
          return NextResponse.json({ ok: false, error: "Akses ditolak: Anda tidak memiliki izin mengedit komisi affiliate." }, { status: 403 });
        }
      }
    }

    if (action === "update-custom-diskon") {
      if (!sku) return NextResponse.json({ ok: false, error: "SKU wajib diisi" }, { status: 400 });
      const val = custom_harga_diskon !== "" && custom_harga_diskon !== null ? parseFloat(custom_harga_diskon) : null;
      
      const oldData = await q<any>(`select custom_harga_diskon from harga_all_produk where sku = $1`, [sku]);
      const oldVal = oldData.length > 0 ? oldData[0].custom_harga_diskon : null;

      await q(`update harga_all_produk set custom_harga_diskon = $1, diperbarui_pada = now() where sku = $2`, [val, sku]);
      await q(`insert into harga_riwayat_update (sku, aksi, nilai_lama, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5, $6)`, [sku, 'Edit Harga Diskon', oldVal, val, username, userId]);

      return NextResponse.json({ ok: true, message: `Harga diskon kustom SKU ${sku} diperbarui.` });
    }
    
    if (action === "update-custom-pancing") {
      if (!sku) return NextResponse.json({ ok: false, error: "SKU wajib diisi" }, { status: 400 });
      const val = custom_harga_pancing !== "" && custom_harga_pancing !== null ? parseFloat(custom_harga_pancing) : null;
      
      const oldData = await q<any>(`select custom_harga_pancing from harga_all_produk where sku = $1`, [sku]);
      const oldVal = oldData.length > 0 ? oldData[0].custom_harga_pancing : null;

      await q(`update harga_all_produk set custom_harga_pancing = $1, diperbarui_pada = now() where sku = $2`, [val, sku]);
      await q(`insert into harga_riwayat_update (sku, aksi, nilai_lama, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5, $6)`, [sku, 'Edit Harga Pancing', oldVal, val, username, userId]);

      return NextResponse.json({ ok: true, message: `Harga pancing kustom SKU ${sku} diperbarui.` });
    }
    
    if (action === "mass-update-harga") {
      if (!skus || !Array.isArray(skus) || skus.length === 0) return NextResponse.json({ ok: false, error: "Daftar SKU tidak valid" }, { status: 400 });
      
      const oldData = await q<any>(`select sku, custom_harga_diskon, custom_harga_pancing from harga_all_produk where sku = any($1)`, [skus]);
      
      let params: any[] = [skus];
      let queryStr = `update harga_all_produk set diperbarui_pada = now()`;
      
      const hasDiskon = custom_harga_diskon !== undefined;
      const hasPancing = custom_harga_pancing !== undefined;
      const valD = hasDiskon && custom_harga_diskon !== "" && custom_harga_diskon !== null ? parseFloat(custom_harga_diskon) : null;
      const valP = hasPancing && custom_harga_pancing !== "" && custom_harga_pancing !== null ? parseFloat(custom_harga_pancing) : null;

      if (hasDiskon) {
        params.push(valD);
        queryStr += `, custom_harga_diskon = $${params.length}`;
      }
      if (hasPancing) {
        params.push(valP);
        queryStr += `, custom_harga_pancing = $${params.length}`;
      }
      
      queryStr += ` where sku = any($1)`;
      await q(queryStr, params);

      if (hasDiskon && oldData.length > 0) {
        const values: any[] = [];
        let i = 1;
        const placeholders = oldData.map((od: any) => {
          const chunk = `($${i++}, $${i++}, $${i++}, $${i++}, $${i++}, $${i++})`;
          values.push(od.sku, 'Mass Update Diskon', od.custom_harga_diskon, valD, username, userId);
          return chunk;
        });
        await q(`insert into harga_riwayat_update (sku, aksi, nilai_lama, nilai_baru, username, user_id) values ${placeholders.join(',')}`, values);
      }

      if (hasPancing && oldData.length > 0) {
        const values: any[] = [];
        let i = 1;
        const placeholders = oldData.map((od: any) => {
          const chunk = `($${i++}, $${i++}, $${i++}, $${i++}, $${i++}, $${i++})`;
          values.push(od.sku, 'Mass Update Pancing', od.custom_harga_pancing, valP, username, userId);
          return chunk;
        });
        await q(`insert into harga_riwayat_update (sku, aksi, nilai_lama, nilai_baru, username, user_id) values ${placeholders.join(',')}`, values);
      }

      return NextResponse.json({ ok: true, message: `Update massal pada ${skus.length} SKU berhasil.` });
    }

    if (action === "update-komisi-toko") {
      const { sku, toko, komisi_persen, harga_jual } = body;
      await q(`
        insert into harga_komisi_toko (sku, username_toko, komisi_persen, harga_jual, diperbarui_pada)
        values ($1, $2, $3, $4, now())
        on conflict (sku, username_toko) do update 
        set komisi_persen = coalesce(excluded.komisi_persen, harga_komisi_toko.komisi_persen), 
            harga_jual = coalesce(excluded.harga_jual, harga_komisi_toko.harga_jual), 
            diperbarui_pada = now()
      `, [sku, toko, komisi_persen !== undefined ? komisi_persen : null, harga_jual !== undefined ? harga_jual : null]);
      
       const aksiName = komisi_persen !== undefined ? 'Edit Komisi Persen' : 'Edit Harga Jual Manual';
      await q(`insert into harga_riwayat_update (sku, aksi, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5)`, 
        [sku, `${aksiName} (${toko})`, komisi_persen !== undefined ? komisi_persen : harga_jual, username, userId]);

      return NextResponse.json({ ok: true, message: `Komisi toko ${toko} SKU ${sku} diperbarui.` });
    }

    if (action === "mass-update-komisi-toko") {
      const { toko, komisi_persen } = body;
      await q(`
        insert into harga_komisi_toko (sku, username_toko, komisi_persen, harga_jual, diperbarui_pada)
        select sku, $1, $2, 0, now() from harga_komisi_produk
        on conflict (sku, username_toko) do update
        set komisi_persen = excluded.komisi_persen,
            diperbarui_pada = now()
      `, [toko, komisi_persen]);
      
      await q(`insert into harga_riwayat_update (sku, aksi, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5)`, 
        ['ALL', `Mass Update Komisi (${toko})`, komisi_persen, username, userId]);

      return NextResponse.json({ ok: true, message: `Komisi massal toko ${toko} diperbarui menjadi ${komisi_persen}%.` });
    }

    if (action === "add-komisi-produk") {
      const { parent_sku } = body;
      if (!parent_sku) return NextResponse.json({ ok: false, error: "Parent SKU wajib diisi" }, { status: 400 });

      const qInsert = `
        ${sqlBase}
        insert into harga_komisi_produk (sku, parent_sku, category, net_price, diperbarui_pada)
        select c3.sku, c3.sku_induk, c3.category, c3.net_price_detail, now()
        from calc3 c3
        where c3.sku_induk ilike $1
        on conflict (sku) do nothing
      `;
      await q(qInsert, [parent_sku]);
      return NextResponse.json({ ok: true, message: `Produk dengan Parent SKU ${parent_sku} ditambahkan ke Komisi.` });
    }

    if (action === "delete-komisi-produk") {
      const { parent_sku } = body;
      if (!parent_sku) return NextResponse.json({ ok: false, error: "Parent SKU wajib diisi" }, { status: 400 });

      await q(`delete from harga_komisi_produk where parent_sku ilike $1`, [parent_sku]);
      return NextResponse.json({ ok: true, message: `Produk dengan Parent SKU ${parent_sku} dihapus dari Komisi.` });
    }

    if (action === "batch-update-jual") {
      const { toko, updates } = body;
      if (!toko || !updates || !Array.isArray(updates)) return NextResponse.json({ ok: false, error: "Data tidak valid" }, { status: 400 });

      let count = 0;
      for (const u of updates) {
        if (!u.sku) continue;
        await q(`
          insert into harga_komisi_toko (sku, username_toko, harga_jual, diperbarui_pada)
          values ($1, $2, $3, now())
          on conflict (sku, username_toko) do update 
          set harga_jual = excluded.harga_jual, diperbarui_pada = now()
        `, [u.sku, toko, u.harga_jual]);
        count++;
      }
      
      await q(`insert into harga_riwayat_update (sku, aksi, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5)`, 
        ['ALL', `Batch Update Jual (${toko})`, null, username, userId]);

      return NextResponse.json({ ok: true, message: `${count} SKU pada toko ${toko} berhasil diperbarui.` });
    }

    if (action === "mass-delete-jual-toko") {
      const { toko } = body;
      if (!toko) return NextResponse.json({ ok: false, error: "Toko wajib diisi" }, { status: 400 });

      await q(`
        update harga_komisi_toko 
        set harga_jual = 0, diperbarui_pada = now() 
        where username_toko = $1
      `, [toko]);

      await q(`insert into harga_riwayat_update (sku, aksi, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5)`, 
        ['ALL', `Mass Delete Jual (${toko})`, null, username, userId]);

      return NextResponse.json({ ok: true, message: `Semua harga jual manual toko ${toko} berhasil dihapus.` });
    }

    if (action === "update-jual-parent-sku") {
      const { toko, parent_sku, harga_jual } = body;
      if (!toko) return NextResponse.json({ ok: false, error: "Toko wajib diisi" }, { status: 400 });
      if (!parent_sku) return NextResponse.json({ ok: false, error: "Parent SKU wajib diisi" }, { status: 400 });
      const valJual = harga_jual !== "" && harga_jual !== null ? parseFloat(harga_jual) : 0;

      await q(`
        insert into harga_komisi_toko (sku, username_toko, harga_jual, diperbarui_pada)
        select sku, $1, $2, now()
        from harga_komisi_produk
        where parent_sku ilike $3
        on conflict (sku, username_toko) do update
        set harga_jual = excluded.harga_jual, diperbarui_pada = now()
      `, [toko, valJual, parent_sku]);

      await q(`insert into harga_riwayat_update (sku, aksi, nilai_baru, username, user_id) values ($1, $2, $3, $4, $5)`, 
        [parent_sku, `Edit Harga Jual Parent SKU (${toko})`, valJual, username, userId]);

      return NextResponse.json({ ok: true, message: `Harga jual untuk Parent SKU ${parent_sku} di toko ${toko} berhasil diperbarui.` });
    }

    return NextResponse.json({ ok: false, error: "Action tidak dikenal" }, { status: 400 });
  } catch (err: any) {
    console.error("POST /api/produk/harga error:", err);
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
