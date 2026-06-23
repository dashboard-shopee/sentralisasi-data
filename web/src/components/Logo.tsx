// Logo SYNTRA — mark "S" geometris (interlock) warna oranye.
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-label="SYNTRA">
      <g transform="translate(8,0) skewX(-9)" fill="#f1592a">
        <rect x="14" y="20" width="64" height="16" rx="3" />
        <rect x="14" y="20" width="16" height="36" rx="3" />
        <rect x="14" y="42" width="64" height="16" rx="3" />
        <rect x="62" y="42" width="16" height="36" rx="3" />
        <rect x="14" y="64" width="64" height="16" rx="3" />
      </g>
    </svg>
  );
}
