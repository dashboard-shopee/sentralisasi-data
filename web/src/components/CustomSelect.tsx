"use client";

import { useState, useEffect, useRef } from "react";

interface Option {
  value: string;
  label: string;
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  size?: "sm" | "md";
}

export default function CustomSelect({ value, onChange, options, placeholder = "Semua Toko", size = "md" }: CustomSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const selectedOption = options.find((opt) => opt.value === value);
  const isSm = size === "sm";

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={
          "flex items-center justify-between gap-3 bg-white border border-[#eef0f6] rounded-xl outline-none focus:border-[#ee4d2d] focus:ring-2 focus:ring-[#ee4d2d]/10 transition-all hover:border-[#ee4d2d]/30 cursor-pointer select-none text-left " +
          (isSm 
            ? "px-3 py-1 text-[12px] font-semibold text-[#4b5563] min-w-[130px]" 
            : "px-3.5 py-1.5 text-[13px] font-semibold text-[#3a3f4d] min-w-[150px]")
        }
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <span className={`text-[#8a90a2] transition-transform duration-200 ${isOpen ? "rotate-180" : ""} ${isSm ? "text-[8px]" : "text-[9px]"}`}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-1.5 w-full min-w-[180px] max-h-[260px] overflow-y-auto bg-white border border-[#eef0f6] rounded-2xl shadow-[0_12px_40px_rgba(0,0,0,0.08)] py-1.5 z-[100]">
          {options.map((opt) => {
            const active = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                className={
                  "w-full text-left px-3.5 py-2 text-[12.5px] font-medium transition-colors cursor-pointer block truncate " +
                  (active ? "text-[#ee4d2d] bg-[#fff1ed]" : "text-[#4b5563] hover:bg-[#f6f7fb] hover:text-[#ee4d2d]")
                }
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
