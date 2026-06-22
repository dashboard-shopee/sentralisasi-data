import { rpShort, numShort } from "./format";

export type Fmt = "rp" | "num" | "pct" | "ratio";
export type VarDef = { key: string; label: string; fmt: Fmt; ikon: string };

export const fmtVal = (v: number, f: Fmt) =>
  f === "rp"
    ? rpShort(v)
    : f === "num"
    ? numShort(v)
    : f === "pct"
    ? (v || 0).toFixed(1) + "%"
    : (v || 0).toFixed(2);

// Penjualan + Pesanan — urut dari yang paling penting
export const VARS_JUAL: VarDef[] = [
  { key: "omzet", label: "Omzet", fmt: "rp", ikon: "💰" },
  { key: "pesanan", label: "Pesanan", fmt: "num", ikon: "🛒" },
  { key: "unit", label: "Unit Terjual", fmt: "num", ikon: "📦" },
  { key: "pembeli", label: "Pembeli", fmt: "num", ikon: "🧑" },
  { key: "pengunjung", label: "Pengunjung", fmt: "num", ikon: "👁️" },
  { key: "konversi", label: "Konversi %", fmt: "pct", ikon: "🎯" },
  { key: "aov", label: "Omzet / Pesanan", fmt: "rp", ikon: "🧾" },
  { key: "keranjang", label: "Masuk Keranjang", fmt: "num", ikon: "➕" },
  { key: "omzetPesanan", label: "Omzet Pesanan", fmt: "rp", ikon: "💵" },
  { key: "pesananBatal", label: "Pesanan Batal", fmt: "num", ikon: "❌" },
];

// Iklan — urut dari yang paling penting
export const VARS_IKLAN: VarDef[] = [
  { key: "omzetIklan", label: "Omzet Iklan", fmt: "rp", ikon: "💵" },
  { key: "biayaIklan", label: "Biaya Iklan", fmt: "rp", ikon: "💸" },
  { key: "roas", label: "ROAS Iklan", fmt: "ratio", ikon: "📈" },
  { key: "konversi", label: "Konversi", fmt: "num", ikon: "🎯" },
  { key: "klik", label: "Iklan Diklik", fmt: "num", ikon: "🖱️" },
  { key: "dilihat", label: "Iklan Dilihat", fmt: "num", ikon: "👁️" },
  { key: "ctr", label: "CTR %", fmt: "pct", ikon: "📊" },
  { key: "cr", label: "CR %", fmt: "pct", ikon: "✅" },
  { key: "cpc", label: "CPC", fmt: "rp", ikon: "💲" },
];
