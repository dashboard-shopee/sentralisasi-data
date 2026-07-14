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
  multiple?: boolean;
}

export default function CustomSelect({
  value,
  onChange,
  options,
  placeholder = "Semua Toko",
  size = "md",
  multiple = false,
}: CustomSelectProps) {
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

  // Parse comma-separated selected values
  const selectedValues = value ? value.split(",").filter(Boolean) : [];
  const isSm = size === "sm";

  // Label display logic
  let labelText = placeholder;
  if (!multiple) {
    const selectedOption = options.find((opt) => opt.value === value);
    if (selectedOption) labelText = selectedOption.label;
  } else {
    if (selectedValues.length === 1) {
      const opt = options.find((o) => o.value === selectedValues[0]);
      if (opt) labelText = opt.label;
    } else if (selectedValues.length > 1) {
      labelText = `${selectedValues.length} Toko Terpilih`;
    }
  }

  const handleSelect = (optValue: string) => {
    if (!multiple) {
      onChange(optValue);
      setIsOpen(false);
    } else {
      let nextValues: string[];
      if (optValue === "") {
        // Klik "Semua Toko" -> kosongkan (semua terpilih)
        nextValues = [];
      } else {
        if (selectedValues.includes(optValue)) {
          nextValues = selectedValues.filter((v) => v !== optValue);
        } else {
          nextValues = [...selectedValues, optValue];
        }
      }
      
      // Jika semua opsi terpilih secara manual, kosongkan juga (kembali ke "Semua Toko")
      if (nextValues.length === options.length) {
        nextValues = [];
      }
      
      onChange(nextValues.join(","));
    }
  };

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
        <span className="truncate">{labelText}</span>
        <span className={`text-[#8a90a2] transition-transform duration-200 ${isOpen ? "rotate-180" : ""} ${isSm ? "text-[8px]" : "text-[9px]"}`}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-1.5 w-full min-w-[190px] max-h-[280px] overflow-y-auto bg-white border border-[#eef0f6] rounded-2xl shadow-[0_12px_40px_rgba(0,0,0,0.08)] py-1.5 z-[100]">
          {/* Opsi "Semua Toko / Semua" di bagian paling atas */}
          <button
            type="button"
            onClick={() => handleSelect("")}
            className={
              "w-full text-left px-3.5 py-2 text-[12.5px] font-medium transition-colors cursor-pointer flex items-center gap-2.5 min-w-0 " +
              (selectedValues.length === 0
                ? "text-[#ee4d2d] bg-[#fff1ed]"
                : "text-[#4b5563] hover:bg-[#f6f7fb] hover:text-[#ee4d2d]")
            }
          >
            {multiple && (
              <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-all shrink-0 ${
                selectedValues.length === 0 
                  ? "bg-[#ee4d2d] border-[#ee4d2d] text-white" 
                  : "border-[#d8dce6] bg-white"
              }`}>
                {selectedValues.length === 0 && (
                  <svg className="w-2 h-2 fill-current" viewBox="0 0 20 20">
                    <path d="M0 11l2-2 5 5L18 3l2 2L7 18z" />
                  </svg>
                )}
              </div>
            )}
            <span className="truncate min-w-0">{placeholder}</span>
          </button>

          {/* Opsi Toko */}
          {options.map((opt) => {
            const isSelected = selectedValues.includes(opt.value);
            const active = !multiple ? opt.value === value : isSelected;
            
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleSelect(opt.value)}
                className={
                  "w-full text-left px-3.5 py-2 text-[12.5px] font-medium transition-colors cursor-pointer flex items-center gap-2.5 min-w-0 " +
                  (active ? "text-[#ee4d2d] bg-[#fff1ed]" : "text-[#4b5563] hover:bg-[#f6f7fb] hover:text-[#ee4d2d]")
                }
              >
                {multiple && (
                  <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-all shrink-0 ${
                    isSelected 
                      ? "bg-[#ee4d2d] border-[#ee4d2d] text-white" 
                      : "border-[#d8dce6] bg-white"
                  }`}>
                    {isSelected && (
                      <svg className="w-2 h-2 fill-current" viewBox="0 0 20 20">
                        <path d="M0 11l2-2 5 5L18 3l2 2L7 18z" />
                      </svg>
                    )}
                  </div>
                )}
                <span className="truncate min-w-0">{opt.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
