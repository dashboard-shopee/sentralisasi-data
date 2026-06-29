"use client";

import { useCallback, useEffect, useState } from "react";

type Entry = { status: string; keterangan: string | null; waktu: string };
type Trigger = { key: string; label: string; last: Entry | null; history: Entry[] };
type Program = { key: string; label: string; triggers: Trigger[] };

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
    s === "ok" ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : s === "gagal" ? "bg-rose-50 text-rose-700 border-rose-200"
    : "bg-slate-100 text-slate-600 border-slate-200";
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${style} uppercase`}>{s}</span>;
}

export default function LogPage() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number>(0);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/log", { cache: "no-store" });
      const j = await r.json();
      setPrograms(j.programs || []);
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
                          {t.history.length > 1 && (
                            <button
                              onClick={() => setOpen((o) => ({ ...o, [k]: !o[k] }))}
                              className="text-[11px] text-[#ee4d2d] font-semibold mt-1.5 hover:underline"
                            >
                              {open[k] ? "Sembunyikan" : `Riwayat (${t.history.length})`}
                            </button>
                          )}
                          {open[k] && (
                            <div className="mt-2 border-t border-[#eef0f6] pt-2 flex flex-col gap-1">
                              {t.history.map((h, i) => (
                                <div key={i} className="flex items-center justify-between text-[11px] text-[#8a90a2]">
                                  <span>{waktuAbsolut(h.waktu)}</span>
                                  <StatusBadge status={h.status} />
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
