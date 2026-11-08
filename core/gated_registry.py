"""Каталог и реестр адаптеров под флагом droid."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Mapping
from typing import cast

from core.backend_adapter import AdapterRegistry, BackendAdapter, BackendModel
from core.catalog_flags import CatalogDict, GatedCatalog, apply_droid_catalog_gate


def gated_catalog(raw: bytes, build: Callable[[CatalogDict], CatalogDict]) -> CatalogDict:
    """Оборачивает в GatedCatalog при droid_off."""
    data = json.loads(raw)
    ref = data.get("technical_ref") if isinstance(data, dict) else None
    if isinstance(ref, dict) and "droid_off" in ref:
        off = build(apply_droid_catalog_gate(data, enabled=False))
        return GatedCatalog(build(copy.deepcopy(data)), off)
    return build(data)


class GatedRegistry(AdapterRegistry):
    """Реестр адаптеров с пулом; модели из catalog_source()."""

    def __init__(self) -> None:
        super().__init__()
        self._sync: Callable[[], object] = lambda: None
        self._pool: dict[str, BackendAdapter] = {}
        self._make: Callable[[CatalogDict], AdapterRegistry] = lambda _: self

    @classmethod
    def from_fleet(
        cls, catalog: Mapping[str, object], kinds: Mapping[str, object],
        catalog_source: Callable[[], Mapping[str, object]], host: object = None,
    ) -> GatedRegistry:
        reg = cast(GatedRegistry, super().from_fleet(catalog, kinds, catalog_source, host))
        reg._pool = dict(reg._adapters)
        reg._make = lambda c: AdapterRegistry.from_fleet(c, kinds, catalog_source, host)
        if isinstance(catalog, GatedCatalog):
            reg._sync = catalog.sync
            catalog.add_listener(reg.reconcile)
        return reg

    def reconcile(self, catalog: Mapping[str, object]) -> None:
        """Переключает адаптеры по флагу."""
        bk = cast(Mapping[str, CatalogDict], catalog.get("backends") or {})
        live = [b for b, c in bk.items() if c.get("enabled", True)]
        with self._lock:
            miss = {b: bk[b] for b in live if b not in self._pool}
            if miss:
                sub: CatalogDict = {**catalog, "backends": miss, "backend_order": list(miss)}
                self._pool.update(self._make(sub)._adapters)
            self._adapters = {b: self._pool[b] for b in live}

    def shutdown(self, exclude: tuple[str, ...] = ()) -> None:
        """Останавливает пул."""
        with self._lock:
            self._adapters = {**self._pool, **self._adapters}
        super().shutdown(exclude)

    def get(self, backend_id: str) -> BackendAdapter | None:
        self._sync()
        return super().get(backend_id)

    def adapters(self) -> list[BackendAdapter]:
        self._sync()
        return super().adapters()

    def adapter_for_model(self, model_id: str) -> BackendAdapter | None:
        self._sync()
        return super().adapter_for_model(model_id)

    def models(self) -> list[tuple[BackendAdapter, BackendModel]]:
        self._sync()
        return super().models()
