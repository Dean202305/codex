from pathlib import Path


def test_macos_build_script_creates_dmg_output() -> None:
    script = Path("scripts/build_macos_app.sh").read_text(encoding="utf-8")

    assert "DMG_PATH" in script
    assert "hdiutil create" in script
    assert "本地安装包" in script
