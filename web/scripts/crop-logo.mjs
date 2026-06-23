import sharp from "sharp";
import { fileURLToPath } from "url";

const root = new URL("../../", import.meta.url);
const src = fileURLToPath(new URL("logo.jpeg", root));
const pub = (n) => fileURLToPath(new URL("web/public/" + n, root));

// Logo penuh (mark + teks): trim background -> ngepas
await sharp(src).trim({ threshold: 14 }).png().toFile(pub("syntra-logo.png"));

// Mark saja: extract region atas (tanpa teks). Lalu trim di instance terpisah.
const markBuf = await sharp(src).extract({ left: 330, top: 205, width: 375, height: 415 }).png().toBuffer();
await sharp(markBuf).trim({ threshold: 14 }).png().toFile(pub("syntra-mark.png"));

const a = await sharp(pub("syntra-mark.png")).metadata();
const b = await sharp(pub("syntra-logo.png")).metadata();
console.log("syntra-mark.png:", a.width + "x" + a.height);
console.log("syntra-logo.png:", b.width + "x" + b.height);
