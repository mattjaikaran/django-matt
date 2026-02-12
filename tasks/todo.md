# Django Matt — Active Tasks

## In Progress

- [ ] Add test coverage for `auth/` module (JWT, OAuth, SSO, Passkeys, RBAC, API keys)
- [ ] Add test coverage for `billing/` module (Stripe, PayPal, Polar, webhooks)
- [ ] Add test coverage for `multitenancy/` module (Organization, Team, Membership, isolation)

## Up Next

- [ ] Add test coverage for `views/` (CRUD views, APIViewSet)
- [ ] Add test coverage for `flags/` (feature flags, backends, rollout)
- [ ] Add test coverage for `analytics/` (tracker, backends, aggregations)
- [ ] Add test coverage for `experiments/` (A/B testing, bandits, analysis)
- [ ] Add test coverage for `graphql/` (schema gen, dataloaders, middleware)
- [ ] Add test coverage for `management/` commands
- [ ] Implement `/health/` endpoint (referenced in Dockerfile.prod but doesn't exist)
- [ ] Implement `matt routes`, `matt models`, `matt info`, `matt doctor` CLI commands (referenced in Makefile)

## Remaining Roadmap Items

- [ ] PlanetScale support (Stage 9B.6)
- [ ] Kubernetes/Helm charts (Stage 9C.3)
- [ ] vLLM / llama.cpp / LocalAI integrations (Stage 10C)
- [ ] Vue renderer (Stage 12D.4)
- [ ] Svelte renderer (Stage 12D.5)

## Done

- [x] Optimize CLAUDE.md (1,215 → 135 lines)
- [x] Fix CI — add pyright/twine deps, remove continue-on-error, fix Django constraint
- [x] Align pyproject.toml version targets to py312
- [x] Add .pre-commit-config.yaml
- [x] Rename claude.md → CLAUDE.md
