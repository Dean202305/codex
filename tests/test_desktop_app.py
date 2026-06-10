from pathlib import Path

import yaml

from resume_screening.desktop_app import app_support_dir, ensure_desktop_config, find_free_port


def test_app_support_dir_can_be_overridden_for_tests(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(tmp_path / "app-home"))

    assert app_support_dir() == tmp_path / "app-home"


def test_ensure_desktop_config_creates_portable_default_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(tmp_path / "app-home"))

    config_path = ensure_desktop_config()

    assert config_path == tmp_path / "app-home" / "config.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert raw["resume_dir"] == "/Users/mac/Downloads"
    assert raw["job_book"] == "/Users/mac/Downloads/小A自动化岗位说明书_副本.xlsx"
    assert raw["index_path"] == str(tmp_path / "app-home" / "data" / "processed_index.json")
    assert raw["model"]["allow_without_model"] is False
    assert raw["model"]["fallback_to_local_when_unavailable"] is True


def test_ensure_desktop_config_uses_local_model_defaults_on_windows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(tmp_path / "app-home"))
    monkeypatch.setattr("resume_screening.desktop_app.platform.system", lambda: "Windows")
    monkeypatch.setattr("resume_screening.desktop_app.Path.home", staticmethod(lambda: tmp_path / "home"))

    config_path = ensure_desktop_config()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert raw["resume_dir"] == str(tmp_path / "home" / "Downloads")
    assert raw["job_book"] == str(tmp_path / "home" / "Downloads" / "岗位说明书.xlsx")
    assert raw["result_book"] == str(tmp_path / "home" / "Downloads" / "招聘结果表.xlsx")
    assert raw["model"]["provider"] == "local-qwen"
    assert raw["model"]["model"] == "qwen3.5-local"
    assert raw["model"]["api_key"] == ""
    assert raw["model"]["allow_without_model"] is False
    assert raw["model"]["fallback_to_local_when_unavailable"] is True
    assert raw["model"]["local"]["auto_start"] is True
    assert raw["model"]["local"]["auto_download"] is False


def test_ensure_desktop_config_migrates_legacy_relative_index_path(monkeypatch, tmp_path: Path) -> None:
    app_home = tmp_path / "app-home"
    app_home.mkdir()
    config_path = app_home / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "resume_dir": "/tmp/resumes",
                "job_book": "/tmp/jobs.xlsx",
                "result_book": "/tmp/result.xlsx",
                "index_path": "data/processed_index.json",
                "model": {"allow_without_model": True},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(app_home))

    ensure_desktop_config()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert raw["resume_dir"] == "/tmp/resumes"
    assert raw["index_path"] == str(app_home / "data" / "processed_index.json")


def test_ensure_desktop_config_keeps_existing_config(monkeypatch, tmp_path: Path) -> None:
    app_home = tmp_path / "app-home"
    app_home.mkdir()
    config_path = app_home / "config.yaml"
    config_path.write_text("resume_dir: /tmp/custom\nindex_path: /tmp/custom-index.json\n", encoding="utf-8")
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(app_home))

    assert ensure_desktop_config() == config_path
    assert config_path.read_text(encoding="utf-8") == "resume_dir: /tmp/custom\nindex_path: /tmp/custom-index.json\n"


def test_find_free_port_returns_socket_assigned_port(monkeypatch) -> None:
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def bind(self, address):
            self.address = address

        def getsockname(self):
            return ("127.0.0.1", 54321)

    monkeypatch.setattr("resume_screening.desktop_app.socket.socket", lambda *args, **kwargs: FakeSocket())

    port = find_free_port()

    assert port == 54321
