# Task Harness

An auditable long-running Agent Skill derived from the original
`kangarooking/task-harness` workflow.

Version 2 keeps the familiar root files while fixing the failure modes exposed
by real repository audits:

- revisioned, independently approved task amendments
- dependency-aware canonical task states with legacy `passes` projection
- executable verification and nonzero test discovery
- build tag/feature/platform matrices
- evidence-bound completion and independent second review
- structured blockers and regressions
- target responsibilities and reuse constraints to prevent parallel systems
- explicit authorization boundaries for install, commit, push, and production

## Layout

- `SKILL.md`: Agent workflow and strict rules
- `references/methodology.md`: design rationale and migration guidance
- `references/templates/`: v2 manifest, evidence, review, amendment, task, log,
  and initializer templates
- `references/examples/sub2api-migration.md`: real read-only migration case study
- `scripts/validate_harness.py`: dependency, path, criteria, evidence, review,
  and zero-test validator
- `tests/test_validate_harness.py`: validator regression tests

## Validate

```sh
python -m unittest discover -s tests -v
python scripts/validate_harness.py --root references/templates
```

Template targets are non-required placeholders so the unrendered template is
self-validating. A generated project must replace them with real paths, set
`required: true`, and validate with `--strict-paths`.

## License

MIT-0, matching the referenced original Skill.
