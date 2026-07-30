#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# matt-audit.sh — Pre-commit hook that runs django-matt code-quality audits.
#
# On pre-commit, this script runs the full audit suite at STRICT level and
# blocks the commit when CRITICAL or HIGH findings are present.
#
# Override defaults via environment:
#   MATT_PROJECT_PATH    — project root to audit (default: auto-detect)
#   MATT_AUDIT_LEVEL     — audit level (default: strict)
#   MATT_AUDIT_FAIL_ON   — comma-separated severities to fail on
#                           (default: critical,high)
# ---------------------------------------------------------------------------
set -euo pipefail

# ---- helpers ----------------------------------------------------------------
_red()    { printf '\033[31m%s\033[0m\n' "$*"; }
_green()  { printf '\033[32m%s\033[0m\n' "$*"; }
_yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
_bold()   { printf '\033[1m%s\033[0m\n' "$*"; }

_die() { _red "matt-audit: $*" >&2; exit 1; }

# ---- project-root discovery ------------------------------------------------
_find_project_root() {
    # 1. Explicit env override wins.
    if [[ -n "${MATT_PROJECT_PATH:-}" ]]; then
        echo "$MATT_PROJECT_PATH"
        return
    fi

    # 2. Walk up from cwd looking for a .matt/ directory or pyproject.toml
    #    that contains django-matt configuration.
    local dir
    dir="$PWD"
    while true; do
        if [[ -d "$dir/.matt" ]] || [[ -f "$dir/pyproject.toml" ]]; then
            echo "$dir"
            return
        fi
        [[ "$dir" == "/" ]] && break
        dir="$(dirname "$dir")"
    done

    # 3. Fall back to cwd.
    echo "$PWD"
}

# ---- changed-files discovery ------------------------------------------------
_has_python_changes() {
    # pre-commit sets this env var with staged files when pass_filenames: false
    # isn't used. But we use pass_filenames: false so we check git ourselves.
    # Only skip if there are zero staged .py files in the entire repo.
    local staged
    staged=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null \
        | grep '\.py$' || true)
    [[ -n "$staged" ]]
}

# ---- main audit -------------------------------------------------------------
run_audit() {
    local project_root="$1"
    local audit_level="${MATT_AUDIT_LEVEL:-strict}"
    local fail_on="${MATT_AUDIT_FAIL_ON:-critical,high}"

    # Determine the python to use — prefer the one in the active venv.
    local python_exe="${MATT_PYTHON:-python}"

    # Build the fail-on severities set (uppercase).
    local fail_critical=0 fail_high=0 fail_medium=0
    local IFS=','
    for sev in $fail_on; do
        case "${sev,,}" in
            critical) fail_critical=1 ;;
            high)     fail_high=1 ;;
            medium)   fail_medium=1 ;;
            *)        echo "matt-audit: WARNING: unknown fail-on severity '$sev', ignoring" >&2 ;;
        esac
    done

    # Run the audit inline via Python.
    local output exit_code
    output=$(
        cd "$project_root" && "$python_exe" -c '
import json, sys, os
from pathlib import Path

# Let the audit framework import from the project root.
sys.path.insert(0, os.getcwd())

try:
    from django_matt.audits import run_audit, AuditLevel, AuditSeverity
except ImportError:
    print(json.dumps({"error": "django-matt is not installed in this environment"}))
    sys.exit(0)

level = AuditLevel("'"$audit_level"'")

try:
    report = run_audit("all", level=level, project_path=os.getcwd())
except Exception as exc:
    print(json.dumps({"error": f"Audit execution failed: {exc}"}))
    sys.exit(0)

findings = []
for f in report.all_findings:
    findings.append({
        "id": f.id,
        "severity": f.severity.value,
        "category": f.category.value,
        "message": f.message,
        "file": f.file,
        "line": f.line,
        "suggestion": f.suggestion,
    })

print(json.dumps({
    "findings": findings,
    "total": len(findings),
    "passed": report.passed,
    "level": report.level.value,
    "total_files": report.total_files,
}))
' 2>&1
    ) || exit_code=$?

    # If the python process itself failed (not just audit findings).
    if [[ -n "${exit_code:-}" ]] && [[ "${exit_code:-}" -ne 0 ]]; then
        _red "matt-audit: Python audit runner crashed (exit $exit_code)"
        echo "$output" >&2
        exit 2
    fi

    # Parse JSON output.
    local data
    data=$(echo "$output" | grep -E '^\s*\{' | head -1)

    if [[ -z "$data" ]]; then
        # Likely an import error or uninstalled django-matt.
        if echo "$output" | grep -q "is not installed"; then
            echo "matt-audit: django-matt not installed — skipping audit"
            exit 0
        fi
        echo "matt-audit: could not parse audit output, showing raw:"
        echo "$output" >&2
        exit 0
    fi

    # Check for explicit error.
    local err
    err=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("error",""))' 2>/dev/null || true)
    if [[ -n "$err" ]]; then
        _red "matt-audit: $err"
        exit 2
    fi

    # Extract counts per severity.
    local total critical_count high_count medium_count low_count info_count
    total=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["total"])')
    critical_count=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for f in d["findings"] if f["severity"]=="critical"))')
    high_count=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for f in d["findings"] if f["severity"]=="high"))')
    medium_count=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for f in d["findings"] if f["severity"]=="medium"))')
    low_count=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for f in d["findings"] if f["severity"]=="low"))')
    info_count=$(echo "$data" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(sum(1 for f in d["findings"] if f["severity"]=="info"))')

    # ---- summary ------------------------------------------------------------
    echo ""
    _bold "matt-audit — django-matt AI Code Audit"
    echo "  Level: $audit_level"
    echo "  Total findings: $total"
    echo ""

    local has_blocking=0

    # Display severity counts.
    if [[ "$critical_count" -gt 0 ]]; then
        _red    "  CRITICAL  $critical_count"
        has_blocking=1
    fi
    if [[ "$high_count" -gt 0 ]]; then
        _yellow "  HIGH      $high_count"
        if [[ "$fail_high" -eq 1 ]]; then
            has_blocking=1
        fi
    fi
    if [[ "$medium_count" -gt 0 ]]; then
        _yellow "  MEDIUM    $medium_count"
        if [[ "$fail_medium" -eq 1 ]]; then
            has_blocking=1
        fi
    fi
    if [[ "$low_count" -gt 0 ]]; then
        printf '  \033[34mLOW       %d\033[0m\n' "$low_count"
    fi
    if [[ "$info_count" -gt 0 ]]; then
        printf '  INFO      %d\033[0m\n' "$info_count"
    fi
    echo ""

    # If nothing to block on, we're done.
    if [[ "$has_blocking" -eq 0 ]]; then
        _green "  PASSED — no blocking findings"
        echo ""
        exit 0
    fi

    # ---- blocking findings detail -------------------------------------------
    _red "  FAILED — blocking findings:"
    echo ""

    echo "$data" | python3 -c '
import json, sys, os

fail_on = set(os.environ.get("MATT_AUDIT_FAIL_ON", "critical,high").split(","))
fail_on = {s.strip().lower() for s in fail_on}

data = json.load(sys.stdin)
for f in data["findings"]:
    if f["severity"] not in fail_on:
        continue
    loc = ""
    if f["file"]:
        loc = f["file"]
        if f["line"]:
            loc += ":" + str(f["line"])
    sev = f["severity"].upper()
    msg = f["message"]
    sug = ""
    if f.get("suggestion"):
        sug = "  → " + f["suggestion"]
    print(f"  [{f[\"id\"]}] {sev}  {loc}")
    print(f"       {msg}{sug}")
    print()
' MATT_AUDIT_FAIL_ON="$fail_on"

    # Block the commit.
    exit 1
}

# ---- entry point ------------------------------------------------------------
main() {
    local project_root
    project_root=$(_find_project_root)

    if [[ ! -d "$project_root" ]]; then
        _die "project root not found; set MATT_PROJECT_PATH"
    fi

    # Skip entirely if nothing to audit.
    if ! _has_python_changes; then
        echo "matt-audit: no staged Python changes — skipping"
        exit 0
    fi

    run_audit "$project_root"
}

main "$@"
