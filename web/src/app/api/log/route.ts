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
      { key: "hpp", label: "Log Ambil HPP (Jubelio)" },
    ],
  },
  {
    key: "harga",
    label: "Syntra Monitoring Harga",
    pemicu: [
      { key: "grab", label: "Log Ambil Produk & Konteks (Fase 1 — tiap jam)" },
      { key: "kategori", label: "Log Ambil Kategori Produk" },
      { key: "fakta_harian", label: "Log Fakta Harian (Garansi + Campaign)" },
      { key: "fakta_mingguan", label: "Log Fakta Mingguan (Flash + Voucher + Paket)" },
      { key: "fakta_bulanan", label: "Log Housekeeping Bulanan" },
      { key: "rubah_harga", label: "Log Rubah Harga" },
      { key: "provisioning", label: "Log Provisioning (Pasang Promo)" },
      { key: "laporan", label: "Log Fase 3 (Laporan — Grab Ulang Status Terkini)" },
    ],
  },
  {
    key: "riset",
    label: "Syntra Riset Kompetitor",
    pemicu: [{ key: "siklus", label: "Log Setiap Siklus" }],
  },
];

type Row = { program: string; pemicu: string; status: string; keterangan: string | null; detail: unknown; waktu: string };
// Event kaya bot harga (catat()): detail = {fase,toko,modul,aksi,...}. Baris ini
// TIDAK ditampilkan sbg heartbeat, tapi ke tabel event terpisah (hargaEvents).
type Detail = { fase?: string; toko?: string; modul?: string; aksi?: string } | null;
type HargaEvent = { waktu: string; status: string; keterangan: string | null;
                    fase: string | null; toko: string | null; modul: string | null; aksi: string | null;
                    detail: Record<string, unknown> | null };

function isEvent(d: unknown): d is Record<string, unknown> {
  return !!d && typeof d === "object" && !Array.isArray(d) && "modul" in (d as object);
}

export async function GET() {
  let rows: Row[] = [];
  try {
    rows = await q<Row>(
      `select program, pemicu, status, keterangan, detail, waktu
         from siklus_log order by waktu desc limit 1000`
    );
  } catch {
    // tabel belum ada / DB error -> balikin katalog kosong, jangan 500
    rows = [];
  }

  // Pisahkan EVENT bot harga (punya detail.modul) dari heartbeat trigger.
  const hargaEvents: HargaEvent[] = [];
  const heartbeat: Row[] = [];
  for (const r of rows) {
    if (r.program === "harga" && isEvent(r.detail)) {
      const d = r.detail as Record<string, unknown> & Detail;
      hargaEvents.push({
        waktu: r.waktu, status: r.status, keterangan: r.keterangan,
        fase: (d.fase as string) ?? null, toko: (d.toko as string) ?? null,
        modul: (d.modul as string) ?? null, aksi: (d.aksi as string) ?? r.keterangan,
        detail: d,
      });
    } else {
      heartbeat.push(r);
    }
  }

  const byKey: Record<string, Row[]> = {};
  for (const r of heartbeat) (byKey[`${r.program}|${r.pemicu}`] ??= []).push(r);

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
  for (const r of heartbeat) {
    // pemicu 'harga' yg ga kekatalog JANGAN dibikinin kartu nyasar (17 Jul, owner):
    // heartbeat modul udah tampil di grid per-modul dalam kartu Syntra Monitoring Harga.
    if (r.program === "harga") continue;
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

  // Heartbeat per-MODUL bot harga (17 Jul, permintaan owner): baris event TERBARU per modul
  // (grab fakta F1 harian + aksi F2) -> kartu "modul ini terakhir jalan kapan & hasilnya apa".
  // Halaman log ga nampilin tabel event lagi (owner mau clean) -- cukup kartu ini.
  const modulSeen = new Set<string>();
  const modulTerakhir: { modul: string; waktu: string; status: string; toko: string | null; aksi: string | null }[] = [];
  for (const e of hargaEvents) {
    const m = e.modul || "";
    if (!m || modulSeen.has(m)) continue;
    modulSeen.add(m);
    modulTerakhir.push({ modul: m, waktu: e.waktu, status: e.status, toko: e.toko, aksi: e.aksi ?? e.keterangan });
  }

  return NextResponse.json({ programs: [...programs, ...extraPrograms], modulTerakhir });
}
