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
    assert raw["model"]["allow_without_model"] is True


def test_ensure_desktop_config_keeps_existing_config(monkeypatch, tmp_path: Path) -> None:
    app_home = tmp_path / "app-home"
    app_home.mkdir()
    config_path = app_home / "config.yaml"
    config_path.write_text("resume_dir: /tmp/custom\n", encoding="utf-8")
    monkeypatch.setenv("RESUME_SCREENING_APP_HOME", str(app_home))

    assert ensure_desktop_config() == config_path
    assert config_path.read_text(encoding="utf-8") == "resume_dir: /tmp/custom\n"


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
