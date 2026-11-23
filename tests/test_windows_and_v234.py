from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from src import discovery, lock, quota_client, ui_payload, windows_setup


class TestWindowsConfig(unittest.TestCase):
    def test_win32_user_data_dir_prefers_existing_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roaming = Path(tmp)
            lower_dir = roaming / "antigravity"
            lower_dir.mkdir()
            with patch.object(config.sys, "platform", "win32"), patch.dict(
                config.os.environ, {"APPDATA": str(roaming)}, clear=False
            ):
                resolved = config._default_antigravity_user_data_dir()
            if (roaming / "Antigravity").exists():
                self.assertEqual(resolved, roaming / "Antigravity")
            else:
                self.assertEqual(resolved, lower_dir)

    def test_win32_user_data_dir_defaults_capitalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(config.sys, "platform", "win32"), patch.dict(
                config.os.environ, {"APPDATA": tmp}, clear=False
            ):
                resolved = config._default_antigravity_user_data_dir()
                self.assertEqual(resolved, Path(tmp) / "Antigravity")


class TestLeaderLockWindowsFallback(unittest.TestCase):
    def test_msvcrt_acquire_and_release_seeks_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "test.lock"
            fake_msvcrt = SimpleNamespace(
                LK_NBLCK=1,
                LK_UNLCK=0,
                locking=MagicMock(),
            )
            with patch.object(lock, "fcntl", None), patch.object(lock, "msvcrt", fake_msvcrt):
                mgr = lock.LeaderLock(lock_path=lock_path)
                self.assertTrue(mgr.try_acquire())
                self.assertTrue(mgr.is_leader)
                fd = mgr._fp.fileno()
                fake_msvcrt.locking.assert_any_call(fd, 1, 1)
                mgr.release()
                self.assertFalse(mgr.is_leader)
                fake_msvcrt.locking.assert_any_call(fd, 0, 1)

    def test_msvcrt_contention_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "test.lock"
            fake_msvcrt = SimpleNamespace(
                LK_NBLCK=1,
                LK_UNLCK=0,
                locking=MagicMock(side_effect=OSError("locked")),
            )
            with patch.object(lock, "fcntl", None), patch.object(lock, "msvcrt", fake_msvcrt):
                mgr = lock.LeaderLock(lock_path=lock_path)
                self.assertFalse(mgr.try_acquire())
                self.assertFalse(mgr.is_leader)
                mgr.release()

    def test_read_holder_pid_filters_dead_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "test.lock"
            lock_path.write_text("99999999\n", encoding="utf-8")
            mgr = lock.LeaderLock(lock_path=lock_path)
            with patch.object(lock.LeaderLock, "_is_pid_alive", return_value=False):
                self.assertIsNone(mgr.read_holder_pid())
            with patch.object(lock.LeaderLock, "_is_pid_alive", return_value=True):
                self.assertEqual(mgr.read_holder_pid(), 99999999)


class TestWindowsAndV234Discovery(unittest.TestCase):
    def test_parse_netstat_listening_ports(self) -> None:
        sample = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    127.0.0.1:50647        0.0.0.0:0              LISTENING       26740
  TCP    [::1]:50650            [::]:0                 DINLEME         26740
  TCP    127.0.0.1:50647        127.0.0.1:59001        ESTABLISHED     26740
"""
        parsed = discovery._parse_netstat_listening_ports(sample)
        self.assertEqual(parsed, {26740: [50647, 50650]})

    def test_discover_win32_legacy_and_v234_cdp_fallback(self) -> None:
        cim_rows = [
            {
                "ProcessId": 1001,
                "CommandLine": "language_server.exe --standalone --subclient_type hub --read_host_bridge_token_from_stdin --host_bridge_url=http://127.0.0.1:51234",
            },
            {
                "ProcessId": 1002,
                "CommandLine": "language_server.exe --csrf_token=deadbeef-1234",
            },
        ]
        netstat_out = (
            "  TCP    127.0.0.1:51234        0.0.0.0:0              LISTENING       1001\n"
            "  TCP    127.0.0.1:52000        0.0.0.0:0              LISTENING       1002\n"
        )
        with patch.object(discovery.sys, "platform", "win32"), patch.object(
            discovery, "_run_win32_powershell_json", return_value=cim_rows
        ), patch.object(
            discovery.subprocess, "check_output", return_value=netstat_out.encode("utf-8")
        ), patch.object(
            discovery, "_extract_token_from_cdp", return_value="cdp-token-999"
        ):
            eps = discovery.discover_language_servers()

        self.assertEqual(len(eps), 2)
        self.assertEqual(eps[0].pid, 1001)
        self.assertEqual(eps[0].csrf_token, "cdp-token-999")
        self.assertEqual(eps[0].ports, [51234])
        self.assertEqual(eps[1].pid, 1002)
        self.assertEqual(eps[1].csrf_token, "deadbeef-1234")
        self.assertEqual(eps[1].ports, [52000])

    def test_discover_v234_log_fallback_when_cdp_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp) / "logs" / "20261123T120000"
            logs_dir.mkdir(parents=True)
            (logs_dir / "main.log").write_text(
                "[AuthBootstrap] Loading Hub window URL: https://127.0.0.1:54321/#t=log-token-abc\n",
                encoding="utf-8",
            )
            processes = [
                (
                    777,
                    "/opt/Antigravity/language_server --standalone --subclient_type hub --read_host_bridge_token_from_stdin",
                )
            ]
            with patch.object(
                discovery, "_discover_server_processes_and_ports", return_value=(processes, {})
            ), patch.object(
                discovery, "_extract_token_from_cdp", return_value=""
            ), patch.object(
                config, "ANTIGRAVITY_LOGS_DIR", Path(tmp) / "logs"
            ):
                eps = discovery.discover_language_servers()

        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0].pid, 777)
        self.assertEqual(eps[0].csrf_token, "log-token-abc")
        self.assertEqual(eps[0].ports, [54321])

    def test_win32_desktop_process_info_and_diagnose_hint(self) -> None:
        rows = [
            {
                "ProcessId": 4242,
                "Name": "Antigravity.exe",
                "CommandLine": '"C:\\Program Files\\Antigravity\\Antigravity.exe"',
            }
        ]
        with patch.object(discovery.sys, "platform", "win32"), patch.object(
            discovery, "_run_win32_powershell_json", return_value=rows
        ), patch.object(
            discovery, "_resolve_cdp_port_and_file", return_value=(None, Path("C:/x/DevToolsActivePort"), False)
        ), patch.object(
            discovery, "discover_cdp_page_targets", return_value=[]
        ):
            diag = discovery.diagnose_cdp_status()

        self.assertEqual(diag["reason"], "cdp_disabled_in_antigravity_2_33")
        self.assertEqual(diag["antigravity_pid"], 4242)
        self.assertIn("--enable-cdp-windows", diag["fix_hint"])


class TestWindowsSetup(unittest.TestCase):
    def test_enable_cdp_windows_rejects_non_win32(self) -> None:
        with patch.object(windows_setup.sys, "platform", "linux"):
            res = windows_setup.enable_cdp_windows()
        self.assertFalse(res["ok"])

    def test_enable_cdp_windows_parses_powershell_json(self) -> None:
        payload = json.dumps({"ok": True, "patched": ["Desktop\\Antigravity.lnk"], "already_enabled": [], "errors": []})
        with patch.object(windows_setup.sys, "platform", "win32"), patch.object(
            windows_setup.subprocess, "check_output", return_value=payload.encode("utf-8")
        ):
            res = windows_setup.enable_cdp_windows()
        self.assertTrue(res["ok"])
        self.assertEqual(res["patched"], ["Desktop\\Antigravity.lnk"])


class TestArgonStability(unittest.TestCase):
    def test_quota_client_preserves_argon_group_within_ttl(self) -> None:
        with patch.object(quota_client, "_CACHED_ARGON", None):
            three_groups = {
                "response": {
                    "groups": [
                        {"displayName": "Gemini Models", "buckets": [{"window": "weekly", "remainingFraction": 0.89}]},
                        {"displayName": "Claude and GPT models", "buckets": [{"window": "weekly", "remainingFraction": 0.50}]},
                        {"displayName": "Gemini 4 Argon", "buckets": [{"window": "weekly", "remainingFraction": 0.95}]},
                    ]
                }
            }
            r1 = quota_client._parse_quota_response(three_groups)
            self.assertEqual(r1.argon_weekly_pct, 95)

            two_groups = {
                "response": {
                    "groups": [
                        {"displayName": "Gemini Models", "buckets": [{"window": "weekly", "remainingFraction": 0.99}]},
                        {"displayName": "Claude and GPT models", "buckets": [{"window": "weekly", "remainingFraction": 0.50}]},
                    ]
                }
            }
            r2 = quota_client._parse_quota_response(two_groups)
            self.assertEqual(r2.argon_weekly_pct, 95)
            self.assertTrue(any("Argon" in g.display_name for g in r2.groups))

    def test_ui_payload_renders_with_argon_ttl_merge(self) -> None:
        js = ui_payload.build_injection_js()
        self.assertIn("lastArgonGroup", js)
        self.assertIn("ARGON_TTL_MS", js)


if __name__ == "__main__":
    unittest.main()
