import builtins
import json
import logging
import os
import sys

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
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "0", "60", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Recommended Intake (Algebraic):" in out
    assert "Recommended Intake (Optimized):" in out


def test_trend_window_reprompts_on_zero(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "6", "0", "3", "weight", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Moving averages for weight (window=3):" in out


def test_demo_data_gives_sensible_maintenance(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "4", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    line = next(l for l in out.splitlines() if "Estimated Maintenance Calories" in l)
    maintenance = int(line.split(":")[1].split()[0])
    assert 2000 <= maintenance <= 3000


def test_loading_demo_twice_rejects_duplicates(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "7", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    assert "Added 0 of 20 demo entries" in out


def test_plan_goal_prints_disclaimer(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "60", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "not medical advice" in out
    assert "Warning:" not in out  # a moderate goal is not flagged


def test_plan_goal_warns_about_unsafe_loss(monkeypatch, capsys):
    # 50 lb in 30 days: floored at the safe minimum, with a warning and a safe time frame.
    feed_input(monkeypatch, ["7", "5", "196.8", "146.8", "30", "11"])
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
    feed_input(monkeypatch, ["7", "1", "2025-08-01", "500", "2200", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "Entry rejected: weight change too large" in out


def test_file_load_reports_skip_reasons(monkeypatch, capsys, tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("date,weight,calories\n2025-07-01,200,2200\n2025-09-01,190,300\n")
    feed_input(monkeypatch, ["7", "2", str(path), "11"])
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
    feed_input(monkeypatch, ["7", "5", "150", "300", "5", "11"])
    cli.main()
    captured = capsys.readouterr()
    assert "Recommended Intake (Algebraic): 5000" in captured.out
    assert "Warning: Reaching 300 lbs in 5 days would require eating more than 5000" in captured.out
    assert "realistic time frame" in captured.out


@pytest.mark.parametrize("answers", [
    ["7", "5", "196.8", "146.8", "30", "11"],   # unsafe loss
    ["7", "5", "150", "300", "5", "11"],        # extreme gain
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


# --- Persistence and editing ---------------------------------------------

def saved_rows(path):
    return [(row["date"], row["weight"], row["calories"]) for row in json.loads(path.read_text())]


def test_menu_prompt_matches_number_of_options(monkeypatch, capsys):
    prompts = []
    monkeypatch.setattr(builtins, "input", lambda prompt="": prompts.append(prompt) or "11")
    cli.main()
    assert "11. Exit" in capsys.readouterr().out
    assert prompts == ["Choose an option (1 - 11): "]
    assert len(cli.MENU_OPTIONS) == 11


def test_invalid_choice_names_the_full_range(monkeypatch, capsys):
    feed_input(monkeypatch, ["12", "11"])
    cli.main()
    assert "Please select a number 1 - 11." in capsys.readouterr().out


def test_changes_are_saved_and_reloaded(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "11"])
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert "No saved entries yet" in out
    assert saved_rows(path) == [("2025-07-01", 200.0, 2200)]

    # A new session starts with the saved entry.
    feed_input(monkeypatch, ["8", "11"])
    cli.main(path)
    out = capsys.readouterr().out
    assert f"Loaded 1 saved entry from {path}" in out
    assert "2025-07-01  200 lbs  2200 cals" in out

    feed_input(monkeypatch, ["1", "2025-07-02", "199", "2100", "11"])
    cli.main(path)
    feed_input(monkeypatch, ["11"])
    cli.main(path)
    assert f"Loaded 2 saved entries from {path}" in capsys.readouterr().out


def test_rejected_entry_is_not_saved(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "100", "11"])
    cli.main(path)
    assert not path.exists()


def test_demo_data_is_saved(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "11"])
    cli.main(path)
    assert len(saved_rows(path)) == 20


def test_file_import_is_saved(monkeypatch, tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("date,weight,calories\n2025-07-01,200,2200\n2025-07-02,199.5,2100\n")
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["2", str(src), "11"])
    cli.main(path)
    assert len(saved_rows(path)) == 2


def test_list_entries_when_empty(monkeypatch, capsys):
    feed_input(monkeypatch, ["8", "11"])
    cli.main()
    assert "No entries yet." in capsys.readouterr().out


def test_edit_entry_updates_and_saves(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "9", "2025-07-01", "200.4", "2300", "11"])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Current: 2025-07-01  200 lbs  2200 cals" in out
    assert "Entry updated." in out
    assert saved_rows(path)[0] == ("2025-07-01", 200.4, 2300)


def test_edit_entry_rejection_leaves_saved_data(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "11"])
    cli.main(path)
    before = path.read_text()

    feed_input(monkeypatch, ["9", "2025-07-01", "200", "300", "11"])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Entry not updated: calories out of range" in out
    assert path.read_text() == before


def test_edit_missing_date(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "9", "2030-01-01", "11"])
    cli.main()
    assert "No entry for 2030-01-01." in capsys.readouterr().out


def test_edit_and_delete_on_empty_log(monkeypatch, capsys):
    feed_input(monkeypatch, ["9", "10", "11"])
    cli.main()
    out = capsys.readouterr().out
    assert "No entries to edit." in out
    assert "No entries to delete." in out


def test_delete_entry_with_confirmation(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "10", "2025-07-01", "y", "11"])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Entry deleted." in out
    rows = saved_rows(path)
    assert len(rows) == 19
    assert rows[0][0] == "2025-07-02"


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_delete_entry_needs_yes(monkeypatch, capsys, tmp_path, answer):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "10", "2025-07-01", answer, "11"])
    cli.main(path)
    assert "Not deleted." in capsys.readouterr().out
    assert len(saved_rows(path)) == 20


def test_delete_missing_date(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "10", "2030-01-01", "11"])
    cli.main()
    assert "No entry for 2030-01-01." in capsys.readouterr().out


@pytest.mark.parametrize("interrupt", [EOFError, KeyboardInterrupt])
def test_interrupt_exits_cleanly_and_keeps_saved_data(monkeypatch, capsys, tmp_path, interrupt):
    path = tmp_path / "log.json"
    answers = iter(["7", "10", "2025-07-01"])

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise interrupt  # Ctrl-D / Ctrl-C at the delete confirmation

    monkeypatch.setattr(builtins, "input", fake_input)
    assert cli.main(path) == 0
    assert "Goodbye!" in capsys.readouterr().out
    assert len(saved_rows(path)) == 20  # nothing deleted, nothing lost


def test_corrupt_data_file_refuses_to_start(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    path.write_text("{oops")
    feed_input(monkeypatch, [])  # must not reach the menu
    assert cli.main(path) == 1
    err = capsys.readouterr().err
    assert "Could not read saved data" in err
    assert "--data-file" in err
    assert path.read_text() == "{oops"


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="POSIX permissions only; root can search any directory")
def test_unsearchable_data_directory_refuses_to_start(monkeypatch, capsys, tmp_path):
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "log.json").write_text("[]")
    locked.chmod(0)
    feed_input(monkeypatch, [])  # must not reach the menu
    try:
        assert cli.main(locked / "log.json") == 1
    finally:
        locked.chmod(0o700)
    assert "Could not read saved data" in capsys.readouterr().err


def test_save_failure_is_reported_and_session_continues(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"

    def failing_save(log, p):
        raise PermissionError("read-only")

    monkeypatch.setattr(cli, "save_log", failing_save)
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "8", "11"])
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert "Warning: could not save" in out
    assert "2025-07-01  200 lbs  2200 cals" in out  # still in memory


def test_parse_args_data_file():
    assert cli.parse_args([]).data_file is None
    assert cli.parse_args(["--data-file", "x.json"]).data_file == "x.json"
    assert cli.parse_args(["-v", "--data-file", "x.json"]).verbose is True


def test_run_uses_data_file_flag(monkeypatch, capsys, tmp_path):
    path = tmp_path / "flag.json"
    feed_input(monkeypatch, ["7", "11"])
    assert cli.run(["--data-file", str(path)]) == 0
    assert len(saved_rows(path)) == 20


def test_run_uses_env_var(monkeypatch, tmp_path):
    path = tmp_path / "env.json"
    monkeypatch.setenv("CALORIE_TRACKER_DATA", str(path))
    feed_input(monkeypatch, ["7", "11"])
    cli.run([])
    assert len(saved_rows(path)) == 20


def test_run_defaults_to_home(monkeypatch, isolated_home):
    feed_input(monkeypatch, ["7", "11"])
    cli.run([])
    assert len(saved_rows(isolated_home / ".calorie_tracker" / "log.json")) == 20


def test_run_rejects_non_json_data_file(monkeypatch, capsys, tmp_path):
    feed_input(monkeypatch, [])
    assert cli.run(["--data-file", str(tmp_path / "log.csv")]) == 2
    assert ".json" in capsys.readouterr().err


def flaky_save(monkeypatch, failures):
    """Make the first `failures` saves fail, then save for real."""
    real_save = cli.save_log
    calls = {"n": 0}

    def save(log, path):
        calls["n"] += 1
        if calls["n"] <= failures:
            raise PermissionError("read-only")
        real_save(log, path)

    monkeypatch.setattr(cli, "save_log", save)


@pytest.mark.parametrize("exit_answer", ["11", EOFError, KeyboardInterrupt])
def test_failed_save_is_retried_on_exit(monkeypatch, capsys, tmp_path, exit_answer):
    path = tmp_path / "log.json"
    flaky_save(monkeypatch, failures=1)
    answers = iter(["1", "2025-07-01", "200", "2200", exit_answer])

    def fake_input(prompt=""):
        answer = next(answers)
        if not isinstance(answer, str):
            raise answer
        return answer

    monkeypatch.setattr(builtins, "input", fake_input)
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert "Warning: could not save" in out
    assert "unsaved changes were lost" not in out
    assert saved_rows(path) == [("2025-07-01", 200.0, 2200)]


def test_exit_warns_when_changes_could_not_be_saved(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    flaky_save(monkeypatch, failures=2)
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "11"])
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Warning: unsaved changes were lost.\n\nGoodbye!")
    assert not path.exists()


def test_exit_after_successful_saves_does_not_save_again(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "11"])
    calls = []
    real_save = cli.save_log
    monkeypatch.setattr(cli, "save_log", lambda log, p: (calls.append(p), real_save(log, p)))
    cli.main(path)
    assert calls == [path]
