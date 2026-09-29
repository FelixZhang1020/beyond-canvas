"""The port convention, enforced rather than remembered.

Settled with the operator: every port this product listens on
sits between 7000 and 7700 and ends in a zero. The tens digit is free, the unit
digit is not, which leaves seventy-one addresses and makes any port belonging
to this studio recognisable at a glance in `lsof`.

The hundreds digit carries the meaning, and it is the same grouping section 7
uses for memory, so the number tells you when a thing is loaded as well as
where:

    70x0  the things a person opens: the page, the board, the preview
    71x0  the resident core, up for the whole class
    72x0  the resident media models
    73x0  the rotating slot, one at a time, unload before load

These are tests rather than a paragraph in a document because the old scheme
drifted into a collision that nothing noticed: `studio/serve.py` defaulted to
8080 and so did the local studio model, so whichever started second could not
bind, and the board reported the page as up when what answered was the model.
A convention with no check is a convention until the first hurry.
"""

import re
from pathlib import Path

import pytest
import yaml

from studio.ops.modelboard import EXTRA_PORTS, port_of
from studio.providers.llamacpp import DEFAULT_BASE_URL

LOW, HIGH = 7000, 7700
PROFILES = sorted(Path("studio/profiles").glob("*.yaml"))


def profile_ports(path):
    """Every slot in one profile that names a port, as (slot, port)."""
    slots = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("slots") or {}
    found = []
    for slot, config in slots.items():
        port = port_of((config.get("options") or {}).get("base_url", ""))
        if port:
            found.append((slot, port))
    return found


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_every_profile_port_is_in_range(path):
    for slot, port in profile_ports(path):
        assert LOW <= port <= HIGH, f"{path.stem}:{slot} listens on {port}"


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_every_profile_port_ends_in_zero(path):
    for slot, port in profile_ports(path):
        assert port % 10 == 0, f"{path.stem}:{slot} listens on {port}"


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_no_two_models_in_one_profile_share_a_port(path):
    """The bug this whole convention came out of. Two servers, one port, and the
    second one silently fails to bind.

    Two SLOTS may share a port when they are the same model: CosyVoice 2 serves
    both `tts.studio` and `tts.export` from one server, in instructed mode and
    cloning mode, and loading it twice would waste 4.5 GB of a box that counts
    every gigabyte. What must never happen is two different models on one port,
    which is the case that silently fails to bind."""
    models = load(path)
    holders: dict[int, set[str]] = {}
    for slot, port in profile_ports(path):
        holders.setdefault(port, set()).add(models[slot])
    clashing = {port: sorted(names) for port, names in holders.items() if len(names) > 1}
    assert not clashing, f"{path.stem} puts different models on one port: {clashing}"


def load(path):
    """Every slot in a profile mapped to the model it names."""
    import yaml
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # localimage is one multiplexed server accepting an explicit model id;
    # all other providers retain the one-model-per-listener collision guard.
    return {slot: ('localimage-worker' if entry['provider'] == 'localimage' else entry['model'])
            for slot, entry in (document.get('slots') or {}).items()}


def test_the_page_does_not_sit_on_a_model_port():
    """`studio/serve.py` and the local studio model collided on 8080 for a day."""
    page = next(port_of(url) for slot, _, url, _ in EXTRA_PORTS if slot == "studio.page")
    model_ports = {port for path in PROFILES for _, port in profile_ports(path)}
    assert page not in model_ports, f"the page is back on a model port ({page})"


def test_every_port_outside_the_profiles_follows_the_convention_too():
    """Whisper and the page are not model slots, and the rule is not about slots."""
    for slot, _, url, _ in EXTRA_PORTS:
        port = port_of(url)
        assert port and LOW <= port <= HIGH and port % 10 == 0, f"{slot} is on {port}"


def test_the_llamacpp_client_default_follows_the_convention():
    """A client that defaults outside the range would quietly reintroduce it."""
    port = port_of(DEFAULT_BASE_URL)
    assert port and LOW <= port <= HIGH and port % 10 == 0


def test_the_board_serves_inside_the_range():
    from studio.ops.modelboard import BOARD_PORT

    assert LOW <= BOARD_PORT <= HIGH and BOARD_PORT % 10 == 0


def test_no_source_file_still_points_at_the_old_scheme():
    """Documentation that names a dead port sends someone to a closed door.

    Dated plans outside these folders are exempt: they say what was
    true when they were written, and rewriting them would be a lie about the
    past rather than a fix.
    """
    stale = re.compile(r"127\.0\.0\.1:(80[0-9][0-9]|8767)|--port +(80[0-9][0-9]|8767)")
    roots = [Path("studio"), Path("skills"), Path("evalkit"), Path("tests"),
             Path("README.md"), Path("docs/measured")]
    offenders = []
    for root in roots:
        files = [root] if root.is_file() else [
            p for p in root.rglob("*")
            if p.suffix in {".py", ".yaml", ".md", ".json", ".js", ".sh"}
            and "__pycache__" not in p.parts
        ]
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if stale.search(line):
                    offenders.append(f"{path}:{number}: {line.strip()[:70]}")
    assert not offenders, "still pointing at the old ports:\n" + "\n".join(offenders)


def test_the_convention_leaves_room_to_grow():
    """Seventy-one addresses against fourteen in use. If this ever gets tight the
    answer is a second band, not a port ending in something other than zero."""
    used = {port for path in PROFILES for _, port in profile_ports(path)}
    used |= {port_of(url) for _, _, url, _ in EXTRA_PORTS}
    available = len(range(LOW, HIGH + 1, 10))
    assert len(used) < available / 2, f"{len(used)} of {available} taken"



def model_ports():
    """Every port something other than the page answers on."""
    ports = {port for path in PROFILES for _, port in profile_ports(path)}
    ports |= {port_of(url) for slot, _, url, _ in EXTRA_PORTS if slot != "studio.page"}
    return ports


def test_the_page_server_default_port_is_the_page_port():
    """The command line once disagreed with the function it calls.

    `main` passed its own default down, so the collision only
    reappeared for a caller who omitted the port — a test, an embedding, the
    Spark's launcher. A default that is wrong everywhere except the one path
    anybody exercises is the worst kind, because nothing reports it.
    """
    import inspect

    from studio import serve

    page = next(port_of(url) for slot, _, url, _ in EXTRA_PORTS if slot == "studio.page")
    default = inspect.signature(serve.make_server).parameters["port"].default
    assert default == page, f"make_server defaults to {default}, not the page port {page}"


def test_the_page_port_has_one_source():
    """Two literals for one port drift; this one already had, by 1100."""
    from studio.serve import PAGE_PORT

    page = next(port_of(url) for slot, _, url, _ in EXTRA_PORTS if slot == "studio.page")
    assert PAGE_PORT == page, f"serve.py says {PAGE_PORT}, the board says {page}"


def test_the_page_port_avoids_macos_airplay():
    """The local classroom must not reuse Control Center's AirPlay port."""
    from studio.server.ports import PAGE_PORT
    from studio.serve import AIRPLAY_PORTS

    assert PAGE_PORT == 7060
    assert PAGE_PORT not in AIRPLAY_PORTS


def test_no_readme_sends_a_person_to_a_model_port():
    """Both READMEs told a reader to open 7100 for the page, which is the studio
    model. One of them printed a command that would try to bind it.

    A line naming a model server is exempt: that is where a model port belongs.
    """
    naming = re.compile(r"127\.0\.0\.1:([0-9]{4})|http\.server +([0-9]{4})|--port +([0-9]{4})")
    serving_a_model = re.compile(r"llama-server|whisper-server|localmodels\.sh|modelboard")
    taken = model_ports()
    offenders = []
    for path in (Path("README.md"), Path("studio/page/README.md")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if serving_a_model.search(line):
                continue
            for match in naming.finditer(line):
                port = int(next(group for group in match.groups() if group))
                if port in taken:
                    offenders.append(f"{path}:{number}: {line.strip()[:70]}")
    assert not offenders, "a reader following this lands on a model:\n" + "\n".join(offenders)


def test_the_runtime_agrees_with_the_convention_this_file_states():
    """The numbers live in studio/server/ports.py so the product can act on them; they
    are written out again here so a test cannot be satisfied by editing them."""
    from studio.server import ports

    assert (ports.LOW, ports.HIGH) == (7000, 7700)


def test_an_off_convention_port_is_named_rather_than_silently_used():
    """Enforcement stops at the command line: a person can still type any port.

    Found live with two of our own servers outside the band, one
    on 8412 and one on 8767. Neither said anything, so the only way to notice
    was `lsof`. The port a person types is theirs to choose; going quiet about
    it is what let the 8080 collision live for a day.
    """
    from studio.server.ports import off_convention

    for stray in (8412, 8767, 7015, 6999):
        said = off_convention(stray)
        assert said and str(stray) in said and "7000" in said and "7700" in said

    assert off_convention(7000) is None
    assert off_convention(7700) is None
    assert off_convention(0) is None, "port 0 is how a test asks for an ephemeral one"


def test_the_page_says_so_when_it_is_started_off_convention(capsys, monkeypatch, tmp_path):
    """The warning has to be on the path a person actually runs, not beside it."""
    from studio import serve

    class Stopped:
        def serve_forever(self):
            raise KeyboardInterrupt

        def server_close(self):
            pass

    class Opened:
        # A real Classroom always carries the profile it resolved; the double has
        # to as well, or it stops standing in for the thing under test.
        profile = "stepfun"

        def close(self):
            pass

    monkeypatch.setattr(serve, "Classroom", lambda *a, **k: Opened())
    monkeypatch.setattr(serve, "make_server", lambda *a, **k: Stopped())
    serve.main(["--port", "8412", "--ledger", str(tmp_path / "ledger.jsonl")])
    said = capsys.readouterr()
    assert "8412" in said.err, (
        "a warning on stdout arrives after the error it should precede: stdout is\n"
        "block-buffered into a pipe or a file while stderr is not, so a redirected\n"
        "run printed the bind failure first and the reason for it last")


def test_the_board_says_so_when_it_is_started_off_convention(capsys, monkeypatch):
    from studio.ops import modelboard

    monkeypatch.setattr(modelboard, "serve", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["modelboard", "--port", "8767"])
    modelboard.main()
    assert "8767" in capsys.readouterr().err


def test_a_taken_page_port_says_what_is_holding_it():
    """macOS AirPlay Receiver holds *:5000 and *:7000. A loopback bind wins over
    it, so the teacher's own browser is fine and nothing looks wrong — until
    `--host 0.0.0.0` for a tablet, which is refused with "Address already in
    use" and no hint of the cause. Measured: 0.0.0.0:5000 and
    0.0.0.0:7000 both refused with SO_REUSEADDR set, 0.0.0.0:7040 bound.

    The Spark is Linux and has no such thing, so the sentence is platform-bound.
    """
    from studio.serve import why_busy

    tablet = why_busy("0.0.0.0", 7000, platform="darwin")
    assert "AirPlay" in tablet and "--port" in tablet

    assert "AirPlay" not in why_busy("0.0.0.0", 7000, platform="linux")
    assert "AirPlay" not in why_busy("127.0.0.1", 7000, platform="darwin"), \
        "a loopback bind beats AirPlay, so on loopback it is another studio"
    assert "--port" in why_busy("127.0.0.1", 7000, platform="darwin")


def test_the_remedy_it_offers_is_itself_inside_the_band():
    """It suggested `--port 8442` for a busy 8412: a remedy that breaks the rule
    the same program had just printed a warning about."""
    from studio.serve import why_busy

    for port in (7000, 7690, 8412):
        said = why_busy("127.0.0.1", port, platform="darwin")
        suggested = int(re.search(r"--port (\d+)", said).group(1))
        assert LOW <= suggested <= HIGH and suggested % 10 == 0, said


def test_the_exhibit_port_has_one_source():
    """The exhibit's port used to be a bare literal in its own argparse line,
    registered in `studio/server/ports.py` nowhere. Nothing was broken by
    that -- the server bound 7090 and answered -- but the number could not be
    looked up, so to anybody reading `--port 7090` it was a figure with no
    origin, and that is how it was reported: as confusing rather than as wrong.
    A constant nothing checks drifts back into a literal, so this pins the two
    together the way `test_the_page_port_has_one_source` pins the page's.
    """
    import inspect

    from studio.server.ports import EXHIBIT_PORT
    from studio.showpiece.__main__ import main

    source = inspect.getsource(main)
    assert "default=EXHIBIT_PORT" in source, (
        "the exhibit's --port default no longer reads from studio.server.ports")
    assert "default=7090" not in source, "the literal is back alongside the constant"
    assert EXHIBIT_PORT == 7090, (
        f"the exhibit moved to {EXHIBIT_PORT}; launch.json, the project snapshot and "
        f"docs/measured/ (demonstration-dashboard, first-driven-run, harness-view) all name 7090 "
        f"and would need moving too")


def test_the_exhibit_port_is_not_a_model_port():
    """The page and the exhibit are the two things a person opens at once. If
    either landed on a model's port the collision would only show while the GPU
    machine's models are running, which nobody has while developing.
    """
    from studio.server.ports import EXHIBIT_PORT

    assert EXHIBIT_PORT not in model_ports(), (
        f"the exhibit is on {EXHIBIT_PORT}, which a model already answers on")


def test_the_remedy_never_names_a_port_we_already_own():
    """It suggested `--port 7090` for a busy 7060 hours after 7090
    became the exhibit's registered port. Inside the band, ending in zero, and
    wrong: the remedy for "something is already listening" pointed at another one
    of our servers. The operator hit it in a terminal.

    The earlier bug this function was written for was the same shape one level
    up -- a suggestion that broke the rule the program had just printed. So the
    test is over every port in the band rather than the one that failed.
    """
    from studio.server.ports import REGISTERED, spare_port

    for busy in range(LOW, HIGH + 1, 10):
        suggested = spare_port(busy)
        assert LOW <= suggested <= HIGH and suggested % 10 == 0, f"{busy} -> {suggested}"
        assert suggested not in REGISTERED, (
            f"a busy {busy} is answered with {suggested}, which is already ours")
        assert suggested != busy, f"{busy} was offered itself"


def test_the_registry_names_every_port_the_studio_binds():
    """`REGISTERED` is what stops the remedy above pointing at one of our own.
    A port added to this module and left out of the registry would be offered to
    somebody as free, so the two are kept in step here rather than by memory.
    """
    from studio.server import ports

    named = {value for key, value in vars(ports).items()
             if key.endswith("_PORT") and isinstance(value, int)}
    assert named == set(ports.REGISTERED), (
        f"named but unregistered: {sorted(named - set(ports.REGISTERED))}; "
        f"registered but unnamed: {sorted(set(ports.REGISTERED) - named)}")


def test_the_voice_lab_port_matches_the_one_registered_for_it():
    """`studio/ops/voice_lab.py` is over the size guard's hard limit, so it cannot be
    edited to import this and keeps its own literal. A number written twice
    drifts, so the copy is checked instead of trusted -- if either moves, the
    registry stops protecting the other from being suggested as free.
    """
    from studio.server.ports import VOICE_LAB_PORT
    from studio.ops.voice_lab import PORT

    assert PORT == VOICE_LAB_PORT, (
        f"voice_lab.py says {PORT}, studio/server/ports.py says {VOICE_LAB_PORT}")
