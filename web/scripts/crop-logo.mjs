import sharp from "sharp";
import { fileURLToPath } from "url";

const root = new URL("../../", import.meta.url);
const src = fileURLToPath(new URL("logo.jpeg", root));
const pub = (n) => fileURLToPath(new URL("web/public/" + n, root));

// 1) Key-out background near-white -> transparan
const { data, info } = await sharp(src).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
for (let i = 0; i < info.width * info.height; i++) {
  const o = i * 4;
  if (data[o] > 225 && data[o + 1] > 225 && data[o + 2] > 225) data[o + 3] = 0;
}
const keyed = await sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer();

// 2) Logo penuh (mark + teks) -> trim transparan
await sharp(keyed).trim().png().toFile(pub("syntra-logo.png"));
// 3) Mark saja -> extract lalu trim
const mk = await sharp(keyed).extract({ left: 330, top: 205, width: 375, height: 415 }).png().toBuffer();
await sharp(mk).trim().png().toFile(pub("syntra-mark.png"));

const a = await sharp(pub("syntra-mark.png")).metadata();
const b = await sharp(pub("syntra-logo.png")).metadata();
console.log("mark:", a.width + "x" + a.height, "| logo:", b.width + "x" + b.height, "| transparan ✓");
