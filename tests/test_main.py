import builtins

import pytest

from src import main as cli


def feed_input(monkeypatch, answers):
    """Make input() return each answer in turn; fail loudly if the CLI asks for more."""
    it = iter(answers)

    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            pytest.fail(f"Unexpected extra prompt: {prompt!r}")

    monkeypatch.setattr(builtins, "input", fake_input)


def test_prompt_int_enforces_minimum(monkeypatch, capsys):
    feed_input(monkeypatch, ["0", "-5", "abc", "7"])
    assert cli.prompt_int("Days: ", minimum=1) == 7
    out = capsys.readouterr().out
    assert out.count("at least 1") == 2
    assert "valid whole number" in out


def test_prompt_int_without_minimum_accepts_any_int(monkeypatch):
    feed_input(monkeypatch, ["-3"])
    assert cli.prompt_int("Value: ") == -3


def test_plan_goal_reprompts_on_zero_time_frame(monkeypatch, capsys):
    # Load demo data, plan a goal with time frame 0 then 60, then exit.
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "0", "60", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Recommended Intake (Algebraic):" in out
    assert "Recommended Intake (Optimized):" in out


def test_trend_window_reprompts_on_zero(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "6", "0", "3", "weight", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Moving averages for weight (window=3):" in out


def test_demo_data_gives_sensible_maintenance(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "4", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    line = next(l for l in out.splitlines() if "Estimated Maintenance Calories" in l)
    maintenance = int(line.split(":")[1].split()[0])
    assert 2000 <= maintenance <= 3000


def test_loading_demo_twice_rejects_duplicates(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "7", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    assert "Added 0 of 20 demo entries" in out
