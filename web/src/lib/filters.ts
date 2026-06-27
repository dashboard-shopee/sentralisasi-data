import { unstable_cache } from "next/cache";
import { q } from "./db";
import { labelPeriode } from "./format";

export type Filter = { periode: string; a: string; b: string; toko: string[] };
export type PeriodOpt = { value: string; label: string };
export type Options = {
  grans: string[];
  periodsByGran: Record<string, PeriodOpt[]>;
  toko: string[];
};

const GRANS = ["harian", "mingguan", "bulanan", "tahunan"];
// Lebar rentang default (jumlah periode ke belakang) per granularitas.
export const WIN: Record<string, number> = { harian: 14, mingguan: 12, bulanan: 12, tahunan: 6 };

// di-cache 5 menit: opsi filter (periode + toko) jarang berubah (paling sehari sekali pas data baru masuk).
export const getOptions = unstable_cache(
  async (): Promise<Options> => {
    const punya = (await q<{ periode: string }>("select distinct periode from fact_penjualan")).map(
      (r) => r.periode
    );
    const grans = GRANS.filter((g) => punya.includes(g));
    const periodsByGran: Record<string, PeriodOpt[]> = {};
    for (const g of grans) {
      const rows = await q<{ m: string }>(
        "select distinct periode_mulai m from fact_penjualan where periode=$1 order by periode_mulai desc",
        [g]
      );
      periodsByGran[g] = rows.map((r) => ({
        value: new Date(r.m).toISOString(),
        label: labelPeriode(g, r.m),
      }));
    }
    const toko = (await q<{ nama: string }>("select nama from dim_toko order by shop_index")).map(
      (r) => r.nama
    );
    return { grans, periodsByGran, toko };
  },
  ["filter-options-v1"],
  { revalidate: 300 }
);

const isSameDayWib = (d1: string | Date, d2: string | Date) => {
  const w1 = new Date(new Date(d1).getTime() + 7 * 3600 * 1000);
  const w2 = new Date(new Date(d2).getTime() + 7 * 3600 * 1000);
  return (
    w1.getUTCFullYear() === w2.getUTCFullYear() &&
    w1.getUTCMonth() === w2.getUTCMonth() &&
    w1.getUTCDate() === w2.getUTCDate()
  );
};

function pick(v: string | undefined): string | undefined {
  return v && v.length ? v : undefined;
}

export function resolveFilter(
  sp: Record<string, string | string[] | undefined>,
  opt: Options,
  def?: { g?: string; win?: number }
): Filter {
  const gParam = typeof sp.g === "string" ? sp.g : undefined;
  const fallbackG =
    def?.g && opt.grans.includes(def.g)
      ? def.g
      : opt.grans.includes("bulanan")
      ? "bulanan"
      : opt.grans[0] ?? "bulanan";
  const periode = gParam && opt.grans.includes(gParam) ? gParam : fallbackG;

  const vals = (opt.periodsByGran[periode] ?? []).map((p) => p.value); // desc (terbaru dulu)
  const dParam = pick(typeof sp.d === "string" ? sp.d : undefined);
  const sParam = pick(typeof sp.s === "string" ? sp.s : undefined);
  // pakai default window hanya bila granularitas tidak di-override via URL
  const win = !gParam && def?.win ? def.win : WIN[periode] ?? 12;

  const hasToday = vals.length > 0 && isSameDayWib(vals[0], new Date());

  let b: string;
  let a: string;

  if (sParam && vals.includes(sParam)) {
    b = sParam;
  } else {
    b = (periode === "harian" && hasToday && vals.length > 1) ? vals[1] : vals[0];
  }

  if (dParam && vals.includes(dParam)) {
    a = dParam;
  } else {
    const offset = (periode === "harian" && hasToday && vals.length > 1) ? 1 : 0;
    a = vals[Math.min(offset + win - 1, Math.max(0, vals.length - 1))];
  }

  // a = lebih lama, b = lebih baru. Tukar bila perlu.
  if (a && b && new Date(a) > new Date(b)) [a, b] = [b, a];

  const tParam = typeof sp.t === "string" ? sp.t : undefined;
  const toko = tParam ? tParam.split(",").filter(Boolean) : [];
  return { periode, a: a ?? b, b: b ?? a, toko };
}
