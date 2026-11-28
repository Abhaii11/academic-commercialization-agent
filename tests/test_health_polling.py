"""A page with a run open does not ask for /health every second.

Found on main (55b6b7e) on 2026-11-28 while PR #518 was being built: once a
run was open, app.js asked for /health every second (CAPACITY_INTERVAL_ACTIVE
= 1000, chosen by whether any run id was on screen), and kept on for as long
as the tab was open and visible. A reader of a shared report finished weeks
before sent 3,600 requests an hour; so did an owner's tab left on any
finished run. Counted on main in tests/js/landing_contract.mjs with the
shipped app.js on a clock the test moves: 61 readings in the first minute of
a completed, failed, cancelled, timed-out or gone run, and of a reader's view
of a run going or done; 61 of a running run's page, beside a progress poll
that asks at most every 4 s once a run has gone 90 s (run.js intervalFor).

What a run's page takes from the reading is the deployment's, not the run's:
the capacity line (an administrator's slot count; for everyone else, a line
only when every slot is taken), "offline" when the server cannot be reached,
the operator's contact under a failure only they can look into, the
retention period on the page of a run that is gone, and the model a resume
would use. The run's state, stage and estimate are its progress poll's.

What the page does now (app.js scheduleCapacity):

- A running run's page asks every 10 s, as every other page does, so never
  more often than its progress; and once more when it sees the run end, as
  the run's slot has just been given back.
- A page whose facts no longer change for its reader asks no more once it
  holds a reading: a run that has ended or is not there, someone else's run,
  and whatever a visitor with a link reads (a run or a comparison).
- A reading that failed is asked for again every 10 s until one answers, so
  "offline" does not outlast the outage.
- A hidden tab asks for nothing, as before, and a tab brought back asks at
  once only where the view still needs a reading.

The behaviour is exercised with the shipped modules in
tests/js/landing_contract.mjs (the scenarios listed in
tests/test_landing_page.py), and in Chromium by e2e/browser_smoke.py (a
reader of a finished shared run asks for no /health in 3.5 s after its
boot). The checks here keep the rule between the two polls in place.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = (_ROOT / "web/static/js/app.js").read_text(encoding="utf-8")
_RUN = (_ROOT / "web/static/js/run.js").read_text(encoding="utf-8")
_LANDING = (_ROOT / "tests/test_landing_page.py").read_text(encoding="utf-8")
_SMOKE = (_ROOT / "e2e/browser_smoke.py").read_text(encoding="utf-8")


def _ms(literal: str) -> int:
    return int(literal.replace("_", ""))


def test_the_health_reading_is_never_asked_for_more_often_than_a_runs_progress():
    """The rule, not the numbers: whatever either interval becomes, /health is not the busier poll."""
    capacity = re.findall(r"const CAPACITY_INTERVAL\w* = ([\d_]+);", _APP)
    assert capacity, "app.js names the health reading's interval"
    body = _RUN[_RUN.index("function intervalFor(elapsedMs) {"):]
    body = body[:body.index("\n}\n")]
    progress = [_ms(n) for n in re.findall(r"return ([\d_]+);", body)]
    assert progress, "run.js intervalFor returns the progress poll's intervals"
    assert min(_ms(n) for n in capacity) >= max(progress), (capacity, progress)


def test_how_often_is_decided_when_the_timer_fires_not_when_it_is_set():
    """A run's page schedules the reading before the run's first read says whether it has ended."""
    schedule = _APP[_APP.index("function scheduleCapacity() {"):]
    schedule = schedule[:schedule.index("\n}\n")]
    fired = schedule[schedule.index("setTimeout(async () => {"):]
    assert fired.index("if (capacityCurrent()) return;") < fired.index("await refreshCapacity();")
    assert "activeRunId ?" not in schedule, "Not chosen by whether a run is on screen"


def test_each_way_a_run_settles_says_so():
    follow = _APP[_APP.index("async function openRun("):]
    follow = follow[:follow.index("\n}\n")]
    assert follow.index("activeRunSettled = false;") < follow.index("showRun(runId);"), "Reset for each run opened"
    for hook in ("onUpdate(progress) {", "onDone(progress) {"):
        part = follow[follow.index(hook):]
        assert "activeRunSettled = true;" in part[:part.index("\n    },")], hook
    gone = _APP[_APP.index("function showGone() {"):]
    assert "activeRunSettled = true;" in gone[:gone.index("\n}\n")]


def test_the_behaviour_is_run_in_the_landing_harness_and_in_chromium():
    for scenario in ("a_finished_run_reads_the_health_once_not_every_second",
                     "a_reader_reads_the_health_once_whether_the_run_is_going_or_done",
                     "a_reading_that_failed_is_asked_again_until_one_answers",
                     "a_running_runs_page_reads_the_health_no_faster_than_its_progress",
                     "a_running_runs_page_still_shows_what_the_health_reading_says",
                     "a_hidden_tab_asks_for_no_health_reading_until_it_is_back"):
        assert f'"{scenario}"' in _LANDING, scenario
    assert "assert health_while_reading == 0" in _SMOKE
