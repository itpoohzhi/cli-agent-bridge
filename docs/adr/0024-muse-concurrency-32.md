# 0024 — Параллельность Muse до 32 процессов

## Status

Accepted (2026-11-10). Решение принял владелец.

## Контекст и проблематика

Модель `muse-wonder-full-1.0` используется в ролях Coder, Architect,
Analyst, Summarizer и судьи согласно `~/Мой диск/Context/models.md`.
Бэкенд Muse имел `max_concurrent = 1`.
Один слот ограничивал одновременную работу всех ролей на Muse.
Требование владельца — обеспечить минимум 32 параллельных хода.

## Архитектурное решение

1. В конфигурации Muse устанавливается `max_concurrent = 32`.
2. `MuseAdapter.CONSTRAINTS.max_concurrent_max = None` не вводит
   верхний предел адаптера для этого параметра.
3. Глобальный `_MUSE_SLOTS = BoundedSemaphore(1)` заменён пер-инстансным
   `BoundedSemaphore(self.max_concurrent)`.
4. Проверка `muse_max_concurrent_must_be_one` удалена.

## Принятый риск

**RW-001.** Параллельные muse-процессы работают под одним UID с флагами
`--yolo --trust-workspace`. Каталоги каждого хода
`workspace/muse/turn-<uuid>/` с правами 0700 при одном UID не изолируют
процессы друг от друга. Владелец принял риск 2026-11-10.

Компенсаторы сохранены: sha256-pin, удаление `META_API_KEY` и `MUSE_BIN`
из окружения, allowlist окружения и удаление каталога в `finally`.

## Последствия

- Правило «Muse строго 1» из ADR 0002 снято.
- Нужен регресс-тест `backend_entry_error(muse, max_concurrent=32) == ''`.
- Риск same-UID доступа остаётся принятым и документированным как RW-001.
