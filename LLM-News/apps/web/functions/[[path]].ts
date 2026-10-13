interface Environment {
  BACKEND_ORIGIN: string;
}

interface PagesContext {
  request: Request;
  env: Environment;
}

/**
 * Keep the browser on one origin while the static UI and API live on separate
 * free services. Cloudflare Pages invokes this function only for paths listed
 * in public/_routes.json.
 */
export async function onRequest(context: PagesContext): Promise<Response> {
  const configuredOrigin = context.env.BACKEND_ORIGIN?.trim().replace(/\/$/, "");
  if (!configuredOrigin) {
    return new Response("Backend origin is not configured", { status: 503 });
  }

  let backend: URL;
  try {
    backend = new URL(configuredOrigin);
  } catch {
    return new Response("Backend origin is invalid", { status: 503 });
  }
  if (backend.protocol !== "https:" && backend.hostname !== "127.0.0.1" && backend.hostname !== "localhost") {
    return new Response("Backend origin must use HTTPS", { status: 503 });
  }

  const incoming = new URL(context.request.url);
  const target = new URL(`${incoming.pathname}${incoming.search}`, backend);
  const headers = new Headers(context.request.headers);
  headers.delete("host");
  headers.set("x-forwarded-host", incoming.host);
  headers.set("x-forwarded-proto", incoming.protocol.replace(":", ""));

  const method = context.request.method.toUpperCase();
  const response = await fetch(target, {
    method,
    headers,
    body: method === "GET" || method === "HEAD" ? undefined : context.request.body,
    redirect: "manual",
  });
  const responseHeaders = new Headers(response.headers);
  responseHeaders.set("x-newssense-proxy", "cloudflare-pages");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}
