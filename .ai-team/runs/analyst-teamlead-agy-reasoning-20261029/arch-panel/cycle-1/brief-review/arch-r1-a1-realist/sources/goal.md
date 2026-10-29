# Цель: analyst-teamlead-agy-reasoning-20261029

- **Задача:** Реализовать по пресету `analyst-teamlead` (S2) реалтайм-стриминг размышлений (`reasoning_content`) в `bridges/agy-bridge/server.py` из SQLite `~/.gemini/antigravity-cli/conversations/<cid>.db` (`steps.step_payload` protobuf field `20.3`) во время генерации, синхронизировать финальное дренирование `_TranscriptTail` с `Run._pump`, сохранить отданный `reasoning` во флаге `delivered` при mid-turn ошибках и изолировать `sess_key` от фоновых запросов без инструментов; провести через Совет Тимлидов (`ARCH_PANEL` и `COUNCIL`), влить MR в `dev` и `main`, задеплоить в `~/.dsh/bridges/agy-bridge/server.py` (`:9887`) и проверить тяжёлым путём L3.
- **Терминальный критерий:**
  1. `SA-DOD-001..008 PASS` на `analysis/agy-realtime-reasoning/`.
  2. `ARCH_GATE PASS` + `ARCH_PANEL PASS` (`verify_panel_proof.py exit=0`).
  3. `CODE_GATE PASS` + `Verifier / FINAL_GATE PASS` + `Clean-room L2 PASS`.
  4. `COUNCIL ACCEPT` (`verify_panel_proof.py exit=0`, `pol-receipt/1`).
  5. Remote-first MR открыт и влит в `origin/dev`, затем `dev -> main` влит в `origin/main`, локальный checkout синхронизирован (`git pull --ff-only`).
  6. Обновлённый `bridges/agy-bridge/server.py` задеплоен в `~/.dsh/bridges/agy-bridge/server.py`, сервис `:9887` перезапущен и проверен живым SSE-запросом к `gemini-4-argon` (`reasoning_effort=high`) с реальным стримингом чанков `reasoning_content` во время фазы размышления.
