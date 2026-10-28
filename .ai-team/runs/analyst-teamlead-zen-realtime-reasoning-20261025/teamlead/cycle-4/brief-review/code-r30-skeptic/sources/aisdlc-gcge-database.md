# Database rules

## Стек

- **PostgreSQL** поднимается через Docker Compose.
- **SQLAlchemy 2.0 async-стек**: `AsyncSession`, `async_sessionmaker`, `create_async_engine`. Драйвер — `psycopg` (psycopg3, поддерживает async нативно).
- **Любое обращение к БД — `async def` + `await`**. Никакого синхронного `Session.execute(...)` — только `await session.execute(...)`.
- Repository-методы все `async def`. Service-методы все `async def`. Handler'ы Litestar — `async def` + `await service.method()`.

## Миграции

- Любое изменение схемы базы требует Alembic migration. Без исключений.
- Нельзя менять структуру таблиц без миграции (даже если «локально работает»).
- Все миграции должны быть воспроизводимыми (запускать в чистой БД на любой машине должны давать тот же результат).
- Разрешено использовать `alembic revision --autogenerate`, но миграцию **обязательно проверить глазами**: autogenerate иногда добавляет `op.drop_*` для нетронутых колонок или ошибается с типами.
- Алембик у нас работает в **async-режиме** — `alembic/env.py` запускает миграции через `asyncio.run(run_migrations_online())` с `async_engine_from_config`.

## Repository pattern

- Сервис не лезет в `AsyncSession` напрямую — только через `LinkRepository`.
- Repository принимает `AsyncSession` в `__init__`.
- Все методы repository — `async def` + `await session.execute(...)` / `await session.get(...)` / `await session.commit()`.
- `expire_on_commit=False` в `async_sessionmaker` — иначе после commit любое обращение к атрибуту триггерит refresh, что в async требует await и легко ломается.

## Что проверять

- Все изменения в БД-логике покрываются integration tests с реальной PostgreSQL (не SQLite-in-memory).
- Integration tests используют autouse-фикстуру очистки таблиц через `await session.execute(text("DELETE FROM links"))`.

<!-- HL-RESILIENCE-GATES-V5 -->
## Ёмкость хранилищ, серверные квоты и защита от шторма (`HL-ENV/v1`, `C-MULT-I1`, `S-HERD-I1`)

Канонический SSoT — `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`). Владение `database.md` распространяется на серверные квоты хранилищ (`PostgreSQL`, `Redis`/`Valkey`), серверные таймауты сессий и безопасность миграций:

1. **Серверные квоты соединений (`C-MULT-I1` для `PG` и `Redis`)**:
   - Для каждого хранилища $d \in \{\text{PG}, \text{Redis}\} $ в таблице `HL-ENV/v1` (`HL-ENV-01`) фиксируется выделенная серверная квота `Limit_dep_share[d]` (`PostgreSQL max_connections` / `pgbouncer`, `Redis maxclients`).
   - Суммарный пиковый потолок соединений по всем одновременно живым ролям процессов $r \in \text{roles}$ (`control_plane`, `migrations_cron`, `crawler_workers`, `llm_workers`, `pod_fetcher` с $N_{\text{proc}} = P_{\text{live}} \times W$) с учётом коэффициента перекрытия поколений пула при hot-reload $G_{\text{reload}, r, k} \in \{1, 2\}$ обязан укладываться в $60\%$ квоты:
     $$C_{\text{dep}}(d) = \sum_{r \in \text{roles}} N_{\text{proc}, r} \times \left(\sum_{k \in \text{pools}_{r,d}} G_{\text{reload}, r, k} \cdot \text{pool\_max\_size}_{r,k} + \text{dedicated\_conns}_{r,d}\right) \le 0.60 \times \text{Limit\_dep\_share}[d]$$
2. **Запрет прямого доступа воркеров Data Plane к PostgreSQL (`C-MULT-I1`, `S-HERD-I1`)**:
   - Воркеры data plane ($N_{\text{proc}} = P_{\text{live}} \times W$) **не имеют права** открывать прямые соединения к `PostgreSQL`: единственным читателем/писателем реляционной БД является `Control Plane`, а воркеры получают данные через иммутабельный `Snapshot` с условным опросом `If-None-Match` (`HTTP 304`, `S-HERD-I3`) и `Pod-Level Single Fetch` / джиттером (`S-HERD-I1..I2`).
3. **Обязательные серверные и пуловые таймауты БД (`C-MULT-I2`, `R-BULK-I1`)**:
   - Каждый `create_async_engine` задаёт явные `pool_size`, `max_overflow`, `pool_timeout`, `pool_pre_ping=True`, а на уровне сессии/соединения — явные `statement_timeout`, `idle_in_transaction_session_timeout` и `lock_timeout`. Запросы без конечного `statement_timeout` и транзакции, удерживаемые во время внешнего сетевого I/O, блокируют мерж (`REJECT`).
4. **Безопасность миграций под нагрузкой (`Migration Storm Safety`)**:
   - Миграции запускаются как единичный `Job`/процесс (`N_proc = 1`), никогда не выполняются внутри `lifespan` каждого из $P_{\text{live}} \times W$ воркеров при старте пода (`S-HERD-I1`), используют `lock_timeout` и `CREATE INDEX CONCURRENTLY` для нагруженных таблиц.
