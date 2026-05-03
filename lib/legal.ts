import { readFile } from "node:fs/promises";
import path from "node:path";

export async function readLegal(file: "PRIVACY.md" | "TERMS.md" | "SECURITY.md" | "ACCESSIBILITY.md") {
  const p = path.join(process.cwd(), "legal", file);
  return await readFile(p, "utf8");
}
