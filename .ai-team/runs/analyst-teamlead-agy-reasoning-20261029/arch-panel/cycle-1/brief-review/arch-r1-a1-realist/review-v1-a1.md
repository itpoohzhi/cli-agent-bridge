{
  "items": [
    {
      "id": "BR-01",
      "status": "covered",
      "evidence_quote": "Локальная SQLite-база `~/.gemini/antigravity-cli/conversations/<cid>.db` ... `status=8` GENERATING ... подполе `20.3` в `step_payload` содержит накопленный текст `thinking`",
      "fix": ""
    },
    {
      "id": "BR-02",
      "status": "covered",
      "evidence_quote": "RC-2` синхронизация финального дренирования `_TranscriptTail` до `done`, `RC-3` учёт `reasoning` в `delivered`, `RC-4` изоляция горячих сессий `_session_store` от фоновых запросов без `tools`",
      "fix": ""
    },
    {
      "id": "BR-03",
      "status": "covered",
      "evidence_quote": "Проверь соответствие Architecture Packet каждому требованию `REQ-001..REQ-012`, каждому приёмочному критерию `AC-001..AC-016` и разделам `handoff-architect.md`.",
      "fix": ""
    },
    {
      "id": "BR-04",
      "status": "covered",
      "evidence_quote": "конверт `HL-ENV/v1` из 46 полей ... а также проверяемость `verification_surface` и все пункты `Definition of Done overlay` из `aisdlc-gcge/skills/architecture.md`",
      "fix": ""
    },
    {
      "id": "JD-02",
      "status": "covered",
      "evidence_quote": "",
      "fix": ""
    },
    {
      "id": "JD-03",
      "status": "covered",
      "evidence_quote": "суди ЗАНОВО, не подтверждай прошлый вердикт автоматически",
      "fix": ""
    },
    {
      "id": "JD-04",
      "status": "covered",
      "evidence_quote": "ФОРМАТ ОТВЕТА (строго):",
      "fix": ""
    },
    {
      "id": "JD-05",
      "status": "covered",
      "evidence_quote": "",
      "fix": ""
    },
    {
      "id": "JD-06",
      "status": "covered",
      "evidence_quote": "",
      "fix": ""
    },
    {
      "id": "JD-07",
      "status": "covered",
      "evidence_quote": "КОНТЕКСТ:; 📋 ФАКТ-КАРТА; РЕЖИМ: architecture",
      "fix": ""
    },
    {
      "id": "JD-08",
      "status": "violated",
      "evidence_quote": "",
      "fix": "Вложить блок «ЯКОРЯ ПАКЕТА» с вариантами (а)–(г) и полную рубрику подкатегорий для COVERAGE и self-sweep. Восстановить полный текст пункта 6: приложенный фрагмент council.md обрывается посреди предложения."
    },
    {
      "id": "HY-02",
      "status": "violated",
      "evidence_quote": "",
      "fix": "Согласовать допустимые значения вердикта по критериям: начальный формат разрешает PASS|FAIL, а вложенный фрагмент предписывает PASS/INCONCLUSIVE."
    },
    {
      "id": "HY-04",
      "status": "covered",
      "evidence_quote": "",
      "fix": ""
    },
    {
      "id": "HY-05",
      "status": "violated",
      "evidence_quote": "",
      "fix": "Исключить из передаваемого судье фрагмента упоминание brief-review при сохранении необходимых правил архитектурного совета."
    },
    {
      "id": "HY-06",
      "status": "covered",
      "evidence_quote": "",
      "fix": ""
    }
  ],
  "unmapped_requirements": [],
  "bloat_flags": [],
  "leakage_flags": [
    "Во вложенном фрагменте arch-council.md присутствует упоминание brief-review."
  ],
  "model_verdict": "REJECT"
}
