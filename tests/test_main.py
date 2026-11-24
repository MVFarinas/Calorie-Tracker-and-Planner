import builtins
import json
import logging
import os
import sys

import pytest

from calorie_tracker import main as cli

EXIT = cli.EXIT_CHOICE


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
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "0", "60", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Recommended Intake (Algebraic):" in out
    assert "Recommended Intake (Optimized):" in out


def test_trend_window_reprompts_on_zero(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "6", "1", "0", "3", "weight", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "at least 1" in out
    assert "Moving averages for weight in lbs (window=3):" in out


def test_demo_data_gives_sensible_maintenance(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "4", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    line = next(text for text in out.splitlines() if "Estimated Maintenance Calories" in text)
    maintenance = int(line.split(":")[1].split()[0])
    assert 2000 <= maintenance <= 3000


def test_loading_demo_twice_rejects_duplicates(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "7", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "Added 20 of 20 demo entries" in out
    assert "Added 0 of 20 demo entries" in out


def test_plan_goal_prints_disclaimer(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "5", "196.8", "190", "60", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "not medical advice" in out
    assert "Warning:" not in out  # a moderate goal is not flagged


def test_plan_goal_warns_about_unsafe_loss(monkeypatch, capsys):
    # 50 lb in 30 days: floored at the safe minimum, with a warning and a safe time frame.
    feed_input(monkeypatch, ["7", "5", "196.8", "146.8", "30", EXIT])
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
    feed_input(monkeypatch, ["7", "1", "2025-08-01", "500", "2200", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "Entry rejected: weight change too large" in out


def test_file_load_reports_skip_reasons(monkeypatch, capsys, tmp_path):
    path = tmp_path / "a.csv"
    path.write_text("date,weight,calories\n2025-07-01,200,2200\n2025-09-01,190,300\n")
    feed_input(monkeypatch, ["7", "2", str(path), EXIT])
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
    feed_input(monkeypatch, ["7", "5", "150", "300", "5", EXIT])
    cli.main()
    captured = capsys.readouterr()
    assert "Recommended Intake (Algebraic): 5000" in captured.out
    assert "Warning: Reaching 300 lbs in 5 days would require eating more than 5000" in captured.out
    assert "realistic time frame" in captured.out


@pytest.mark.parametrize("answers", [
    ["7", "5", "196.8", "146.8", "30", EXIT],   # unsafe loss
    ["7", "5", "150", "300", "5", EXIT],        # extreme gain
])
def test_unsafe_goals_log_nothing_at_default_level(monkeypatch, capsys, answers):
    # stdout warnings are enough; nothing (in particular no target weight) is logged.
    records: list[logging.LogRecord] = []
    handler = logging.Handler(level=logging.WARNING)
    monkeypatch.setattr(handler, "emit", records.append)
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

    def fake_input(prompt=""):
        prompts.append(prompt)
        return EXIT

    monkeypatch.setattr(builtins, "input", fake_input)
    cli.main()
    assert "13. Exit" in capsys.readouterr().out
    assert prompts == ["Choose an option (1 - 13): "]
    assert len(cli.MENU_OPTIONS) == 13


def test_invalid_choice_names_the_full_range(monkeypatch, capsys):
    feed_input(monkeypatch, ["14", EXIT])
    cli.main()
    assert "Please select a number 1 - 13." in capsys.readouterr().out


def test_changes_are_saved_and_reloaded(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", EXIT])
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert "No saved entries yet" in out
    assert saved_rows(path) == [("2025-07-01", 200.0, 2200)]

    # A new session starts with the saved entry.
    feed_input(monkeypatch, ["8", EXIT])
    cli.main(path)
    out = capsys.readouterr().out
    assert f"Loaded 1 saved entry from {path}" in out
    assert "2025-07-01  200 lbs  2200 cals" in out

    feed_input(monkeypatch, ["1", "2025-07-02", "199", "2100", EXIT])
    cli.main(path)
    feed_input(monkeypatch, [EXIT])
    cli.main(path)
    assert f"Loaded 2 saved entries from {path}" in capsys.readouterr().out


def test_rejected_entry_is_not_saved(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "100", EXIT])
    cli.main(path)
    assert not path.exists()


def test_demo_data_is_saved(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", EXIT])
    cli.main(path)
    assert len(saved_rows(path)) == 20


def test_file_import_is_saved(monkeypatch, tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("date,weight,calories\n2025-07-01,200,2200\n2025-07-02,199.5,2100\n")
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["2", str(src), EXIT])
    cli.main(path)
    assert len(saved_rows(path)) == 2


def test_list_entries_when_empty(monkeypatch, capsys):
    feed_input(monkeypatch, ["8", EXIT])
    cli.main()
    assert "No entries yet." in capsys.readouterr().out


def test_edit_entry_updates_and_saves(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "9", "2025-07-01", "200.4", "2300", EXIT])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Current: 2025-07-01  200 lbs  2200 cals" in out
    assert "Entry updated." in out
    assert saved_rows(path)[0] == ("2025-07-01", 200.4, 2300)


def test_edit_entry_rejection_leaves_saved_data(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", EXIT])
    cli.main(path)
    before = path.read_text()

    feed_input(monkeypatch, ["9", "2025-07-01", "200", "300", EXIT])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Entry not updated: calories out of range" in out
    assert path.read_text() == before


def test_edit_missing_date(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "9", "2030-01-01", EXIT])
    cli.main()
    assert "No entry for 2030-01-01." in capsys.readouterr().out


def test_edit_and_delete_on_empty_log(monkeypatch, capsys):
    feed_input(monkeypatch, ["9", "10", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "No entries to edit." in out
    assert "No entries to delete." in out


def test_delete_entry_with_confirmation(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "10", "2025-07-01", "y", EXIT])
    cli.main(path)
    out = capsys.readouterr().out
    assert "Entry deleted." in out
    rows = saved_rows(path)
    assert len(rows) == 19
    assert rows[0][0] == "2025-07-02"


@pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
def test_delete_entry_needs_yes(monkeypatch, capsys, tmp_path, answer):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "10", "2025-07-01", answer, EXIT])
    cli.main(path)
    assert "Not deleted." in capsys.readouterr().out
    assert len(saved_rows(path)) == 20


def test_delete_missing_date(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "10", "2030-01-01", EXIT])
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
            raise interrupt from None  # Ctrl-D / Ctrl-C at the delete confirmation

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
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "8", EXIT])
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
    feed_input(monkeypatch, ["7", EXIT])
    assert cli.run(["--data-file", str(path)]) == 0
    assert len(saved_rows(path)) == 20


def test_run_uses_env_var(monkeypatch, tmp_path):
    path = tmp_path / "env.json"
    monkeypatch.setenv("CALORIE_TRACKER_DATA", str(path))
    feed_input(monkeypatch, ["7", EXIT])
    cli.run([])
    assert len(saved_rows(path)) == 20


def test_run_defaults_to_home(monkeypatch, isolated_home):
    feed_input(monkeypatch, ["7", EXIT])
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


@pytest.mark.parametrize("exit_answer", [EXIT, EOFError, KeyboardInterrupt])
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
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", EXIT])
    assert cli.main(path) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Warning: unsaved changes were lost.\n\nGoodbye!")
    assert not path.exists()


def test_exit_after_successful_saves_does_not_save_again(monkeypatch, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", EXIT])
    calls = []
    real_save = cli.save_log

    def recording_save(log, p):
        calls.append(p)
        real_save(log, p)

    monkeypatch.setattr(cli, "save_log", recording_save)
    cli.main(path)
    assert calls == [path]


# --- Weight units ----------------------------------------------------------

def test_parse_args_units():
    assert cli.parse_args([]).units is None
    assert cli.parse_args(["--units", "kg"]).units == "kg"
    assert cli.parse_args(["--units", "LB"]).units == "lbs"


def test_parse_args_rejects_unknown_unit(capsys):
    with pytest.raises(SystemExit):
        cli.parse_args(["--units", "stone"])
    assert "unknown weight unit" in capsys.readouterr().err


def test_kg_entry_is_stored_in_lbs_and_shown_in_kg(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["1", "2025-07-01", "90.5", "2200", "8", EXIT])
    cli.main(path, units="kg")
    out = capsys.readouterr().out
    assert "2025-07-01  90.5 kg  2200 cals" in out
    (date, weight, calories), = saved_rows(path)
    assert weight == pytest.approx(90.5 / 0.45359237)


def test_unit_choice_is_saved_next_to_the_data_file(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "12", "kg", EXIT])
    cli.main(path)
    assert "Weights are now shown in kg." in capsys.readouterr().out
    assert json.loads((tmp_path / "log.settings.json").read_text()) == {"unit": "kg"}
    assert isinstance(json.loads(path.read_text()), list)  # log schema unchanged

    feed_input(monkeypatch, ["8", EXIT])
    cli.main(path)
    assert "2025-07-01  90.72 kg  2200 cals" in capsys.readouterr().out


def test_units_flag_overrides_saved_unit_without_changing_it(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    (tmp_path / "log.settings.json").write_text('{"unit": "kg"}')
    feed_input(monkeypatch, ["7", "8", EXIT])
    assert cli.run(["--data-file", str(path), "--units", "lbs"]) == 0
    assert "2025-07-01  200 lbs  2200 cals" in capsys.readouterr().out
    assert json.loads((tmp_path / "log.settings.json").read_text()) == {"unit": "kg"}


def test_invalid_unit_choice_keeps_current_unit(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["12", "stone", EXIT])
    cli.main(path)
    assert "Still using lbs." in capsys.readouterr().out
    assert not (tmp_path / "log.settings.json").exists()


def test_corrupt_settings_do_not_stop_the_cli(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    (tmp_path / "log.settings.json").write_text("{oops")
    feed_input(monkeypatch, ["7", "8", EXIT])
    assert cli.main(path) == 0
    assert "2025-07-01  200 lbs  2200 cals" in capsys.readouterr().out


def test_summary_and_goal_planner_in_kg(monkeypatch, capsys):
    # 22.7 kg is about 50 lbs, the same unsafe goal as the lbs test above.
    feed_input(monkeypatch, ["7", "3", "5", "89.27", "66.59", "30", EXIT])
    cli.main(units="kg")
    out = capsys.readouterr().out
    assert "Weight change: 1.45 kg" in out
    assert "Recommended Intake (Algebraic): 1200" in out
    assert "Warning: Losing 22.7 kg in 30 days" in out
    assert "lbs" not in out.split("--- Summary ---")[1]


def test_edit_entry_in_kg(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "9", "2025-07-01", "91", "2300", EXIT])
    cli.main(path, units="kg")
    out = capsys.readouterr().out
    assert "Current: 2025-07-01  90.72 kg  2200 cals" in out
    assert saved_rows(path)[0][1] == pytest.approx(91 / 0.45359237)


def test_weight_moving_average_in_kg(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "6", "1", "20", "weight", EXIT])
    cli.main(units="kg")
    out = capsys.readouterr().out
    assert "Moving averages for weight in kg (window=20):" in out
    average_lbs = sum(e.weight for e in cli.FileLoader.load_file(str(cli.DEMO_DATA))) / 20
    assert f"[{round(average_lbs * 0.45359237, 2)}]" in out


# --- Trend chart ----------------------------------------------------------

def test_trend_chart_with_demo_data(monkeypatch, capsys):
    feed_input(monkeypatch, ["7", "6", "2", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "Weight (lbs): o scale  * trend  @ both" in out
    assert "Latest trend weight: 197.5 lbs (scale: 196.8 lbs)" in out
    assert "Overall: Losing weight" in out
    chart = out.split("Weight (lbs):")[1].split("Latest trend weight")[0]
    assert all(len(line) <= 80 for line in chart.splitlines())


def test_trend_chart_with_no_entries(monkeypatch, capsys):
    feed_input(monkeypatch, ["6", "2", EXIT])
    cli.main()
    assert "No entries to chart yet." in capsys.readouterr().out


def test_trend_chart_with_one_entry(monkeypatch, capsys):
    feed_input(monkeypatch, ["1", "2025-07-01", "200", "2200", "6", "2", EXIT])
    cli.main()
    out = capsys.readouterr().out
    assert "Latest trend weight: 200 lbs (scale: 200 lbs)" in out
    assert "Overall:" not in out


def test_trend_menu_invalid_choice(monkeypatch, capsys):
    feed_input(monkeypatch, ["6", "3", EXIT])
    cli.main()
    assert "Please select 1 or 2." in capsys.readouterr().out


# --- Export ---------------------------------------------------------------

@pytest.mark.parametrize("name", ["out.csv", "out.json"])
def test_export_round_trips_through_loader(monkeypatch, capsys, tmp_path, name):
    target = tmp_path / name
    feed_input(monkeypatch, ["7", "11", str(target), EXIT])
    cli.main()
    assert f"Exported 20 entries to {target} (weights in lbs)." in capsys.readouterr().out
    demo = cli.FileLoader.load_file(str(cli.DEMO_DATA))
    exported = cli.FileLoader.load_file(str(target))
    assert [(e.date, e.weight, e.calories) for e in exported] == [(e.date, e.weight, e.calories) for e in demo]


def test_export_in_kg_imports_back_into_a_fresh_log(monkeypatch, capsys, tmp_path):
    target = tmp_path / "out.csv"
    feed_input(monkeypatch, ["7", "11", str(target), EXIT])
    cli.main(units="kg")
    assert "(weights in kg)" in capsys.readouterr().out
    feed_input(monkeypatch, ["2", str(target), EXIT])
    cli.main()
    assert f"Loaded 20 of 20 entries from {target}" in capsys.readouterr().out


def test_export_refuses_to_overwrite_without_confirmation(monkeypatch, capsys, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("keep me")
    feed_input(monkeypatch, ["7", "11", str(target), "n", EXIT])
    cli.main()
    assert "Nothing exported." in capsys.readouterr().out
    assert target.read_text() == "keep me"

    feed_input(monkeypatch, ["7", "11", str(target), "y", EXIT])
    cli.main()
    assert "Exported 20 entries" in capsys.readouterr().out
    assert len(cli.FileLoader.load_file(str(target))) == 20


def test_export_with_empty_log(monkeypatch, capsys):
    feed_input(monkeypatch, ["11", EXIT])
    cli.main()
    assert "No entries to export." in capsys.readouterr().out


@pytest.mark.parametrize("answer,message", [
    ("", "Nothing exported."),
    ("out.txt", "must end in .csv or .json"),
])
def test_export_bad_paths(monkeypatch, capsys, tmp_path, answer, message):
    monkeypatch.chdir(tmp_path)
    feed_input(monkeypatch, ["7", "11", answer, EXIT])
    cli.main()
    assert message in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_export_into_missing_folder_reports_error(monkeypatch, capsys, tmp_path):
    feed_input(monkeypatch, ["7", "11", str(tmp_path / "nope" / "out.csv"), EXIT])
    assert cli.main() == 0
    assert "Could not export to" in capsys.readouterr().out


def test_export_to_a_folder_is_refused(monkeypatch, capsys, tmp_path):
    folder = tmp_path / "dir.json"
    folder.mkdir()
    feed_input(monkeypatch, ["7", "11", str(folder), EXIT])
    cli.main()
    assert "is a folder" in capsys.readouterr().out


def test_export_onto_the_data_file_is_refused(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "11", str(path), EXIT])
    cli.main(path)
    assert "That file holds your saved log or settings" in capsys.readouterr().out
    assert all("unit" not in row for row in json.loads(path.read_text()))


def test_export_onto_the_settings_file_is_refused(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    settings = tmp_path / "log.settings.json"
    feed_input(monkeypatch, ["7", "12", "kg", "11", str(settings), EXIT])
    cli.main(path)
    assert "That file holds your saved log or settings" in capsys.readouterr().out
    assert json.loads(settings.read_text()) == {"unit": "kg"}


def test_export_path_with_nul_character_is_reported(monkeypatch, capsys, tmp_path):
    path = tmp_path / "log.json"
    feed_input(monkeypatch, ["7", "11", "foo\0.csv", EXIT])
    assert cli.main(path) == 0
    assert "Could not export to" in capsys.readouterr().out


def write_plain_csv(tmp_path):
    path = tmp_path / "plain.csv"
    path.write_text("date,weight,calories\n2025-07-01,90.5,2200\n")
    return path


@pytest.mark.parametrize("answer,shown", [("kg", "90.5 kg"), ("", "41.05 kg")])
def test_kg_mode_asks_the_unit_of_plain_weights(monkeypatch, capsys, tmp_path, answer, shown):
    path = write_plain_csv(tmp_path)
    feed_input(monkeypatch, ["2", str(path), answer, "8", EXIT])
    cli.main(units="kg")
    out = capsys.readouterr().out
    assert "Loaded 1 of 1 entries" in out
    assert f"2025-07-01  {shown}  2200 cals" in out


def test_kg_mode_reasks_on_unknown_file_unit(monkeypatch, capsys, tmp_path):
    path = write_plain_csv(tmp_path)
    feed_input(monkeypatch, ["2", str(path), "stone", "kg", EXIT])
    cli.main(units="kg")
    out = capsys.readouterr().out
    assert "Please enter 'lbs' or 'kg'." in out
    assert "Loaded 1 of 1 entries" in out


def test_lbs_mode_reads_plain_weights_as_lbs_without_asking(monkeypatch, capsys, tmp_path):
    path = write_plain_csv(tmp_path)
    path.write_text("date,weight,calories\n2025-07-01,190.5,2200\n")
    feed_input(monkeypatch, ["2", str(path), EXIT])
    cli.main()
    assert "Loaded 1 of 1 entries" in capsys.readouterr().out


def test_kg_mode_does_not_ask_when_the_file_names_its_unit(monkeypatch, capsys, tmp_path):
    target = tmp_path / "out.json"
    feed_input(monkeypatch, ["7", "11", str(target), EXIT])
    cli.main(units="kg")
    capsys.readouterr()
    feed_input(monkeypatch, ["2", str(target), EXIT])
    cli.main(units="kg")
    out = capsys.readouterr().out
    assert "Loaded 20 of 20 entries" in out
    assert "say their unit" not in out


def test_weight_prompts_name_the_unit(monkeypatch):
    prompts = []
    answers = iter(["7", "1", "2025-08-01", "89", "2200", "5", "89", "85", "60", "9", "2025-07-01", "90", "2200", EXIT])

    def fake_input(prompt=""):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(builtins, "input", fake_input)
    cli.main(units="kg")
    weight_prompts = [p for p in prompts if "weight" in p]
    assert weight_prompts == ["Enter weight (kg): ", "Enter current weight (kg): ",
                              "Enter target weight (kg): ", "Enter new weight (kg): "]
