import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

// Penanda "terakhir diperbarui" untuk halaman Monitoring Harga:
//  - dataTerakhir = update terbaru tabel harga_olah_data (real, dari grab)
//  - fase = kapan tiap fase bot harga terakhir jalan (dari siklus_log program='harga')
export async function GET() {
  const out: { dataTerakhir: string | null; fase: Record<string, string | null> } = {
    dataTerakhir: null,
    fase: {},
  };
  try {
    const d = await q<{ mx: string | null }>(`select max(diperbarui_pada) as mx from harga_olah_data`);
    out.dataTerakhir = d[0]?.mx ?? null;
  } catch {}
  try {
    const rows = await q<{ pemicu: string; waktu: string }>(
      `select distinct on (pemicu) pemicu, waktu
         from siklus_log where program='harga'
        order by pemicu, waktu desc`
    );
    for (const r of rows) out.fase[r.pemicu] = r.waktu;
  } catch {}
  return NextResponse.json(out);
}
