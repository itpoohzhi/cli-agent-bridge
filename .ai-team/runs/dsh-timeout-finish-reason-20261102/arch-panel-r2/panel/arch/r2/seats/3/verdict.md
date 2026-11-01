PANEL-NONCE: 3b4c949b67a4b51d
ARTIFACT-SHA256: 8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908

AGREE RW-001 — проверил: `bridges/agy-bridge/server.py:2924-2932`. Реальный `_RuntimeFlags` уже содержит шестое поле `stream_resilience_enabled: bool = True`, которого нет в NamedTuple из пакета. Кроме того, `_parse_runtime_flags` (`server.py:2951-2964`) содержит особую ветку для этого поля: ключ берётся из `_NEW_FLAG_ENV`, а дефолт равен True. Если заменить определение на версию из пакета, `_RuntimeFlags(**values)` перестанет находить это поле, и флаг пропадёт. Из-за дефолта True резилиентность стрима молча сменит поведение. Для нового строкового поля нужны отдельная ветка в парсере и запись в `_NEW_FLAG_ENV`, иначе проверка `isinstance(value, bool)` на строке 2960 отвергнет весь `dynamic_config.json`. Требуется правка: добавить поле, а не переписывать кортеж.

AGREE RW-002 — проверил: `tests/test_agy_bridge_resilience.py:13328-13329`. Тест `test_enabled_graceful_timeout_retains_single_length_final` независимо ждёт `terminals == ["length"]` для `idle_timeout` при `AGY_GRACEFUL_TIMEOUT_ON_PARTIAL=true`. В списке из 10 тестов в разделе 5 пакета его нет, и после смены дефолта на `"stop"` он упадёт. Номер строки негативного ассерта указан как 5464, а в файле он на 5468 (это мелочь). Ассерт на `4617` останется верным, потому что он проверяет кадры ошибки. Нужен grep по `"length"` и `_is_length` по всему `tests/` (в пакете перечислена только часть вхождений) и явное решение, что делать с тестом на 13329.

VERDICT: NEEDS WORK
