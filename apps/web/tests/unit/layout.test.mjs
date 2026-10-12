import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { loadTypeScript } from "../helpers/load-module.mjs";

// Execute the real TypeScript module using the compiler already installed by Next.js.
const filename = path.resolve(import.meta.dirname, "../../src/lib/layout.ts");
const layoutModule = loadTypeScript(filename);

const node = (id) => ({ id, data: {}, position: { x: 0, y: 0 } });

test("loading a smaller graph discards relationships from the previous layout", () => {
  const { getLayoutedElements } = layoutModule;
  getLayoutedElements([node("A"), node("B"), node("C")], [
    { id: "ab", source: "A", target: "B" },
    { id: "bc", source: "B", target: "C" },
  ]);

  const result = getLayoutedElements([node("B")], []);

  assert.deepEqual(result.nodes.map(({ id, position }) => ({ id, position })), [
    { id: "B", position: { x: 0, y: 0 } },
  ]);
  assert.deepEqual(result.edges, []);
});
