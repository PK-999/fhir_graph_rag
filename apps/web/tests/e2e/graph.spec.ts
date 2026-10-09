import { test, expect } from "@playwright/test";

const graph = {
  nodes: [
    { id: "Encounter/e-1", labels: ["Encounter"], properties: { id: "Encounter/e-1", class_code: "AMB" } },
    { id: "Patient/p-1", labels: ["Patient"], properties: { id: "Patient/p-1", name_0_given_0: "Asha", name_0_family: "Rao", gender: "female" } },
    { id: "Condition/c-1", labels: ["Condition"], properties: { id: "Condition/c-1", code_coding_0_code: "44054006", code_coding_0_display: "Type 2 diabetes mellitus" } },
    { id: "MedicationRequest/m-1", labels: ["MedicationRequest"], properties: { id: "MedicationRequest/m-1", medication_codeable_concept_coding_0_display: "Metformin", status: "active" } },
  ],
  edges: [
    { source: "Encounter/e-1", target: "Patient/p-1", type: "SUBJECT", properties: {} },
    { source: "Condition/c-1", target: "Patient/p-1", type: "SUBJECT", properties: {} },
    { source: "MedicationRequest/m-1", target: "Patient/p-1", type: "SUBJECT", properties: {} },
  ],
  truncated: false,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/graph/**", async (route) => {
    const url = new URL(route.request().url());
    let body;
    if (url.pathname.endsWith("/expand")) {
      body = {
        nodes: [graph.nodes[1]],
        edges: [
          graph.edges[0],
          { id: "reason-link", source: "Encounter/e-1", target: "Patient/p-1", type: "REASON_REFERENCE", properties: {} },
        ],
      };
    } else if (url.pathname.includes("/explore/")) {
      body = { node_id: "Encounter/e-1", labels: ["Encounter"], categories: [{ relationship: "REASON_REFERENCE", neighbor_type: "Patient", count: 1 }] };
    } else {
      body = graph;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/graph?node=Encounter%2Fe-1");
  await expect(page.locator(".react-flow__node")).toHaveCount(4);
});

test("flattened FHIR names and clinical displays identify graph nodes", async ({ page }) => {
  const nodes = page.locator(".react-flow__node");
  await expect(nodes.filter({ hasText: "Asha Rao" })).toHaveCount(1);
  await expect(nodes.filter({ hasText: "Type 2 diabetes mellitus" })).toHaveCount(1);
  await expect(nodes.filter({ hasText: "Metformin" })).toHaveCount(1);

  await nodes.filter({ hasText: "Asha Rao" }).click();
  await expect(page.getByRole("heading", { name: "Asha Rao" })).toHaveCount(2);
  const properties = page.getByRole("heading", { name: "Properties", exact: true }).locator("..");
  await expect(properties.getByText("name 0 given 0", { exact: true })).toBeVisible();
  await expect(properties.getByText("name 0 family", { exact: true })).toBeVisible();
});

test("expansion retains parallel relationship types without repeating existing edges", async ({ page }) => {
  await expect(page.locator(".react-flow__edge")).toHaveCount(3);
  await page.locator('.react-flow__node[data-id="Encounter/e-1"]').click();
  const expand = page.getByRole("button", { name: /Reason.*Patient/ });

  await expand.click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(4);
  await expand.click();
  await expect(page.locator(".react-flow__edge")).toHaveCount(4);
});

test("summary edges identify display groupings without claiming FHIR reference provenance", async ({ page }) => {
  await page.route("**/api/v1/graph/**", route => route.fulfill({ json: {
    nodes: [graph.nodes[1], { id: "Summary/Condition", labels: ["Summary"], properties: { name: "Conditions", count: 1 } }],
    edges: [{ source: "Patient/p-1", target: "Summary/Condition", type: "HAS_CONDITION", properties: {} }],
  } }));
  await page.goto("/graph?node=Encounter%2Fe-summary");
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
  const point = await page.locator(".react-flow__edge-interaction").evaluate((element) => {
    const path = element as SVGPathElement;
    const position = path.getPointAtLength(path.getTotalLength() / 2);
    const screen = new DOMPoint(position.x, position.y).matrixTransform(path.getScreenCTM()!);
    return { x: screen.x, y: screen.y };
  });
  await page.mouse.click(point.x, point.y);
  await expect(page.getByRole("heading", { name: "Display grouping", exact: true })).toBeVisible();
  await expect(page.getByText(/groups resources for display/)).toBeVisible();
});
