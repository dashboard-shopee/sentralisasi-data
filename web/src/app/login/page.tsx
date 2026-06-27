"use client";

import { useState } from "react";

export default function Login() {
  const [pw, setPw] = useState("");
  const [otp, setOtp] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [showOtpInput, setShowOtpInput] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    
    try {
      const r = await fetch("/api/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password: pw }),
      });
      const data = await r.json();

      if (r.ok) {
        if (data.requiresOtp) {
          setShowOtpInput(true);
          setErr("");
        } else {
          // Staf biasa langsung login, reload halaman
          window.location.href = "/";
        }
      } else {
        setErr(data.error || "Password salah, coba lagi.");
      }
    } catch (ex) {
      setErr("Gagal menghubungkan ke server.");
    } finally {
      setLoading(false);
    }
  }

  async function submitOtp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");

    try {
      const r = await fetch("/api/login/verify-otp", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ otp: otp }),
      });
      const data = await r.json();

      if (r.ok) {
        // Owner terverifikasi, reload halaman
        window.location.href = "/";
      } else {
        setErr(data.error || "Kode OTP salah atau telah kadaluwarsa.");
      }
    } catch (ex) {
      setErr("Gagal menghubungi server untuk verifikasi.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 grid place-items-center px-4" style={{ background: "var(--bg)" }}>
      <div className="card p-7 w-full max-w-[360px]">
        <div className="flex flex-col items-center text-center mb-6">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/syntra-logo.png" alt="SYNTRA — System Centralized" className="h-20 w-auto" />
          <div className="text-[11px] text-[#9aa0b2] mt-2">System Centralized · masuk untuk lanjut</div>
        </div>

        {!showOtpInput ? (
          // FORM PASSWORD UTAMA
          <form onSubmit={submitPassword}>
            <label className="text-[13px] font-medium text-[#6b7180]">Password</label>
            <div className="relative mt-1.5">
              <input
                type={showPw ? "text" : "password"}
                autoFocus
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder="Masukkan password"
                className={"w-full border rounded-xl pl-3 pr-11 py-2.5 text-[14px] outline-none " + (err ? "border-[#ec407a]" : "border-[#e6e9f0] focus:border-[#ee4d2d]")}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                aria-label={showPw ? "Sembunyikan password" : "Lihat password"}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[18px] px-1 text-[#9aa0b2] hover:text-[#6b7180]"
              >
                {showPw ? "🙈" : "👁️"}
              </button>
            </div>
            
            {err && <div className="text-[12px] text-[#ec407a] mt-2">{err}</div>}

            <button
              type="submit"
              disabled={loading || !pw}
              className="mt-5 w-full py-2.5 rounded-xl text-white font-semibold text-[14px] disabled:opacity-50 cursor-pointer"
              style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
            >
              {loading ? "Memeriksa…" : "Masuk"}
            </button>
          </form>
        ) : (
          // FORM OTP 2FA (WhatsApp)
          <form onSubmit={submitOtp}>
            <div className="text-center mb-4">
              <div className="text-[14px] font-semibold text-[#3a3f4d]">Verifikasi Dua Langkah</div>
              <div className="text-[11.5px] text-[#6b7180] mt-1">
                Masukkan 6 digit kode OTP yang telah dikirim ke WhatsApp <span className="font-semibold">0821-1441-7314</span>.
              </div>
            </div>

            <label className="text-[13px] font-medium text-[#6b7180]">Kode OTP</label>
            <input
              type="text"
              pattern="[0-9]*"
              inputMode="numeric"
              maxLength={6}
              autoFocus
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder="Masukkan 6 digit OTP"
              className={"w-full border rounded-xl px-3 py-2.5 text-center tracking-[0.25em] text-[18px] font-bold outline-none mt-1.5 " + (err ? "border-[#ec407a]" : "border-[#e6e9f0] focus:border-[#ee4d2d]")}
            />

            {err && <div className="text-[12px] text-[#ec407a] mt-2 text-center">{err}</div>}

            <button
              type="submit"
              disabled={loading || otp.length !== 6}
              className="mt-5 w-full py-2.5 rounded-xl text-white font-semibold text-[14px] disabled:opacity-50 cursor-pointer"
              style={{ background: "linear-gradient(135deg,#ee4d2d,#ff7043)" }}
            >
              {loading ? "Memverifikasi…" : "Verifikasi & Masuk"}
            </button>

            <button
              type="button"
              onClick={() => {
                setShowOtpInput(false);
                setOtp("");
                setErr("");
              }}
              className="mt-3 w-full py-2 rounded-xl text-[#6b7180] hover:bg-[#f6f7fb] text-[13px] font-medium transition-all"
            >
              Kembali
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
