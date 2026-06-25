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
    <div className="card p-4 sm:p-5 min-w-0" title={label}>
      <div
        className="w-10 h-10 sm:w-11 sm:h-11 rounded-2xl grid place-items-center text-[16px] sm:text-[18px] mb-2.5 sm:mb-3"
        style={{ background: tint }}
      >
        {ikon}
      </div>
      <div className="text-[12px] sm:text-[13px] text-[#8a90a2] font-medium truncate" title={label}>
        {label}
      </div>
      <div 
        className="text-[19px] min-[360px]:text-[21px] min-[400px]:text-[23px] sm:text-[26px] font-extrabold tracking-tight mt-1 leading-none truncate" 
        title={value}
      >
        {value}
      </div>
      {sub ? (
        <div 
          className="text-[10px] sm:text-[12px] mt-1.5 font-semibold truncate" 
          style={{ color }}
          title={sub}
        >
          {sub}
        </div>
      ) : null}
    </div>
  );
}

