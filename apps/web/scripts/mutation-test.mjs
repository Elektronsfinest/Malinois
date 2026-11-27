/**
 * Windows-compatible Mutation Testing Runner for Malinois Frontend Utilities.
 *
 * Usage:
 *   cd apps/web
 *   npm run test:mutation
 */

import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const WEB_DIR = resolve(import.meta.dirname, "..");

const MUTANTS = [
  {
    id: "DATE-01",
    file: "src/utils/dates.ts",
    description: "Flip overdue check 'daysDiff < 0' to 'daysDiff <= 0'",
    target: "if (daysDiff < 0) {",
    replacement: "if (daysDiff <= 0) {",
  },
  {
    id: "DATE-02",
    file: "src/utils/dates.ts",
    description: "Flip threshold boundary 'daysDiff <= thresholdDays' to 'daysDiff < thresholdDays'",
    target: "if (daysDiff <= thresholdDays) {",
    replacement: "if (daysDiff < thresholdDays) {",
  },
  {
    id: "DATE-03",
    file: "src/utils/dates.ts",
    description: "Break Polish pluralization 'daysDiff === 1' to 'daysDiff === 2'",
    target: 'const unit = daysDiff === 1 ? "dzień" : "dni";',
    replacement: 'const unit = daysDiff === 2 ? "dzień" : "dni";',
  },
  {
    id: "DATE-04",
    file: "src/utils/dates.ts",
    description: "Swap day/month order in formatPolishDate",
    target: "return `${day}.${month}.${year}`;",
    replacement: "return `${month}.${day}.${year}`;",
  },
  {
    id: "DRAFT-01",
    file: "src/utils/draftStorage.ts",
    description: "Disable draft clearing when a different user logs in",
    target: "if (owner && owner !== nextUserEmail.trim().toLowerCase()) {",
    replacement: "if (false && owner && owner !== nextUserEmail.trim().toLowerCase()) {",
  },
  {
    id: "DRAFT-02",
    file: "src/utils/draftStorage.ts",
    description: "Invert user-switch check (clears drafts for SAME user instead)",
    target: "if (owner && owner !== nextUserEmail.trim().toLowerCase()) {",
    replacement: "if (owner && owner === nextUserEmail.trim().toLowerCase()) {",
  },
];

let killed = 0;
const survived = [];

console.log(`Running ${MUTANTS.length} frontend mutants...\n`);

for (const m of MUTANTS) {
  const fullPath = resolve(WEB_DIR, m.file);
  const original = readFileSync(fullPath, "utf8");
  if (!original.includes(m.target)) {
    console.log(`[SKIP]     ${m.id}: target not found in ${m.file}`);
    continue;
  }

  const mutated = original.replace(m.target, m.replacement);
  let mutantKilled = false;
  try {
    writeFileSync(fullPath, mutated, "utf8");
    execSync("npx vitest run src/UtilsAndSecurity.test.tsx", {
      cwd: WEB_DIR,
      stdio: "pipe",
    });
  } catch {
    mutantKilled = true;
  } finally {
    writeFileSync(fullPath, original, "utf8");
  }

  if (mutantKilled) {
    killed += 1;
    console.log(`[KILLED]   ${m.id} (${m.file}): ${m.description}`);
  } else {
    survived.push(m);
    console.log(`[SURVIVED] ${m.id} (${m.file}): ${m.description}`);
  }
}

const total = killed + survived.length;
const score = total > 0 ? ((killed / total) * 100).toFixed(1) : "0.0";
console.log(`\nFrontend Mutation Score: ${killed}/${total} killed (${score}%)`);

if (survived.length > 0) {
  process.exit(1);
}
