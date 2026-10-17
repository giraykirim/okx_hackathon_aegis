import { NextResponse } from "next/server";
import { buildErc8004RegistrationJson } from "@/app/agent-registration.json/route";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(buildErc8004RegistrationJson());
}
