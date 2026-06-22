"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { rpShort, num } from "@/lib/format";
import { fmtVal } from "@/lib/variables";
import type { VarDef } from "@/lib/variables";

export const PALETTE = [
  "#ee4d2d", "#ff8a65", "#ffb74d", "#16b8a6", "#42a5f5",
  "#7e57c2", "#ec407a", "#66bb6a", "#8d6e63", "#ffa726",
];

// Warna kontras untuk grafik multi-variabel (maks 4)
const CHART = ["#ee4d2d", "#2563eb", "#16b8a6", "#9333ea"];

const tip = {
  borderRadius: 12,
  border: "1px solid #eef1f6",
  boxShadow: "0 6px 20px rgba(20,23,40,.08)",
  fontSize: 12,
};

export function AreaTrend({ data }: { data: { label: string; omzet: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <AreaChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="gomzet" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ee4d2d" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#ee4d2d" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} tickFormatter={(v) => rpShort(v)} width={58} />
        <Tooltip formatter={(v) => rpShort(v)} contentStyle={tip} />
        <Area type="monotone" dataKey="omzet" stroke="#ee4d2d" strokeWidth={2.5} fill="url(#gomzet)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function DonutToko({ data }: { data: { toko: string; omzet: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={250}>
      <PieChart>
        <Pie data={data} dataKey="omzet" nameKey="toko" innerRadius={62} outerRadius={95} paddingAngle={2} stroke="none">
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v) => rpShort(v)} contentStyle={tip} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// Grafik custom: tiap variabel = 1 garis dengan sumbu-Y sendiri (tersembunyi),
// jadi 4 variabel beda skala (Rp, jumlah, %) bisa dibandingkan bentuk trennya.
export function FlexChart({ data, series }: { data: Record<string, number | string>[]; series: VarDef[] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        {series.map((s) => (
          <YAxis key={s.key} yAxisId={s.key} hide domain={["auto", "auto"]} />
        ))}
        <Tooltip
          contentStyle={tip}
          formatter={(v, name) => {
            const s = series.find((x) => x.label === name);
            return s ? fmtVal(Number(v), s.fmt) : String(v);
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Line key={s.key} yAxisId={s.key} type="monotone" dataKey={s.key} name={s.label} stroke={CHART[i % CHART.length]} strokeWidth={2.5} dot={false} />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

// Pesanan + Omzet per toko (dua batang, dua sumbu)
const potong = (s: string) => (s.length > 13 ? s.slice(0, 12) + "…" : s);
export function BarTokoDuo({ data }: { data: { toko: string; pesanan: number; omzet: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 8 }}>
        <XAxis dataKey="toko" tick={{ fontSize: 10, fill: "#9aa0b2" }} axisLine={false} tickLine={false} interval={0} angle={-35} textAnchor="end" height={104} tickMargin={6} tickFormatter={potong} />
        <YAxis yAxisId="l" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} tickFormatter={(v) => num(v)} width={44} />
        <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} tickFormatter={(v) => rpShort(v)} width={58} />
        <Tooltip contentStyle={tip} cursor={{ fill: "#f6f7fb" }} formatter={(v, name) => (name === "Omzet" ? rpShort(v) : num(v) + " pesanan")} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar yAxisId="l" dataKey="pesanan" name="Pesanan" fill="#ee4d2d" radius={[6, 6, 0, 0]} barSize={14} />
        <Bar yAxisId="r" dataKey="omzet" name="Omzet" fill="#16b8a6" radius={[6, 6, 0, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ComboAnalisa({
  data,
}: {
  data: { label: string; omzet: number; biaya: number; omzetIklan: number; roas: number; acos: number }[];
}) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
        <YAxis yAxisId="l" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} tickFormatter={(v) => rpShort(v)} width={58} />
        <YAxis yAxisId="r" orientation="right" tick={{ fontSize: 11, fill: "#16b8a6" }} axisLine={false} tickLine={false} domain={[0, "auto"]} width={32} />
        <YAxis yAxisId="acos" hide domain={[0, "auto"]} />
        <Tooltip contentStyle={tip} formatter={(v, name) => (name === "ROAS" ? Number(v).toFixed(2) : name === "ACOS" ? Number(v).toFixed(1) + "%" : rpShort(v))} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar yAxisId="l" dataKey="omzet" name="Omzet" fill="#ee4d2d" radius={[6, 6, 0, 0]} barSize={11} />
        <Bar yAxisId="l" dataKey="biaya" name="Biaya Iklan" fill="#42a5f5" radius={[6, 6, 0, 0]} barSize={11} />
        <Line yAxisId="l" type="monotone" dataKey="omzetIklan" name="Omzet Iklan" stroke="#7e57c2" strokeWidth={2.5} dot={false} />
        <Line yAxisId="r" type="monotone" dataKey="roas" name="ROAS" stroke="#16b8a6" strokeWidth={3} dot={false} />
        <Line yAxisId="acos" type="monotone" dataKey="acos" name="ACOS" stroke="#f59e0b" strokeWidth={2.5} strokeDasharray="4 3" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export function BarToko({
  data,
  dataKey = "pesanan",
  rupiah = false,
  warna = "#ee4d2d",
  suffix = " pesanan",
}: {
  data: Record<string, string | number>[];
  dataKey?: string;
  rupiah?: boolean;
  warna?: string;
  suffix?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <XAxis type="number" tick={{ fontSize: 11, fill: "#9aa0b2" }} axisLine={false} tickLine={false} tickFormatter={(v) => (rupiah ? rpShort(v) : num(v))} />
        <YAxis type="category" dataKey="toko" tick={{ fontSize: 11, fill: "#6b7180" }} axisLine={false} tickLine={false} width={120} />
        <Tooltip formatter={(v) => (rupiah ? rpShort(v) : num(v) + suffix)} contentStyle={tip} cursor={{ fill: "#f6f7fb" }} />
        <Bar dataKey={dataKey} fill={warna} radius={[0, 8, 8, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  );
}
