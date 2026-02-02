#!/usr/bin/env node
'use strict';
const path = require('path');
try {
  require('dotenv').config({ path: path.join(__dirname, '..', '..', '.env') });
} catch (_) {}
const { Pool } = require('pg');
const fs = require('fs');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://localhost:5432/accounting',
  ssl: process.env.DATABASE_URL && process.env.DATABASE_URL.indexOf('localhost') === -1
    ? { rejectUnauthorized: false }
    : false,
});

async function main() {
  const schemaPath = path.join(__dirname, '..', 'src', 'schema.sql');
  const sql = fs.readFileSync(schemaPath, 'utf8');
  const client = await pool.connect();
  try {
    await client.query(sql);
    console.log('[init-db] Schema applied.');
    await client.query(`
      INSERT INTO fiscal_years (year, start_date, end_date, closed)
      VALUES (2026, '2026-01-01', '2026-12-31', FALSE)
      ON CONFLICT (year) DO NOTHING;
    `);
    console.log('[init-db] Fiscal year 2026 ensured.');
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((e) => {
  console.error('[init-db] Error:', e.message);
  process.exit(1);
});
