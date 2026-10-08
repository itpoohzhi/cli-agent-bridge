"""Адаптеры бэкендов хаба. Реестр видов задан В КОДЕ: конфигурация код не загружает."""

from adapters.droid_adapter import DroidAdapter
from adapters.muse_adapter import MuseAdapter

ADAPTER_KINDS = {"droid": DroidAdapter, "muse": MuseAdapter}

__all__ = ["ADAPTER_KINDS", "DroidAdapter", "MuseAdapter"]
