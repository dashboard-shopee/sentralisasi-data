import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { verifySession } from "@/lib/auth";
import { q } from "@/lib/db";
import { TABS_BY_PAGE } from "@/lib/permissions";

// Bersihin input allowed_tabs dari client: cuma terima key & value yang valid,
// default ke "semua tab" (page) kalau key tidak ada / bukan array.
function sanitizeAllowedTabs(raw: any): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const page of Object.keys(TABS_BY_PAGE)) {
    const val = raw && Array.isArray(raw[page]) ? raw[page] : null;
    out[page] = val ? val.filter((t: string) => TABS_BY_PAGE[page].includes(t)) : [...TABS_BY_PAGE[page]];
  }
  return out;
}

// Helper untuk verifikasi hak akses Owner
async function verifyOwner() {
  const cookieStore = await cookies();
  const token = cookieStore.get("dash_auth")?.value;
  if (!token) return null;

  const secret = process.env.JWT_SECRET || "syntra_jwt_secret_key_2026_marketing_shopee";
  const user = await verifySession(token, secret);
  if (user && user.role === "owner") {
    return user;
  }
  return null;
}

// 1. GET: Ambil daftar seluruh user (Owner only)
export async function GET() {
  const owner = await verifyOwner();
  if (!owner) {
    return NextResponse.json({ ok: false, error: "Akses ditolak" }, { status: 403 });
  }

  try {
    const users = await q(
      "select id, username, password, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_net_price, can_view_margin, can_view_hpp, can_view_harga_jual_komisi, allowed_tabs, avatar_emoji, session_duration_days from dashboard_user order by id asc"
    );

    // Parse allowed_menus/allowed_tabs dari string jika disimpan sebagai string JSON di DB
    const parsedUsers = users.map((u: any) => ({
      ...u,
      allowed_menus: typeof u.allowed_menus === "string" ? JSON.parse(u.allowed_menus) : u.allowed_menus,
      allowed_tabs: sanitizeAllowedTabs(typeof u.allowed_tabs === "string" ? JSON.parse(u.allowed_tabs) : u.allowed_tabs),
    }));

    return NextResponse.json({ ok: true, users: parsedUsers });
  } catch (err: any) {
    console.error("GET Users Error:", err);
    return NextResponse.json({ ok: false, error: "Gagal mengambil data user" }, { status: 500 });
  }
}

// 2. POST: Tambah user baru (Owner only)
export async function POST(req: Request) {
  const owner = await verifyOwner();
  if (!owner) {
    return NextResponse.json({ ok: false, error: "Akses ditolak" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const { username, password, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_net_price, can_view_margin, can_view_hpp, can_view_harga_jual_komisi, allowed_tabs, avatar_emoji, session_duration_days } = body;

    if (!username || !password) {
      return NextResponse.json({ ok: false, error: "Username dan password wajib diisi" }, { status: 400 });
    }

    // Cek jika username sudah terpakai
    const checkRes = await q("select id from dashboard_user where username = $1 or password = $2", [username, password]);
    if (checkRes.length > 0) {
      return NextResponse.json({ ok: false, error: "Username atau password sudah digunakan pengguna lain" }, { status: 400 });
    }

    // Insert user
    await q(
      `insert into dashboard_user (username, password, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_net_price, can_view_margin, can_view_hpp, can_view_harga_jual_komisi, allowed_tabs, avatar_emoji, session_duration_days)
       values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)`,
      [
        username.trim(),
        password.trim(),
        JSON.stringify(allowed_menus || []),
        !!can_edit_ads,
        !!can_edit_competitor,
        !!can_edit_harga,
        !!can_edit_komisi,
        !!can_edit_kalkulator,
        can_view_net_price !== false,
        can_view_margin !== false,
        can_view_hpp !== false,
        can_view_harga_jual_komisi !== false,
        JSON.stringify(sanitizeAllowedTabs(allowed_tabs)),
        avatar_emoji ? avatar_emoji.trim() : null,
        Number(session_duration_days || 7)
      ]
    );

    return NextResponse.json({ ok: true, message: "User berhasil dibuat!" });
  } catch (err: any) {
    console.error("POST User Error:", err);
    return NextResponse.json({ ok: false, error: "Gagal membuat user baru" }, { status: 500 });
  }
}

// 3. PUT: Edit user (Owner only)
export async function PUT(req: Request) {
  const owner = await verifyOwner();
  if (!owner) {
    return NextResponse.json({ ok: false, error: "Akses ditolak" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const { id, username, password, allowed_menus, can_edit_ads, can_edit_competitor, can_edit_harga, can_edit_komisi, can_edit_kalkulator, can_view_net_price, can_view_margin, can_view_hpp, can_view_harga_jual_komisi, allowed_tabs, avatar_emoji, session_duration_days } = body;

    if (!id || !username || !password) {
      return NextResponse.json({ ok: false, error: "ID, username, dan password wajib diisi" }, { status: 400 });
    }

    // Ambil data user yang mau di-edit
    const checkUser = await q<any>("select username from dashboard_user where id = $1", [id]);
    if (checkUser.length === 0) {
      return NextResponse.json({ ok: false, error: "User tidak ditemukan" }, { status: 404 });
    }

    const currentUsername = checkUser[0].username;

    // Proteksi: Nama 'Owner' tidak boleh diubah untuk menghindari hilangnya superuser
    if (currentUsername === "Owner" && username.trim() !== "Owner") {
      return NextResponse.json({ ok: false, error: "Nama akun Owner tidak boleh diubah" }, { status: 400 });
    }

    const isOwner = currentUsername === "Owner";
    const fullTabs: Record<string, string[]> = {};
    for (const page of Object.keys(TABS_BY_PAGE)) fullTabs[page] = [...TABS_BY_PAGE[page]];

    // Update data
    await q(
      `update dashboard_user
       set username = $1, password = $2, allowed_menus = $3, can_edit_ads = $4, can_edit_competitor = $5, can_edit_harga = $6, can_edit_komisi = $7, can_edit_kalkulator = $8, can_view_net_price = $9, can_view_margin = $10, can_view_hpp = $11, can_view_harga_jual_komisi = $12, allowed_tabs = $13, avatar_emoji = $14, session_duration_days = $15
       where id = $16`,
      [
        username.trim(),
        password.trim(),
        JSON.stringify(allowed_menus || []),
        isOwner ? true : !!can_edit_ads,
        isOwner ? true : !!can_edit_competitor,
        isOwner ? true : !!can_edit_harga,
        isOwner ? true : !!can_edit_komisi,
        isOwner ? true : !!can_edit_kalkulator,
        isOwner ? true : can_view_net_price !== false,
        isOwner ? true : can_view_margin !== false,
        isOwner ? true : can_view_hpp !== false,
        isOwner ? true : can_view_harga_jual_komisi !== false,
        JSON.stringify(isOwner ? fullTabs : sanitizeAllowedTabs(allowed_tabs)),
        avatar_emoji ? avatar_emoji.trim() : null,
        Number(session_duration_days || 30),
        id
      ]
    );

    return NextResponse.json({ ok: true, message: "User berhasil diperbarui!" });
  } catch (err: any) {
    console.error("PUT User Error:", err);
    return NextResponse.json({ ok: false, error: "Gagal mengupdate user" }, { status: 500 });
  }
}

// 4. DELETE: Hapus user (Owner only)
export async function DELETE(req: Request) {
  const owner = await verifyOwner();
  if (!owner) {
    return NextResponse.json({ ok: false, error: "Akses ditolak" }, { status: 403 });
  }

  try {
    const { searchParams } = new URL(req.url);
    const id = searchParams.get("id");

    if (!id) {
      return NextResponse.json({ ok: false, error: "ID user wajib diisi" }, { status: 400 });
    }

    // Cek jika mencoba menghapus Owner
    const checkUser = await q<any>("select username from dashboard_user where id = $1", [id]);
    if (checkUser.length > 0 && checkUser[0].username === "Owner") {
      return NextResponse.json({ ok: false, error: "Akun Owner utama tidak boleh dihapus!" }, { status: 400 });
    }

    await q("delete from dashboard_user where id = $1", [id]);
    return NextResponse.json({ ok: true, message: "User berhasil dihapus!" });
  } catch (err: any) {
    console.error("DELETE User Error:", err);
    return NextResponse.json({ ok: false, error: "Gagal menghapus user" }, { status: 500 });
  }
}
