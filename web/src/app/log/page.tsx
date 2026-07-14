"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type DetailItem = { sku?: string; market?: string; serupa?: number; acuan?: number };
type Entry = { status: string; keterangan: string | null; waktu: string; detail?: DetailItem[] | null };
type Trigger = { key: string; label: string; last: Entry | null; history: Entry[] };
type Program = { key: string; label: string; triggers: Trigger[] };
type HargaEvent = {
  waktu: string; status: string; keterangan: string | null;
  fase: string | null; toko: string | null; modul: string | null; aksi: string | null;
  detail: Record<string, unknown> | null;
};

function DetailProduk({ detail }: { detail: DetailItem[] }) {
  return (
    <div className="mt-2 border border-[#eef0f6] rounded-lg overflow-hidden">
      <table className="w-full text-[11px]">
        <thead className="bg-[#f7f8fb] text-[#8a90a2]">
          <tr className="text-left">
            <th className="px-2.5 py-1.5 font-semibold">SKU</th>
            <th className="px-2.5 py-1.5 font-semibold">Market</th>
            <th className="px-2.5 py-1.5 font-semibold text-right">Kompetitor serupa</th>
            <th className="px-2.5 py-1.5 font-semibold text-center">Acuan</th>
          </tr>
        </thead>
        <tbody>
          {detail.map((d, i) => (
            <tr key={i} className="border-t border-[#f3f4f8]">
              <td className="px-2.5 py-1.5 font-medium text-slate-700">{d.sku || "—"}</td>
              <td className="px-2.5 py-1.5 text-[#8a90a2]">{d.market || "—"}</td>
              <td className="px-2.5 py-1.5 text-right tabular-nums font-semibold text-slate-800">{d.serupa ?? 0}</td>
              <td className="px-2.5 py-1.5 text-center">{d.acuan ? "✓" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function waktuAbsolut(iso: string) {
  return new Date(iso).toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }) + " WIB";
}

function waktuRelatif(iso: string) {
  const detik = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (detik < 60) return "baru saja";
  const menit = Math.floor(detik / 60);
  if (menit < 60) return `${menit} menit lalu`;
  const jam = Math.floor(menit / 60);
  if (jam < 24) return `${jam} jam lalu`;
  const hari = Math.floor(jam / 24);
  return `${hari} hari lalu`;
}

function StatusBadge({ status }: { status: string }) {
  const s = (status || "ok").toLowerCase();
  const style =
    s === "live" ? "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200"
    : s === "ok" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "gagal" ? "bg-rose-50 text-rose-700 border-rose-200"
    : s === "skip" || s === "warning" ? "bg-amber-50 text-amber-700 border-amber-200"
    : "bg-slate-100 text-slate-600 border-slate-200";
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${style} uppercase`}>{s}</span>;
}

// ── Seksi EVENT bot harga: apa yang BERUBAH (harga dibenerin, promo dipasang/dicabut) ──
const MODUL_LABEL: Record<string, string> = {
  harga: "Harga", promo_toko: "Promo Toko", voucher: "Voucher", paket: "Paket",
  garansi: "Garansi", campaign: "Campaign", flash: "Flash",
};

function AktivitasHarga({ events }: { events: HargaEvent[] }) {
  const [fToko, setFToko] = useState<string>("");
  const [fModul, setFModul] = useState<string>("");
  const [fStatus, setFStatus] = useState<string>("");

  const tokoOpts = useMemo(() => [...new Set(events.map((e) => e.toko).filter(Boolean) as string[])].sort(), [events]);
  const modulOpts = useMemo(() => [...new Set(events.map((e) => e.modul).filter(Boolean) as string[])].sort(), [events]);
  const statusOpts = useMemo(() => [...new Set(events.map((e) => (e.status || "ok").toLowerCase()))].sort(), [events]);

  const tampil = useMemo(
    () => events.filter((e) =>
      (!fToko || e.toko === fToko) &&
      (!fModul || e.modul === fModul) &&
      (!fStatus || (e.status || "ok").toLowerCase() === fStatus)
    ),
    [events, fToko, fModul, fStatus]
  );

  const Chip = ({ val, cur, set, label }: { val: string; cur: string; set: (v: string) => void; label: string }) => (
    <button
      onClick={() => set(cur === val ? "" : val)}
      className={`px-2.5 py-1 rounded-full text-[11.5px] font-semibold border transition-all ${
        cur === val
          ? "bg-[#ee4d2d] text-white border-[#ee4d2d]"
          : "bg-white text-slate-600 border-[#e6e9f0] hover:bg-slate-50"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="card p-5">
      <h2 className="font-bold text-[15px] mb-1 flex items-center gap-2">
        <span className="w-1.5 h-4 rounded bg-[#ee4d2d] inline-block" />
        ⚡ Aktivitas Monitoring Harga
      </h2>
      <p className="text-[12px] text-[#8a90a2] mb-3">Cuma yang BERUBAH — harga dibenerin, promo dipasang/dicabut. Terbaru di atas.</p>

      {events.length === 0 ? (
        <div className="text-[12.5px] text-[#c4c8d4] py-6 text-center">Belum ada aktivitas. Event muncul begitu bot jalan (Fase 2).</div>
      ) : (
        <>
          <div className="flex flex-col gap-2 mb-3">
            {tokoOpts.length > 1 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-[#b4b9c6] font-semibold w-12">Toko</span>
                {tokoOpts.map((t) => <Chip key={t} val={t} cur={fToko} set={setFToko} label={t} />)}
              </div>
            )}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-[#b4b9c6] font-semibold w-12">Modul</span>
              {modulOpts.map((m) => <Chip key={m} val={m} cur={fModul} set={setFModul} label={MODUL_LABEL[m] || m} />)}
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] text-[#b4b9c6] font-semibold w-12">Status</span>
              {statusOpts.map((s) => <Chip key={s} val={s} cur={fStatus} set={setFStatus} label={s} />)}
            </div>
          </div>

          <div className="border border-[#eef0f6] rounded-lg overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="bg-[#f7f8fb] text-[#8a90a2]">
                <tr className="text-left">
                  <th className="px-2.5 py-2 font-semibold whitespace-nowrap">Waktu</th>
                  <th className="px-2.5 py-2 font-semibold">Toko</th>
                  <th className="px-2.5 py-2 font-semibold">Modul</th>
                  <th className="px-2.5 py-2 font-semibold">Aksi</th>
                  <th className="px-2.5 py-2 font-semibold text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {tampil.slice(0, 300).map((e, i) => (
                  <tr key={i} className="border-t border-[#f3f4f8] align-top">
                    <td className="px-2.5 py-2 whitespace-nowrap">
                      <div className="text-slate-700 font-medium">{waktuRelatif(e.waktu)}</div>
                      <div className="text-[10.5px] text-[#b4b9c6]">{waktuAbsolut(e.waktu)}</div>
                    </td>
                    <td className="px-2.5 py-2 font-semibold text-slate-700 whitespace-nowrap">{e.toko || "—"}</td>
                    <td className="px-2.5 py-2 whitespace-nowrap">
                      <span className="text-[11px] font-semibold text-slate-600">{e.fase ? `${e.fase}·` : ""}{MODUL_LABEL[e.modul || ""] || e.modul || "—"}</span>
                    </td>
                    <td className="px-2.5 py-2 text-slate-700">{e.aksi || e.keterangan || "—"}</td>
                    <td className="px-2.5 py-2 text-center"><StatusBadge status={e.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-[#b4b9c6] mt-2">
            {tampil.length} event{tampil.length !== events.length ? ` (dari ${events.length})` : ""}{tampil.length > 300 ? " · 300 teratas ditampilkan" : ""}
          </p>
        </>
      )}
    </div>
  );
}

export default function LogPage() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [hargaEvents, setHargaEvents] = useState<HargaEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number>(0);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/log", { cache: "no-store" });
      const j = await r.json();
      setPrograms(j.programs || []);
      setHargaEvents(j.hargaEvents || []);
      setUpdatedAt(Date.now());
    } catch {
      /* abaikan */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60_000);
    return () => clearInterval(t);
  }, [load]);

  return (
    <div className="max-w-[1100px] w-full mx-auto">
      <div className="mb-5 flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-[22px] font-extrabold tracking-tight">🧾 Log Otomatisasi</h1>
          <p className="text-[13px] text-[#8a90a2] mt-0.5">
            Jejak kapan tiap trigger program jalan — buat mastiin otomatisasi hidup.
          </p>
        </div>
        <button
          onClick={load}
          className="text-[13px] font-semibold px-3 py-2 rounded-lg border border-[#e6e9f0] bg-white hover:bg-slate-50 hover:text-[#ee4d2d] transition-all"
        >
          🔄 Refresh
        </button>
      </div>

      {loading && programs.length === 0 ? (
        <div className="card p-8 text-center text-[#8a90a2] text-[13px]">Memuat…</div>
      ) : (
        <div className="flex flex-col gap-6">
          <AktivitasHarga events={hargaEvents} />
          {programs.map((p) => (
            <div key={p.key} className="card p-5">
              <h2 className="font-bold text-[15px] mb-3 flex items-center gap-2">
                <span className="w-1.5 h-4 rounded bg-[#ee4d2d] inline-block" />
                {p.label}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {p.triggers.map((t) => {
                  const k = `${p.key}.${t.key}`;
                  const last = t.last;
                  return (
                    <div key={t.key} className="border border-[#eef0f6] rounded-xl p-3.5 bg-[#fafbfd]">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-semibold text-[13px] text-slate-800">{t.label}</span>
                        {last ? <StatusBadge status={last.status} /> : (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold border bg-slate-100 text-slate-400 border-slate-200 uppercase">
                            belum pernah
                          </span>
                        )}
                      </div>
                      {last ? (
                        <>
                          <div className="text-[15px] font-bold text-slate-800 tabular-nums">{waktuRelatif(last.waktu)}</div>
                          <div className="text-[11.5px] text-[#8a90a2]">{waktuAbsolut(last.waktu)}</div>
                          {last.keterangan && (
                            <div className="text-[11.5px] text-[#9aa0b2] mt-0.5">{last.keterangan}</div>
                          )}

                          <div className="flex items-center gap-3 mt-1.5">
                            {last.detail && last.detail.length > 0 && (
                              <button
                                onClick={() => setOpen((o) => ({ ...o, [`${k}:d`]: !o[`${k}:d`] }))}
                                className="text-[11px] text-[#ee4d2d] font-semibold hover:underline"
                              >
                                {open[`${k}:d`] ? "Tutup detail" : `📦 Detail produk (${last.detail.length})`}
                              </button>
                            )}
                            {t.history.length > 1 && (
                              <button
                                onClick={() => setOpen((o) => ({ ...o, [k]: !o[k] }))}
                                className="text-[11px] text-[#ee4d2d] font-semibold hover:underline"
                              >
                                {open[k] ? "Sembunyikan" : `🕘 Riwayat (${t.history.length})`}
                              </button>
                            )}
                          </div>

                          {open[`${k}:d`] && last.detail && last.detail.length > 0 && (
                            <DetailProduk detail={last.detail} />
                          )}

                          {open[k] && (
                            <div className="mt-2 border-t border-[#eef0f6] pt-2 flex flex-col gap-1.5">
                              {t.history.map((h, i) => (
                                <div key={i}>
                                  <div className="flex items-center justify-between text-[11px] text-[#8a90a2]">
                                    <span className="flex items-center gap-1.5">
                                      {waktuAbsolut(h.waktu)}
                                      {h.detail && h.detail.length > 0 && (
                                        <button
                                          onClick={() => setOpen((o) => ({ ...o, [`${k}:h${i}`]: !o[`${k}:h${i}`] }))}
                                          className="text-[#ee4d2d] font-semibold hover:underline"
                                        >
                                          {open[`${k}:h${i}`] ? "tutup" : `detail (${h.detail.length})`}
                                        </button>
                                      )}
                                    </span>
                                    <StatusBadge status={h.status} />
                                  </div>
                                  {open[`${k}:h${i}`] && h.detail && h.detail.length > 0 && (
                                    <DetailProduk detail={h.detail} />
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-[12.5px] text-[#c4c8d4]">Belum ada catatan. Trigger ini belum pernah jalan.</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {updatedAt > 0 && (
        <p className="text-[11px] text-[#b4b9c6] mt-4 text-right">
          Diperbarui otomatis tiap 60 detik · terakhir {new Date(updatedAt).toLocaleTimeString("id-ID")}
        </p>
      )}
    </div>
  );
}
