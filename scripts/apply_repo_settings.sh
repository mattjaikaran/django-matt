#!/usr/bin/env bash
# Apply .github/repo-settings.yml via gh cli.
#
# Requires: gh (authenticated), yq (for YAML parsing).
# Usage: scripts/apply_repo_settings.sh [owner/repo]
#
# If [owner/repo] is omitted, the script infers it from the current repo.

set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
SETTINGS_FILE=".github/repo-settings.yml"

if [[ ! -f "$SETTINGS_FILE" ]]; then
  echo "Missing $SETTINGS_FILE" >&2
  exit 1
fi

command -v yq >/dev/null || { echo "yq required (brew install yq)" >&2; exit 1; }
command -v gh >/dev/null || { echo "gh cli required (brew install gh)" >&2; exit 1; }

echo "Applying repo settings to $REPO"

DESCRIPTION=$(yq '.description' "$SETTINGS_FILE" | tr -d '\n' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//')
HOMEPAGE=$(yq '.homepage' "$SETTINGS_FILE")

gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --homepage "$HOMEPAGE" \
  --enable-issues="$(yq '.features.issues' "$SETTINGS_FILE")" \
  --enable-wiki="$(yq '.features.wiki' "$SETTINGS_FILE")" \
  --enable-discussions="$(yq '.features.discussions' "$SETTINGS_FILE")" \
  --enable-projects="$(yq '.features.projects' "$SETTINGS_FILE")" \
  --enable-squash-merge="$(yq '.merge_settings.allow_squash_merge' "$SETTINGS_FILE")" \
  --enable-merge-commit="$(yq '.merge_settings.allow_merge_commit' "$SETTINGS_FILE")" \
  --enable-rebase-merge="$(yq '.merge_settings.allow_rebase_merge' "$SETTINGS_FILE")" \
  --enable-auto-merge="$(yq '.merge_settings.allow_auto_merge' "$SETTINGS_FILE")" \
  --delete-branch-on-merge="$(yq '.merge_settings.delete_branch_on_merge' "$SETTINGS_FILE")"

# Topics: gh accepts repeated --add-topic flags. Replace the full set by
# clearing first (gh has no --clear, so diff + remove stale ones).
CURRENT_TOPICS=$(gh api "repos/$REPO/topics" -q '.names[]' 2>/dev/null || true)
DESIRED_TOPICS=$(yq '.topics[]' "$SETTINGS_FILE")

for topic in $CURRENT_TOPICS; do
  if ! grep -qx "$topic" <<<"$DESIRED_TOPICS"; then
    gh repo edit "$REPO" --remove-topic "$topic"
  fi
done
for topic in $DESIRED_TOPICS; do
  gh repo edit "$REPO" --add-topic "$topic"
done

echo
echo "Done. Topics:"
gh api "repos/$REPO/topics" -q '.names | join(", ")'

echo
echo "REMINDER: Social preview image must be uploaded manually via"
echo "  Settings → General → Social preview → Upload"
echo "Path: $(yq '.social_preview.path' "$SETTINGS_FILE")"
