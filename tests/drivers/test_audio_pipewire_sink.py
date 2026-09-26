"""PipeWire driver: finding the default sink to capture from (`pw-dump`).

No pw-dump is ever run: the driver module's `subprocess` is replaced.
"""
import json
import types

from deskglow.drivers import audio_pipewire as pw


def _fake_subprocess(stdout=None, exc=None):
    def run(*a, **kw):
        if exc is not None:
            raise exc
        return types.SimpleNamespace(stdout=stdout, returncode=0)
    return types.SimpleNamespace(run=run)


def test_default_sink_name_finds_an_audio_sink(monkeypatch):
    dump = [
        {"id": 1, "info": {"props": {"media.class": "Audio/Source",
                                     "node.name": "alsa_input.mic"}}},
        {"id": 2, "info": {"props": {"media.class": "Audio/Sink",
                                     "node.name": "alsa_output.pci-0000_00"}}},
    ]
    monkeypatch.setattr(pw, "subprocess",
                        _fake_subprocess(stdout=json.dumps(dump)))
    assert pw.default_sink_name() == "alsa_output.pci-0000_00"


def test_default_sink_name_returns_none_when_there_is_no_sink(monkeypatch):
    dump = [{"id": 1, "info": {"props": {"media.class": "Video/Source"}}}, {}]
    monkeypatch.setattr(pw, "subprocess",
                        _fake_subprocess(stdout=json.dumps(dump)))
    assert pw.default_sink_name() is None


def test_default_sink_name_survives_malformed_json(monkeypatch):
    """pw-dump can print warnings on stdout; that must not raise."""
    monkeypatch.setattr(pw, "subprocess",
                        _fake_subprocess(stdout="{not json at all"))
    assert pw.default_sink_name() is None


def test_default_sink_name_survives_empty_output(monkeypatch):
    monkeypatch.setattr(pw, "subprocess", _fake_subprocess(stdout=""))
    assert pw.default_sink_name() is None


def test_default_sink_name_survives_a_missing_binary(monkeypatch):
    """PipeWire not installed is a normal situation, not a crash."""
    monkeypatch.setattr(pw, "subprocess",
                        _fake_subprocess(exc=FileNotFoundError("pw-dump")))
    assert pw.default_sink_name() is None


def test_default_sink_name_survives_a_timeout(monkeypatch):
    import subprocess as real_subprocess
    monkeypatch.setattr(
        pw, "subprocess",
        _fake_subprocess(exc=real_subprocess.TimeoutExpired("pw-dump", 5)))
    assert pw.default_sink_name() is None


def test_default_sink_name_survives_unexpected_json_shapes(monkeypatch):
    """A dict (not a list), nulls, missing info -- all must return None."""
    for payload in ('{"a": 1}', "null", "[null]", '[{"info": null}]',
                    '[{"info": {"props": null}}]', "[1, 2, 3]"):
        monkeypatch.setattr(pw, "subprocess",
                            _fake_subprocess(stdout=payload))
        assert pw.default_sink_name() is None
