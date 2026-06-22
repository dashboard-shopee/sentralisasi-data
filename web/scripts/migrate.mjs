import { readFileSync } from "fs";
import pg from "pg";

const env = readFileSync(new URL("../.env.local", import.meta.url), "utf8");
const url = env.match(/DATABASE_URL\s*=\s*(.+)/)[1].trim().replace(/^["']|["']$/g, "");
const c = new pg.Client({ connectionString: url, ssl: { rejectUnauthorized: false } });
await c.connect();
await c.query("alter table dim_produk add column if not exists sku text");
await c.query("alter table dim_produk add column if not exists sku_induk text");
const r = await c.query(
  "select column_name from information_schema.columns where table_name='dim_produk' order by ordinal_position"
);
console.log("dim_produk columns:", r.rows.map((x) => x.column_name).join(", "));
await c.end();
