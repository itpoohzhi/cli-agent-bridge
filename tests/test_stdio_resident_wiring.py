"""Проверки регистрации резидентного stdio-адаптера."""

from typing import cast

from adapters import (
    ADAPTER_KINDS,
    DroidAdapter,
    MuseAdapter,
    PassthroughAdapter,
    StdioResidentAdapter,
)
from core.backend_adapter import BackendAdapter


def test_stdio_resident_kind_registered() -> None:
    assert ADAPTER_KINDS["stdio_resident"] is StdioResidentAdapter


def test_adapter_api_version_is_one() -> None:
    assert StdioResidentAdapter.adapter_api == 1
    assert ADAPTER_KINDS["stdio_resident"].adapter_api == 1


def test_adapter_subclasses_backend_adapter() -> None:
    assert issubclass(StdioResidentAdapter, BackendAdapter)


def test_adapter_instantiation_from_kinds() -> None:
    adapter_class = cast(type[StdioResidentAdapter], ADAPTER_KINDS["stdio_resident"])
    adapter = adapter_class({})

    assert callable(adapter.preflight_check)
    assert callable(adapter.execute_chat)
    assert callable(adapter.shutdown)


def test_existing_kinds_unbroken() -> None:
    assert ADAPTER_KINDS["droid"] is DroidAdapter
    assert ADAPTER_KINDS["muse"] is MuseAdapter
    assert ADAPTER_KINDS["passthrough"] is PassthroughAdapter
