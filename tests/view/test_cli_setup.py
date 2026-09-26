"""`deskglow setup` (scan, pick, save, test) and `deskglow repair`."""
import pytest
from fakes import FakeScanner, make_services

from deskglow.services.link import AdapterError
from deskglow.view import cli

FFF0 = "0000fff0-0000-1000-8000-00805f9b34fb"


def _adv(addr, name="MELK-OA10", rssi=-45, certain=True):
    return {"address": addr, "name": name, "rssi": rssi,
            "service_uuids": [FFF0] if certain else []}


@pytest.fixture
def sent(monkeypatch):
    seen = []

    async def fake_send(self, req):
        seen.append(req)
        return 0

    monkeypatch.setattr(cli.Cli, "send", fake_send)
    return seen


def setup_with(*adverts, error=None):
    services = make_services(scanner=FakeScanner(adverts, error=error))
    return services, cli.main(["setup"], services_factory=lambda: services)


# ------------------------------------------------------------------- setup ---

def test_setup_saves_the_only_strip_found(capsys, sent):
    """One candidate is chosen automatically and its MAC persisted."""
    services, rc = setup_with(_adv("AA:BB:CC:DD:EE:FF"))
    assert rc == 0
    assert services.storage.config["address"] == "AA:BB:CC:DD:EE:FF"
    assert sent == [{"cmd": "reload"},
                    {"cmd": "set_mode", "mode": "solid", "args": {"rgb": [255, 255, 255]}}]
    assert "AA:BB:CC:DD:EE:FF" in capsys.readouterr().out
    assert services.scanner.timeouts == [10.0]


def test_setup_lets_the_user_pick_from_several(monkeypatch, sent):
    """With several candidates the user's choice is the one that gets saved."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
    services, rc = setup_with(_adv("11:11:11:11:11:11", rssi=-40),
                              _adv("22:22:22:22:22:22", certain=False))
    assert rc == 0
    assert services.storage.config["address"] == "22:22:22:22:22:22"


def test_setup_lists_candidates_with_a_likely_hint(monkeypatch, capsys, sent):
    monkeypatch.setattr("builtins.input", lambda _prompt="": "1")
    setup_with(_adv("11:11:11:11:11:11"), _adv("22:22:22:22:22:22", certain=False))
    out = capsys.readouterr().out
    assert "11:11:11:11:11:11  signal -45dBm  ← likely" in out
    assert "22:22:22:22:22:22  signal -45dBm\n" in out


def test_setup_defaults_to_the_first_candidate_on_bare_enter(monkeypatch, sent):
    """Pressing enter picks the strongest/most likely candidate."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    services, rc = setup_with(_adv("11:11:11:11:11:11", rssi=-30),
                              _adv("22:22:22:22:22:22", rssi=-60))
    assert rc == 0
    assert services.storage.config["address"] == "11:11:11:11:11:11"


def test_setup_reports_when_nothing_is_found(capsys, sent):
    """No strips found is a guided failure, exit 1, and nothing is saved."""
    services, rc = setup_with(_adv("99:00:00:00:00:01", name="Bose QC35", certain=False))
    assert rc == 1
    out = capsys.readouterr().out
    assert "No LED strips found" in out
    assert "deskglow setup" in out
    assert "address" not in services.storage.config
    assert sent == []


def test_setup_reports_a_scan_failure_without_a_traceback(capsys, sent):
    """A dead Bluetooth adapter yields advice on stderr, not a stack trace."""
    services, rc = setup_with(error=RuntimeError("org.bluez: No adapter"))
    assert rc == 1
    err = capsys.readouterr().err
    assert "Scan failed" in err
    assert "No adapter" in err
    assert "Is Bluetooth turned on?" in err
    assert "address" not in services.storage.config


@pytest.mark.parametrize("answer", [EOFError(), KeyboardInterrupt(), "x", "9"])
def test_setup_cancelled_at_the_prompt_saves_nothing(monkeypatch, sent, answer):
    """Ctrl-D/Ctrl-C/garbage/out-of-range at the prompt aborts cleanly with exit 1."""
    def fake_input(_prompt=""):
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr("builtins.input", fake_input)
    services, rc = setup_with(_adv("11:11:11:11:11:11"), _adv("22:22:22:22:22:22"))
    assert rc == 1
    assert "address" not in services.storage.config
    assert sent == []


# ------------------------------------------------------------------ repair ---

def test_repair_resets_the_adapter_for_the_configured_strip(sent):
    """`repair` bounces the adapter, forgets the stale bond, then reconnects."""
    services = make_services()
    services.storage.config["address"] = "AA:BB:CC:DD:EE:FF"
    assert cli.main(["repair"], services_factory=lambda: services) == 0
    assert services.link.resets == ["AA:BB:CC:DD:EE:FF"]
    assert sent == [{"cmd": "reload"}]


def test_repair_without_a_configured_strip_passes_no_address(sent):
    """With no MAC saved there is no bond to drop; the adapter reset still runs."""
    services = make_services()
    assert cli.main(["repair"], services_factory=lambda: services) == 0
    assert services.link.resets == [None]


def test_repair_reports_an_adapter_error_instead_of_crashing(capsys, sent):
    """A missing bluetoothctl (AdapterError) must explain itself, exit 1, no reload."""
    services = make_services()
    services.link.reset_error = AdapterError("'bluetoothctl' was not found. Install BlueZ")
    assert cli.main(["repair"], services_factory=lambda: services) == 1
    out = capsys.readouterr()
    assert "bluetoothctl" in out.err.lower()
    assert sent == []


def test_setup_saves_the_advertised_name_with_the_address(sent):
    services, rc = setup_with(_adv("AA:BB:CC:DD:EE:FF", name="ELK-BLEDOM"))
    assert rc == 0
    assert services.storage.config == {"address": "AA:BB:CC:DD:EE:FF", "name": "ELK-BLEDOM"}
