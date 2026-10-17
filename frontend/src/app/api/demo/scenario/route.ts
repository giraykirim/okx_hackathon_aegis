import { NextResponse } from "next/server";
import { fetchBackendJson, isAdminAuthorized } from "@/lib/server-backend";
import type { Decision } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const auth = isAdminAuthorized(request);
  if (!auth.authorized) {
    return NextResponse.json({ detail: auth.reason }, { status: auth.statusCode });
  }

  let bodyText = "";
  try {
    bodyText = await request.text();
  } catch {
    return NextResponse.json({ detail: "Invalid request body" }, { status: 400 });
  }

  const token = process.env.AEGIS_CONTROL_TOKEN!;
  const res = await fetchBackendJson<Decision>("/api/demo/scenario", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: bodyText,
    timeoutMs: 8000,
  });

  if (!res.ok || !res.data) {
    return NextResponse.json(
      { detail: res.error || "Scenario execution rejected by backend" },
      { status: res.status || 503 }
    );
  }

  return NextResponse.json(res.data);
}
