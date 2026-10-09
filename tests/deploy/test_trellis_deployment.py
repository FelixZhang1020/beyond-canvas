"""Fresh-host prerequisites, without downloads, Docker startup or a GPU."""
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / 'deploy/trellis2'


def test_prepare_bind_source_preserves_existing_lock(tmp_path):
    deployment = tmp_path / 'trellis2'
    deployment.mkdir()
    lock = tmp_path / 'gpu.lock'
    command = ['bash', str(DEPLOY / 'prepare-runtime.sh'), str(deployment)]
    # A fresh installation starts in the exact state Compose refuses to mount.
    assert not lock.exists()
    subprocess.run(command, check=True)
    assert lock.is_file()
    lock.write_text('existing lock metadata')
    inode = lock.stat().st_ino
    subprocess.run(command, check=True)
    assert lock.stat().st_ino == inode
    assert lock.read_text() == 'existing lock metadata'


def test_prepare_rejects_directory_without_removing_it(tmp_path):
    deployment = tmp_path / 'trellis2'
    deployment.mkdir()
    lock = tmp_path / 'gpu.lock'
    lock.mkdir()
    result = subprocess.run(['bash', str(DEPLOY / 'prepare-runtime.sh'), str(deployment)], capture_output=True)
    assert result.returncode != 0
    assert lock.is_dir()


def test_spark_publishes_bridge_without_taking_4090_worker_port():
    base = yaml.safe_load((DEPLOY / 'compose.yaml').read_text())['services']['trellis2']
    spark = yaml.safe_load((DEPLOY / 'compose.dgx-spark.yaml').read_text())['services']['trellis2']
    bridge = '127.0.0.1:7240:7240'
    assert bridge not in base['ports']
    assert bridge in spark['ports']


def test_installer_prepares_mount_before_first_container_run():
    script = (DEPLOY / 'install-dgx-spark.sh').read_text()
    assert script.index('bash "$script_root/prepare-runtime.sh"') < script.index('"${compose[@]}" run')
