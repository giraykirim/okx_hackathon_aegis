"""Shared offline network/process guard for the backend test suite.

External transports and subprocesses stay blocked. The only exception is the
asyncio event loop's internal self-pipe, which on Windows creates its pair with
``socket.socketpair()`` -> loopback ``connect()``. That call is not external
traffic, so it is allowed through (and only it); every other ``connect``/
``connect_ex`` and all subprocess creation still raise.
"""

import asyncio
import socket
import subprocess


def deny_external_network(monkeypatch, message):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_socketpair = socket.socketpair

    def denied(*args, **kwargs):
        raise AssertionError(message)

    def socketpair_bypass(*args, **kwargs):
        # Allow only the event-loop self-pipe construction, then restore the guard.
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            socket.socket.connect = denied
            socket.socket.connect_ex = denied

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "socketpair", socketpair_bypass)
    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", denied)
