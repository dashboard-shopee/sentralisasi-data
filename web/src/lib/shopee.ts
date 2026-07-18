// shop_id Shopee per nama toko (buat link produk). Sumber tunggal — dipakai ServerTable,
// halaman harga, pusat promosi. URL produk: https://shopee.co.id/product/<shopId>/<itemId>.
export const SHOP_ID_BY_NAME: Record<string, string> = {
  "Kimmioshop": "1772452045",
  "lollysweet": "1770737480",
  "Ravella Shop": "1482379795",
  "Topikece Store": "1086654958",
  "Alialia Store": "1083692044",
  "OLIOLIO.ID": "552378634",
  "NOMIDE STORE": "416053468",
  "YARRA STORE": "144416606",
  "ZIOSCARF SUPPLIER HIJAB IMPORT": "93819147",
  "BEVERRA OFFICIAL STORE": "13556329",
};

export function urlProdukShopee(toko: string | null | undefined, itemId: string | number | null | undefined): string | null {
  if (!toko || !itemId) return null;
  const shopId = SHOP_ID_BY_NAME[String(toko)];
  if (!shopId) return null;
  return `https://shopee.co.id/product/${shopId}/${itemId}`;
}

// Warna KPI margin (spec owner 18 Jul): <0 merah · 0–8% oranye · 8–20% hijau · >20% biru.
export function warnaMargin(m: number | null | undefined): string {
  if (m === null || m === undefined) return "text-[#9aa0b2]";
  if (m < 0) return "text-[#e11d48]";        // rugi
  if (m < 0.08) return "text-[#f59e0b]";     // tipis
  if (m <= 0.20) return "text-[#047857]";    // sehat
  return "text-[#2563eb]";                   // gemuk
}

// Warna harga toko vs patokan (Harga Diskon induk): bawah=merah · sama=hitam · atas=biru.
export function warnaHargaVs(harga: number, patokan: number | null | undefined): string {
  if (!patokan || patokan <= 0 || !harga) return "text-[#4b5563]";
  if (harga < patokan) return "text-[#e11d48]";
  if (harga > patokan) return "text-[#2563eb]";
  return "text-[#161a27]";
}
