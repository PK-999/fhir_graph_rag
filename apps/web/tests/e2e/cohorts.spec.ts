import { test, expect } from "@playwright/test";

test("selecting a long condition name submits its code and displays matched patients", async ({ page }) => {
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/v1/cohorts/query", async (route) => {
    submitted = route.request().postDataJSON();
    if (submitted?.conditions instanceof Array && submitted.conditions[0] === "44054006") {
      await route.fulfill({ json: { count: 1, patients: [{ id: "Patient/p-1", name: "Asha Rao", birthDate: "1985-06-15" }], query: "MATCH (p:Patient) RETURN p LIMIT 100" } });
    } else {
      await route.fulfill({ status: 422, json: { detail: [{ msg: "Each condition must be at most 20 characters" }] } });
    }
  });

  await page.goto("/cohorts");
  await page.getByRole("button", { name: "Add Condition" }).click();
  const condition = page.getByPlaceholder("e.g. Diabetes");
  await condition.fill("diabetes");
  await page.getByText("Type 2 diabetes mellitus", { exact: true }).click();
  await expect(condition).toHaveValue("Type 2 diabetes mellitus");
  await page.getByRole("button", { name: "Execute Query" }).click();

  await expect.poll(() => submitted).toEqual({ conditions: ["44054006"], min_age: null, max_age: null });
  await expect(page.getByRole("cell", { name: "Asha Rao", exact: true })).toBeVisible();
  await expect(page.getByText("(1 matched)", { exact: true })).toBeVisible();
});

test("a failed cohort query displays an error rather than successful results", async ({ page }) => {
  await page.route("**/api/v1/cohorts/query", async (route) => {
    await route.fulfill({ status: 503, json: { detail: "Neo4j is unavailable. Try again later." } });
  });

  await page.goto("/cohorts");
  await page.getByRole("button", { name: "Execute Query" }).click();

  await expect(page.getByRole("alert").filter({ hasText: "Neo4j is unavailable. Try again later." })).toBeVisible();
  await expect(page.getByText(/matched\)/)).toHaveCount(0);
});
