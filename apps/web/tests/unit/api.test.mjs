import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { loadTypeScript } from "../helpers/load-module.mjs";

const apiFile = path.resolve(import.meta.dirname, "../../src/lib/api.ts");
const serverFile = path.resolve(import.meta.dirname, "../../src/lib/server-api.ts");

function withEnvironment(values, run) {
  const saved = { ...process.env };
  try {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.API_INTERNAL_URL;
    Object.assign(process.env, values);
    run();
  } finally {
    process.env = saved;
  }
}

test("browser requests use the local public endpoint by default", () => {
  withEnvironment({}, () => {
    const { apiUrl } = loadTypeScript(apiFile);
    assert.equal(apiUrl("/patients"), "http://localhost:8010/api/v1/patients");
  });
});

test("browser requests never select the server-only internal endpoint", () => {
  withEnvironment({ NEXT_PUBLIC_API_URL: "https://demo.test/api/v1/", API_INTERNAL_URL: "http://api:8000/api/v1" }, () => {
    const { apiUrl } = loadTypeScript(apiFile);
    assert.equal(apiUrl("/assistant/query"), "https://demo.test/api/v1/assistant/query");
    assert.equal(apiUrl("patients?limit=5"), "https://demo.test/api/v1/patients?limit=5");
  });
});

test("server requests prefer the runtime internal endpoint", () => {
  withEnvironment({ NEXT_PUBLIC_API_URL: "https://demo.test/api/v1", API_INTERNAL_URL: "http://api:8000/api/v1/" }, () => {
    const api = loadTypeScript(apiFile);
    const { serverApiUrl } = loadTypeScript(serverFile, { "./api": api });
    assert.equal(serverApiUrl("/dashboard/summary"), "http://api:8000/api/v1/dashboard/summary");
    process.env.API_INTERNAL_URL = "http://other-api:8000/api/v1";
    assert.equal(serverApiUrl("/patients"), "http://other-api:8000/api/v1/patients");
  });
});

test("server requests fall back to the public endpoint and then local default", () => {
  for (const [values, expected] of [[{ NEXT_PUBLIC_API_URL: "https://demo.test/api/v1" }, "https://demo.test/api/v1/patients"], [{}, "http://localhost:8010/api/v1/patients"]]) {
    withEnvironment(values, () => {
      const api = loadTypeScript(apiFile);
      const { serverApiUrl } = loadTypeScript(serverFile, { "./api": api });
      assert.equal(serverApiUrl("/patients"), expected);
    });
  }
});
