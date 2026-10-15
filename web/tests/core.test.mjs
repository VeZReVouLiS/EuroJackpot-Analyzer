import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { runChecks } from "./checks.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const files = { golden: join(here, "golden.json"), seed: join(here, "..", "..", "app", "seed", "draws.json") };

test("the JavaScript port matches the Python implementation", async () => {
  const failures = await runChecks(async (name) => JSON.parse(readFileSync(files[name], "utf-8")));
  assert.deepEqual(failures, []);
});
