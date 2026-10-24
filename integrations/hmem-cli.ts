
import { saveFinding, searchFindings } from "./hmem-bridge.ts";

const [action, ...args] = process.argv.slice(2);

try {
  if (action === "save") {
    const finding = JSON.parse(args.join(" "));
    const saved = saveFinding(finding);

    console.log(JSON.stringify({
      ok: true,
      id: saved.id,
      content: saved.content,
      source: saved.source,
    }));
  } else if (action === "search") {
    const query = args.join(" ");
    console.log(JSON.stringify({
      ok: true,
      ...searchFindings(query),
    }));
  } else {
    throw new Error("Use action 'save' or 'search'.");
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
