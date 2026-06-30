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
        W += ` and (sku ilike $1 or sku_induk ilike $1 or nama_produk ilike $1)`;
      }

      let order = "sku asc";
      if (sortCol) {
        const allowed = ["sku", "sku_induk", "nama_produk", "category", "net_price_awal", "net_price_detail", "harga_awal", "harga_diskon", "harga_pancing", "diperbarui_pada"];
        if (allowed.includes(sortCol)) {
          order = `${sortCol} ${sortDir === "asc" ? "asc" : "desc"}`;
        }
      }

      params.push(size, offset);
      const rows = await q<any>(
        `select sku, sku_induk, nama_produk, category, net_price_awal, net_price_detail, harga_awal, harga_diskon, harga_pancing, harga_toko, diperbarui_pada 
         from harga_all_produk 
         where ${W} 
         order by ${order} 
         limit $${params.length - 1} offset $${params.length}`,
        params
      );

      const countParams = search ? [`%${search}%`] : [];
      const total = await q<{ count: string }>(
        `select count(*) from harga_all_produk where ${W}`,
        countParams
      );

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
