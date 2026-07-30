import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_harness.py"
SOURCE_REVISION = "sha256:" + "a" * 64
DIFF_DIGEST = "sha256:" + "b" * 64
STDOUT_DIGEST = "sha256:" + "c" * 64
STDERR_DIGEST = "sha256:" + "d" * 64
DEFAULT_VARIANT = {"name": "default", "build_tags": [], "features": []}


def base_manifest():
    return {
        "schema_version": "2.0",
        "revision": 1,
        "baseline": {"source_revision": SOURCE_REVISION},
        "verification_policy": {"zero_tests": "fail", "require_independent_review": True},
        "features": [{
            "id": "feat-01",
            "category": "foundation",
            "priority": 1,
            "description": "test",
            "status": "ready",
            "passes": False,
            "definition_revision": 1,
            "depends_on": [],
            "scope": {"include": ["behavior"], "exclude": []},
            "targets": [{
                "path": "existing.txt", "role": "implementation",
                "responsibility": "owner", "required": True,
            }],
            "steps": [{"id": "step-1", "action": "change", "expected_result": "works"}],
            "acceptance_criteria": [{"id": "ac-01", "description": "works"}],
            "verification": {"checks": [{
                "id": "unit", "kind": "test",
                "command": ["python", "-m", "unittest"], "cwd": ".",
                "timeout_seconds": 60, "criterion_ids": ["ac-01"],
                "minimum_tests_discovered": 1,
                "required_variants": [DEFAULT_VARIANT],
            }]},
            "reuse": {"fingerprint": "foundation:owner:works", "decision": "extend_existing"},
            "evidence": [], "reviews": [], "amendments": [],
        }],
    }


def task_digest(task):
    excluded = {"status", "passes", "evidence", "reviews", "amendments", "blocked_reason", "regression"}
    value = {key: item for key, item in task.items() if key not in excluded}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def amendment(task, base_manifest_revision=1, applied_manifest_revision=2):
    return {
        "task_id": task["id"], "decision": "approved",
        "base_definition_revision": task["definition_revision"] - 1,
        "applied_definition_revision": task["definition_revision"],
        "base_manifest_revision": base_manifest_revision,
        "applied_manifest_revision": applied_manifest_revision,
        "patch": [{"op": "replace", "path": f"/features/{task['id']}/description", "value": task["description"]}],
        "result_definition_digest": task_digest(task),
        "proposed_by": {"actor_id": "proposer", "session_id": "proposal-session"},
        "approved_by": {"actor_id": "approver", "session_id": "approval-session"},
    }


def evidence(discovered=1, **overrides):
    check = {
        "check_id": "unit", "kind": "test",
        "command": ["python", "-m", "unittest"], "cwd": ".", "timeout_seconds": 60,
        "criterion_ids": ["ac-01"], "exit_code": 0, "timed_out": False,
        "variant": DEFAULT_VARIANT,
        "tests": {"discovered": discovered, "passed": discovered, "failed": 0, "skipped": 0},
        "stdout_digest": STDOUT_DIGEST, "stderr_digest": STDERR_DIGEST,
        "output_excerpt": "tests passed", "result": "passed",
    }
    check.update(overrides.pop("check", {}))
    result = {
        "evidence_id": "ev-1", "task_id": "feat-01", "attempt_id": "att-1", "definition_revision": 1,
        "code_revision": {"source_revision": SOURCE_REVISION, "dirty": False, "diff_digest": DIFF_DIGEST},
        "executor": {"actor_id": "implementer", "session_id": "implementation-session"},
        "started_at": "2026-07-30T00:00:00Z", "finished_at": "2026-07-30T00:00:01Z",
        "checks": [check], "overall_result": "passed",
    }
    result.update(overrides)
    return result


def review(**overrides):
    result = {
        "review_id": "review-1", "reviewed_at": "2026-07-30T00:00:02Z",
        "task_id": "feat-01", "evidence_id": "ev-1", "definition_revision": 1,
        "reviewer": {"actor_id": "reviewer", "session_id": "review-session"},
        "decision": "approved", "findings": [],
        "checks": {
            "scope_matches": True, "criteria_covered": True,
            "tests_discovered_nonzero": True, "required_variants_covered": True,
            "no_parallel_system_created": True, "evidence_revision_current": True,
            "source_revision_current": True,
        },
    }
    result.update(overrides)
    return result


class ValidatorTests(unittest.TestCase):
    def run_validator(self, manifest, files=None, strict=True, outside_files=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "feature_list.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "existing.txt").write_text("owner", encoding="utf-8")
            for name, value in (files or {}).items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            for name, value in (outside_files or {}).items():
                path = root.parent / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--root", str(root), "--json"]
            if strict:
                command.append("--strict-paths")
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            return result, json.loads(result.stdout[result.stdout.index("{"):])

    def errors(self, manifest, files=None, outside_files=None):
        return self.run_validator(manifest, files, outside_files=outside_files)[1]["errors"]

    def awaiting_manifest(self):
        manifest = base_manifest()
        task = manifest["features"][0]
        task["status"] = "awaiting_review"
        task["evidence"] = [".task-harness/evidence/feat-01/att-1.json"]
        return manifest

    def passed_manifest(self):
        manifest = self.awaiting_manifest()
        task = manifest["features"][0]
        task["status"], task["passes"] = "passed", True
        task["reviews"] = [".task-harness/reviews/feat-01/review-1.json"]
        return manifest

    def test_ready_manifest_is_valid(self):
        result, diagnostics = self.run_validator(base_manifest())
        self.assertEqual(result.returncode, 0, diagnostics)

    def test_passes_must_project_status(self):
        manifest = base_manifest()
        manifest["features"][0]["passes"] = True
        self.assertTrue(any("passes_projection" in item for item in self.errors(manifest)))

    def test_dependency_cycle_fails(self):
        manifest = base_manifest()
        second = json.loads(json.dumps(manifest["features"][0]))
        second["id"], second["priority"] = "feat-02", 2
        second["reuse"]["fingerprint"] = "foundation:owner:other"
        manifest["features"][0]["depends_on"], second["depends_on"] = ["feat-02"], ["feat-01"]
        manifest["features"].append(second)
        self.assertTrue(any("dependency_cycle" in item for item in self.errors(manifest)))

    def test_plan_mismatch_cannot_bypass_zero_tests(self):
        manifest = self.awaiting_manifest()
        forged = evidence(0, check={"kind": "lint", "command": ["different"], "criterion_ids": ["wrong"]})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: forged})
        self.assertTrue(any("check_plan_mismatch" in item for item in errors))
        self.assertTrue(any("zero_tests" in item for item in errors))

    def test_all_required_variants_must_be_covered(self):
        manifest = self.awaiting_manifest()
        manifest["features"][0]["verification"]["checks"][0]["required_variants"].append(
            {"name": "unit-tag", "build_tags": ["unit"], "features": []})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: evidence()})
        self.assertTrue(any("variant_coverage" in item for item in errors))

    def test_stale_source_revision_fails(self):
        manifest = self.awaiting_manifest()
        stale = evidence(code_revision={"source_revision": "sha256:" + "e" * 64, "dirty": False, "diff_digest": DIFF_DIGEST})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: stale})
        self.assertTrue(any("source_revision" in item for item in errors))

    def test_review_checks_false_fails(self):
        manifest = self.passed_manifest()
        bad = review()
        bad["checks"]["criteria_covered"] = False
        files = {manifest["features"][0]["evidence"][0]: evidence(), manifest["features"][0]["reviews"][0]: bad}
        self.assertTrue(any("review_checks" in item for item in self.errors(manifest, files)))

    def test_review_requires_different_actor_and_session(self):
        for reviewer_id in (
            {"actor_id": "implementer", "session_id": "different"},
            {"actor_id": "different", "session_id": "implementation-session"},
        ):
            with self.subTest(reviewer=reviewer_id):
                manifest = self.passed_manifest()
                files = {
                    manifest["features"][0]["evidence"][0]: evidence(),
                    manifest["features"][0]["reviews"][0]: review(reviewer=reviewer_id),
                }
                self.assertTrue(any("review_not_independent" in item for item in self.errors(manifest, files)))

    def test_evidence_reference_traversal_fails(self):
        manifest = self.awaiting_manifest()
        manifest["features"][0]["evidence"] = ["../outside.json"]
        errors = self.errors(manifest, outside_files={"outside.json": evidence()})
        self.assertTrue(any("path_escape" in item for item in errors))

    def test_cwd_escape_fails(self):
        manifest = self.awaiting_manifest()
        escaped = evidence(check={"cwd": ".."})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: escaped})
        self.assertTrue(any("path_escape" in item for item in errors))

    def test_malformed_target_reports_diagnostic(self):
        manifest = base_manifest()
        manifest["features"][0]["targets"] = ["not-an-object"]
        errors = self.errors(manifest)
        self.assertTrue(any("target_type" in item for item in errors))
        self.assertFalse(any("validator_exception" in item for item in errors))

    def test_definition_revision_requires_amendment(self):
        manifest = base_manifest()
        manifest["features"][0]["definition_revision"] = 2
        self.assertTrue(any("missing_amendment" in item for item in self.errors(manifest)))

    def test_passed_task_requires_passed_dependencies(self):
        manifest = self.passed_manifest()
        dependency = json.loads(json.dumps(base_manifest()["features"][0]))
        dependency["id"], dependency["priority"] = "dep", 2
        dependency["reuse"]["fingerprint"] = "dep"
        manifest["features"][0]["depends_on"] = ["dep"]
        manifest["features"].append(dependency)
        files = {
            manifest["features"][0]["evidence"][0]: evidence(),
            manifest["features"][0]["reviews"][0]: review(),
        }
        self.assertTrue(any("unpassed_dependency" in item for item in self.errors(manifest, files)))

    def test_contradictory_test_counts_fail(self):
        manifest = self.awaiting_manifest()
        bad = evidence(check={"tests": {"discovered": 1, "passed": 0, "failed": 9, "skipped": 0}})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: bad})
        self.assertTrue(any("test_counts" in item for item in errors))

    def test_amendment_patch_must_match_current_definition(self):
        manifest = base_manifest()
        manifest["revision"] = 2
        task = manifest["features"][0]
        task["definition_revision"] = 2
        task["description"] = "current definition"
        task["amendments"] = [".task-harness/amendments/a.json"]
        bad = amendment(task)
        bad["patch"][0]["value"] = "unrelated approved value"
        errors = self.errors(manifest, {task["amendments"][0]: bad})
        self.assertTrue(any("amendment_patch" in item for item in errors))

    def test_amendment_cannot_modify_state(self):
        manifest = base_manifest()
        manifest["revision"] = 2
        task = manifest["features"][0]
        task["definition_revision"] = 2
        task["amendments"] = [".task-harness/amendments/a.json"]
        bad = amendment(task)
        bad["patch"] = [{"op": "replace", "path": "/features/feat-01/status", "value": "ready"}]
        errors = self.errors(manifest, {task["amendments"][0]: bad})
        self.assertTrue(any("protected state" in item for item in errors))

    def test_global_amendment_revision_chain_is_contiguous(self):
        manifest = base_manifest()
        manifest["revision"] = 3
        first = manifest["features"][0]
        first["definition_revision"] = 2
        first["amendments"] = [".task-harness/amendments/a.json"]
        second = json.loads(json.dumps(base_manifest()["features"][0]))
        second["id"], second["priority"], second["description"] = "feat-02", 2, "second"
        second["definition_revision"] = 2
        second["reuse"]["fingerprint"] = "second"
        second["amendments"] = [".task-harness/amendments/b.json"]
        manifest["features"].append(second)
        files = {
            first["amendments"][0]: amendment(first, 1, 2),
            second["amendments"][0]: amendment(second, 2, 3),
        }
        self.assertFalse(any("amendment_revision" in item for item in self.errors(manifest, files)))

    def test_placeholder_source_and_bad_digest_fail(self):
        manifest = self.awaiting_manifest()
        manifest["baseline"]["source_revision"] = "{{source}}"
        bad = evidence(code_revision={"source_revision": "{{source}}", "dirty": False, "diff_digest": "x"})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: bad})
        self.assertTrue(any("source_revision" in item for item in errors))
        self.assertTrue(any("source_digest" in item for item in errors))

    def test_missing_evidence_metadata_and_output_fail(self):
        manifest = self.awaiting_manifest()
        bad = evidence()
        for field in ("attempt_id", "started_at", "finished_at"):
            bad.pop(field)
        for field in ("stdout_digest", "stderr_digest", "output_excerpt"):
            bad["checks"][0].pop(field)
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: bad})
        self.assertTrue(any("evidence_metadata" in item for item in errors))
        self.assertTrue(any("evidence_output" in item for item in errors))

    def test_manifest_revision_requires_global_amendment_chain(self):
        manifest = base_manifest()
        manifest["revision"] = 2
        self.assertTrue(any("amendment_revision" in item for item in self.errors(manifest)))

    def test_boolean_test_counts_fail(self):
        manifest = self.awaiting_manifest()
        bad = evidence(check={"tests": {"discovered": True, "passed": True, "failed": False, "skipped": False}})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: bad})
        self.assertTrue(any("test_counts" in item or "zero_tests" in item for item in errors))

    def test_timeout_must_match_plan(self):
        manifest = self.awaiting_manifest()
        bad = evidence(check={"timeout_seconds": 999999})
        errors = self.errors(manifest, {manifest["features"][0]["evidence"][0]: bad})
        self.assertTrue(any("check_plan_mismatch" in item for item in errors))

    def test_review_metadata_is_required(self):
        manifest = self.passed_manifest()
        bad = review(reviewed_at=None)
        files = {
            manifest["features"][0]["evidence"][0]: evidence(),
            manifest["features"][0]["reviews"][0]: bad,
        }
        self.assertTrue(any("review_metadata" in item for item in self.errors(manifest, files)))

    def test_path_escape_fails(self):
        manifest = base_manifest()
        manifest["features"][0]["targets"][0]["path"] = "../escape.txt"
        self.assertTrue(any("path_escape" in item for item in self.errors(manifest)))


if __name__ == "__main__":
    unittest.main()
