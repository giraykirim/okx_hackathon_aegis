"""Offline tests cannot inherit operator credentials or open external transports."""

import asyncio
import os
import socket
import subprocess

import pytest

from aegis.settings import Settings


def pytest_configure(config):
    # Apply before test-module collection can import the module-level FastAPI app.
    config._aegis_original_settings_config = Settings.model_config
    Settings.model_config = {**Settings.model_config, "env_file": None}


def pytest_unconfigure(config):
    Settings.model_config = config._aegis_original_settings_config


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    for key in tuple(os.environ):
        if key.startswith(("AEGIS_", "EVREN_", "OKX_")) and key != "AEGIS_OFFLINE_PROOF_PATH":
            monkeypatch.delenv(key, raising=False)

    def denied(*args, **kwargs):
        raise AssertionError("Offline pytest forbids external network/process execution")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", denied)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", denied)
