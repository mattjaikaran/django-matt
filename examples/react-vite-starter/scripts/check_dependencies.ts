#!/usr/bin/env bun
/**
 * Dependency gate — fail when a package.json dependency is not documented
 * in DEPENDENCIES.md.
 *
 * Usage:
 *   bun run scripts/check_dependencies.ts
 *   bun run scripts/check_dependencies.ts --json
 *
 * Exit: 0 = all dependencies documented, 1 = missing entries.
 */

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { parseArgs } from "node:util";
import { argv, exit } from "node:process";

const PROJECT_ROOT = new URL("..", import.meta.url).pathname;

interface Violation {
  check: string;
  filepath: string;
  line: number;
  message: string;
}

export function parseDependencyNames(pkgJson: string): string[] {
  const pkg = JSON.parse(pkgJson) as {
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
  };
  return [
    ...Object.keys(pkg.dependencies ?? {}),
    ...Object.keys(pkg.devDependencies ?? {}),
  ];
}

export function parseDocumentedDependencies(depsMd: string): Set<string> {
  const names = new Set<string>();
  for (const line of depsMd.split("\n")) {
    const match = line.trim().match(/^\|\s*([a-zA-Z0-9@/_.+-]+)\s*\|/);
    if (!match) continue;
    const name = match[1];
    if (/^[-:]+$/.test(name)) continue; // skip table separator rows
    names.add(name);
  }
  return names;
}

export function findMissingDependencies(pkgJson: string, depsMd: string): string[] {
  const deps = parseDependencyNames(pkgJson);
  const documented = parseDocumentedDependencies(depsMd);
  return deps.filter((name) => !documented.has(name));
}

function main(): number {
  const { values } = parseArgs({
    args: argv.slice(2),
    options: {
      json: { type: "boolean", default: false },
    },
    strict: false,
  });

  const pkgJson = readFileSync(join(PROJECT_ROOT, "package.json"), "utf-8");
  const depsMdPath = join(PROJECT_ROOT, "DEPENDENCIES.md");

  const violations: Violation[] = [];
  if (!existsSync(depsMdPath)) {
    for (const name of parseDependencyNames(pkgJson)) {
      violations.push({
        check: "MISSING_DEPENDENCY_ENTRY",
        filepath: "DEPENDENCIES.md",
        line: 0,
        message: `"${name}" — DEPENDENCIES.md is missing; document this dependency`,
      });
    }
  } else {
    const depsMd = readFileSync(depsMdPath, "utf-8");
    for (const name of findMissingDependencies(pkgJson, depsMd)) {
      violations.push({
        check: "MISSING_DEPENDENCY_ENTRY",
        filepath: "DEPENDENCIES.md",
        line: 0,
        message: `"${name}" — document this dependency in DEPENDENCIES.md`,
      });
    }
  }

  if (values.json) {
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
      console.log("All dependencies documented.");
    }
    for (const v of violations) {
      console.log(`[${v.check}] ${v.filepath} — ${v.message}`);
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
