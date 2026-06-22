export default function KpiCard({
  ikon,
  label,
  value,
  sub,
  tint = "#fff1ed",
  color = "#ee4d2d",
}: {
  ikon: string;
  label: string;
  value: string;
  sub?: string;
  tint?: string;
  color?: string;
}) {
  return (
    <div className="card p-5">
      <div
        className="w-11 h-11 rounded-2xl grid place-items-center text-[18px] mb-3"
        style={{ background: tint }}
      >
        {ikon}
      </div>
      <div className="text-[13px] text-[#8a90a2] font-medium">{label}</div>
      <div className="text-[26px] font-extrabold tracking-tight mt-0.5 leading-none">
        {value}
      </div>
      {sub ? (
        <div className="text-[12px] mt-1.5 font-semibold" style={{ color }}>
          {sub}
        </div>
      ) : null}
    </div>
  );
}
