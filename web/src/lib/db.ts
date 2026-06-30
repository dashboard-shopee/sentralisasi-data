import { Pool } from "pg";

// Pool global (hindari bikin pool baru tiap hot-reload di dev).
const g = globalThis as unknown as { _pool?: Pool };
export const pool: Pool =
  g._pool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
    max: 1, // Batasi 1 koneksi per container serverless
    idleTimeoutMillis: 1000, // Tutup koneksi idle dalam 1 detik untuk menghemat limit DB
    connectionTimeoutMillis: 5000, // Fail fast jika koneksi penuh
  });
if (!g._pool) g._pool = pool;

export async function q<T = Record<string, unknown>>(
  sql: string,
  params: unknown[] = []
): Promise<T[]> {
  const r = await pool.query(sql, params);
  return r.rows as T[];
}
