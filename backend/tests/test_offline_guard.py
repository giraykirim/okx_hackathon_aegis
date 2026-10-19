"""Exercise the socketpair exception without creating real sockets or traffic."""

import socket
import threading

import pytest
from _offline_guard import deny_external_network


def install_fake_guard(monkeypatch, pair):
    calls = []

    def connect(sock, address):
        calls.append(address)
        return 0

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect)
    monkeypatch.setattr(socket, "socketpair", pair)
    deny_external_network(monkeypatch, "offline")
    return calls


def test_connect_is_blocked_outside_internal_pair(monkeypatch):
    calls = install_fake_guard(monkeypatch, lambda: (None, None))
    for address in (("127.0.0.1", 1234), ("203.0.113.1", 443)):
        with pytest.raises(AssertionError, match="offline"):
            socket.socket.connect(object(), address)
    assert not calls


def test_pair_allows_only_own_loopback(monkeypatch):
    def pair():
        socket.socket.connect(object(), ("127.0.0.1", 1234))
        socket.socket.connect_ex(object(), ("::1", 1234, 0, 0))
        with pytest.raises(AssertionError, match="offline"):
            socket.socket.connect(object(), ("203.0.113.1", 443))
        return None, None

    calls = install_fake_guard(monkeypatch, pair)
    socket.socketpair()
    assert calls == [("127.0.0.1", 1234), ("::1", 1234, 0, 0)]


def test_other_thread_remains_blocked_during_pair(monkeypatch):
    results = []

    def worker():
        try:
            socket.socket.connect(object(), ("127.0.0.1", 1234))
        except AssertionError:
            results.append("blocked")

    def pair():
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()
        return None, None

    calls = install_fake_guard(monkeypatch, pair)
    socket.socketpair()
    assert results == ["blocked"]
    assert not calls


def test_pair_failure_restores_thread_scope(monkeypatch):
    def pair():
        raise OSError("pair failed")

    calls = install_fake_guard(monkeypatch, pair)
    with pytest.raises(OSError, match="pair failed"):
        socket.socketpair()
    with pytest.raises(AssertionError, match="offline"):
        socket.socket.connect(object(), ("127.0.0.1", 1234))
    assert not calls
