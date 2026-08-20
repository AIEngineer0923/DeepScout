# Contributing to DeepScout

Thank you for your interest in contributing to DeepScout.

## Prerequisites

- Git
- Docker (Phase 1+)
- Python 3.12+ and Node.js 20 LTS (Phase 1+)

No proprietary or maintainer-only tooling is required to contribute.

## Workflow

1. Fork or clone the repository
2. Create a topic branch from `main`
3. Make focused changes with tests where applicable
4. Run `bash scripts/scan-secrets.sh` before pushing
5. Open a pull request with a clear description and test plan

## Branch policy

- Do not push directly to `main`
- One logical unit of work per PR
- Keep diffs focused and reviewable

## Code quality

- Minimal, purposeful changes
- No secrets in Git, logs, traces, or test fixtures
- No silent placeholders presented as complete features
- Match existing conventions in each module

## Security

Report vulnerabilities per [SECURITY.md](SECURITY.md). Do not open public issues
for security bugs.

## License

By contributing, you agree that your contributions are licensed under the
Apache License 2.0.
