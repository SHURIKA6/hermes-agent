"""Regression test for the empty hosted-room bindings cache (issue #134619)."""
import threading
from types import SimpleNamespace

from gateway import hosted_rooms
import pytest


def _service(tmp_path):
    from tui_gateway.hosted_room_service import HostedRoomService

    server = SimpleNamespace(_methods={}, _sessions={}, _sessions_lock=threading.Lock())
    service = HostedRoomService(server, db_path=tmp_path / "state.db")
    return service


def test_unchanged_empty_polls_skip_second_list_operation(tmp_path):
    service = _service(tmp_path)

    original = hosted_rooms.list_rooms
    calls = {"n": 0}

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    hosted_rooms.list_rooms = counting
    try:
        assert service.bindings() == ()
        calls["n"] = 0
        # Warm cached result: repeated empty polls must not reopen SQLite.
        for _ in range(5):
            assert service.bindings() == ()
        assert calls["n"] == 0, calls["n"]

        # An independently created room invalidates the cache and is discovered.
        gw = hosted_rooms.local_authority_gateway_id()
        hosted_rooms.create_room(service.db_path, room_id="r1", name="R1",
                                authority_gateway_id=gw, members=[])
        calls["n"] = 0
        result = service.bindings()
        assert [b.room_id for b in result] == ["r1"]
        assert calls["n"] == 1, calls["n"]
    finally:
        hosted_rooms.list_rooms = original


def test_nonempty_result_stays_on_existing_path(tmp_path):
    service = _service(tmp_path)
    gw = hosted_rooms.local_authority_gateway_id()
    hosted_rooms.create_room(service.db_path, room_id="r1", name="R1",
                            authority_gateway_id=gw, members=[])

    original = hosted_rooms.list_rooms
    calls = {"n": 0}

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    hosted_rooms.list_rooms = counting
    try:
        assert [b.room_id for b in service.bindings()] == ["r1"]
        assert calls["n"] == 1
        calls["n"] = 0
        assert [b.room_id for b in service.bindings()] == ["r1"]
        # Non-empty results are never cached: every poll re-queries.
        assert calls["n"] == 1
    finally:
        hosted_rooms.list_rooms = original
