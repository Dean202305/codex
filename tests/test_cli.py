import subprocess
import sys

from typer.testing import CliRunner

from resume_screening.cli import app


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
    )

    assert result.returncode == 0
    assert "run" in result.stdout
