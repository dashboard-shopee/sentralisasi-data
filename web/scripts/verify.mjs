import { readFileSync } from "fs";
import pg from "pg";

const env = readFileSync(new URL("../.env.local", import.meta.url), "utf8");
const get = (k) => (env.match(new RegExp("^" + k + "=(.+)$", "m"))?.[1] || "").trim().replace(/^["']|["']$/g, "");
const url = get("DATABASE_URL");
const pass = get("DASH_PASSWORD");
const BASE = "http://localhost:3000";

const c = new pg.Client({ connectionString: url, ssl: { rejectUnauthorized: false } });
await c.connect();
const r = await c.query("select distinct periode_mulai from fact_penjualan where periode='harian' order by periode_mulai desc limit 7");
await c.end();
const days = r.rows.map((x) => new Date(x.periode_mulai).toISOString());
const s = days[0], d = days[days.length - 1];
console.log("range 7 hari:", d.slice(0, 10), "→", s.slice(0, 10), `(${days.length} hari)`);

// login -> cookie
const lr = await fetch(`${BASE}/api/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password: pass }) });
const cookie = (lr.headers.get("set-cookie") || "").split(";")[0];
console.log("login:", lr.status, cookie ? "(cookie ok)" : "(NO COOKIE)");

async function api(qs) {
  const res = await fetch(`${BASE}/api/produk?${qs}`, { headers: { cookie } });
  return res;
}
const j = async (qs) => (await api(qs)).json();

const base = `g=harian&d=${encodeURIComponent(d)}&s=${encodeURIComponent(s)}`;
let x = await j(`kind=jual&${base}&page=1&size=3&sort=omzet&dir=desc`);
console.log("\nJUAL omzet desc -> total:", x.total, "| top:", x.rows[0]?.produk?.slice(0, 35), "omzet", x.rows[0]?.omzet, "konv", x.rows[0]?.konversi?.toFixed(2), "skuInduk", JSON.stringify(x.rows[0]?.skuInduk));
let x2 = await j(`kind=jual&${base}&page=2&size=3&sort=omzet&dir=desc`);
console.log("JUAL page2 -> first:", x2.rows[0]?.produk?.slice(0, 35), "omzet", x2.rows[0]?.omzet, "(harus < top page1)");
let x3 = await j(`kind=jual&${base}&page=1&size=3&sort=pesanan&dir=asc`);
console.log("JUAL pesanan asc -> first pesanan:", x3.rows[0]?.pesanan);
let x4 = await j(`kind=jual&${base}&page=1&size=5&sort=omzet&dir=desc&q=topi`);
console.log("JUAL search 'topi' -> total:", x4.total, "| contoh:", x4.rows[0]?.produk?.slice(0, 40));
let x5 = await j(`kind=iklan&${base}&page=1&size=3&sort=omzetIklan&dir=desc`);
console.log("\nIKLAN omzet desc -> total:", x5.total, "| top:", x5.rows[0]?.produk?.slice(0, 35), "roas", x5.rows[0]?.roas?.toFixed(2), "ctr", x5.rows[0]?.ctr?.toFixed(2));
const csv = await (await api(`kind=jual&${base}&download=csv&sort=omzet&dir=desc`)).text();
console.log("\nCSV head:", csv.split("\n").slice(0, 2).join(" || ").slice(0, 160));
console.log("CSV baris:", csv.split("\n").length - 1);
