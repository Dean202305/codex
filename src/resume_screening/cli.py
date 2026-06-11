from __future__ import annotations

from pathlib import Path

import typer

from resume_screening.config import load_config
from resume_screening.pipeline import ScreeningPipeline


app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Resume screening automation."""


@app.command()
def run(config: Path = typer.Option(..., "--config", "-c", exists=True, readable=True)) -> None:
    app_config = load_config(config)
    stats = ScreeningPipeline(app_config).run()
    typer.echo("处理完成")
    typer.echo(f"处理数量：{stats.processed}")
    typer.echo(f"推荐初试：{stats.recommend}")
    typer.echo(f"可考虑：{stats.consider}")
    typer.echo(f"待人工二筛：{stats.manual}")
    typer.echo(f"未通过：{stats.reject}")
    typer.echo(f"疑似重复：{stats.duplicate}")
    typer.echo(f"模型失败：{stats.model_failures}")
    typer.echo(f"提取失败/警告：{stats.extraction_failures}")
    typer.echo(f"文件名不规范：{stats.non_standard_names}")


@app.command()
def web(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """Start the local web interface."""
    import uvicorn

    from resume_screening.web.app import create_app

    typer.echo(f"启动本地网页：http://{host}:{port}")
    uvicorn.run(create_app(config_path=config), host=host, port=port)


@app.command()
def desktop() -> None:
    """Start the packaged local desktop app."""
    from resume_screening.desktop_app import main as desktop_main

    desktop_main()


if __name__ == "__main__":
    app()
