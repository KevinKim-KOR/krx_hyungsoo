"""임시 Git 저장소만 사용하는 검증 도구·훅 시험."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import verify_scope as scope

TOOL_ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    "krx_verify_hook", TOOL_ROOT / ".codex/hooks/krx_verify.py"
)
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


class VerificationToolsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="krx-verify-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.storage = self.directory / "evidence"
        self.path = scope.record_path(self.repo, "session-a", self.storage)
        self.command("init", "-q")
        self.command("config", "user.name", "검증 도구 시험")
        self.command("config", "user.email", "verify-test@example.invalid")
        self.command("config", "core.hooksPath", str(self.directory / "empty-hooks"))
        self.write("app/example.py", "answer = 1\n")
        self.write("docs/result.md", "줄 수: 1\n")
        self.command("add", "app/example.py", "docs/result.md")
        self.command("commit", "-qm", "시험용 기준")

    def command(self, *arguments):
        subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            check=True,
            capture_output=True,
            timeout=10,
        )

    def write(self, relative, text):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def begin(self):
        return scope.start(self.repo, self.path, ["docs/result.md"])

    def stop(self, message="종합 판정: VERIFIED", **extra):
        payload = {
            "hook_event_name": "Stop",
            "session_id": "session-a",
            "cwd": str(self.repo),
            "last_assistant_message": message,
            "stop_hook_active": False,
        }
        payload.update(extra)
        return hook.evaluate(payload, self.repo, self.storage)

    def test_staged_and_worktree_are_measured_separately(self):
        self.write("app/example.py", "answer = 2\n")
        self.command("add", "app/example.py")
        self.write("app/example.py", "answer = 3\n")
        record = self.begin()
        facts = record["snapshot"]["files"]["app/example.py"]
        self.assertEqual(facts["status"], "MM")
        self.assertEqual(facts["file"]["lines"], 1)
        self.assertTrue(facts["index"])
        self.assertEqual(
            record["snapshot"]["totals"], {"staged": 1, "unstaged": 1, "untracked": 0}
        )

    def test_clean_source_becoming_modified_is_detected(self):
        self.begin()
        self.write("app/example.py", "answer = 2\n")
        self.assertEqual(scope.check(self.repo, self.path)[2], ["app/example.py"])
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED")

    def test_only_staging_changes_also_invalidate_the_scope(self):
        self.write("app/example.py", "answer = 2\n")
        self.begin()
        self.command("add", "app/example.py")
        self.assertEqual(scope.check(self.repo, self.path)[2], ["app/example.py"])

    def test_head_change_is_detected(self):
        self.begin()
        self.command("commit", "--allow-empty", "-qm", "시험 HEAD 변경")
        self.assertIn("HEAD 변경", scope.check(self.repo, self.path)[2])

    def test_new_untracked_source_is_detected(self):
        self.begin()
        self.write("app/new.py", "answer = 2\n")
        self.assertEqual(scope.check(self.repo, self.path)[2], ["app/new.py"])

    def test_rename_with_spaces_keeps_destination_and_origin(self):
        self.command("mv", "app/example.py", "app/renamed file.py")
        snapshot = self.begin()["snapshot"]
        self.assertEqual(
            snapshot["files"]["app/renamed file.py"]["from"], "app/example.py"
        )
        self.assertEqual(snapshot["totals"]["staged"], 1)

    def test_tracked_deletion_is_included(self):
        self.command("rm", "app/example.py")
        self.assertTrue(
            self.begin()["snapshot"]["files"]["app/example.py"]["file"]["deleted"]
        )

    def test_line_count_uses_wc_l_convention(self):
        self.write("app/example.py", "first\nsecond")
        self.assertEqual(
            self.begin()["snapshot"]["files"]["app/example.py"]["file"]["lines"], 1
        )

    def test_document_correction_is_explicitly_accepted(self):
        self.begin()
        self.write("docs/result.md", "줄 수: 2\n")
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED")
        record = scope.finish(
            self.repo, self.path, "VERIFIED", ["docs/result.md"], "줄 수 실측 정정"
        )
        self.assertEqual(
            record["doc_corrections"], {"docs/result.md": "줄 수 실측 정정"}
        )
        self.assertEqual(scope.check(self.repo, self.path)[2], [])

    def test_document_correction_cannot_accept_code(self):
        self.write("app/example.py", "answer = 2\n")
        self.begin()
        self.write("app/example.py", "answer = 3\n")
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED", ["app/example.py"], "정정")

    def test_document_correction_requires_reason(self):
        self.begin()
        self.write("docs/result.md", "줄 수: 2\n")
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED", ["docs/result.md"])

    def test_new_document_is_not_an_existing_document_correction(self):
        self.begin()
        self.write("docs/new.md", "새 문서\n")
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED", ["docs/new.md"], "정정")

    def test_document_deletion_cannot_be_accepted(self):
        self.begin()
        self.command("rm", "docs/result.md")
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED", ["docs/result.md"], "정정")

    def test_active_record_cannot_be_silently_overwritten(self):
        self.begin()
        with self.assertRaises(scope.ScopeError):
            self.begin()
        scope.finish(self.repo, self.path, "BLOCKED")
        self.assertEqual(self.begin()["phase"], "verifying")

    def test_no_record_and_missing_input_are_explicit_errors(self):
        with self.assertRaises(scope.ScopeError):
            scope.check(self.repo, self.path)
        with self.assertRaises(scope.ScopeError):
            scope.start(self.repo, self.path, ["docs/missing.md"])
        with self.assertRaises(scope.ScopeError):
            scope.start(self.repo, self.path, [])

    def test_live_and_user_files_are_never_opened(self):
        forbidden = [
            "state/live.sqlite",
            "logs/runtime.log",
            "znotes/note.txt",
            ".env",
            scope.USER_DOCUMENT,
        ]
        for name in forbidden:
            self.write(name, "읽으면 안 되는 시험 값\n")
        original = Path.read_bytes

        def guarded_read(path):
            if path.relative_to(self.repo).as_posix() in forbidden:
                raise AssertionError("금지 파일 내용 접근")
            return original(path)

        with patch.object(Path, "read_bytes", guarded_read):
            record = self.begin()
        for name in forbidden:
            self.assertNotIn(name, record["snapshot"]["files"])
        self.assertEqual(record["snapshot"]["problems"], [])

    def test_changed_tracked_live_file_blocks_pass_without_reading_it(self):
        self.write("state/fixture.txt", "원본\n")
        self.command("add", "state/fixture.txt")
        self.command("commit", "-qm", "시험 추적 파일")
        self.write("state/fixture.txt", "변경\n")
        self.assertTrue(self.begin()["snapshot"]["problems"])
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED")

    def test_user_owned_document_in_index_blocks_pass_without_reading_it(self):
        self.write(scope.USER_DOCUMENT, "사용자 소유 시험 문서\n")
        self.command("add", scope.USER_DOCUMENT)
        original = Path.read_bytes

        def guarded_read(path):
            if path == self.repo / scope.USER_DOCUMENT:
                raise AssertionError("사용자 문서 내용 접근")
            return original(path)

        with patch.object(Path, "read_bytes", guarded_read):
            self.assertTrue(self.begin()["snapshot"]["problems"])
            with self.assertRaises(scope.ScopeError):
                scope.finish(self.repo, self.path, "VERIFIED")

    def test_forbidden_input_and_traversal_are_refused(self):
        for name in (".env", scope.USER_DOCUMENT, "../outside.md", "/etc/passwd"):
            with self.subTest(name=name), self.assertRaises(scope.ScopeError):
                scope.start(self.repo, self.path, [name])

    @unittest.skipIf(os.name == "nt", "Windows 심볼릭 링크 생성 권한에 의존하지 않음")
    def test_symlink_file_and_directory_do_not_expose_the_target(self):
        secret = self.directory / "secret.txt"
        secret.write_text("읽으면 안 됨", encoding="utf-8")
        (self.repo / "app/link.py").symlink_to(secret)
        (self.repo / "linked").symlink_to(self.directory, target_is_directory=True)
        self.assertIn("problem", scope.file_facts(self.repo, "app/link.py"))
        self.assertIn("problem", scope.file_facts(self.repo, "linked/secret.txt"))

    def test_private_evidence_is_outside_repo_and_session_scoped(self):
        self.begin()
        other = scope.record_path(self.repo, "session-b", self.storage)
        self.assertIsNone(scope.read_record(other))
        self.assertFalse(self.path.is_relative_to(self.repo))
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(scope.ScopeError):
            scope.record_path(self.repo, "session-a", self.repo / "evidence")
        with self.assertRaises(scope.ScopeError):
            scope.record_path(self.repo, "", self.storage)

    def test_corrupt_record_is_not_treated_as_missing(self):
        self.begin()
        self.path.write_text("invalid-json", encoding="utf-8")
        with self.assertRaises(scope.ScopeError):
            scope.read_record(self.path)

    def test_structurally_invalid_json_is_not_accepted(self):
        self.begin()
        self.path.write_text('{"phase":"verifying","inputs":[]}', encoding="utf-8")
        with self.assertRaises(scope.ScopeError):
            scope.read_record(self.path)

    def test_untracked_source_is_reported_as_not_deliverable(self):
        self.write("app/new.py", "answer = 2\n")
        self.assertIn("Git 비추적", " ".join(self.begin()["snapshot"]["problems"]))
        with self.assertRaises(scope.ScopeError):
            scope.finish(self.repo, self.path, "VERIFIED")

    def test_unresolved_merge_cannot_be_recorded_as_verified(self):
        original = scope.git

        def with_conflict(repo, *args):
            if args[:1] == ("status",):
                return "UU app/example.py\0"
            return original(repo, *args)

        with patch.object(scope, "git", with_conflict):
            self.assertIn("병합 충돌", " ".join(self.begin()["snapshot"]["problems"]))
            with self.assertRaises(scope.ScopeError):
                scope.finish(self.repo, self.path, "VERIFIED")

    def test_configured_commands_run_the_same_hook(self):
        config = json.loads(
            (TOOL_ROOT / ".codex/hooks.json").read_text(encoding="utf-8")
        )
        payload = json.dumps(
            {"hook_event_name": "SessionStart", "session_id": "session-a"}
        )
        for event in ("SessionStart", "Stop"):
            entry = config["hooks"][event][0]["hooks"][0]
            self.assertEqual(entry["type"], "command")
            self.assertLessEqual(entry["timeout"], 10)
            command = entry["command"].replace(
                "$(git rev-parse --show-toplevel)", str(TOOL_ROOT)
            )
            mac_result = subprocess.run(
                command,
                shell=True,
                input=payload,
                text=True,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(mac_result.returncode, 0, mac_result.stderr)
            expected = json.loads(mac_result.stdout)
            windows_argv = shlex.split(entry["commandWindows"])
            windows_argv[0] = sys.executable
            windows_argv[2] = windows_argv[2].replace(
                "root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], "
                "text=True).strip()",
                "root = " + repr(str(TOOL_ROOT)),
            )
            # Windows용 Python 인자를 확인한다. Windows 셸 실행 검사는 아니다.
            windows_result = subprocess.run(
                windows_argv, input=payload, text=True, capture_output=True, timeout=10
            )
            self.assertEqual(windows_result.returncode, 0, windows_result.stderr)
            self.assertEqual(json.loads(windows_result.stdout), expected)

    def test_hook_does_not_affect_ordinary_answers(self):
        self.begin()
        self.write("app/example.py", "answer = 2\n")
        self.assertEqual(self.stop("질문에 대한 일반 답변입니다."), {})
        self.assertEqual(self.stop("다음 단계에서 VERIFIED 여부를 확인합니다."), {})
        self.assertEqual(self.stop("종합 판정: REJECTED"), {})

    def test_hook_does_not_activate_for_unstarted_or_other_sessions(self):
        self.assertEqual(self.stop(), {})
        self.begin()
        self.assertEqual(self.stop(session_id="session-b"), {})

    def test_hook_requires_finished_record_for_pass_report(self):
        self.begin()
        self.assertEqual(self.stop()["decision"], "block")
        scope.finish(self.repo, self.path, "VERIFIED")
        self.assertEqual(self.stop(), {})

    def test_hook_checks_final_report_matches_record(self):
        self.begin()
        scope.finish(self.repo, self.path, "VERIFIED_WITH_NOTES")
        self.assertEqual(self.stop()["decision"], "block")
        self.assertEqual(self.stop("**VERIFIED_WITH_NOTES**"), {})

    def test_hook_catches_source_change_after_finish(self):
        self.begin()
        scope.finish(self.repo, self.path, "VERIFIED")
        self.write("app/example.py", "answer = 2\n")
        result = self.stop()
        self.assertEqual(result["decision"], "block")
        self.assertIn("app/example.py", result["reason"])

    def test_hook_does_not_loop_on_its_own_continuation(self):
        self.begin()
        self.assertEqual(self.stop(stop_hook_active=True), {})

    def test_session_start_only_gives_small_routing_context(self):
        result = hook.evaluate(
            {"hook_event_name": "SessionStart"}, self.repo, self.storage
        )
        self.assertIn("$krx-verify", result["hookSpecificOutput"]["additionalContext"])
        self.assertFalse(self.storage.exists())

    def test_cli_missing_session_reports_error_in_json(self):
        environment = os.environ.copy()
        environment.pop("CODEX_THREAD_ID", None)
        result = subprocess.run(
            [
                sys.executable,
                str(Path(scope.__file__)),
                "check",
                "--repo",
                str(self.repo),
            ],
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--session-id", json.loads(result.stdout)["error"])

    def test_cli_begin_check_finish_and_document_correction(self):
        environment = dict(os.environ, TMPDIR=str(self.directory))

        def run_cli(*args):
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(scope.__file__)),
                    *args,
                    "--repo",
                    str(self.repo),
                    "--session-id",
                    "cli-fixture",
                ],
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode, json.loads(result.stdout)

        self.assertEqual(run_cli("begin", "--input", "docs/result.md")[0], 0)
        self.assertEqual(run_cli("check"), (0, {"changes": [], "problems": []}))
        self.write("docs/result.md", "줄 수: 2\n")
        self.assertEqual(run_cli("finish", "--verdict", "VERIFIED")[0], 2)
        code, record = run_cli(
            "finish",
            "--verdict",
            "VERIFIED",
            "--accept-doc",
            "docs/result.md",
            "--doc-reason",
            "줄 수 실측 정정",
        )
        self.assertEqual(code, 0)
        self.assertEqual(record["verdict"], "VERIFIED")
        self.assertEqual(run_cli("check")[0], 0)


if __name__ == "__main__":
    unittest.main()
