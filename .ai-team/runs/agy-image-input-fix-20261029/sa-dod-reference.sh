# Композитный DoD системного аналитика (запуск в каталоге analysis/<тема>/)
(f1=$(rg -c "\[F-[0-9]+\]" evidence-ledger.md 2>/dev/null || echo 0); \
 f2=$(rg -c "^\[F-[0-9]+\][^|]*\|[^|]*\|\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*$" evidence-ledger.md 2>/dev/null || echo 0); \
 [ "$f1" -gt 0 ] && [ "$f1" -eq "$f2" ] && echo "SA-DOD-001 PASS ($f1 facts)" || echo "SA-DOD-001 FAIL: $f1 vs $f2") && \
(d=$(rg -in "вероятно|скорее всего|наверное|по-видимому|должно быть" handoff-*.md 2>/dev/null || true); \
 [ -z "$d" ] && echo "SA-DOD-002 PASS (no guesses)" || echo "SA-DOD-002 FAIL: guesses found") && \
(p1=$(rg -c "INV-[0-9]+" research-plan.md 2>/dev/null || echo 0); \
 p2=$(rg -c "^\s*INV-[0-9]+( \| [^|]+){11}\s*$" research-plan.md 2>/dev/null || echo 0); \
 p3=$(rg -c "^\s*INV-[0-9]+.*\| (closed|open) \| (F-[0-9]+|OPEN-[0-9]+) \|" research-plan.md 2>/dev/null || echo 0); \
 [ "$p1" -gt 0 ] && [ "$p1" -eq "$p2" ] && [ "$p2" -eq "$p3" ] && echo "SA-DOD-003 PASS ($p1 spikes)" || echo "SA-DOD-003 FAIL: $p1/$p2/$p3") && \
(q1=$(rg -c "OPEN-[0-9]+" open-questions.md 2>/dev/null || echo 0); \
 q2=$(rg -c "^\s*OPEN-[0-9]+ \| (БЛОКЕР|МОЖНО ПРОДОЛЖИТЬ) \| [^|]+ \| [^|]+ \| [^|]+ \| [^|]+ \| [^|]*\s*$" open-questions.md 2>/dev/null || echo 0); \
 [ "$q1" -eq "$q2" ] && echo "SA-DOD-004 PASS ($q1 open questions)" || echo "SA-DOD-004 FAIL: $q1 vs $q2") && \
(ac=$(rg -in "^\s*(Given|When|Then)\b|^\s*(Дано|Когда|Тогда)\s*:" handoff-*.md 2>/dev/null || true); \
 [ -z "$ac" ] && echo "SA-DOD-006 PASS (no AC in handoff)" || echo "SA-DOD-006 FAIL: AC leaked") && \
(ov=$(awk -F'|' '{tb=$5;ft=$11;gsub(/ /,"",tb);gsub(/ /,"",ft); if(tb ~ /^[0-9]+$/ && ft ~ /^[0-9]+$/ && ft+0 > tb+0 && $12 !~ /таймбокс превышен/) print $1}' research-plan.md 2>/dev/null || true); \
 [ -z "$ov" ] && echo "SA-DOD-008 PASS (timeboxes clean)" || echo "SA-DOD-008 FAIL: unflagged overrun $ov")
