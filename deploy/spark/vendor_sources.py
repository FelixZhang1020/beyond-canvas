"""Fetch every GitHub-hosted piece the Spark's 3D containers build from, at its pinned revision.

The node cannot reach GitHub, so the TRELLIS.2 and Pixal3D builds cannot clone
anything. This runs on the Mac and lays the same pinned sources out in one
folder that sync.sh then carries across: each repository as an archive of its
exact revision (no history), with its submodules filled in at the revisions the
parent pins, plus the two release files the builds would otherwise download
(Pixal3D's utils3d wheel and NAF's weights).

Revisions are read from deploy/trellis2/versions.env; this file only says where
each one lives. Archives come from codeload.github.com and submodule revisions
from a blob-less bare clone, because the GitHub API allows sixty unauthenticated
calls an hour and the Mac's shared exit address had already spent them.

    python3 deploy/spark/vendor_sources.py [DESTINATION]   # default deploy/trellis2/vendor (gitignored)

Dockerfile.dgx-spark for TRELLIS.2 and Pixal3D copy from that folder.
"""
import io
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / 'trellis2' / 'versions.env'
REPOSITORIES = {  # versions.env key: (GitHub repository, folder in the vendor tree)
    'TRELLIS2_SOURCE_REVISION': ('microsoft/TRELLIS.2', 'trellis2'),
    'UTILS3D_REVISION': ('EasternJournalist/utils3d', 'utils3d'),
    'NVDIFFRAST_REVISION': ('NVlabs/nvdiffrast', 'nvdiffrast'),
    'NVDIFFREC_REVISION': ('JeffreyXiang/nvdiffrec', 'nvdiffrec'),
    'CUMESH_REVISION': ('JeffreyXiang/CuMesh', 'CuMesh'),
    'FLEXGEMM_REVISION': ('JeffreyXiang/FlexGEMM', 'FlexGEMM'),
    'PIXAL3D_SOURCE_REVISION': ('TencentARC/Pixal3D', 'Pixal3D'),
    'NAF_REVISION': ('valeoai/NAF', 'torch/hub/valeoai_NAF_main'),
}
RELEASE_FILES = {'PIXAL3D_UTILS3D_WHEEL': 'wheels', 'NAF_WEIGHTS': 'torch/hub/checkpoints'}


def versions() -> dict[str, str]:
    pairs = (line.split('=', 1) for line in VERSIONS.read_text().splitlines() if re.match(r'^[A-Z0-9_]+=', line))
    return {key: value.strip() for key, value in pairs}


def archive_url(repository: str, revision: str) -> str:
    """A tarball of one revision. `repository` is owner/name on GitHub, or a full https URL."""
    if repository.startswith('https://gitlab.com/'):   # o-voxel's Eigen submodule lives on GitLab
        base = repository.removesuffix('.git')
        return f'{base}/-/archive/{revision}/{base.rsplit("/", 1)[1]}-{revision}.tar.gz'
    name = re.sub(r'^https://github\.com/', '', repository).removesuffix('.git')
    return f'https://codeload.github.com/{name}/tar.gz/{revision}'


def unpack(repository: str, revision: str, target: Path) -> None:
    """The repository's tree at revision, without history, into target."""
    with urllib.request.urlopen(archive_url(repository, revision), timeout=300) as response:
        archive = tarfile.open(fileobj=io.BytesIO(response.read()), mode='r:gz')
    target.mkdir(parents=True, exist_ok=True)
    for member in archive.getmembers():
        member.name = member.name.split('/', 1)[1] if '/' in member.name else ''
        if member.name:
            archive.extract(member, target, filter='data')


def submodules(repository: str, revision: str, tree: Path, log: list[str]) -> None:
    """Fill each submodule of tree at the revision the parent pins, recursively."""
    modules = tree / '.gitmodules'
    if not modules.is_file():
        return
    entries = re.findall(r'path\s*=\s*(\S+)\s+url\s*=\s*(\S+)', modules.read_text())
    clone_url = repository if repository.startswith('https://') else f'https://github.com/{repository}.git'
    with tempfile.TemporaryDirectory() as bare:
        subprocess.run(['git', 'clone', '-q', '--bare', '--filter=blob:none', clone_url, bare], check=True)
        for path, url in entries:
            listing = subprocess.run(['git', '--git-dir', bare, 'ls-tree', revision, '--', path],
                                     check=True, capture_output=True, text=True).stdout.split()
            pinned = listing[2]
            unpack(url, pinned, tree / path)
            log.append(f'{url} {pinned} {tree.name}/{path}')
            submodules(url, pinned, tree / path, log)


def main() -> None:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else VERSIONS.parent / 'vendor'
    pins, log = versions(), []
    for key, (repository, folder) in REPOSITORIES.items():
        target = destination / folder
        if not (target / '.vendored').is_file():
            unpack(repository, pins[key], target)
            submodules(repository, pins[key], target, log)
            (target / '.vendored').write_text(pins[key] + '\n')
        log.append(f'{repository} {pins[key]} {folder}')
    for key, folder in RELEASE_FILES.items():
        target = destination / folder / pins[key].rsplit('/', 1)[1]
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(pins[key], timeout=300) as response:
                target.write_bytes(response.read())
        log.append(f'{pins[key]} {target.relative_to(destination)}')
    (destination / 'VENDORED').write_text('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
