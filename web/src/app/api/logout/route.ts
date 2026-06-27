import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST() {
  const cookieStore = await cookies();
  
  // Hapus cookie auth
  cookieStore.delete("dash_auth");
  
  return NextResponse.json({ ok: true, message: "Logged out successfully" });
}
