const SOURCE_ORIGIN = "https://granted-hours.pages.dev";

const PRIVATE_REQUEST_HEADERS = [
  "authorization",
  "cf-access-jwt-assertion",
  "cookie",
  "proxy-authorization",
];

function buildUpstreamRequest(request, upstreamUrl) {
  const upstreamRequest = new Request(upstreamUrl, request);

  for (const header of PRIVATE_REQUEST_HEADERS) {
    upstreamRequest.headers.delete(header);
  }

  return upstreamRequest;
}

function rewritePagesRedirect(response, requestUrl, upstreamUrl) {
  const headers = new Headers(response.headers);
  const location = headers.get("location");

  if (location) {
    const redirectUrl = new URL(location, upstreamUrl);

    if (redirectUrl.origin === SOURCE_ORIGIN) {
      redirectUrl.protocol = requestUrl.protocol;
      redirectUrl.host = requestUrl.host;
      headers.set("location", redirectUrl.toString());
    }
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

export default {
  async fetch(request) {
    const requestUrl = new URL(request.url);
    const upstreamUrl = new URL(
      `${requestUrl.pathname}${requestUrl.search}`,
      SOURCE_ORIGIN,
    );

    try {
      const upstreamRequest = buildUpstreamRequest(request, upstreamUrl);
      const response = await fetch(upstreamRequest, { redirect: "manual" });

      return rewritePagesRedirect(response, requestUrl, upstreamUrl);
    } catch (error) {
      console.error(
        JSON.stringify({
          event: "pages_origin_unavailable",
          error: error instanceof Error ? error.name : "UnknownError",
        }),
      );

      return new Response("Granted Hours is temporarily unavailable.", {
        status: 502,
        headers: {
          "cache-control": "no-store",
          "content-type": "text/plain; charset=utf-8",
        },
      });
    }
  },
};
