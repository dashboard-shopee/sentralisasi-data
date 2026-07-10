import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

// Pusat Promosi — fakta per-program (diisi bot Syntra Monitoring Harga Fase 1).
// Tab: promo_toko | paket | voucher | campaign | garansi | flash | komisi
export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const tab = p.get("tab") || "promo_toko";
  const search = (p.get("q") || "").trim();
  const filterToko = (p.get("toko") || "").trim();      // NAMA toko (mis. 'Kimmioshop')
  const page = parseInt(p.get("page") || "1") || 1;
  const size = Math.min(parseInt(p.get("size") || "50") || 50, 200);
  const offset = (page - 1) * size;

  try {
    // DETAIL 1 variasi (buat expand-row di /produk/harga): semua fakta promo variasi ini.
    if (tab === "detail") {
      const item = p.get("item");
      const model = p.get("model");
      const tk = p.get("toko");
      const sku = p.get("sku") || "";
      if (!item || !tk) return NextResponse.json({ error: "item & toko wajib" }, { status: 400 });
      const promos = await q<Record<string, unknown>>(
        `select jenis, harga_promo "hargaPromo", status, mulai, berakhir
         from harga_promo_konteks where toko=$1 and item_id=$2 and model_id=$3 order by jenis`,
        [tk, item, model || 0]
      );
      const garansi = await q<Record<string, unknown>>(
        `select current_price "currentPrice", bid_price "bidPrice", best_price "bestPrice"
         from harga_fakta_garansi where toko=$1 and item_id=$2 and model_id=$3`,
        [tk, item, model || 0]
      );
      const komisi = sku
        ? await q<Record<string, unknown>>(
            `select d.nama "toko", k.komisi_persen "komisiPersen", k.harga_jual "hargaJual"
             from harga_komisi_toko k left join dim_toko d on d.username=k.username_toko
             where k.sku=$1 and coalesce(k.harga_jual,0)>0`,
            [sku]
          )
        : [];
      return NextResponse.json({ promos, garansi, komisi });
    }

    // PRODUK dalam 1 voucher (buat expand-row tab Voucher). item_scope jsonb = daftar itemid
    // (voucher produk); null = voucher SEMUA produk toko.
    if (tab === "voucher_produk") {
      const vid = p.get("voucher_id");
      const tk = p.get("toko");
      if (!vid || !tk) return NextResponse.json({ error: "voucher_id & toko wajib" }, { status: 400 });
      const v = await q<{ item_scope: number[] | null }>(
        `select item_scope from harga_fakta_voucher where toko=$1 and voucher_id=$2`, [tk, vid]
      );
      const scope = v[0]?.item_scope;
      if (!scope || !Array.isArray(scope) || scope.length === 0) {
        return NextResponse.json({ shopWide: true, produk: [] });
      }
      const produk = await q<Record<string, unknown>>(
        `select distinct on (item_id) item_id "itemId", sku, nama_produk "namaProduk", harga_tampil "hargaTampil"
         from harga_olah_data where toko=$1 and item_id = any($2::bigint[]) order by item_id`,
        [tk, scope]
      );
      return NextResponse.json({ shopWide: false, produk });
    }

    // PRODUK dalam 1 Promo Toko (expand-row tab Promo Toko).
    if (tab === "promo_toko_produk") {
      const pid = p.get("promotion_id");
      const tk = p.get("toko");
      if (!pid || !tk) return NextResponse.json({ error: "promotion_id & toko wajib" }, { status: 400 });
      const produk = await q<Record<string, unknown>>(
        `select i.item_id "itemId", i.model_id "modelId", o.sku, o.nama_produk "namaProduk",
                o.nama_variasi "namaVariasi", i.harga_promo "hargaPromo"
         from harga_fakta_promo_toko_item i
         left join harga_olah_data o on o.toko=i.toko and o.item_id=i.item_id and o.model_id=i.model_id
         where i.toko=$1 and i.promotion_id=$2 order by i.item_id limit 1000`,
        [tk, pid]
      );
      return NextResponse.json({ produk });
    }

    // SKU variasi dalam 1 item komisi (expand-row tab Komisi). Sisi SYNTRA (harga_komisi_toko).
    if (tab === "komisi_produk") {
      const item = p.get("item_id");
      const tk = p.get("toko");
      if (!item || !tk) return NextResponse.json({ error: "item_id & toko wajib" }, { status: 400 });
      const produk = await q<Record<string, unknown>>(
        `select o.sku, max(o.nama_produk) "namaProduk",
                max(k.komisi_persen) "komisiPersen", max(k.harga_jual) "hargaJual"
         from harga_olah_data o
         join dim_toko d on d.nama = o.toko
         join harga_komisi_toko k on k.username_toko = d.username and upper(k.sku) = upper(o.sku)
         where o.toko=$1 and o.item_id=$2 and coalesce(k.harga_jual,0) > 0
         group by o.sku order by o.sku`,
        [tk, item]
      );
      return NextResponse.json({ produk });
    }

    const tokos = await q<{ username: string; nama: string }>(
      `select username, nama from dim_toko order by shop_index`
    );

    // Susun WHERE + params dinamis per tab. `s` = alias tabel utama.
    const where: string[] = [];
    const params: unknown[] = [];
    const like = (cols: string[]) => {
      params.push(`%${search}%`);
      const ph = `$${params.length}`;
      where.push(`(${cols.map((c) => `${c} ilike ${ph}`).join(" or ")})`);
    };
    const eqToko = (col: string) => {
      params.push(filterToko);
      where.push(`${col} = $${params.length}`);
    };

    let base = "";        // FROM + JOIN
    let cols = "";        // SELECT list
    let order = "";

    if (tab === "promo_toko") {
      // Entity promo toko (berjalan + akan datang). Klik -> produk (tab=promo_toko_produk).
      cols = `s.toko, s.promotion_id "promotionId", s.nama, s.status, s.item_count "itemCount",
              s.mulai, s.berakhir, s.diperbarui_pada "diperbaruiPada"`;
      base = `from harga_fakta_promo_toko s`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.nama"]);
      order = `s.status asc, s.berakhir asc`;
    } else if (tab === "garansi") {
      // Margin per-variasi (rumus identik All Produk): 1 - %biaya - (HPP + biaya_tetap)/harga.
      // Dihitung utk 3 harga garansi: Harga Kini / Terbaik / Program.
      const marginExpr = (priceCol: string) =>
        `(case when ${priceCol} > 0 and sc.sku_u is not null then 1.0 - sc.total_pct_biaya - ((sc.hpp + sc.biaya_tetap_adjusted) / nullif(${priceCol}, 0)) else null end)::numeric`;
      cols = `s.toko, s.item_id "itemId", s.model_id "modelId", o.sku, o.nama_produk "namaProduk",
              o.nama_variasi "namaVariasi", s.current_price "currentPrice", s.best_price "bestPrice",
              s.bid_price "bidPrice", s.stok, s.diperbarui_pada "diperbaruiPada",
              ${marginExpr("s.current_price")} "marginCurrent",
              ${marginExpr("s.best_price")} "marginBest",
              ${marginExpr("s.bid_price")} "marginProgram"`;
      base = `from harga_fakta_garansi s
              left join harga_olah_data o on o.toko=s.toko and o.item_id=s.item_id and o.model_id=s.model_id
              left join (
                select upper(h.sku) as sku_u,
                  coalesce(e.hpp,0)::numeric as hpp,
                  (coalesce((select value::numeric from kalkulator_settings where key='batch_admin_fee_pct'),0.16)
                   + coalesce((select value::numeric from kalkulator_settings where key='batch_discount_ads_pct'),0.06)
                   + coalesce((select value::numeric from kalkulator_settings where key='batch_salary_pct'),0.08)
                   + coalesce((select value::numeric from kalkulator_settings where key='batch_commission_pct'),0.0)) as total_pct_biaya,
                  (coalesce((select value::numeric from kalkulator_settings where key='batch_packing_fee'),400)
                   + (case when coalesce(sm.total_qty,0) > 0
                          then coalesce((select value::numeric from kalkulator_settings where key='batch_service_fee'),1250) * coalesce(sm.total_orders,0) / sm.total_qty
                          else coalesce((select value::numeric from kalkulator_settings where key='batch_service_fee'),1250) end))::numeric as biaya_tetap_adjusted
                from harga_all_produk h
                left join erp_sku_list e on h.sku = e.sku
                left join erp_shopee_metrics sm on h.sku = sm.sku
              ) sc on sc.sku_u = upper(o.sku)`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["o.sku", "o.nama_produk", "s.item_id::text"]);
      order = `s.toko asc, s.item_id asc`;
    } else if (tab === "campaign") {
      cols = `s.toko, s.campaign_id "campaignId", s.session_id "sessionId", s.campaign_name "campaignName",
              s.session_name "sessionName", s.session_start "sessionStart", s.session_end "sessionEnd",
              s.nomination_end "nominationEnd",
              (select count(*) from harga_fakta_campaign_item i where i.toko=s.toko and i.session_id=s.session_id) "nominated",
              s.diperbarui_pada "diperbaruiPada"`;
      base = `from harga_fakta_campaign_sesi s`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.campaign_name", "s.session_name"]);
      order = `s.toko asc, s.nomination_end asc`;
    } else if (tab === "flash") {
      cols = `s.toko, s.flash_sale_id "flashSaleId", s.status, s.timeslot_id "timeslotId",
              s.start_time "startTime", s.end_time "endTime", s.item_count "itemCount",
              s.diperbarui_pada "diperbaruiPada"`;
      base = `from harga_fakta_flash_sesi s`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.flash_sale_id::text"]);
      order = `s.toko asc, s.start_time asc`;
    } else if (tab === "voucher") {
      cols = `s.toko, s.voucher_id "voucherId", s.code, s.name, s.discount, s.min_price "minPrice",
              s.tipe, s.start_time "startTime", s.end_time "endTime", s.status,
              s.diperbarui_pada "diperbaruiPada"`;
      base = `from harga_fakta_voucher s`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.code", "s.name"]);
      order = `s.toko asc, s.end_time asc`;
    } else if (tab === "paket") {
      cols = `s.toko, s.bundle_deal_id "bundleDealId", s.name, s.status,
              s.start_time "startTime", s.end_time "endTime", s.diperbarui_pada "diperbaruiPada"`;
      base = `from harga_fakta_paket s`;
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.name"]);
      order = `s.toko asc, s.end_time asc`;
    } else if (tab === "komisi") {
      // #9 BANDING per ITEM: SYNTRA ("harusnya", harga_komisi_toko harga_jual>0) vs SHOPEE
      // ("aktual", harga_fakta_komisi = grab browser). Master per item; klik -> detail SKU (komisi_produk).
      // verdict: sesuai (dua-dua) / belum_dikomisikan (Syntra ya, Shopee belum) / harusnya_dicabut (Shopee aktif, Syntra ngga).
      cols = `s."toko", s."itemId", s."itemName", s."verdict", s."syntraPersen", s."shopeePersen", s."jmlSku"`;
      base = `from (
        select coalesce(sy.toko, sh.toko) "toko",
               coalesce(sy.item_id, sh.item_id) "itemId",
               coalesce(sh.item_name, sy.nama_produk) "itemName",
               sy.persen "syntraPersen", sh.persen "shopeePersen",
               coalesce(sy.jml_sku, 0) "jmlSku",
               case when sy.item_id is not null and sh.item_id is not null then 'sesuai'
                    when sy.item_id is not null then 'belum_dikomisikan'
                    else 'harusnya_dicabut' end "verdict"
        from (
          select o.toko, o.item_id, max(o.nama_produk) nama_produk,
                 max(k.komisi_persen) persen, count(distinct k.sku) jml_sku
          from harga_komisi_toko k
          join dim_toko d on d.username = k.username_toko
          join harga_olah_data o on o.toko = d.nama and upper(o.sku) = upper(k.sku)
          where coalesce(k.harga_jual,0) > 0
          group by o.toko, o.item_id
        ) sy
        full outer join (
          select toko, item_id, persen, item_name from harga_fakta_komisi
        ) sh on sh.toko = sy.toko and sh.item_id = sy.item_id
      ) s`;
      if (filterToko) eqToko(`s."toko"`);
      if (search) like([`s."itemName"`]);
      order = `s."verdict" asc, s."itemName" asc`;
    } else if (tab === "garansi_nom") {
      // Garansi Harga Terbaik — 3 kategori (Nominasi Produk). kat: rekomendasi | terbaik | perlu_ditinjau.
      // floor = Harga Terbaik (best), ceiling = Harga Program. Sumber harga_fakta_garansi_nom (bot harian).
      const kat = (p.get("kat") || "terbaik").trim();
      cols = `s.toko, s.item_id "itemId", s.model_id "modelId", s.item_name "itemName",
              s.model_name "modelName", s.floor, s.ceiling, s.stok, s.bid_status "bidStatus"`;
      base = `from harga_fakta_garansi_nom s`;
      params.push(kat); where.push(`s.kategori = $${params.length}`);
      if (filterToko) eqToko("s.toko");
      if (search) like(["s.item_name", "s.model_name"]);
      order = `s.stok desc, s.item_name asc`;
    } else {
      return NextResponse.json({ error: "Tab tidak dikenal" }, { status: 400 });
    }

    const W = where.length ? `where ${where.join(" and ")}` : "";
    const rowsSql = `select ${cols} ${base} ${W} order by ${order} limit $${params.length + 1} offset $${params.length + 2}`;
    const rows = await q<Record<string, unknown>>(rowsSql, [...params, size, offset]);
    const totalRes = await q<{ count: string }>(`select count(*) ${base} ${W}`, params);
    const total = parseInt(totalRes[0]?.count || "0");

    return NextResponse.json({ rows, total, tokos, tab });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("GET /api/produk/pusat-promosi error:", msg);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
