import { Pool } from "pg";

// Pool global (hindari bikin pool baru tiap hot-reload di dev).
const g = globalThis as unknown as { _pool?: Pool };
export const pool: Pool =
  g._pool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    max: 3,                        // Transaction mode bisa handle banyak koneksi bersamaan
    idleTimeoutMillis: 500,        // Lepas idle cepat di serverless
    connectionTimeoutMillis: 5000, // Fail fast jika koneksi bermasalah
  });
if (!g._pool) g._pool = pool;

export async function q<T = Record<string, unknown>>(
  sql: string,
  params: unknown[] = []
): Promise<T[]> {
  const r = await pool.query(sql, params);
  return r.rows as T[];
}
