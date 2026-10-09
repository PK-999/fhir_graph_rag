import { test, expect, type Page } from "@playwright/test";

const clinicalAnswer = {
  status: "answered",
  answer: "Retrieved 1 patient whose latest HbA1c is above 8% with an active Metformin prescription.",
  results: [{ patient_id: "Patient/p-1", name: "Asha Rao", latest_hba1c: 8.7, unit: "%", observed_at: "2026-09-20T09:00:00Z" }],
  result_count: 1,
  evidence: [
    { type: "Patient", id: "Patient/p-1", label: "Asha Rao", patient_id: "Patient/p-1", source_url: "/resources/Patient/p-1", facts: { "name[0].given[0]": "Asha", "name[0].family": "Rao" } },
    { type: "Observation", id: "Observation/o-1", label: "Hemoglobin A1c", patient_id: "Patient/p-1", source_url: "/resources/Observation/o-1", facts: { "code.coding[0].code": "4548-4", "valueQuantity.value": 8.7, "valueQuantity.unit": "%", "effectiveDateTime": "2026-09-20T09:00:00Z", "status": "final" } },
    { type: "MedicationRequest", id: "MedicationRequest/m-1", label: "Metformin", patient_id: "Patient/p-1", source_url: "/resources/MedicationRequest/m-1", facts: { "medicationCodeableConcept.coding[0].code": "6809", "status": "active", "authoredOn": "2026-09-01" } },
  ],
  cypher: "MATCH (p:Patient) RETURN p LIMIT $limit",
  plan: { intent: "latest_lab_medication", limit: 20, lab_code: "4548-4", medication_code: "6809", threshold: 8, comparison: "gt", unit: "%" },
  parameters: { limit: 20, lab_code: "4548-4", medication_code: "6809", threshold: 8, unit: "%" },
  planner: "deterministic",
};

async function ask(page: Page, query = "Find patients whose latest HbA1c is above 8% with active Metformin") {
  await page.getByRole("textbox", { name: "Question" }).fill(query);
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
}

test("supported examples populate the composer and clinical results expose exact resource facts", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", async (route) => {
    const request = route.request().postDataJSON();
    if (request.query === "Find patients whose latest HbA1c is above 8% with active Metformin") {
      await route.fulfill({ json: clinicalAnswer });
    } else {
      await route.fulfill({ status: 422, json: { detail: "Unexpected question" } });
    }
  });
  await page.goto("/assistant");
  await expect(page.getByText(/Synthetic data only/).first()).toBeVisible();
  await page.getByRole("button", { name: "List five patients", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Question" })).toHaveValue("List five patients");
  await expect(page.getByRole("button", { name: "Find patients with type 2 diabetes", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Show history for Patient/p-000001", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Find patients whose latest HbA1c is above 8% with active Metformin", exact: true }).click();
  await page.getByRole("button", { name: "Ask question", exact: true }).click();

  const results = page.getByRole("table", { name: "Retrieved results" });
  await expect(results.getByRole("cell", { name: "Asha Rao", exact: true })).toBeVisible();
  await expect(results.getByRole("link", { name: "Patient/p-1", exact: true })).toHaveAttribute("href", "/patients/p-1");
  await expect(page.getByText("1 result returned", { exact: true })).toBeVisible();
  const observation = page.getByRole("article", { name: "Evidence Observation/o-1" });
  await expect(observation.getByText("valueQuantity.value", { exact: true })).toBeVisible();
  await expect(observation.getByText("8.7", { exact: true })).toBeVisible();
  await expect(observation.getByText("%", { exact: true })).toBeVisible();
  await expect(observation.getByText("2026-09-20T09:00:00Z", { exact: true })).toBeVisible();
  await expect(observation.getByRole("link", { name: "View patient" })).toHaveAttribute("href", "/patients/p-1");
  const medication = page.getByRole("article", { name: "Evidence MedicationRequest/m-1" });
  await expect(medication.getByText("Metformin", { exact: true })).toBeVisible();
  await expect(medication.getByText("active", { exact: true })).toBeVisible();
  await expect(page.getByText("Generated Cypher", { exact: true })).toHaveCount(0);
});

test("FHIR source inspection fetches the observation through the configured API and does not navigate to a patient", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", (route) => route.fulfill({ json: clinicalAnswer }));
  await page.route("**/api/v1/resources/Observation/o-1", (route) => route.fulfill({ json: { resourceType: "Observation", id: "o-1", status: "final", valueQuantity: { value: 8.7, unit: "%" }, effectiveDateTime: "2026-09-20T09:00:00Z" } }));
  await page.goto("/assistant");
  await ask(page);
  const observation = page.getByRole("article", { name: "Evidence Observation/o-1" });
  await observation.getByRole("button", { name: "Inspect FHIR source" }).click();
  await expect(observation.getByRole("region", { name: "FHIR source Observation/o-1" })).toContainText('"resourceType": "Observation"');
  await expect(observation.getByRole("region", { name: "FHIR source Observation/o-1" })).toContainText('"value": 8.7');
  await expect(page).toHaveURL(/\/assistant$/);
});

test("zero matches remain an answered query with an explicit empty state", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", (route) => route.fulfill({ json: { ...clinicalAnswer, answer: "No patients matched the requested criteria.", results: [], result_count: 0, evidence: [] } }));
  await page.goto("/assistant");
  await ask(page);
  await expect(page.getByText("No matching results", { exact: true })).toBeVisible();
  await expect(page.getByText("0 results returned", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Retrieved results" })).toHaveCount(0);
  await expect(page.getByText("Unsupported question", { exact: true })).toHaveCount(0);
});

test("an unsupported question shows abstention without clinical results or source claims", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", (route) => route.fulfill({ json: { status: "abstained", answer: "Treatment advice is outside the supported questions. Try patient listing, condition cohorts, latest labs with medication, or patient history.", results: [], result_count: 0, evidence: [], cypher: null, plan: null, parameters: {}, planner: "deterministic" } }));
  await page.goto("/assistant");
  await ask(page, "What treatment should I recommend?");
  await expect(page.getByText("Unsupported question", { exact: true })).toBeVisible();
  await expect(page.getByText(/Treatment advice is outside/)).toBeVisible();
  await expect(page.getByRole("table", { name: "Retrieved results" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Inspect FHIR source" })).toHaveCount(0);
  await expect(page.getByText("0 results returned", { exact: true })).toHaveCount(0);
});

test("assistant service failures are visible and preserve the question for retry", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", (route) => route.fulfill({ status: 503, json: { detail: "The graph service is unavailable. Try again later." } }));
  await page.goto("/assistant");
  await ask(page, "List five patients");
  await expect(page.getByRole("alert", { name: "Question service error" })).toContainText("The graph service is unavailable. Try again later.");
  await expect(page.getByRole("textbox", { name: "Question" })).toHaveValue("List five patients");
  await expect(page.getByRole("button", { name: "Ask question", exact: true })).toBeEnabled();
  await expect(page.getByRole("table", { name: "Retrieved results" })).toHaveCount(0);
});

test("a failed source request shows an error and can be retried without losing the evidence", async ({ page }) => {
  let attempts = 0;
  await page.route("**/api/v1/assistant/query", (route) => route.fulfill({ json: clinicalAnswer }));
  await page.route("**/api/v1/resources/MedicationRequest/m-1", (route) => {
    attempts += 1;
    return attempts === 1
      ? route.fulfill({ status: 502, json: { detail: "FHIR source is unavailable." } })
      : route.fulfill({ json: { resourceType: "MedicationRequest", id: "m-1", status: "active" } });
  });
  await page.goto("/assistant");
  await ask(page);
  const medication = page.getByRole("article", { name: "Evidence MedicationRequest/m-1" });
  await medication.getByRole("button", { name: "Inspect FHIR source" }).click();
  await expect(medication.getByRole("alert")).toContainText("FHIR source is unavailable.");
  await medication.getByRole("button", { name: "Retry source" }).click();
  await expect(medication.getByRole("region", { name: "FHIR source MedicationRequest/m-1" })).toContainText('"status": "active"');
  await expect(medication.getByRole("alert")).toHaveCount(0);
});

test("the history example is runnable and exposes recorded encounter time with source evidence", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", async route => {
    expect(route.request().postDataJSON().query).toBe("Show history for Patient/p-000001");
    await route.fulfill({ json: {
      status: "answered", answer: "Retrieved one recorded history row.", result_count: 1, planner: "demo",
      results: [{ patient_id: "Patient/p-000001", resource_id: "Encounter/e-1", resource_type: "Encounter", event_at: "2026-01-02T08:00:00Z", event_field: "Encounter.period.start", status: "finished" }],
      evidence: [{ type: "Encounter", id: "Encounter/e-1", patient_id: "Patient/p-000001", label: "Encounter", source_url: "/resources/Encounter/e-1", facts: { "Encounter.period.start": "2026-01-02T08:00:00Z", "Encounter.status": "finished" } }],
    } });
  });
  await page.goto("/assistant");
  await page.getByRole("button", { name: "Show history for Patient/p-000001", exact: true }).click();
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(page.getByRole("columnheader", { name: "Recorded time", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "2026-01-02T08:00:00Z", exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Evidence Encounter/e-1" }).getByText("Encounter.period.start", { exact: true })).toBeVisible();
});

const historyPlan = { intent: "patient_history", patient_id: "Patient/p", limit: 2, comparison: "gt" };
function historyPage(offset: number) {
  const ids = offset === 0 ? ["e-1", "e-2"] : ["e-3"];
  return {
    status: "answered", answer: `Retrieved ${ids.length} history rows on this page.`, result_count: ids.length,
    planner: "explicit", plan: historyPlan,
    pagination: { offset, limit: 2, has_more: offset === 0, next_offset: offset === 0 ? 2 : null },
    results: ids.map(id => ({ patient_id: "Patient/p", resource_id: `Encounter/${id}`, resource_type: "Encounter", status: "finished" })),
    evidence: [
      { type: "Patient", id: "Patient/p", label: "Patient", patient_id: "Patient/p", source_url: "/resources/Patient/p", facts: { "Patient.name[0].family": "Example" } },
      ...ids.map(id => ({ type: "Encounter", id: `Encounter/${id}`, label: "Encounter", patient_id: "Patient/p", source_url: `/resources/Encounter/${id}`, facts: { "Encounter.status": "finished", "Encounter.subject.reference": "Patient/p" } })),
    ],
  };
}

test("load more preserves the original history plan and appends ordered rows with unique evidence", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", async route => {
    const body = route.request().postDataJSON();
    if (body.offset === 2) {
      expect(body).toMatchObject({ query: "Show history for Patient/p", plan: historyPlan, offset: 2 });
      await route.fulfill({ json: historyPage(2) });
    } else {
      await route.fulfill({ json: historyPage(0) });
    }
  });
  await page.goto("/assistant");
  await ask(page, "Show history for Patient/p");
  await expect(page.getByText("2 results returned", { exact: true })).toBeVisible();
  // Editing the composer must not reinterpret an already loaded result set.
  await page.getByRole("textbox", { name: "Question" }).fill("List five patients");
  await page.getByRole("button", { name: "Load more results", exact: true }).click();
  const rows = page.getByRole("table", { name: "Retrieved results" }).getByRole("row");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(1)).toContainText("Encounter/e-1");
  await expect(rows.nth(2)).toContainText("Encounter/e-2");
  await expect(rows.nth(3)).toContainText("Encounter/e-3");
  await expect(page.getByRole("article", { name: "Evidence Patient/p", exact: true })).toHaveCount(1);
  await expect(page.getByRole("article", { name: /^Evidence Encounter\// })).toHaveCount(3);
  await expect(page.getByText("3 results returned", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Load more results", exact: true })).toHaveCount(0);
  await expect(page.getByText("All matching rows have been loaded.", { exact: true })).toBeVisible();
});

test("a failed later page retains earlier rows and retries the same offset", async ({ page }) => {
  let failed = false;
  await page.route("**/api/v1/assistant/query", async route => {
    const body = route.request().postDataJSON();
    if (body.offset === 2 && !failed) {
      failed = true;
      await route.fulfill({ status: 503, json: { detail: "Graph retrieval failed" } });
    } else {
      await route.fulfill({ json: historyPage(body.offset || 0) });
    }
  });
  await page.goto("/assistant");
  await ask(page, "Show history for Patient/p");
  await page.getByRole("button", { name: "Load more results", exact: true }).click();
  await expect(page.getByRole("alert", { name: "More results error" })).toContainText("Graph retrieval failed");
  await expect(page.getByRole("table", { name: "Retrieved results" }).getByRole("row")).toHaveCount(3);
  await page.getByRole("button", { name: "Retry more results", exact: true }).click();
  await expect(page.getByText("3 results returned", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert", { name: "More results error" })).toHaveCount(0);
});

test("asking a new question clears accumulated pages and continuation errors", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", async route => {
    const body = route.request().postDataJSON();
    await route.fulfill({ json: body.query === "List five patients" ? { ...clinicalAnswer, pagination: { offset: 0, limit: 20, has_more: false, next_offset: null } } : historyPage(0) });
  });
  await page.goto("/assistant");
  await ask(page, "Show history for Patient/p");
  await expect(page.getByRole("button", { name: "Load more results", exact: true })).toBeVisible();
  await ask(page, "List five patients");
  await expect(page.getByText("1 result returned", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Evidence Encounter/e-1", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Load more results", exact: true })).toHaveCount(0);
});

for (const mutation of ["wrong offset", "repeated row", "changed plan", "empty page"]) {
  test(`an invalid continuation with ${mutation} preserves loaded history for retry`, async ({ page }) => {
    await page.route("**/api/v1/assistant/query", async route => {
      const body = route.request().postDataJSON();
      const payload = historyPage(body.offset || 0);
      if (body.offset === 2) {
        if (mutation === "wrong offset") payload.pagination.offset = 0;
        if (mutation === "repeated row") payload.results[0].resource_id = "Encounter/e-1";
        if (mutation === "changed plan") payload.plan = { ...historyPlan, patient_id: "Patient/other" };
        if (mutation === "empty page") { payload.results = []; payload.evidence = []; payload.result_count = 0; }
      }
      await route.fulfill({ json: payload });
    });
    await page.goto("/assistant");
    await ask(page, "Show history for Patient/p");
    await page.getByRole("button", { name: "Load more results", exact: true }).click();
    await expect(page.getByRole("alert", { name: "More results error" })).toContainText("Continuation page is invalid");
    await expect(page.getByRole("table", { name: "Retrieved results" }).getByRole("row")).toHaveCount(3);
    await expect(page.getByRole("button", { name: "Retry more results", exact: true })).toBeVisible();
  });
}

test("optional model claims remain cited and provenance inspection exposes the artifact audit", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", async route => {
    expect(route.request().postDataJSON().use_summary_model).toBe(true);
    await route.fulfill({ json: { ...clinicalAnswer,
      claims: [{ evidence_id: "Observation/o-1", field: "Observation.valueQuantity.value", value: 8.7 }],
      summary: "Observation/o-1 — Observation.valueQuantity.value: 8.7",
      summary_metadata: { requested: true, status: "validated", model: "local-test", claim_count: 1 },
    } });
  });
  await page.route("**/api/v1/lineage/resources/Observation/o-1", route => route.fulfill({ json: {
    resource_id: "Observation/o-1", status: "available", hash_scope: "canonical artifact JSON before server-managed metadata",
    events: [{ source_artifact: "ndjson/Observation.ndjson", source_location: "line:7", content_sha256: "a".repeat(64), confirmed_stage: "build_graph", run_status: "completed" }],
  } }));
  await page.goto("/assistant");
  await page.getByRole("checkbox", { name: "Select cited facts with the local model" }).check();
  await ask(page);
  await expect(page.getByRole("region", { name: "Validated model claims" })).toContainText("Observation.valueQuantity.value");
  const observation = page.getByRole("article", { name: "Evidence Observation/o-1" });
  await observation.getByRole("button", { name: "Inspect provenance" }).click();
  await expect(observation.getByRole("region", { name: "Provenance Observation/o-1" })).toContainText("line:7");
  await expect(observation.getByRole("region", { name: "Provenance Observation/o-1" })).toContainText("a".repeat(64));
});

test("a rejected model selection preserves the retrieved facts and source cards", async ({ page }) => {
  await page.route("**/api/v1/assistant/query", route => route.fulfill({ json: { ...clinicalAnswer,
    claims: [], summary: null, summary_metadata: { requested: true, status: "rejected", model: "local-test", claim_count: 0 },
  } }));
  await page.goto("/assistant");
  await page.getByRole("checkbox", { name: "Select cited facts with the local model" }).check();
  await ask(page);
  await expect(page.getByText("Model selection rejected; retrieved facts remain available.", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "Evidence Observation/o-1" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Validated model claims" })).toHaveCount(0);
});
