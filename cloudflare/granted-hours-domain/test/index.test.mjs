import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.js";

test("proxies the Pages origin without forwarding private headers", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedRequest;

  globalThis.fetch = async (request) => {
    forwardedRequest = request;
    return new Response("ok", {
      status: 200,
      headers: { "content-type": "text/plain" },
    });
  };

  try {
    const response = await worker.fetch(
      new Request("https://granted-hours.hyperint.net/timetable/?date=2026-07-31", {
        headers: {
          authorization: "Bearer private",
          cookie: "private=value",
        },
      }),
    );

    assert.equal(response.status, 200);
    assert.equal(await response.text(), "ok");
    assert.equal(
      forwardedRequest.url,
      "https://granted-hours.pages.dev/timetable/?date=2026-07-31",
    );
    assert.equal(forwardedRequest.headers.get("authorization"), null);
    assert.equal(forwardedRequest.headers.get("cookie"), null);
    assert.equal(forwardedRequest.headers.get("cache-control"), "no-cache");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("keeps fingerprinted asset caching intact", async () => {
  const originalFetch = globalThis.fetch;
  let forwardedRequest;

  globalThis.fetch = async (request) => {
    forwardedRequest = request;
    return new Response("asset", { status: 200 });
  };

  try {
    await worker.fetch(
      new Request(
        "https://granted-hours.hyperint.net/timetable/assets/index-DaL6ALu-.js",
      ),
    );

    assert.equal(forwardedRequest.headers.get("cache-control"), null);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("keeps Pages redirects on the public custom hostname", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(null, {
      status: 302,
      headers: { location: "https://granted-hours.pages.dev/timetable/" },
    });

  try {
    const response = await worker.fetch(
      new Request("https://granted-hours.hyperint.net/"),
    );

    assert.equal(response.status, 302);
    assert.equal(
      response.headers.get("location"),
      "https://granted-hours.hyperint.net/timetable/",
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("returns a non-cacheable gateway error when Pages is unavailable", async () => {
  const originalFetch = globalThis.fetch;
  const originalConsoleError = console.error;

  globalThis.fetch = async () => {
    throw new TypeError("network unavailable");
  };
  console.error = () => {};

  try {
    const response = await worker.fetch(
      new Request("https://granted-hours.hyperint.net/timetable/"),
    );

    assert.equal(response.status, 502);
    assert.equal(response.headers.get("cache-control"), "no-store");
  } finally {
    globalThis.fetch = originalFetch;
    console.error = originalConsoleError;
  }
});
