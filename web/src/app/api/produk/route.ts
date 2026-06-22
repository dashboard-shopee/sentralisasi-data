import { NextResponse } from "next/server";
import { getProdukJual, getProdukIklan, type TableOpts } from "@/lib/data";
import type { Filter } from "@/lib/filters";

export const dynamic = "force-dynamic";

const CSV_JUAL: [string, string][] = [
  ["kode", "Kode Produk"], ["skuInduk", "SKU Induk"], ["produk", "Nama Produk"], ["toko", "Toko"],
  ["omzet", "Omzet"], ["pesanan", "Pesanan"], ["unit", "Unit Terjual"], ["pembeli", "Pembeli"],
  ["pengunjung", "Pengunjung"], ["konversi", "Konversi %"], ["aov", "Omzet per Pesanan"], ["keranjang", "Masuk Keranjang"],
];
const CSV_IKLAN: [string, string][] = [
  ["kode", "Kode Produk"], ["skuInduk", "SKU Induk"], ["produk", "Nama Produk"], ["toko", "Toko"],
  ["dilihat", "Dilihat"], ["klik", "Klik"], ["ctr", "CTR %"], ["cr", "CR %"], ["cpc", "CPC"],
  ["konversi", "Konversi"], ["omzetIklan", "Omzet Iklan"], ["biayaIklan", "Biaya Iklan"], ["roas", "ROAS"],
];

function toCsv(cols: [string, string][], rows: Record<string, unknown>[]) {
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = cols.map(([, l]) => esc(l)).join(",");
  const body = rows.map((r) => cols.map(([k]) => esc(r[k])).join(",")).join("\n");
  return "﻿" + head + "\n" + body; // BOM biar Excel baca UTF-8
}

export async function GET(req: Request) {
  const p = new URL(req.url).searchParams;
  const kind = p.get("kind") === "iklan" ? "iklan" : "jual";
  const f: Filter = {
    periode: p.get("g") || "harian",
    a: p.get("d") || "",
    b: p.get("s") || "",
    toko: (p.get("t") || "").split(",").filter(Boolean),
  };
  const download = p.get("download") === "csv";
  const o: TableOpts = {
    page: parseInt(p.get("page") || "1") || 1,
    size: parseInt(p.get("size") || "50") || 50,
    sort: p.get("sort") || "",
    dir: p.get("dir") || "desc",
    q: p.get("q") || "",
    all: download,
  };
  const data = kind === "iklan" ? await getProdukIklan(f, o) : await getProdukJual(f, o);
  if (download) {
    const csv = toCsv(kind === "iklan" ? CSV_IKLAN : CSV_JUAL, data.rows);
    return new NextResponse(csv, {
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "content-disposition": `attachment; filename="laporan-${kind}-${f.a.slice(0, 10)}_${f.b.slice(0, 10)}.csv"`,
      },
    });
  }
  return NextResponse.json(data);
}
