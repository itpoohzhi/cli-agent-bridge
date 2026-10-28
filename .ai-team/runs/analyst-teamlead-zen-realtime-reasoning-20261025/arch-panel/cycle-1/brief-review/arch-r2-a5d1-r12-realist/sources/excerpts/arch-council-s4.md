## 4. Повторный проход после дельта-пакета

После `ARCH_GATE` дельта-пакета идёт новый проход `a<A+1>` (индекс — brief-review D3) с нуля: R1 → D → C1; леджер пуст, закрытые находки прошлых проходов в него не переносятся (council §3).

- R1 нового прохода (SK-A-11, `brief-review/references/checklist-sources.md`): полный актуальный пакет + delta + `panel-rework-brief-arch-a<A>.json` (вывод саммаризатора), без следов прошлого вердикта. Delta — механический `diff -u` прошлой и новой редакций пакета с sha256 обеих; при `no_architecture_delta` — пакет, это evidence и вывод саммаризатора.
- Каждый RW-NNN прошлого прохода судьи проверяют (verify-fixed); красный — F-блок (consensus §3 п.5). Дедуп, `[pre-existing]` и `late_miss` — `teamlead-gate/references/council.md` §3 («Diff-scope повторного цикла») с заменой «файл/diff» на «раздел пакета/delta».
- Повторный спор (consensus §6) — два прохода подряд (`a<A>`, `a<A+1>`) по тому же ключу дедупа.
