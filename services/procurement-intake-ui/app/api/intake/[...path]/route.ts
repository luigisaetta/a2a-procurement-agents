const INTAKE_BASE_URL =
  process.env.CONVERSATIONAL_INTAKE_BASE_URL ?? "http://127.0.0.1:8012";

interface RouteContext {
  params: Promise<{
    path: string[];
  }>;
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  return proxy(request, context);
}

export async function POST(request: Request, context: RouteContext): Promise<Response> {
  return proxy(request, context);
}

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const sourceUrl = new URL(request.url);
  const targetUrl = new URL(`/${path.join("/")}${sourceUrl.search}`, INTAKE_BASE_URL);
  const accept = request.headers.get("accept") ?? "";
  const isSse = accept.includes("text/event-stream") || targetUrl.pathname.endsWith("/events");

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers: requestHeaders(request, isSse),
    body: request.method === "GET" ? undefined : await request.text(),
    cache: "no-store",
  });

  if (isSse) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  }

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    },
  });
}

function requestHeaders(request: Request, isSse: boolean): HeadersInit {
  const headers: Record<string, string> = {};
  const contentType = request.headers.get("content-type");
  if (contentType && !isSse) {
    headers["Content-Type"] = contentType;
  }
  if (isSse) {
    headers.Accept = "text/event-stream";
  }
  return headers;
}
