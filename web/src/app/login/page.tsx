"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Login() {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(false);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(false);
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    setLoading(false);
    if (r.ok) {
      router.replace("/");
      router.refresh();
    } else {
      setErr(true);
    }
  }

  return (
    <div className="fixed inset-0 grid place-items-center px-4" style={{ background: "var(--bg)" }}>
      <form onSubmit={submit} className="card p-7 w-full max-w-[360px]">
        <div className="flex flex-col items-center text-center mb-6">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/syntra-logo.png" alt="SYNTRA — System Centralized" className="h-20 w-auto" />
          <div className="text-[11px] text-[#9aa0b2] mt-2">System Centralized · masuk untuk lanjut</div>
        </div>

        <label className="text-[13px] font-medium text-[#6b7180]">Password</label>
        <input
          type="password"
          autoFocus
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="Masukkan password"
          className={"mt-1.5 w-full border rounded-xl px-3 py-2.5 text-[14px] outline-none " + (err ? "border-[#ec407a]" : "border-[#e6e9f0] focus:border-[#ee4d2d]")}
        />
        {err && <div className="text-[12px] text-[#ec407a] mt-2">Password salah, coba lagi.</div>}

        <button
          type="submit"
          disabled={loading || !pw}
          className="mt-5 w-full py-2.5 rounded-xl text-white font-semibold text-[14px] disabled:opacity-50"
          style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
        >
          {loading ? "Memeriksa…" : "Masuk"}
        </button>
      </form>
    </div>
  );
}
