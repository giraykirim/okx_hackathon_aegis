import { NextRequest } from "next/server";
import { RECORDED_EVENTS_MARKET_ONLY } from "@/lib/fixtures";
import { getBackendBaseUrl } from "@/lib/server-backend";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const baseUrl = getBackendBaseUrl();
  const lastEventId =
    request.headers.get("last-event-id") ||
    request.nextUrl.searchParams.get("lastEventId") ||
    undefined;

  const headers: Record<string, string> = {
    Accept: "text/event-stream",
  };
  if (lastEventId) {
    headers["Last-Event-ID"] = lastEventId;
  }

  try {
    const upstream = await fetch(`${baseUrl}/api/stream`, {
      headers,
      cache: "no-store",
      signal: request.signal,
    });

    if (upstream.ok && upstream.body) {
      return new Response(upstream.body, {
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
          "X-AEGIS-Backend-Status": "LIVE",
        },
      });
    }
  } catch {
    // Fall through to honest offline SSE replay below
  }

  // Offline SSE replay stream so EventSource clients receive recorded events + heartbeat
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(
        encoder.encode(`: offline-fixture-replay source=backend/evidence/latest.json\n\n`)
      );
      for (const ev of RECORDED_EVENTS_MARKET_ONLY) {
        const idLine = ev.id ? `id: ${ev.id}\n` : "";
        const payload = JSON.stringify(ev);
        controller.enqueue(encoder.encode(`${idLine}event: aegis\ndata: ${payload}\n\n`));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
    },
  });
}
