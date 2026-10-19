"""Shared offline network/process guard for the backend test suite.

External transports and subprocesses stay blocked. The only exception is the
asyncio event loop's internal self-pipe, which on Windows creates its pair with
``socket.socketpair()`` -> loopback ``connect()``. That call is not external
traffic, so it is allowed through (and only it); every other ``connect``/
``connect_ex`` and all subprocess creation still raise.
"""

import asyncio
import ipaddress
import socket
import subprocess
import threading


def deny_external_network(monkeypatch, message):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_socketpair = socket.socketpair
    local = threading.local()

    def denied(*args, **kwargs):
        raise AssertionError(message)

    def internal_loopback(address):
        if not getattr(local, "socketpair_depth", 0) or not isinstance(address, tuple):
            return False
        try:
            return ipaddress.ip_address(address[0]).is_loopback
        except (ValueError, TypeError, IndexError):
            return False

    def guarded_connect(sock, address):
        if internal_loopback(address):
            return original_connect(sock, address)
        return denied()

    def guarded_connect_ex(sock, address):
        if internal_loopback(address):
            return original_connect_ex(sock, address)
        return denied()

    def socketpair_bypass(*args, **kwargs):
        # Keep global guards installed; only this thread's internal loopback is allowed.
        local.socketpair_depth = getattr(local, "socketpair_depth", 0) + 1
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            local.socketpair_depth -= 1

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "socketpair", socketpair_bypass)
    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", denied)
