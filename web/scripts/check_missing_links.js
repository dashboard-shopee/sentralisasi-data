const { Client } = require('pg');

async function main() {
  const client = new Client({
    connectionString: "postgresql://postgres.peuasqcjmlzdybnqmqes:%23EL7w3B%2C8WRbsSF@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?pgbouncer=true",
    ssl: { rejectUnauthorized: false }
  });
  
  await client.connect();

  console.log("=== Checking dim_produk for Kimmio 51209166018 ===");
  const res1 = await client.query("select * from dim_produk where produk_id = 51209166018 or produk_id = '51209166018'");
  console.log(res1.rows);

  console.log("=== Checking dim_produk where sku_induk contains AKS28 ===");
  const res2 = await client.query("select * from dim_produk where sku_induk iLike '%AKS28%' limit 5");
  console.log(res2.rows);

  console.log("=== Checking riset_kompetitor_detail for AKS28 ===");
  const res3 = await client.query("select id, produk_acuan_id, tipe, url from riset_kompetitor_detail where produk_acuan_id in (select id from riset_produk_acuan where sku iLike '%AKS28%') and tipe = 'manual'");
  console.log(res3.rows);

  await client.end();
}

main().catch(console.error);
