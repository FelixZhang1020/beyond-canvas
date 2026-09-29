"""The class console and the Spark's terminal monitor read one account of the chip.

Side by side they once disagreed: the console called a resting video service's last job "11m 17s"
while the monitor showed that clip cancelled after 17 min 41 s, the console's 3D "last" was two days old,
it counted memory in thousands against the monitor's 1024s, and it knew nothing of the models kept
loaded, Blender or tests. Both now draw on `deploy/spark/dashboard_jobs.py`; these tests pin what it says
and that the console passes it on. Docker and the chip are never asked: the tests hand it their answers.
"""
import time

import pytest

import studio.ops.spark_monitor as spark_monitor

jobs = spark_monitor.monitor()


def test_the_last_job_is_the_last_one_however_it_ended():
    today = time.time()
    finished = [{'at': today - 7200, 'kind': 'video', 'seconds': 677.2, 'outcome': 'ok'},
                {'at': today - 600, 'kind': 'video', 'seconds': 1061.0, 'outcome': 'cancelled'},
                {'at': today - 300, 'kind': 'trellis', 'seconds': 612.3, 'outcome': 'cancelled'},
                {'at': today - 60, 'kind': 'trellis', 'seconds': 0.4, 'outcome': 'failed'}]
    rows = jobs.finished_rows(finished, [(today - 30, 'blender', 'Blender: a render', 'done', 10)])
    assert [(row['what'], row['outcome']) for row in rows] == [
        ('Blender: a render', 'done'), ('3D model (TRELLIS.2)', 'refused'),
        ('3D model (TRELLIS.2)', 'cancelled'), ('Video clip (Wan)', 'cancelled'), ('Video clip (Wan)', 'done')]
    assert rows[3]['seconds'] == 1061.0
    assert rows[3]['clock'] == time.strftime('%H:%M', time.localtime(today - 600)), "the Spark's clock, for both screens"


def test_today_counts_a_cancelled_job_as_cancelled_not_as_a_failure():
    now = time.time()
    finished = [{'at': now - 60, 'kind': 'video', 'seconds': 671, 'outcome': 'ok'},
                {'at': now - 30, 'kind': 'video', 'seconds': 1061, 'outcome': 'cancelled'},
                {'at': now - 20, 'kind': 'video', 'seconds': 398, 'outcome': 'failed'},
                {'at': now - 400000, 'kind': 'video', 'seconds': 671, 'outcome': 'ok'}]
    ended = [(now - 10, 'test', 'a trial', 'stopped', 60), (now - 5, 'blender', 'a render', 'done', 10)]
    today = jobs.today_totals(finished, ended)
    assert today['jobs'] == [{'what': 'Video clip (Wan)', 'done': 1, 'refused': 0, 'cancelled': 1, 'failed': 1}]
    assert today['tests'] == {'finished': 2, 'stopped': 1, 'error': 0}


def test_a_running_container_is_described_the_same_for_both_screens(monkeypatch):
    started = time.time() - 243
    monkeypatch.setattr(jobs, 'run', lambda *command, both=False: '')
    box = {'name': 'beyond-canvas-media-0123456789ab', 'started': started, 'pid': 1, 'kind': 'video',
           'task': ('Video clip (Wan)', 'class'), 'held': 72.4}
    finished = [{'kind': 'video', 'seconds': s, 'outcome': 'ok'} for s in (669.0, 671.0, 641.8)]
    row = jobs.box_row(box, finished, idle=False)
    assert row['group'] == 'class' and row['usual_s'] == 669.0 and row['held_gb'] == 72.4
    assert 242 <= row['running_s'] <= 245 and row['stuck'] is False


def test_the_console_hands_on_what_the_monitor_says_and_asks_again_only_after_a_while(monkeypatch):
    asked = []
    monkeypatch.setattr(spark_monitor, '_cached', None)
    monkeypatch.setattr(jobs, 'picture', lambda: asked.append(1) or {'now': [], 'finished': [], 'today': {}})
    for _ in range(5):
        assert spark_monitor.picture() == {'now': [], 'finished': [], 'today': {}}
    assert asked == [1]


def test_a_monitor_that_cannot_read_leaves_a_gap_not_a_broken_console(monkeypatch):
    monkeypatch.setattr(spark_monitor, '_cached', None)
    monkeypatch.setattr(jobs, 'picture', lambda: (_ for _ in ()).throw(OSError('no docker')))
    assert spark_monitor.picture() is None


def test_console_memory_is_counted_in_1024s_as_the_monitor_counts_it(monkeypatch, tmp_path):
    import studio.showpiece.routes as routes
    meminfo = tmp_path / 'meminfo'
    meminfo.write_text('MemTotal:       127600000 kB\nMemAvailable:    41200000 kB\n')
    real = routes.Path
    monkeypatch.setattr(routes, 'Path', lambda value: meminfo if value == '/proc/meminfo' else real(value))
    monkeypatch.setattr(routes.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(routes.shutil, 'which', lambda name: None)
    stats = routes.machine_stats()
    assert stats['memory_total_gb'] == pytest.approx(121.7, abs=0.05)     # the monitor's "of 122 GB"
    assert stats['memory_used_gb'] == pytest.approx(82.4, abs=0.05)       # its "82 ... in use"
