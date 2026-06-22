"use client";

import { useEffect, useState } from "react";
import type { VarDef } from "@/lib/variables";
import { fmtVal } from "@/lib/variables";
import KpiCard from "./KpiCard";
import VarMenu from "./VarMenu";
import { FlexChart } from "./charts";

function useStored(key: string, def: string[]) {
  const [v, setV] = useState<string[]>(def);
  useEffect(() => {
    try {
      const s = localStorage.getItem(key);
      if (s) setV(JSON.parse(s));
    } catch {}
  }, [key]);
  const set = (x: string[]) => {
    setV(x);
    try {
      localStorage.setItem(key, JSON.stringify(x));
    } catch {}
  };
  return [v, set] as const;
}

const TINT = ["#fff1ed", "#eaf2fe", "#e7f7f4", "#f3eefe"];
const COLOR = ["#ee4d2d", "#42a5f5", "#16b8a6", "#7e57c2"];

export default function MetricView({
  catalog,
  kpi,
  trend,
  storageKey,
  defaultKpi,
  defaultChart,
}: {
  catalog: VarDef[];
  kpi: Record<string, number>;
  trend: Record<string, number | string>[];
  storageKey: string;
  defaultKpi: string[];
  defaultChart: string[];
}) {
  const [kpiSel, setKpiSel] = useStored(storageKey + ":kpi", defaultKpi);
  const [chartSel, setChartSel] = useStored(storageKey + ":chart", defaultChart);
  const byKey = (k: string) => catalog.find((c) => c.key === k);

  return (
    <>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[14px] font-bold text-[#6b7180]">Ringkasan Angka</h2>
        <VarMenu all={catalog} selected={kpiSel} onChange={setKpiSel} max={4} label="Atur KPI" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {kpiSel.map((k, i) => {
          const v = byKey(k);
          if (!v) return null;
          return <KpiCard key={k} ikon={v.ikon} label={v.label} value={fmtVal(kpi[k] ?? 0, v.fmt)} tint={TINT[i % 4]} color={COLOR[i % 4]} />;
        })}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-bold text-[15px]">Grafik Tren</h2>
          <VarMenu all={catalog} selected={chartSel} onChange={setChartSel} max={4} label="Atur Grafik" />
        </div>
        <FlexChart data={trend} series={chartSel.map(byKey).filter(Boolean) as VarDef[]} />
      </div>
    </>
  );
}
