import type { Filter } from "./filters";

export const n = (x: unknown) => Number(x ?? 0);

export const num = (x: unknown) => Math.round(n(x)).toLocaleString("id-ID");

export const rp = (x: unknown) => "Rp" + Math.round(n(x)).toLocaleString("id-ID");

export const rpShort = (x: unknown) => {
  const v = n(x);
  if (v >= 1e9) return "Rp" + (v / 1e9).toFixed(1).replace(".", ",") + " M";
  if (v >= 1e6) return "Rp" + (v / 1e6).toFixed(1).replace(".", ",") + " jt";
  if (v >= 1e3) return "Rp" + Math.round(v / 1e3) + " rb";
  return "Rp" + Math.round(v);
};

export const numShort = (x: unknown) => {
  const v = n(x);
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace(".", ",") + " jt";
  if (v >= 1e3) return (v / 1e3).toFixed(1).replace(".", ",") + " rb";
  return String(Math.round(v));
};

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
const wib = (d: Date | string) => new Date(new Date(d).getTime() + 7 * 3600 * 1000);
export const labelBulan = (d: Date | string) => {
  const w = wib(d);
  return `${BULAN[w.getUTCMonth()]} ${String(w.getUTCFullYear()).slice(2)}`;
};
export const labelHari = (d: Date | string) => {
  const w = wib(d);
  return `${w.getUTCDate()} ${BULAN[w.getUTCMonth()]} ${w.getUTCFullYear()}`;
};
export const labelTahun = (d: Date | string) => String(wib(d).getUTCFullYear());
export const labelPeriode = (g: string, d: Date | string) =>
  g === "harian"
    ? labelHari(d)
    : g === "mingguan"
    ? "Minggu " + labelHari(d)
    : g === "bulanan"
    ? labelBulan(d)
    : labelTahun(d);

const isSameDayWib = (d1: string | Date, d2: string | Date) => {
  const w1 = new Date(new Date(d1).getTime() + 7 * 3600 * 1000);
  const w2 = new Date(new Date(d2).getTime() + 7 * 3600 * 1000);
  return (
    w1.getUTCFullYear() === w2.getUTCFullYear() &&
    w1.getUTCMonth() === w2.getUTCMonth() &&
    w1.getUTCDate() === w2.getUTCDate()
  );
};

export function caption(f: Filter): string {
  if (f.periode === "harian" && f.a === f.b) {
    const today = new Date();
    const yesterday = new Date(Date.now() - 24 * 3600 * 1000);
    if (isSameDayWib(f.a, today)) return `Hari ini (${labelHari(f.a)})`;
    if (isSameDayWib(f.a, yesterday)) return `Kemarin (${labelHari(f.a)})`;
  }
  const la = labelPeriode(f.periode, f.a);
  const lb = labelPeriode(f.periode, f.b);
  return la === lb ? la : `${la} – ${lb}`;
}
