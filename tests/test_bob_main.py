from __future__ import annotations

import pytest

from aitapes.bob import BobConfig


def test_bob_config_reads_watsonx_project_id(monkeypatch) -> None:
    monkeypatch.delenv("IBM_BOB_PROJECT_ID", raising=False)
    monkeypatch.setenv("WATSONX_PROJECT_ID", "project-123")

    config = BobConfig.from_env()

    assert config.project_id == "project-123"


def test_tapes_bob_invocation_routes_to_bob_mode(monkeypatch) -> None:
    import aitapes.cli as cli

    seen: dict[str, object] = {}

    def fake_run_bob_main(intent, *, source_dir=".", auto_apply=True, offline=False):
        seen["intent"] = intent
        seen["source_dir"] = source_dir
        seen["auto_apply"] = auto_apply
        seen["offline"] = offline
        return 0

    monkeypatch.setattr(cli, "run_bob_main", fake_run_bob_main)
    monkeypatch.setattr(cli, "run_chat_shell", lambda source_dir=".": pytest.fail("chat shell should not run"))
    monkeypatch.setattr(cli.sys, "argv", ["tapes-bob", "--intent", "demo bob flow", "--source", "repo"])

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 0
    assert seen == {
        "intent": "demo bob flow",
        "source_dir": "repo",
        "auto_apply": True,
        "offline": False,
    }
