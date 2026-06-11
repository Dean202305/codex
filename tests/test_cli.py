import subprocess
import sys
import os

from typer.testing import CliRunner

from resume_screening.cli import app


def cli_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return env


def test_cli_requires_config_argument() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "Missing option" in result.output or "Error" in result.output


def test_cli_module_help_renders() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resume_screening.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=cli_env(),
    )

    assert result.returncode == 0
    assert "run" in result.stdout


def test_cli_module_help_includes_web_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resume_screening.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=cli_env(),
    )

    assert result.returncode == 0
    assert "web" in result.stdout


def test_cli_module_help_includes_desktop_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "resume_screening.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=cli_env(),
    )

    assert result.returncode == 0
    assert "desktop" in result.stdout
