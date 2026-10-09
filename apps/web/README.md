# FHIRGraph web app

Next.js dashboard, patient registry, React Flow graph explorer, and assistant UI for the synthetic FHIR dataset. See the [repository README](../../README.md) for the complete stack, data generation, and API setup.

Run these commands from `apps/web` with Node.js 22 or newer:

```bash
npm ci
NEXT_PUBLIC_API_URL=http://localhost:8010/api/v1 npm run dev
```

The local development app opens at `http://localhost:3000`. Browser requests use `NEXT_PUBLIC_API_URL`, which defaults to `http://localhost:8010/api/v1`; set it before building when deploying to another public API address.

Server-rendered pages prefer `API_INTERNAL_URL` at runtime, then fall back to the public URL and local default. In Docker, set `API_INTERNAL_URL=http://api:8000/api/v1` in the web container's runtime environment so server requests reach the API service. This server-only variable does not need a build argument.

```bash
npm run lint
npm run typecheck
npm run test:unit
npm run build
npm run test:e2e -- graph.spec.ts --reporter=line
npm run test:e2e -- cohorts.spec.ts --reporter=line
```

The graph and cohort regression tests use API fixtures and the installed Playwright Chromium browser. Install Chromium with `npx playwright install chromium` if needed. The live walkthrough requires a populated Docker demo and is explicitly enabled with `LIVE_DEMO=1 PLAYWRIGHT_PORT=4010 npm run test:e2e -- demo.spec.ts`. Supported questions do not require a model. Assistant, graph, and cohort regressions use controlled API fixtures.

Production builds download the existing Geist fonts from Google Fonts. The Docker image runs the standalone build with `node server.js`; for a local standalone run, copy `.next/static` into `.next/standalone/.next/static`, then run `node .next/standalone/server.js`.
