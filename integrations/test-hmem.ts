
import { saveFinding, searchFindings } from "./hmem-bridge.ts";

const saved = saveFinding({
  content:
    "The divide function raises ZeroDivisionError when the divisor is zero. The test expects ValueError.",
  source: "sample_repo/test_calculator.py",
  confidence: 0.95,
  tags: ["bug:division-by-zero", "language:python"],
});

console.log("\n--- SAVED FINDING ---");
console.log({
  id: saved.id,
  content: saved.content,
  source: saved.source,
});

const results = searchFindings("division by zero test error");

console.log("\n--- SEARCH RESULTS ---");
console.log(JSON.stringify(results, null, 2));

if (results.memories.length === 0) {
  throw new Error("H-MEM did not retrieve the saved finding.");
}

console.log("\nSUCCESS: H-MEM saved and retrieved a finding.");
