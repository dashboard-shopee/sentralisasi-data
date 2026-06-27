const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require("@whiskeysockets/baileys");
const qrcode = require("qrcode-terminal");
const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 5001;
const SECRET_TOKEN = process.env.GATEWAY_SECRET_TOKEN || "syntra_gateway_secret_2026";

let sock = null;
let isConnected = false;

// Format nomor HP Indonesia menjadi format WhatsApp JID (628xxxxxxxx@s.whatsapp.net)
function formatJid(phone) {
  let clean = phone.replace(/[^0-9]/g, "");
  if (clean.startsWith("0")) {
    clean = "62" + clean.slice(1);
  }
  return `${clean}@s.whatsapp.net`;
}

// Inisialisasi koneksi Baileys WhatsApp
async function connectToWhatsApp() {
  console.log("Menghubungkan ke WhatsApp...");
  const { state, saveCreds } = await useMultiFileAuthState("auth_info_baileys");
  
  sock = makeWASocket({
    auth: state,
    printQRInTerminal: true,
    browser: ["SYNTRA Gateway", "Chrome", "1.0.0"]
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n[!] SCAN QR CODE INI DENGAN WHATSAPP ANDA:\n");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "close") {
      const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
      console.log("Koneksi terputus karena:", lastDisconnect?.error || "koneksi ditutup");
      isConnected = false;
      
      if (shouldReconnect) {
        console.log("Mencoba menghubungkan kembali...");
        connectToWhatsApp();
      } else {
        console.log("Anda keluar (logged out). Silakan hapus folder 'auth_info_baileys' lalu restart untuk scan ulang.");
      }
    } else if (connection === "open") {
      console.log("\n==================================================");
      console.log("[+] WhatsApp Gateway BERHASIL TERHUBUNG!");
      console.log("==================================================\n");
      isConnected = true;
    }
  });
}

// Endpoint HTTP POST untuk mengirim OTP
app.post("/send-otp", async (req, res) => {
  const authHeader = req.headers["authorization"] || "";
  const token = authHeader.replace("Bearer ", "").trim();

  // Validasi Secret Token
  if (token !== SECRET_TOKEN) {
    return res.status(401).json({ error: "Unauthorized: Token tidak valid." });
  }

  const { target, message } = req.body;
  if (!target || !message) {
    return res.status(400).json({ error: "Target dan message wajib diisi." });
  }

  if (!isConnected || !sock) {
    return res.status(503).json({ error: "WhatsApp Gateway belum terhubung/siap." });
  }

  try {
    const jid = formatJid(target);
    console.log(`[HTTP POST] Mengirim OTP ke ${jid}...`);
    
    await sock.sendMessage(jid, { text: message });
    
    console.log(`[HTTP POST] OTP berhasil dikirim ke ${jid}`);
    return res.json({ success: true, message: "OTP berhasil dikirim!" });
  } catch (err) {
    console.error("Gagal mengirim pesan WhatsApp:", err);
    return res.status(500).json({ error: "Gagal mengirim pesan ke nomor tujuan.", detail: err.message });
  }
});

// Jalankan Server API & Mulai Koneksi WhatsApp
app.listen(PORT, () => {
  console.log(`[+] Server API Gateway berjalan di http://localhost:${PORT}`);
  connectToWhatsApp().catch(err => console.error("Koneksi Baileys Error:", err));
});
