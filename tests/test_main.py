import builtins
import logging

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


def test_plan_goal_prints_disclaimer(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "60", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "not medical advice" in out
    assert "Warning:" not in out  # a moderate goal is not flagged


def test_plan_goal_warns_about_unsafe_loss(monkeypatch, capsys):
    # 50 lb in 30 days: floored at the safe minimum, with a warning and a safe time frame.
    feed_input(monkeypatch, ["7", "5", "196.8", "146.8", "30", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "Recommended Intake (Algebraic): 1200" in out
    assert "Recommended Intake (Optimized): 1200" in out
    assert "Warning: Losing 50.0 lbs in 30 days" in out
    assert "at least 175 days" in out
    assert "not medical advice" in out


def test_parse_args_verbose_flag():
    assert cli.parse_args([]).verbose is False
    assert cli.parse_args(["-v"]).verbose is True
    assert cli.parse_args(["--verbose"]).verbose is True


@pytest.mark.parametrize("verbose,level", [(False, logging.WARNING), (True, logging.DEBUG)])
def test_configure_logging_levels(monkeypatch, verbose, level):
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
    cli.configure_logging(verbose)
    assert calls[0]["level"] == level


def test_manual_entry_rejection_shows_reason(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "1", "2025-08-01", "500", "2200", "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "Entry rejected: weight change too large" in out


def test_file_load_reports_skip_reasons(monkeypatch, capsys, tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("date,weight,calories\n2025-07-01,200,2200\n2025-09-01,190,300\n")
    feed_input(monkeypatch, ["7", "2", str(path), "8"])
    cli.main()
    out = capsys.readouterr().out
    assert "Loaded 0 of 2 entries" in out
    assert "Skipped 1: an entry for that date already exists" in out
    assert "Skipped 1: calories out of range" in out


def test_prompt_float_rejects_nan_and_inf(monkeypatch, capsys):
    feed_input(monkeypatch, ["nan", "inf", "-inf", "abc", "180.5"])
    assert cli.prompt_float("Weight: ") == 180.5
    assert capsys.readouterr().out.count("valid number") == 4


def test_plan_goal_warns_about_extreme_gain(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "5", "150", "300", "5", "8"])
    cli.main()
    captured = capsys.readouterr()
    assert "Recommended Intake (Algebraic): 5000" in captured.out
    assert "Warning: Reaching 300 lbs in 5 days would require eating more than 5000" in captured.out
    assert "realistic time frame" in captured.out


@pytest.mark.parametrize("answers", [
    ["7", "5", "196.8", "146.8", "30", "8"],   # unsafe loss
    ["7", "5", "150", "300", "5", "8"],        # extreme gain
])
def test_unsafe_goals_log_nothing_at_default_level(monkeypatch, capsys, answers):
    # stdout warnings are enough; nothing (in particular no target weight) is logged.
    records = []
    handler = logging.Handler(level=logging.WARNING)
    handler.emit = records.append
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        feed_input(monkeypatch, answers)
        cli.main()
    finally:
        root.removeHandler(handler)
    assert "Warning:" in capsys.readouterr().out
    assert records == []
