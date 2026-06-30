import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const tab = p.get("tab") || "all";
  const search = p.get("q") || "";
  const page = parseInt(p.get("page") || "1") || 1;
  const size = parseInt(p.get("size") || "50") || 50;
  const offset = (page - 1) * size;
  
  // Sort
  const sortCol = p.get("sort") || "";
  const sortDir = p.get("dir") || "desc";

  try {
    const activeTokos = await q<any>(
      `select username, nama from dim_toko order by shop_index`
    );

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
          sku: "h.sku",
          sku_induk: "h.sku_induk",
          nama_produk: "h.nama_produk",
          category: "h.category",
          harga_awal: "h.harga_awal",
          harga_pancing: "h.harga_pancing",
          diperbarui_pada: "h.diperbarui_pada",
          // The calculated columns can't easily be sorted efficiently without making the query heavy,
          // but we can wrap the final query if needed. For now we will allow sorting by wrapping.
        };
        const sqlOrderCol = colMap[sortCol] || sortCol;
        order = `${sqlOrderCol} ${sortDir === "asc" ? "asc" : "desc"}`;
      }

      const sqlBase = `
        with base as (
          select 
            h.sku, h.sku_induk, h.nama_produk, h.category, 
            h.harga_awal, h.harga_pancing, h.diperbarui_pada, h.custom_harga_diskon,
            coalesce(e.hpp, 0) as hpp, coalesce(e.override_net, 0) as override_net,
            coalesce(sm.total_qty, 0)::numeric as total_qty,
            coalesce(sm.total_orders, 0)::numeric as total_orders
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
          select 
            b.*,
            ks.packing_fee, ks.min_hpp, ks.service_fee, ks.total_pct_biaya,
            (ks.packing_fee + (case when b.hpp >= ks.min_hpp then ks.service_fee else 0 end))::numeric as biaya_tetap,
            (case 
              when b.hpp < 500 then 0.25 
              when b.hpp < 1000 then 0.20 
              when b.hpp < 3000 then 0.15 
              else 0.12 
            end)::numeric as target_margin
          from base b cross join kalkulator_settings ks
        ),
        calc2 as (
          select 
            c1.*,
            (case 
              when c1.override_net > 0 then c1.override_net 
              else (c1.hpp + c1.biaya_tetap) / nullif((1.0 - c1.total_pct_biaya - c1.target_margin), 0) 
            end)::numeric as net_price_awal
          from calc1 c1
        ),
        calc3 as (
          select 
            c2.*,
            (case 
              when c2.total_qty > 0 then c2.net_price_awal - ((greatest(0, c2.total_qty - c2.total_orders) / c2.total_qty) * c2.service_fee)
              else c2.net_price_awal
            end)::numeric as net_price_detail,
            (c2.packing_fee + (case when c2.total_qty > 0 then c2.service_fee * c2.total_orders / c2.total_qty else c2.service_fee end))::numeric as biaya_tetap_adjusted
          from calc2 c2
        ),
        mode_diskon as (
          select sku, mode() within group (order by harga_tampil) as mode_harga_tampil
          from harga_olah_data
          where harga_tampil > 0
          group by sku
        ),
        olah_toko as (
          select sku, jsonb_agg(
            jsonb_build_object('toko', toko, 'itemId', item_id, 'harga', harga_tampil)
          ) as catalogs
          from harga_olah_data
          group by sku
        ),
        final as (
          select 
            c3.sku, c3.sku_induk as "sku_induk", c3.nama_produk as "nama_produk", c3.category, 
            c3.harga_awal as "harga_awal", c3.harga_pancing as "harga_pancing", 
            c3.diperbarui_pada as "diperbarui_pada",
            c3.net_price_awal as "net_price_awal", c3.net_price_detail as "net_price_detail",
            c3.custom_harga_diskon as "custom_harga_diskon",
            (case 
               when c3.custom_harga_diskon is not null then c3.custom_harga_diskon
               when md.mode_harga_tampil is not null then md.mode_harga_tampil
               else c3.net_price_detail
            end)::numeric as harga_diskon,
            (case
               when (case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon when md.mode_harga_tampil is not null then md.mode_harga_tampil else c3.net_price_detail end) > 0 
               then 1.0 - c3.total_pct_biaya - ((c3.hpp + c3.biaya_tetap_adjusted) / nullif((case when c3.custom_harga_diskon is not null then c3.custom_harga_diskon when md.mode_harga_tampil is not null then md.mode_harga_tampil else c3.net_price_detail end), 0))
               else 0.0
            end)::numeric as margin_persen,
            coalesce(ot.catalogs, '[]'::jsonb) as catalogs
          from calc3 c3
          left join mode_diskon md on c3.sku = md.sku
          left join olah_toko ot on c3.sku = ot.sku
        )
      `;

      // Main query wrapping to allow sorting on calculated columns easily
      const rowsSql = `
        ${sqlBase}
        select * from final 
        order by ${sortCol ? (["sku", "sku_induk", "nama_produk", "category", "harga_awal", "harga_pancing", "diperbarui_pada"].includes(sortCol) ? sortCol : `"${sortCol}"`) : 'sku'} ${sortDir === "asc" ? "asc" : "desc"} 
        limit $${params.length + 1} offset $${params.length + 2}
      `;
      const queryParams = [...params, size, offset];
      
      const rows = await q<any>(rowsSql, queryParams);

      const totalSql = `select count(*) from harga_all_produk h where ${W}`;
      const total = await q<{ count: string }>(totalSql, params);

      return NextResponse.json({
        rows,
        total: parseInt(total[0]?.count || "0"),
        tokos: activeTokos
      });

    } else if (tab === "olah") {
      let W = "1=1";
      const params: unknown[] = [];
      
      const filterToko = p.get("toko") || "";
      if (filterToko) {
        params.push(filterToko);
        W += ` and toko = $${params.length}`;
      }
      
      const filterSumber = p.get("sumber") || "";
      if (filterSumber) {
        params.push(filterSumber);
        W += ` and sumber_harga = $${params.length}`;
      }

      if (search) {
        params.push(`%${search}%`);
        W += ` and (sku ilike $${params.length} or nama_produk ilike $${params.length} or nama_variasi ilike $${params.length} or item_id::text like $${params.length} or model_id::text like $${params.length})`;
      }

      let order = "toko asc, item_id asc, model_id asc";
      if (sortCol) {
        const allowed = ["toko", "item_id", "model_id", "ptag", "sku", "nama_variasi", "nama_produk", "harga_awal", "harga_diskon_db", "harga_pancing", "harga_akhir_target", "harga_tampil", "selisih", "sumber_harga", "alasan", "diperbarui_pada"];
        if (allowed.includes(sortCol)) {
          order = `${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
        }
      }

      params.push(size, offset);
      const rows = await q<any>(
        `select toko, item_id "itemId", model_id "modelId", ptag, sku, nama_variasi "namaVariasi", nama_produk "namaProduk", 
                harga_awal "hargaAwal", harga_diskon_db "hargaDiskonDb", harga_pancing "hargaPancing", 
                harga_akhir_target "hargaAkhirTarget", harga_tampil "hargaTampil", selisih, 
                sumber_harga "sumberHarga", alasan, diperbarui_pada "diperbaruiPada"
         from harga_olah_data 
         where ${W} 
         order by ${order} 
         limit $${params.length - 1} offset $${params.length}`,
        params
      );

      const countParams = [...params];
      countParams.splice(countParams.length - 2, 2); // remove limit and offset
      const total = await q<{ count: string }>(
        `select count(*) from harga_olah_data where ${W}`,
        countParams
      );

      return NextResponse.json({
        rows,
        total: parseInt(total[0]?.count || "0"),
        tokos: activeTokos
      });

    } else if (tab === "komisi") {
      let W = "1=1";
      const params: unknown[] = [];
      if (search) {
        params.push(`%${search}%`);
        W += ` and (p.sku ilike $1 or p.parent_sku ilike $1 or p.category ilike $1)`;
      }

      let order = "p.sku asc";
      if (sortCol) {
        const allowed = ["sku", "parent_sku", "category", "total_sales", "net_price"];
        if (allowed.includes(sortCol)) {
          order = `p.${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
        }
      }

      // We need to fetch paginated products, then join details.
      // To paginate correctly, we query the products first.
      params.push(size, offset);
      const prods = await q<any>(
        `select p.sku, p.parent_sku "parentSku", p.category, p.total_sales "totalSales", p.net_price "netPrice", p.diperbarui_pada "diperbaruiPada"
         from harga_komisi_produk p
         where ${W}
         order by ${order}
         limit $${params.length - 1} offset $${params.length}`,
        params
      );

      const countParams = search ? [`%${search}%`] : [];
      const total = await q<{ count: string }>(
        `select count(*) from harga_komisi_produk p where ${W}`,
        countParams
      );

      if (prods.length === 0) {
        return NextResponse.json({ rows: [], total: 0, tokos: activeTokos });
      }

      // Fetch all toko records for these loaded SKUs
      const skus = prods.map((pr: any) => pr.sku);
      const tokoDetails = await q<any>(
        `select sku, username_toko "toko", harga_saat_ini "hargaSaatIni", komisi_persen "komisiPersen", harga_jual "hargaJual"
         from harga_komisi_toko
         where sku = any($1)`,
        [skus]
      );

      // Assemble
      const rows = prods.map((pr: any) => {
        const details = tokoDetails.filter((t: any) => t.sku === pr.sku);
        const tokos: Record<string, any> = {};
        details.forEach((d: any) => {
          tokos[d.toko] = {
            hargaSaatIni: Number(d.hargaSaatIni),
            komisiPersen: Number(d.komisiPersen),
            hargaJual: Number(d.hargaJual)
          };
        });
        return {
          ...pr,
          tokos
        };
      });

      return NextResponse.json({
        rows,
        total: parseInt(total[0]?.count || "0"),
        tokos: activeTokos
      });
    }

    return NextResponse.json({ error: "Invalid tab" }, { status: 400 });
  } catch (err: any) {
    console.error("GET /api/produk/harga error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const { action, sku, custom_harga_diskon } = body;

    if (action === "update-custom-diskon") {
      if (!sku) {
        return NextResponse.json({ ok: false, error: "SKU wajib diisi" }, { status: 400 });
      }
      
      const val = custom_harga_diskon !== "" && custom_harga_diskon !== null ? parseFloat(custom_harga_diskon) : null;
      
      await q(
        `update harga_all_produk set custom_harga_diskon = $1, diperbarui_pada = now() where sku = $2`,
        [val, sku]
      );
      return NextResponse.json({ ok: true, message: `Harga diskon kustom SKU ${sku} diperbarui.` });
    }

    return NextResponse.json({ ok: false, error: "Action tidak dikenal" }, { status: 400 });
  } catch (err: any) {
    console.error("POST /api/produk/harga error:", err);
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
