import nodemailer from "nodemailer";

export async function sendOtpEmail(to: string, otp: string): Promise<boolean> {
  const host = process.env.SMTP_HOST || "smtp.gmail.com";
  const port = Number(process.env.SMTP_PORT || 465);
  const secure = process.env.SMTP_SECURE !== "false"; // default true (SSL)
  const user = (process.env.SMTP_USER || "").trim();
  const pass = (process.env.SMTP_PASS || "").trim();

  if (!user || !pass) {
    console.warn(`\n==================================================\n[EMAIL OTP BYPASS] SMTP_USER or SMTP_PASS not configured.\nOTP Code: "${otp}"\n==================================================\n`);
    return false;
  }

  const transporter = nodemailer.createTransport({
    host,
    port,
    secure,
    auth: {
      user,
      pass,
    },
  });

  try {
    await transporter.sendMail({
      from: process.env.EMAIL_FROM || `"SYNTRA Security" <${user}>`,
      to,
      subject: `[SYNTRA] Kode OTP Login Owner`,
      text: `Kode OTP Anda untuk login sebagai Owner adalah: ${otp}. Kode berlaku selama 5 menit.`,
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #eef0f6; border-radius: 12px;">
          <h2 style="color: #ee4d2d; text-align: center; margin-bottom: 20px;">Verifikasi Keamanan SYNTRA</h2>
          <p style="font-size: 14px; color: #3a3f4d; line-height: 1.6;">
            Halo Owner,
          </p>
          <p style="font-size: 14px; color: #3a3f4d; line-height: 1.6;">
            Berikut adalah kode OTP Anda untuk melakukan verifikasi masuk sebagai <strong>Owner</strong>:
          </p>
          <div style="background-color: #fff1ed; border: 1px solid #ffccbc; border-radius: 8px; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; color: #ee4d2d; letter-spacing: 0.15em; margin: 20px 0;">
            ${otp}
          </div>
          <p style="font-size: 11px; color: #9aa0b2; text-align: center; margin-top: 20px;">
            Kode OTP ini berlaku selama 5 menit. Jangan bagikan kode ini kepada siapa pun.
          </p>
        </div>
      `,
    });
    console.log(`[EMAIL OTP SENT] Successfully sent OTP to ${to}`);
    return true;
  } catch (err) {
    console.error("[EMAIL OTP ERROR] Failed to send email via SMTP:", err);
    return false;
  }
}
