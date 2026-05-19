from typer.testing import CliRunner

from resume_screening.cli import app


def test_cli_requires_config_argument() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "Missing option" in result.output or "Error" in result.output
