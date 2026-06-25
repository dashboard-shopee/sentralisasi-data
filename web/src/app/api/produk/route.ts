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

import { pool } from "@/lib/db";

export async function POST(req: Request) {
  try {
    const { edits } = await req.json();
    if (!edits || typeof edits !== "object") {
      return NextResponse.json({ success: false, error: "Invalid payload" }, { status: 400 });
    }

    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      for (const [kode, fields] of Object.entries(edits)) {
        const pid = Number(kode);
        const f = fields as Record<string, string>;

        const updates: string[] = [];
        const params: unknown[] = [pid];

        if (f.budgetManual !== undefined) {
          params.push(f.budgetManual === "" ? null : Number(f.budgetManual));
          updates.push(`budget_manual = $${params.length}`);
        }
        if (f.rekomRoas !== undefined) {
          params.push(f.rekomRoas === "" ? null : Number(f.rekomRoas));
          updates.push(`rekom_roas = $${params.length}`);
        }

        if (updates.length > 0) {
          const checkRes = await client.query("select 1 from iklan_setting where produk_id = $1", [pid]);
          if (checkRes.rowCount === 0) {
            const tokoRes = await client.query("select toko_id from dim_produk where produk_id = $1", [pid]);
            const toko_id = tokoRes.rows[0]?.toko_id || null;
            
            let query = "";
            let insertParams: unknown[] = [];
            if (f.budgetManual !== undefined && f.rekomRoas !== undefined) {
              query = `insert into iklan_setting (produk_id, toko_id, budget_manual, rekom_roas, diperbarui_pada) 
                       values ($1, $2, $3, $4, now())`;
              insertParams = [pid, toko_id, f.budgetManual === "" ? null : Number(f.budgetManual), f.rekomRoas === "" ? null : Number(f.rekomRoas)];
            } else if (f.budgetManual !== undefined) {
              query = `insert into iklan_setting (produk_id, toko_id, budget_manual, diperbarui_pada) 
                       values ($1, $2, $3, now())`;
              insertParams = [pid, toko_id, f.budgetManual === "" ? null : Number(f.budgetManual)];
            } else {
              query = `insert into iklan_setting (produk_id, toko_id, rekom_roas, diperbarui_pada) 
                       values ($1, $2, $3, now())`;
              insertParams = [pid, toko_id, f.rekomRoas === "" ? null : Number(f.rekomRoas)];
            }
            await client.query(query, insertParams);
          } else {
            await client.query(
              `update iklan_setting set ${updates.join(", ")}, diperbarui_pada = now() where produk_id = $1`,
              params
            );
          }
        }
      }
      await client.query("COMMIT");
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }

    return NextResponse.json({ success: true });
  } catch (err: any) {
    console.error("POST /api/produk error:", err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
