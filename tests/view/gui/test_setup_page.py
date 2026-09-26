"""Setup: the daemon scans; pick a row or type an address; Use this strip."""
import pytest
from gui_fakes import push
from PySide6.QtCore import Qt

from deskglow.view.gui.screens.setup import SetupPage

CANDS = [{"address": "A4:C1:38:5E:22:9B", "name": "MELK-OA10", "rssi": -55, "certain": True},
         {"address": "BE:32:57:A0:13:6C", "name": "ELK-BLEDOM", "rssi": -76, "certain": False},
         {"address": "C4:18:E9:02:7F:21", "name": "LEDBLE-7F21", "rssi": -88, "certain": False}]


@pytest.fixture
def page(qtbot, ctx, client):
    client.replies["scan"] = {"ok": True, "candidates": CANDS}
    p = SetupPage(ctx)
    qtbot.addWidget(p)
    p.resize(1040, 720)
    p.show()
    push(ctx, client, configured=False)
    client.requests.clear()
    return p


def click(qtbot, w):
    qtbot.mouseClick(w, Qt.MouseButton.LeftButton)


def test_begin_scans_and_lists_what_the_daemon_found(page, client):
    page.begin()
    assert client.sent() == [{"cmd": "scan", "timeout": 8}]
    assert [w.row.address for w in page.rows] == [c["address"] for c in CANDS]
    assert page.rows[0].isChecked() and page.rows[0].row.likely
    assert page.headline.text() == "Found 3 LED controllers"
    assert page.rescan.isEnabled() and page.use.isEnabled()


def test_use_this_strip_saves_the_chosen_one_then_turns_it_on(qtbot, page, ctx, client):
    went = []
    ctx.navigate.connect(went.append)
    page.begin()
    click(qtbot, page.rows[1])
    client.requests.clear()
    click(qtbot, page.use)
    assert client.sent() == [{"cmd": "set_address", "address": "BE:32:57:A0:13:6C",
                              "name": "ELK-BLEDOM", "rssi": -76}, {"cmd": "on"}]
    assert went == ["home"]


def test_a_failed_save_stays_on_setup(qtbot, page, ctx, client):
    client.replies["set_address"] = {"ok": False, "error": "not a Bluetooth address"}
    went = []
    ctx.navigate.connect(went.append)
    page.begin()
    click(qtbot, page.use)
    assert went == [] and client.sent("on") == []


def test_scan_again(qtbot, page, client):
    page.begin()
    click(qtbot, page.rescan)
    assert len(client.sent("scan")) == 2


def test_scan_failure_is_reported(page, client):
    client.replies["scan"] = {"ok": False, "error": "scan failed: adapter off"}
    page.begin()
    assert page.headline.text() == "Scan failed: scan failed: adapter off"
    assert page.rows == [] and not page.use.isEnabled()


def test_nothing_found(page, client):
    client.replies["scan"] = {"ok": True, "candidates": []}
    page.begin()
    assert page.headline.text() == "No LED controllers found" and not page.use.isEnabled()


def test_manual_address(qtbot, page, client):
    page.begin()
    click(qtbot, page.enter)
    assert page.manual.isVisible()
    page.manual.setText("not a mac")
    assert not page.use.isEnabled()
    page.manual.setText("aa:bb:cc:dd:ee:ff")
    assert page.use.isEnabled()
    client.requests.clear()
    click(qtbot, page.use)
    assert client.sent()[0] == {"cmd": "set_address", "address": "AA:BB:CC:DD:EE:FF"}


def test_cancel_only_when_a_strip_is_already_set_up(qtbot, page, ctx):
    page.begin(back_allowed=False)
    assert not page.cancel.isVisible()
    page.begin(back_allowed=True)
    assert page.cancel.isVisible()
    went = []
    ctx.navigate.connect(went.append)
    click(qtbot, page.cancel)
    assert went == ["home"]


def test_spinner_turns_only_while_scanning(page, client):
    page.spinner.spin(True)
    assert page.spinner._timer.isActive()
    page.begin()
    assert not page.spinner._timer.isActive()
