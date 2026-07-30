#!/usr/bin/env python3
"""Validate a Task Harness v2 manifest and its evidence, review, and amendment records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

VALID_STATUSES = {
    "proposed", "ready", "in_progress", "blocked", "verification_failed",
    "awaiting_review", "review_rejected", "passed", "regressed",
    "superseded", "cancelled",
}
VALID_ROLES = {
    "entrypoint", "implementation", "test", "config", "schema", "migration",
    "generated", "documentation",
}
VALID_KINDS = {"test", "lint", "typecheck", "build", "static", "manual", "benchmark", "fuzz"}
REQUIRED_REVIEW_CHECKS = {
    "scope_matches", "criteria_covered", "tests_discovered_nonzero",
    "required_variants_covered", "no_parallel_system_created",
    "evidence_revision_current", "source_revision_current",
}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
PLACEHOLDER_RE = re.compile(r"^\s*(?:\{\{.*\}\}|<.*>|tbd|unknown)\s*$", re.IGNORECASE)


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def variant_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def definition_digest(task: dict[str, Any]) -> str:
    excluded = {"status", "passes", "evidence", "reviews", "amendments", "blocked_reason", "regression"}
    value = {key: item for key, item in task.items() if key not in excluded}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def get_patch_value(task: dict[str, Any], raw_path: Any) -> tuple[bool, Any]:
    """Resolve amendment paths that use stable IDs for task-owned arrays."""
    if not is_nonempty_string(raw_path) or not raw_path.startswith("/features/"):
        return False, None
    parts = [part.replace("~1", "/").replace("~0", "~") for part in raw_path.split("/")[1:]]
    if len(parts) < 3 or parts[1] != task.get("id"):
        return False, None
    current: Any = task
    for part in parts[2:]:
        if isinstance(current, dict):
            if part not in current:
                return False, None
            current = current[part]
        elif isinstance(current, list):
            matches = [item for item in current if is_object(item) and item.get("id") == part]
            if len(matches) != 1:
                return False, None
            current = matches[0]
        else:
            return False, None
    return True, current


class Validation:
    def __init__(self, root: Path, strict_paths: bool = False) -> None:
        self.root = root.resolve()
        self.strict_paths = strict_paths
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.manifest: dict[str, Any] = {}

    def error(self, code: str, message: str) -> None:
        self.errors.append(f"{code}: {message}")

    def warn(self, code: str, message: str) -> None:
        self.warnings.append(f"{code}: {message}")

    def load_json(self, path: Path, label: str) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.error("missing_file", f"{label} not found: {path}")
            return None
        except (OSError, json.JSONDecodeError) as exc:
            self.error("invalid_json", f"cannot read {label}: {exc}")
            return None
        if not is_object(value):
            self.error("invalid_type", f"{label} root must be an object")
            return None
        return value

    def safe_resolve(self, raw: Any, label: str, required_prefix: Path | None = None) -> Path | None:
        if not is_nonempty_string(raw):
            self.error("invalid_path", f"{label} must be a non-empty relative path")
            return None
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            self.error("path_escape", f"{label} escapes project root: {raw}")
            return None
        resolved = (self.root / path).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            self.error("path_escape", f"{label} resolves outside project: {raw}")
            return None
        if required_prefix is not None:
            prefix = (self.root / required_prefix).resolve()
            try:
                resolved.relative_to(prefix)
            except ValueError:
                self.error("path_namespace", f"{label} must be below {required_prefix.as_posix()}: {raw}")
                return None
        return resolved

    def validate_target(self, target: Any, task_id: str, index: int) -> None:
        if not is_object(target):
            self.error("target_type", f"{task_id} target #{index} must be an object")
            return
        if target.get("role") not in VALID_ROLES:
            self.error("target_role", f"{task_id} target #{index} has invalid role {target.get('role')}")
        if not is_nonempty_string(target.get("responsibility")):
            self.error("target_responsibility", f"{task_id} target #{index} lacks responsibility")
        path = self.safe_resolve(target.get("path"), f"{task_id} target #{index}")
        if path is not None and target.get("required", True) and not path.exists():
            message = f"{task_id} required target does not exist: {target.get('path')}"
            if self.strict_paths:
                self.error("missing_target", message)
            else:
                self.warn("missing_target", message)

    def validate_identity(self, identity: Any, label: str) -> bool:
        if not is_object(identity):
            self.error("identity", f"{label} must be an object")
            return False
        valid = True
        for field in ("actor_id", "session_id"):
            value = identity.get(field)
            if not is_nonempty_string(value) or PLACEHOLDER_RE.match(value):
                self.error("identity", f"{label}.{field} must be a concrete non-placeholder value")
                valid = False
        return valid

    def validate_evidence(self, ref: str, task: dict[str, Any]) -> dict[str, Any] | None:
        task_id = task["id"]
        prefix = Path(".task-harness") / "evidence" / task_id
        path = self.safe_resolve(ref, f"{task_id} evidence reference", prefix)
        if path is None:
            return None
        evidence = self.load_json(path, f"evidence {ref}")
        if evidence is None:
            return None
        if evidence.get("task_id") != task_id:
            self.error("evidence_task", f"{ref} belongs to {evidence.get('task_id')}, not {task_id}")
        if evidence.get("definition_revision") != task.get("definition_revision"):
            self.error("stale_evidence", f"{ref} does not match {task_id} definition revision")
        if not is_nonempty_string(evidence.get("attempt_id")):
            self.error("evidence_metadata", f"{ref} lacks attempt_id")
        for field in ("started_at", "finished_at"):
            if not is_nonempty_string(evidence.get(field)):
                self.error("evidence_metadata", f"{ref} lacks {field}")
        self.validate_identity(evidence.get("executor"), f"{ref} executor")
        if not is_nonempty_string(evidence.get("attempt_id")):
            self.error("evidence_metadata", f"{ref} lacks attempt_id")
        for field in ("started_at", "finished_at"):
            if not is_nonempty_string(evidence.get(field)):
                self.error("evidence_metadata", f"{ref} lacks {field}")

        baseline_revision = self.manifest.get("baseline", {}).get("source_revision")
        if not is_nonempty_string(baseline_revision) or PLACEHOLDER_RE.match(baseline_revision) or not SHA256_RE.match(baseline_revision):
            self.error("source_revision", "manifest baseline source_revision must be a sha256 workspace/source fingerprint")
        code_revision = evidence.get("code_revision")
        if not is_object(code_revision):
            self.error("source_revision", f"{ref} lacks code_revision")
        else:
            if code_revision.get("source_revision") != baseline_revision:
                self.error("source_revision", f"{ref} source revision does not match manifest baseline")
            if code_revision.get("dirty") is not False:
                self.error("source_dirty", f"{ref} must bind a clean source revision; record a workspace fingerprint instead")
            if not is_nonempty_string(code_revision.get("diff_digest")) or not SHA256_RE.match(code_revision.get("diff_digest", "")):
                self.error("source_digest", f"{ref} requires a sha256 diff_digest")

        plan_checks_raw = task.get("verification", {}).get("checks", [])
        plan_checks = {check["id"]: check for check in plan_checks_raw if is_object(check) and is_nonempty_string(check.get("id"))}
        evidence_checks = evidence.get("checks")
        if not isinstance(evidence_checks, list) or not evidence_checks:
            self.error("evidence_checks", f"{ref} has no checks")
            return evidence

        grouped: dict[str, list[dict[str, Any]]] = {}
        for index, check in enumerate(evidence_checks, 1):
            if not is_object(check):
                self.error("evidence_check_type", f"{ref} check #{index} must be an object")
                continue
            check_id = check.get("check_id")
            if check_id not in plan_checks:
                self.error("unknown_check", f"{ref} contains unknown check {check_id}")
                continue
            grouped.setdefault(check_id, []).append(check)

        for check_id, plan in plan_checks.items():
            records = grouped.get(check_id, [])
            if not records:
                self.error("missing_checks", f"{ref} misses required check {check_id}")
                continue
            required_variants = plan.get("required_variants", [])
            required_keys = {variant_key(item) for item in required_variants}
            actual_keys: set[str] = set()
            for check in records:
                for field in ("kind", "command", "cwd", "criterion_ids", "timeout_seconds"):
                    if check.get(field) != plan.get(field):
                        self.error("check_plan_mismatch", f"{ref} check {check_id} {field} differs from verification plan")
                cwd = self.safe_resolve(check.get("cwd"), f"{ref} check {check_id} cwd")
                if cwd is not None and not cwd.is_dir():
                    self.error("cwd_missing", f"{ref} check {check_id} cwd does not exist")
                if check.get("exit_code") != 0 or check.get("result") != "passed" or check.get("timed_out") is not False:
                    self.error("failed_check", f"{ref} check {check_id} did not pass")
                actual_keys.add(variant_key(check.get("variant")))
                for digest_field in ("stdout_digest", "stderr_digest"):
                    digest = check.get(digest_field)
                    if not is_nonempty_string(digest) or not SHA256_RE.match(digest):
                        self.error("evidence_output", f"{ref} check {check_id} requires sha256 {digest_field}")
                if not is_nonempty_string(check.get("output_excerpt")):
                    self.error("evidence_output", f"{ref} check {check_id} lacks output_excerpt")
                if plan.get("kind") == "test":
                    tests = check.get("tests")
                    discovered = tests.get("discovered") if is_object(tests) else None
                    minimum = plan.get("minimum_tests_discovered", 1)
                    if type(discovered) is not int or discovered < minimum:
                        self.error("zero_tests", f"{ref} check {check_id} discovered {discovered}; requires {minimum}")
                    if not is_object(tests) or any(type(tests.get(name)) is not int or tests.get(name, -1) < 0 for name in ("discovered", "passed", "failed", "skipped")):
                        self.error("test_counts", f"{ref} check {check_id} has invalid test counts")
                    elif tests["discovered"] != tests["passed"] + tests["failed"] + tests["skipped"] or tests["failed"] != 0:
                        self.error("test_counts", f"{ref} check {check_id} test counts are contradictory or failed")
            if required_keys != actual_keys:
                self.error("variant_coverage", f"{ref} check {check_id} variants do not exactly cover the plan")
            if len(records) != len(actual_keys):
                self.error("duplicate_variant", f"{ref} check {check_id} repeats a variant")

        if evidence.get("overall_result") != "passed":
            self.error("evidence_result", f"{ref} overall_result is not passed")
        return evidence

    def validate_review(self, ref: str, task: dict[str, Any], evidence: dict[str, Any]) -> bool:
        task_id = task["id"]
        prefix = Path(".task-harness") / "reviews" / task_id
        path = self.safe_resolve(ref, f"{task_id} review reference", prefix)
        if path is None:
            return False
        review = self.load_json(path, f"review {ref}")
        if review is None:
            return False
        if not is_nonempty_string(review.get("review_id")) or PLACEHOLDER_RE.match(review.get("review_id", "")):
            self.error("review_metadata", f"{ref} lacks a concrete review_id")
            return False
        if not is_nonempty_string(review.get("reviewed_at")) or PLACEHOLDER_RE.match(review.get("reviewed_at", "")):
            self.error("review_metadata", f"{ref} lacks a concrete reviewed_at timestamp")
            return False
        if review.get("task_id") != task_id or review.get("evidence_id") != evidence.get("evidence_id"):
            self.error("review_binding", f"{ref} does not bind the current task and evidence")
            return False
        if review.get("definition_revision") != task.get("definition_revision"):
            self.error("stale_review", f"{ref} does not match the task definition revision")
            return False
        implementer = evidence.get("executor", {})
        reviewer = review.get("reviewer")
        reviewer_valid = self.validate_identity(reviewer, f"{ref} reviewer")
        if reviewer_valid and (
            implementer.get("actor_id") == reviewer.get("actor_id") or
            implementer.get("session_id") == reviewer.get("session_id")
        ):
            self.error("review_not_independent", f"{ref} reviewer must use a different actor and session")
            return False
        checks = review.get("checks")
        if not is_object(checks) or any(checks.get(name) is not True for name in REQUIRED_REVIEW_CHECKS):
            self.error("review_checks", f"{ref} does not affirm every required review check")
            return False
        findings = review.get("findings")
        if not isinstance(findings, list):
            self.error("review_findings", f"{ref} findings must be an array")
            return False
        unresolved = [item for item in findings if not is_object(item) or item.get("status") not in {"resolved", "accepted_risk"}]
        if unresolved:
            self.error("review_findings", f"{ref} has unresolved findings")
            return False
        if review.get("decision") != "approved":
            self.error("review_rejected", f"{ref} decision is {review.get('decision')}")
            return False
        return True

    def validate_amendments(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        refs = task.get("amendments", [])
        if not isinstance(refs, list):
            self.error("amendments", f"{task_id} amendments must be an array")
            return
        if task.get("definition_revision", 1) > 1 and not refs:
            self.error("missing_amendment", f"{task_id} revision > 1 requires amendment history")
        expected_definition_revision = 1
        for ref in refs:
            prefix = Path(".task-harness") / "amendments"
            path = self.safe_resolve(ref, f"{task_id} amendment reference", prefix)
            if path is None:
                continue
            amendment = self.load_json(path, f"amendment {ref}")
            if amendment is None:
                continue
            if amendment.get("task_id") != task_id or amendment.get("decision") != "approved":
                self.error("amendment_binding", f"{ref} is not an approved amendment for {task_id}")
            proposer = amendment.get("proposed_by")
            approver = amendment.get("approved_by")
            proposer_valid = self.validate_identity(proposer, f"{ref} proposer")
            approver_valid = self.validate_identity(approver, f"{ref} approver")
            if proposer_valid and approver_valid and (
                proposer.get("actor_id") == approver.get("actor_id") or
                proposer.get("session_id") == approver.get("session_id")
            ):
                self.error("amendment_not_independent", f"{ref} proposer and approver must differ")
            if amendment.get("base_definition_revision") != expected_definition_revision:
                self.error("amendment_revision", f"{ref} base definition revision is not sequential")
            if amendment.get("applied_definition_revision") != expected_definition_revision + 1:
                self.error("amendment_revision", f"{ref} applied definition revision is not sequential")
            patch = amendment.get("patch")
            if not isinstance(patch, list) or not patch:
                self.error("amendment_patch", f"{ref} requires a non-empty patch")
            else:
                forbidden = {"status", "passes", "evidence", "reviews", "amendments", "blocked_reason", "regression", "definition_revision"}
                for operation in patch:
                    if not is_object(operation) or operation.get("op") not in {"replace", "add"}:
                        self.error("amendment_patch", f"{ref} contains an unsupported patch operation")
                        continue
                    raw_path = operation.get("path")
                    parts = raw_path.split("/") if is_nonempty_string(raw_path) else []
                    if any(part in forbidden for part in parts):
                        self.error("amendment_patch", f"{ref} patch modifies protected state")
                        continue
                    found, current_value = get_patch_value(task, raw_path)
                    if not found or current_value != operation.get("value"):
                        self.error("amendment_patch", f"{ref} patch does not match the current {task_id} definition")
            result_digest = amendment.get("result_definition_digest")
            if not is_nonempty_string(result_digest) or result_digest != definition_digest(task):
                self.error("amendment_digest", f"{ref} result definition digest does not match {task_id}")
            expected_definition_revision += 1
        if refs and expected_definition_revision != task.get("definition_revision"):
            self.error("amendment_revision", f"{task_id} amendment chain does not reach current definition revision")

    def validate_feature(self, task: Any, feature_map: dict[str, dict[str, Any]]) -> None:
        if not is_object(task):
            self.error("feature_type", "every feature must be an object")
            return
        task_id = task.get("id")
        if not is_nonempty_string(task_id):
            self.error("feature_id", "every feature needs a non-empty id")
            return
        for field in ("category", "description"):
            if not is_nonempty_string(task.get(field)):
                self.error("feature_field", f"{task_id} needs a non-empty {field}")
        if not isinstance(task.get("priority"), int):
            self.error("priority", f"{task_id} priority must be an integer")
        status = task.get("status")
        if status not in VALID_STATUSES:
            self.error("status", f"{task_id} has invalid status {status}")
        if task.get("passes") is not (status == "passed"):
            self.error("passes_projection", f"{task_id} passes must equal (status == passed)")
        if not isinstance(task.get("definition_revision"), int) or task.get("definition_revision", 0) < 1:
            self.error("definition_revision", f"{task_id} needs a positive definition_revision")
        dependencies = task.get("depends_on")
        if not isinstance(dependencies, list) or any(not is_nonempty_string(item) for item in dependencies):
            self.error("depends_on", f"{task_id} depends_on must be a string array")
            dependencies = []
        for dependency in dependencies:
            if dependency not in feature_map:
                self.error("missing_dependency", f"{task_id} depends on unknown task {dependency}")

        targets = task.get("targets")
        if not isinstance(targets, list) or not targets:
            self.error("targets", f"{task_id} must declare targets")
        else:
            for index, target in enumerate(targets, 1):
                self.validate_target(target, task_id, index)
        if not isinstance(task.get("scope"), dict):
            self.error("scope", f"{task_id} must declare scope")
        if not isinstance(task.get("steps"), list) or not task.get("steps"):
            self.error("steps", f"{task_id} must declare steps")

        criteria = task.get("acceptance_criteria")
        criterion_ids: set[str] = set()
        if not isinstance(criteria, list) or not criteria:
            self.error("criteria", f"{task_id} acceptance criteria must be a non-empty array")
        else:
            for criterion in criteria:
                if not is_object(criterion) or not is_nonempty_string(criterion.get("id")):
                    self.error("criteria", f"{task_id} acceptance criteria need IDs")
                    continue
                if criterion["id"] in criterion_ids:
                    self.error("criteria", f"{task_id} repeats criterion {criterion['id']}")
                criterion_ids.add(criterion["id"])

        verification = task.get("verification")
        checks = verification.get("checks") if is_object(verification) else None
        check_ids: set[str] = set()
        covered: set[str] = set()
        if not isinstance(checks, list) or not checks:
            self.error("verification", f"{task_id} must declare executable verification checks")
            checks = []
        for check in checks:
            if not is_object(check):
                self.error("check_type", f"{task_id} verification checks must be objects")
                continue
            check_id = check.get("id")
            if not is_nonempty_string(check_id) or check_id in check_ids:
                self.error("check_id", f"{task_id} verification check IDs must be unique")
                continue
            check_ids.add(check_id)
            if check.get("kind") not in VALID_KINDS:
                self.error("check_kind", f"{task_id}/{check_id} has invalid kind")
            command = check.get("command")
            if not isinstance(command, list) or not command or any(not is_nonempty_string(item) for item in command):
                self.error("verification_command", f"{task_id}/{check_id} command must be a non-empty argv array")
            self.safe_resolve(check.get("cwd"), f"{task_id}/{check_id} cwd")
            if not isinstance(check.get("timeout_seconds"), int) or check.get("timeout_seconds", 0) <= 0:
                self.error("timeout", f"{task_id}/{check_id} needs a positive timeout_seconds")
            bindings = check.get("criterion_ids")
            if not isinstance(bindings, list) or any(item not in criterion_ids for item in bindings):
                self.error("criterion_binding", f"{task_id}/{check_id} binds unknown or invalid criteria")
            else:
                covered.update(bindings)
            variants = check.get("required_variants")
            if not isinstance(variants, list) or not variants or any(not is_object(item) for item in variants):
                self.error("variants", f"{task_id}/{check_id} requires a non-empty variant matrix")
            elif len({variant_key(item) for item in variants}) != len(variants):
                self.error("variants", f"{task_id}/{check_id} repeats a required variant")
            if check.get("kind") == "test" and (not isinstance(check.get("minimum_tests_discovered"), int) or check.get("minimum_tests_discovered", 0) < 1):
                self.error("zero_test_policy", f"{task_id}/{check_id} must require at least one test")
        missing_criteria = criterion_ids - covered
        if missing_criteria:
            self.error("criteria_uncovered", f"{task_id} criteria lack checks: {sorted(missing_criteria)}")
        reuse = task.get("reuse")
        if not is_object(reuse) or reuse.get("decision") not in {"reuse", "extend_existing", "extend_via_amendment", "supersede", "create_with_justification"}:
            self.error("reuse", f"{task_id} needs an explicit reuse decision")
        if status == "blocked" and not is_object(task.get("blocked_reason")):
            self.error("blocked_reason", f"{task_id} is blocked without structured blocked_reason")
        self.validate_amendments(task)

    def validate(self) -> None:
        manifest = self.load_json(self.root / "feature_list.json", "feature_list.json")
        if manifest is None:
            return
        self.manifest = manifest
        if manifest.get("schema_version") != "2.0":
            self.error("schema_version", "feature_list.json must use schema_version 2.0")
        if not isinstance(manifest.get("revision"), int) or manifest.get("revision", 0) < 1:
            self.error("revision", "manifest revision must be a positive integer")
        baseline = manifest.get("baseline")
        if not is_object(baseline) or not is_nonempty_string(baseline.get("source_revision")):
            self.error("baseline", "manifest baseline needs a concrete source_revision")
        policy = manifest.get("verification_policy")
        if not is_object(policy) or policy.get("zero_tests") != "fail" or policy.get("require_independent_review") is not True:
            self.error("verification_policy", "manifest must require zero-test failure and independent review")
        features = manifest.get("features")
        if not isinstance(features, list) or not features:
            self.error("features", "features must be a non-empty array")
            return
        ids = [item.get("id") for item in features if is_object(item)]
        if len(ids) != len(features) or any(not is_nonempty_string(item) for item in ids) or len(set(ids)) != len(ids):
            self.error("duplicate_id", "feature IDs must be present and unique")
            return
        feature_map = {item["id"]: item for item in features}
        priorities = [item.get("priority") for item in features]
        if all(isinstance(item, int) for item in priorities) and len(set(priorities)) != len(priorities):
            self.error("duplicate_priority", "feature priorities must be unique")
        for task in features:
            self.validate_feature(task, feature_map)

        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(task_id: str) -> None:
            if task_id in visiting:
                self.error("dependency_cycle", f"dependency cycle includes {task_id}")
                return
            if task_id in visited:
                return
            visiting.add(task_id)
            dependencies = feature_map[task_id].get("depends_on", [])
            if isinstance(dependencies, list):
                for dependency in dependencies:
                    if dependency in feature_map:
                        visit(dependency)
            visiting.remove(task_id)
            visited.add(task_id)
        for task_id in feature_map:
            visit(task_id)

        fingerprints: dict[str, str] = {}
        amendments: list[dict[str, Any]] = []
        seen_amendment_refs: set[str] = set()
        for task in features:
            for ref in task.get("amendments", []) if isinstance(task.get("amendments"), list) else []:
                if ref in seen_amendment_refs:
                    self.error("amendment_duplicate", f"amendment reference is reused: {ref}")
                    continue
                seen_amendment_refs.add(ref)
                path = self.safe_resolve(ref, f"global amendment {ref}", Path(".task-harness") / "amendments")
                if path is not None:
                    value = self.load_json(path, f"amendment {ref}")
                    if value is not None:
                        amendments.append(value)
        ordered_amendments = sorted(amendments, key=lambda item: item.get("base_manifest_revision", -1))
        expected_manifest_revision = 1
        for amendment in ordered_amendments:
            if amendment.get("base_manifest_revision") != expected_manifest_revision or amendment.get("applied_manifest_revision") != expected_manifest_revision + 1:
                self.error("amendment_revision", f"global amendment chain breaks at manifest revision {expected_manifest_revision}")
            expected_manifest_revision += 1
        if expected_manifest_revision != manifest.get("revision"):
            self.error("amendment_revision", "global amendment chain does not reach current manifest revision")

        for task_id, task in feature_map.items():
            reuse = task.get("reuse", {})
            fingerprint = reuse.get("fingerprint") if is_object(reuse) else None
            if is_nonempty_string(fingerprint) and fingerprint in fingerprints:
                self.error("duplicate_fingerprint", f"{task_id} duplicates {fingerprints[fingerprint]} fingerprint")
            elif is_nonempty_string(fingerprint):
                fingerprints[fingerprint] = task_id

        evidence_ids: set[str] = set()
        for task in features:
            if task.get("status") not in {"awaiting_review", "passed"}:
                continue
            refs = task.get("evidence")
            if not isinstance(refs, list) or len(refs) != 1:
                self.error("missing_evidence", f"{task['id']} requires exactly one complete current evidence record")
                continue
            evidence = self.validate_evidence(refs[0], task)
            if evidence is None:
                continue
            evidence_id = evidence.get("evidence_id")
            if not is_nonempty_string(evidence_id) or evidence_id in evidence_ids:
                self.error("evidence_id", f"{task['id']} evidence ID must be unique")
            else:
                evidence_ids.add(evidence_id)
            if task.get("status") == "passed":
                unpassed_dependencies = [dependency for dependency in task.get("depends_on", []) if feature_map[dependency].get("status") != "passed"]
                if unpassed_dependencies:
                    self.error("unpassed_dependency", f"{task['id']} passed while dependencies are not passed: {unpassed_dependencies}")
                reviews = task.get("reviews")
                if not isinstance(reviews, list) or len(reviews) != 1:
                    self.error("missing_review", f"{task['id']} passed without exactly one current independent review")
                elif not self.validate_review(reviews[0], task, evidence):
                    self.error("invalid_review", f"{task['id']} has no valid approval")

        counts = Counter(task.get("status") for task in features if is_object(task))
        print("Task Harness validation summary")
        print(f"  tasks: {len(features)}")
        print("  status: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="project root containing feature_list.json")
    parser.add_argument("--strict-paths", action="store_true", help="treat missing required targets as errors")
    parser.add_argument("--json", action="store_true", help="emit diagnostics as JSON")
    args = parser.parse_args()
    validation = Validation(Path(args.root), strict_paths=args.strict_paths)
    try:
        validation.validate()
    except Exception as exc:  # malformed inputs must produce a diagnostic, not a traceback
        validation.error("validator_exception", f"unexpected validation failure: {type(exc).__name__}: {exc}")
    if args.json:
        print(json.dumps({"errors": validation.errors, "warnings": validation.warnings}, ensure_ascii=False, indent=2))
    else:
        for warning in validation.warnings:
            print(f"WARNING {warning}", file=sys.stderr)
        for error in validation.errors:
            print(f"ERROR {error}", file=sys.stderr)
    return 2 if validation.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
