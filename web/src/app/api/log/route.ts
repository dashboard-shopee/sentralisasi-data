import { NextResponse } from "next/server";
import { q } from "@/lib/db";

export const dynamic = "force-dynamic";

// Katalog trigger yg ditampilkan (urutan + label rapi). Program baru ke depan
// tinggal tambah entri di sini; pemicu yg ada di DB tapi belum terdaftar tetap
// ditampilkan otomatis (pakai key mentah sbg label) biar tak ada yg kesembunyi.
const KATALOG = [
  {
    key: "iklan",
    label: "Syntra Iklan",
    pemicu: [
      { key: "reset1", label: "Log Reset 1" },
      { key: "reset2", label: "Log Reset 2" },
      { key: "laporan", label: "Log Laporan" },
      { key: "analisa", label: "Log Analisa Iklan" },
      { key: "ubah_roas", label: "Log Ubah ROAS" },
    ],
  },
  {
    key: "riset",
    label: "Syntra Riset Kompetitor",
    pemicu: [{ key: "siklus", label: "Log Setiap Siklus" }],
  },
];

type Row = { program: string; pemicu: string; status: string; keterangan: string | null; waktu: string };

export async function GET() {
  let rows: Row[] = [];
  try {
    rows = await q<Row>(
      `select program, pemicu, status, keterangan, waktu
         from siklus_log order by waktu desc limit 1000`
    );
  } catch {
    // tabel belum ada / DB error -> balikin katalog kosong, jangan 500
    rows = [];
  }

  const byKey: Record<string, Row[]> = {};
  for (const r of rows) (byKey[`${r.program}|${r.pemicu}`] ??= []).push(r);

  const seen = new Set<string>();
  const buatTrigger = (programKey: string, key: string, label: string) => {
    const hist = byKey[`${programKey}|${key}`] || [];
    seen.add(`${programKey}|${key}`);
    return { key, label, last: hist[0] || null, history: hist.slice(0, 15) };
  };

  const programs = KATALOG.map((p) => ({
    key: p.key,
    label: p.label,
    triggers: p.pemicu.map((t) => buatTrigger(p.key, t.key, t.label)),
  }));

  // Program/pemicu di DB yg belum terdaftar di katalog -> tampilkan juga.
  const extra: Record<string, { key: string; label: string; triggers: Record<string, unknown> }> = {};
  for (const r of rows) {
    const k = `${r.program}|${r.pemicu}`;
    if (seen.has(k)) continue;
    seen.add(k);
    (extra[r.program] ??= { key: r.program, label: r.program, triggers: {} });
    extra[r.program].triggers[r.pemicu] = buatTrigger(r.program, r.pemicu, r.pemicu);
  }
  const extraPrograms = Object.values(extra).map((p) => ({
    key: p.key,
    label: p.label,
    triggers: Object.values(p.triggers),
  }));

  return NextResponse.json({ programs: [...programs, ...extraPrograms] });
}
