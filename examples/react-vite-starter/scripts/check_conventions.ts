#!/usr/bin/env bun
/**
 * Convention enforcer for React frontend — catches AI anti-patterns.
 *
 * Checks:
 *   1. NO_ANY_CAST       — `as any` type assertions
 *   2. NO_TS_IGNORE      — @ts-ignore / @ts-expect-error comments
 *   3. NO_CONSOLE_LOG    — console.log in source files
 *   4. NO_WINDOW_LOCATION — window.location.href navigation
 *   5. NO_INLINE_NAVIGATE — <Navigate> in component render
 *   6. NO_NPM_YARN       — npm install / yarn add in docs
 *   7. NO_DEFAULT_EXPORT — default exports for components
 *   8. API_DIRECT_AXIOS  — raw axios/fetch calls outside lib/api.ts
 *   9. NO_USE_STATE_FOR_FORMS — useState for form state (use react-hook-form + zod)
 *  10. NO_INLINE_FETCH — raw fetch/axios/useQuery/useMutation outside hooks/api
 *  11. COMPONENT_SIZE  — component files over 300 lines
 *
 * Usage:
 *   bun run scripts/check_conventions.ts
 *   bun run scripts/check_conventions.ts --json
 *   bun run scripts/check_conventions.ts --check NO_ANY_CAST
 *
 * Exit: 0 = no violations, 1 = violations found
 */

import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative, extname } from "node:path";
import { parseArgs } from "node:util";
import { argv, exit } from "node:process";

const PROJECT_ROOT = new URL("..", import.meta.url).pathname;

const SCAN_ROOTS = ["src"];

const EXCLUDE_DIRS = new Set([
  "node_modules", "dist", ".git", "coverage", ".vscode"
]);

const API_DIRS = ["src/hooks/", "src/lib/"];

const COMPONENT_SEGMENTS = /components|routes|pages|forms/;

const DEFAULT_EXPORT_SEGMENTS = /components|routes|pages|forms/;

const SOURCE_EXTS = new Set([".ts", ".tsx"]);

interface Violation {
  check: string;
  filepath: string;
  line: number;
  message: string;
}

// ── File collection ──────────────────────────────────────────────────

function collectFiles(root: string): string[] {
  const files: string[] = [];

  function isExcluded(rel: string, entry: string): boolean {
    for (const dir of EXCLUDE_DIRS) {
      if (entry === dir) return true;
      if (rel === dir || rel.startsWith(dir + "/")) return true;
    }
    return false;
  }

  function walk(dir: string) {
    if (!existsSync(dir)) return;
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const rel = relative(root, full);
      if (rel.startsWith(".")) continue;
      if (isExcluded(rel, entry)) continue;
      if (entry === "routeTree.gen.ts") continue;

      try {
        const stat = statSync(full);
        if (stat.isDirectory()) {
          walk(full);
        } else if (SOURCE_EXTS.has(extname(entry))) {
          files.push(full);
        }
      } catch {
        // skip unreadable
      }
    }
  }

  for (const scanRoot of SCAN_ROOTS) {
    walk(join(root, scanRoot));
  }
  return files;
}

// ── Checks ───────────────────────────────────────────────────────────

function* checkNoAnyCast(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (lines[i].includes("as any") && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_ANY_CAST",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: '"as any" type assertion — define proper types',
        };
      }
    }
  }
}

function* checkNoTsIgnore(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/@ts-(ignore|expect-error)/.test(lines[i])) {
        yield {
          check: "NO_TS_IGNORE",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: `@ts-ignore/@ts-expect-error — fix the type error instead`,
        };
      }
    }
  }
}

function* checkNoConsoleLog(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    if (fpath.includes("test") || fpath.includes("setup")) continue;
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/\bconsole\.log\b/.test(lines[i]) && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_CONSOLE_LOG",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "console.log — remove debug logging before commit",
        };
      }
    }
  }
}

function* checkNoWindowLocation(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/window\.location\.href\s*=/.test(lines[i]) && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_WINDOW_LOCATION",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "window.location.href — use useNavigate() from TanStack Router",
        };
      }
    }
  }
}

function* checkNoInlineNavigate(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    const text = readFileSync(fpath, "utf-8");
    const lines = text.split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/<Navigate\s/.test(lines[i]) && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_INLINE_NAVIGATE",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "<Navigate> in component — use router beforeLoad guard instead",
        };
      }
    }
  }
}

function* checkNoNpmYarn(files: string[]): Generator<Violation> {
  // Also check package.json scripts and docs
  const extraFiles = [
    join(PROJECT_ROOT, "package.json"),
    join(PROJECT_ROOT, "README.md"),
  ];
  for (const fpath of [...files, ...extraFiles]) {
    if (!existsSync(fpath)) continue;
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/(npm\s+install|yarn\s+add)/.test(lines[i]) && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_NPM_YARN",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "npm install / yarn add — use bun instead",
        };
      }
    }
  }
}

function* checkNoDefaultExport(files: string[]): Generator<Violation> {
  const componentFiles = files.filter((f) => DEFAULT_EXPORT_SEGMENTS.test(f));
  for (const fpath of componentFiles) {
    const lines = readFileSync(fpath, "utf-8").split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/^export default function/.test(lines[i].trim())) {
        yield {
          check: "NO_DEFAULT_EXPORT",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "Default export on component — use named export",
        };
      }
    }
  }
}

function* checkApiDirectAxios(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    if (API_DIRS.some((dir) => fpath.includes(dir))) continue;
    const text = readFileSync(fpath, "utf-8");
    const lines = text.split("\n");

    // Check for direct axios imports
    for (let i = 0; i < lines.length; i++) {
      if (
        /import\s+axios\s+from/.test(lines[i]) ||
        /from\s+['"]axios['"]/.test(lines[i])
      ) {
        yield {
          check: "API_DIRECT_AXIOS",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "Direct axios import — use api from @/lib/api",
        };
      }
    }
  }
}

function* checkNoUseStateForForms(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    if (!fpath.endsWith(".tsx")) continue;
    const text = readFileSync(fpath, "utf-8");
    if (!/<[Ff]orm[\s>]/.test(text)) continue;
    if (!/\buseState\b/.test(text)) continue;
    if (!/(value=|onChange=|checked=)/.test(text)) continue;
    const lines = text.split("\n");
    for (let i = 0; i < lines.length; i++) {
      if (/\buseState\b/.test(lines[i]) && !lines[i].trim().startsWith("//")) {
        yield {
          check: "NO_USE_STATE_FOR_FORMS",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "useState for form state — use react-hook-form + zod",
        };
        break;
      }
    }
  }
}

function* checkNoInlineFetch(files: string[]): Generator<Violation> {
  for (const fpath of files) {
    if (API_DIRS.some((dir) => fpath.includes(dir))) {
      continue;
    }
    const text = readFileSync(fpath, "utf-8");
    const lines = text.split("\n");
    const hasRawFetch = /\bfetch\s*\(|\baxios\./.test(text);
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.trim().startsWith("//")) continue;
      const isRaw = /\bfetch\s*\(|\baxios\./.test(line);
      const isQuery = /\buseQuery\s*\(|\buseMutation\s*\(/.test(line);
      if (isRaw || (isQuery && hasRawFetch)) {
        yield {
          check: "NO_INLINE_FETCH",
          filepath: relative(PROJECT_ROOT, fpath),
          line: i + 1,
          message: "inline API call — move to src/hooks or src/lib",
        };
      }
    }
  }
}

function* checkComponentSize(files: string[]): Generator<Violation> {
  const isComponentFile = (fpath: string) =>
    fpath.endsWith(".tsx") && COMPONENT_SEGMENTS.test(fpath);
  for (const fpath of files) {
    if (!isComponentFile(fpath)) continue;
    const lines = readFileSync(fpath, "utf-8").split("\n");
    if (lines.length > 300) {
      yield {
        check: "COMPONENT_SIZE",
        filepath: relative(PROJECT_ROOT, fpath),
        line: 301,
        message: `component file exceeds 300 lines (${lines.length}) — split into smaller components`,
      };
    }
  }
}

// ── Orchestration ────────────────────────────────────────────────────

const CHECKS: Record<string, (files: string[]) => Generator<Violation>> = {
  NO_ANY_CAST: checkNoAnyCast,
  NO_TS_IGNORE: checkNoTsIgnore,
  NO_CONSOLE_LOG: checkNoConsoleLog,
  NO_WINDOW_LOCATION: checkNoWindowLocation,
  NO_INLINE_NAVIGATE: checkNoInlineNavigate,
  NO_NPM_YARN: checkNoNpmYarn,
  NO_DEFAULT_EXPORT: checkNoDefaultExport,
  API_DIRECT_AXIOS: checkApiDirectAxios,
  NO_USE_STATE_FOR_FORMS: checkNoUseStateForForms,
  NO_INLINE_FETCH: checkNoInlineFetch,
  COMPONENT_SIZE: checkComponentSize,
};

interface CliArgs {
  json?: boolean;
  check?: string;
  list?: boolean;
}

function main(): number {
  const { values } = parseArgs({
    args: argv.slice(2),
    options: {
      json: { type: "boolean", default: false },
      check: { type: "string" },
      list: { type: "boolean", default: false },
    },
    strict: false,
  });
  const args = values as CliArgs;

  if (args.list) {
    for (const [name] of Object.entries(CHECKS)) {
      console.log(`  ${name}`);
    }
    return 0;
  }

  const files = collectFiles(PROJECT_ROOT);
  const violations: Violation[] = [];

  const checksToRun = args.check
    ? { [args.check]: CHECKS[args.check] }
    : CHECKS;

  for (const fn of Object.values(checksToRun)) {
    if (!fn) {
      console.error(`Unknown check: ${args.check}`);
      return 1;
    }
    for (const v of fn(files)) {
      violations.push(v);
    }
  }

  if (args.json) {
    console.log(
      JSON.stringify(
        {
          violations: violations.map((v) => ({
            check: v.check,
            file: v.filepath,
            line: v.line,
            message: v.message,
          })),
          count: violations.length,
        },
        null,
        2
      )
    );
  } else {
    if (violations.length === 0) {
      console.log("All convention checks passed.");
    }
    for (const v of violations) {
      console.log(`[${v.check}] ${v.filepath}:${v.line} — ${v.message}`);
    }
    console.log(
      violations.length
        ? `\n${violations.length} violation(s) found.`
        : "\n0 violations."
    );
  }

  return violations.length ? 1 : 0;
}

exit(main());
