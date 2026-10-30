"""Адаптеры бэкендов хаба. Реестр видов задан В КОДЕ: конфигурация код не загружает."""

from adapters.droid_adapter import DroidAdapter
from adapters.muse_adapter import MuseAdapter
from adapters.passthrough_adapter import PassthroughAdapter

ADAPTER_KINDS = {
    "droid": DroidAdapter,
    "muse": MuseAdapter,
    "passthrough": PassthroughAdapter,
}

__all__ = ["ADAPTER_KINDS", "DroidAdapter", "MuseAdapter", "PassthroughAdapter"]
