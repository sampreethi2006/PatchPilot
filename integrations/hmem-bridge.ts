
import { HMEM } from "../meterless-hmem/reference/src/index.ts";

const memory = new HMEM({
  actor: "patchpilot",
  persistDir: "./patchpilot-memory",
});

type Finding = {
  content: string;
  source: string;
  confidence?: number;
  tags?: string[];
};

export function saveFinding(finding: Finding) {
  return memory.add({
    content: finding.content,
    type: "factual",
    layer: "working",
    source: finding.source,
    confidence: finding.confidence ?? 0.9,
    tags: [
      "project:patchpilot",
      "tech:python",
      ...(finding.tags ?? []),
    ],
  });
}

export function searchFindings(query: string) {
 const result = memory.query(query, {
  topN: 5,
  threshold: 0.05,
  });

  return {
    context: result.context,
    memories: result.memories.map(({ memory, relevance }) => ({
      id: memory.id,
      content: memory.content,
      source: memory.source,
      confidence: memory.confidence,
      relevance,
    })),
  };
}
