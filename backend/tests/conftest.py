"""Offline tests cannot inherit operator credentials or open external transports."""

import os

import pytest
from _offline_guard import deny_external_network

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

    deny_external_network(monkeypatch, "Offline pytest forbids external network/process execution")
