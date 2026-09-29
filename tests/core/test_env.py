import os

from studio.core.env import load_dotenv


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text('EXAMPLE_KEY="abc123"\n# comment\n\n', encoding="utf-8")
    monkeypatch.delenv("EXAMPLE_KEY", raising=False)
    load_dotenv(path)
    assert os.environ["EXAMPLE_KEY"] == "abc123"


def test_load_dotenv_does_not_overwrite_an_existing_value(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("EXAMPLE_KEY=fromfile\n", encoding="utf-8")
    monkeypatch.setenv("EXAMPLE_KEY", "fromshell")
    load_dotenv(path)
    assert os.environ["EXAMPLE_KEY"] == "fromshell"


def test_load_dotenv_is_quiet_when_the_file_is_absent(tmp_path):
    load_dotenv(tmp_path / "nothing-here")
