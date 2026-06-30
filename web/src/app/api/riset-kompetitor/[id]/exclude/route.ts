import { NextResponse } from "next/server";
import { q } from "@/lib/db";

// Helper to extract item_id from Shopee URL
function extractShopeeItemId(url: string): string | null {
  if (!url) return null;
  const cleanUrl = url.split("?")[0].trim();
  
  // Format: /product/shop_id/item_id
  if (cleanUrl.includes("/product/")) {
    const parts = cleanUrl.split("/product/")[1].split("/");
    if (parts.length >= 2) {
      return parts[1];
    }
  }
  
  // Format: title-i.shop_id.item_id
  const match = cleanUrl.match(/-i\.(\d+)\.(\d+)/);
  if (match && match[2]) {
    return match[2];
  }
  
  // Fallback: split by dot and get last numeric part
  const dotParts = cleanUrl.split(".");
  if (dotParts.length >= 2) {
    const potentialItemId = dotParts[dotParts.length - 1];
    if (/^\d+$/.test(potentialItemId)) {
      return potentialItemId;
    }
  }
  
  return null;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const acuanId = parseInt(id, 10);

  try {
    const body = await request.json();
    const { url, nama_toko, harga, terjual, gambar, item_id } = body;

    if (!url) {
      return NextResponse.json({ success: false, error: "URL kompetitor wajib dikirim." }, { status: 400 });
    }

    // Extract item ID if not explicitly sent
    const itemId = item_id || extractShopeeItemId(url);
    if (!itemId) {
      return NextResponse.json({ success: false, error: "Tidak dapat mengekstrak ID Produk Shopee dari URL." }, { status: 400 });
    }

    // 1. Verify product acuan exists
    const acuan = await q<any>(
      `select id, skip_itemid from riset_produk_acuan where id = $1`,
      [acuanId]
    );
    if (acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan." }, { status: 404 });
    }

    const currentSkipStr = acuan[0].skip_itemid || "";
    
    // 2. Insert into riset_kompetitor_excluded
    await q(
      `insert into riset_kompetitor_excluded (produk_acuan_id, item_id, url, nama_toko, harga, terjual, gambar)
       values ($1, $2, $3, $4, $5, $6, $7)
       on conflict (produk_acuan_id, item_id) do update 
       set url = excluded.url, nama_toko = excluded.nama_toko, harga = excluded.harga, terjual = excluded.terjual, gambar = excluded.gambar, diambil_pada = now()`,
      [acuanId, itemId, url, nama_toko || "", harga || "", parseInt(terjual || "0", 10), gambar || ""]
    );

    // 3. Update skip_itemid on riset_produk_acuan
    let skipList = currentSkipStr.split(",").map((s: string) => s.trim()).filter(Boolean);
    if (!skipList.includes(itemId)) {
      skipList.push(itemId);
    }
    const newSkipStr = skipList.join(",");

    await q(
      `update riset_produk_acuan set skip_itemid = $1 where id = $2`,
      [newSkipStr, acuanId]
    );

    // 4. Delete from riset_kompetitor_detail (both exact url and by item_id suffix)
    await q(
      `delete from riset_kompetitor_detail 
       where produk_acuan_id = $1 and (url = $2 or url like '%' || $3)`,
      [acuanId, url, itemId]
    );

    return NextResponse.json({
      success: true,
      message: "Produk kompetitor berhasil dikecualikan dari riset otomatis."
    });
  } catch (err: any) {
    console.error("API Exclude Competitor Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const acuanId = parseInt(id, 10);

  const { searchParams } = new URL(request.url);
  const itemId = searchParams.get("item_id");

  if (!itemId) {
    return NextResponse.json({ success: false, error: "ID Produk Shopee (item_id) wajib disertakan." }, { status: 400 });
  }

  try {
    // 1. Verify product acuan exists
    const acuan = await q<any>(
      `select id, skip_itemid from riset_produk_acuan where id = $1`,
      [acuanId]
    );
    if (acuan.length === 0) {
      return NextResponse.json({ success: false, error: "Produk acuan tidak ditemukan." }, { status: 404 });
    }

    const currentSkipStr = acuan[0].skip_itemid || "";

    // 2. Delete from riset_kompetitor_excluded
    await q(
      `delete from riset_kompetitor_excluded where produk_acuan_id = $1 and item_id = $2`,
      [acuanId, itemId]
    );

    // 3. Remove from skip_itemid on riset_produk_acuan
    let skipList = currentSkipStr.split(",").map((s: string) => s.trim()).filter(Boolean);
    skipList = skipList.filter((s: string) => s !== itemId);
    const newSkipStr = skipList.join(",");

    // Reset tanggal_update to null to schedule re-scraping and restore the item in visual lists
    await q(
      `update riset_produk_acuan set skip_itemid = $1, tanggal_update = null where id = $2`,
      [newSkipStr, acuanId]
    );

    return NextResponse.json({
      success: true,
      message: "Eksklusi produk kompetitor berhasil dibatalkan. Antrean riset di-reset agar segera di-scrape kembali."
    });
  } catch (err: any) {
    console.error("API Restore Competitor Error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
