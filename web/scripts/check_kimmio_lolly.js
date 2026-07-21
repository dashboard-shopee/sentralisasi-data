const { Client } = require('pg');

async function main() {
  const client = new Client({
    connectionString: "postgresql://postgres.peuasqcjmlzdybnqmqes:%23EL7w3B%2C8WRbsSF@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres?pgbouncer=true",
    ssl: { rejectUnauthorized: false }
  });
  
  await client.connect();
  const res = await client.query("select toko_id, nama, shopee_shop_id from dim_toko where toko_id in (1, 2)");
  console.log(res.rows);
  await client.end();
}

main().catch(console.error);
