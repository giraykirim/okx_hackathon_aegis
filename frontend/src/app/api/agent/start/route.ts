import { NextResponse } from "next/server";
import { fetchBackendJson, isAdminAuthorized } from "@/lib/server-backend";
import type { ControlState } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const auth = isAdminAuthorized(request);
  if (!auth.authorized) {
    return NextResponse.json({ detail: auth.reason }, { status: auth.statusCode });
  }

  const token = process.env.AEGIS_CONTROL_TOKEN!;
  const res = await fetchBackendJson<ControlState>("/api/agent/start", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    timeoutMs: 8000,
  });

  if (!res.ok || !res.data) {
    return NextResponse.json(
      { detail: res.error || "Failed to start agent on backend" },
      { status: res.status || 503 }
    );
  }

  return NextResponse.json(res.data);
}
