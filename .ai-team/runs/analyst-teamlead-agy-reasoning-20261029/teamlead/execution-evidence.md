# Протокол выполнения верификации в чистой комнате (Clean-Room L2 Execution Evidence)

- **run_id**: `analyst-teamlead-agy-reasoning-20261029`
- **base_sha**: `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66`
- **status**: `PASS`
- **bridges/agy-bridge/server.py sha256**: `1285a908bf2793b3a19e93e2149c2bfa353d1fb8625c626658fe790e2ef48147`
- **tests/test_agy_bridge_resilience.py sha256**: `63869e7e51e7b067661afe074b688dfb4c9d5f86040cfcdf6a3b778e825a0680`

## Сводная таблица проверок (VER-001..VER-013)

| ID | Статус | Код возврата | Время (с) | Команда |
|---|---|---|---|---|
| `VER-001` | `PASS` | `0` | `0.12` | `uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py` |
| `VER-002` | `PASS` | `0` | `0.11` | `uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py` |
| `VER-003` | `PASS` | `0` | `83.49` | `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py` |
| `VER-004` | `PASS` | `0` | `7.82` | `set -e; B="$(mktemp -d)"; H="$(mktemp)"; S="$(mktemp)"; git worktree add -q --detach "$B/base" e00da0621fc95f7c63cd1565f4a5d1fd490c8d66; uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > "$H" || true; (cd "$B/base" && uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py > "$S" || true); git worktree remove --force "$B/base"; python3 -I - "$H" "$S" <<'PY'
import json,sys,collections
h=json.load(open(sys.argv[1])); s=json.load(open(sys.argv[2]))
def ms(x,sev): return collections.Counter((d['file'].rsplit('/',1)[-1],d.get('rule'),d['message']) for d in x['generalDiagnostics'] if d['severity']==sev)
err=h['summary']['errorCount']; new_w=ms(h,'warning')-ms(s,'warning')
print('version',h['version'],'errors',err,'warnings',h['summary']['warningCount'],'new_warnings',sum(new_w.values()))
[print('NEW',k) for k in sorted(new_w)]
sys.exit(0 if err==0 and not new_w and h['version'].startswith('1.40.2') else 1)
PY` |
| `VER-005` | `PASS` | `0` | `164.98` | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py" && PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py` |
| `VER-006` | `PASS` | `0` | `0.09` | `test "$(git diff --unified=0 e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/test_agy_bridge_resilience.py | grep -cE '^-[^-]')" = 0 && test -z "$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/ core/ | grep -vx 'tests/test_agy_bridge_resilience.py')" && echo OK` |
| `VER-007` | `PASS` | `0` | `0.12` | `python3 -I - <<'PY'
import ast,re,sys,pathlib
s=pathlib.Path('tests/test_agy_bridge_resilience.py').read_text(encoding='utf-8')
t=ast.parse(s)
need={'tc%02d'%i for i in list(range(1,13))+[20,21,23,24,30,31,32,33,40,41,42,43,44,50,51,60,61,62,63,70,71,72,80,81,82,91,92]}|{'ao%02d'%i for i in range(1,13)}
def asserted(f):
    for n in ast.walk(f):
        if isinstance(n,ast.Assert): return True
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert'): return True
    return False
got=set(); noassert=[]
for f in ast.walk(t):
    if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith('test_'):
        ids=set(re.findall(r'(tc\d{2}|ao\d{2})',f.name))&need
        if not ids: continue
        if asserted(f): got|=ids
        else: noassert.append(f.name)
miss=sorted(need-got)
errs=(['MISSING '+' '.join(miss)] if miss else [])+(['NO_ASSERT '+' '.join(sorted(noassert))] if noassert else [])
print('; '.join(errs) if errs else 'OK %d ids, all asserted'%len(need)); sys.exit(1 if errs else 0)
PY` |
| `VER-008` | `PASS` | `0` | `0.1` | `test "$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- . ':(exclude).ai-team' ':(exclude)analysis' | sort | tr '\n' ' ')" = "bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py " && test -z "$(git ls-files bridges/agy-bridge/dynamic_config.json)" && printf '%s  %s\n' 81dffc06ac79c490968e7efb8321f464d5963f414fcc6bd67a278a99d5985e32 analysis/agy-realtime-reasoning/research-plan.md e9c8afb2684a7621e9fdb0455640e86f972aab600989142119fb440397842ff1 analysis/agy-realtime-reasoning/evidence-ledger.md 47b16bab51b31bb06c35fb02d08dbd3409a9cfb057a52e828d079054a20d9202 analysis/agy-realtime-reasoning/open-questions.md cb1ecde9e00f06d72b75e43f973add3ab93ca27433d7145cbf8ec4f4800b17cd analysis/agy-realtime-reasoning/handoff-architect.md 5ed84fc039f7fea5983404442461e734ec9dae03f57359e2bb441dfae6cb7afe analysis/agy-realtime-reasoning/handoff-qa.md | shasum -a 256 -c --status - && echo OK` |
| `VER-009` | `PASS` | `0` | `0.12` | `python3 -I - <<'PY'
import ast,sys,pathlib
src=pathlib.Path('bridges/agy-bridge/server.py').read_text(encoding='utf-8')
t=ast.parse(src)
allowed={'__future__','hashlib','json','os','queue','re','select','shutil','signal','socket','subprocess','sys','threading','time','uuid','http','pathlib','typing','core','sqlite3','random'}
roots=set()
for n in ast.walk(t):
    if isinstance(n,ast.Import):
        roots|={a.name.split('.')[0] for a in n.names}
    elif isinstance(n,ast.ImportFrom) and n.level==0:
        roots.add((n.module or '').split('.')[0])
calls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='connect' and isinstance(n.func.value,ast.Name) and n.func.value.id=='sqlite3']
nouri=[c.lineno for c in calls if not any(k.arg=='uri' and isinstance(k.value,ast.Constant) and k.value.value is True for k in c.keywords)]
rw=[n.lineno for n in ast.walk(t) if isinstance(n,ast.Constant) and isinstance(n.value,str) and ('mode=rw' in n.value or 'immutable' in n.value)]
need=[x for x in ('AGY_SQLITE_REASONING_ENABLED','SQLITE_REASONING_ENABLED','AGY_BRIDGE_CONVERSATIONS','mode=ro','query_only','busy_timeout') if x not in src]
errs=[]
if sorted(roots-allowed): errs.append('non-stdlib imports %s'%sorted(roots-allowed))
if not calls: errs.append('no sqlite3.connect call')
if nouri: errs.append('sqlite3.connect without uri=True at %s'%nouri)
if rw: errs.append('write-mode or immutable URI literal at %s'%rw)
if 'immutable' in src: errs.append('substring immutable present in server.py')
if need: errs.append('missing %s'%need)
print('FAIL: '+'; '.join(errs) if errs else 'OK'); sys.exit(1 if errs else 0)
PY` |
| `VER-010` | `PASS` | `0` | `84.14` | `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py -k "tc93 or l2_harness" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_agy_bridge_resilience.py" -k tc93 -k l2_harness` |
| `VER-011` | `DEFERRED_L3` | `0` | `0` | `None` |
| `VER-012` | `PASS` | `0` | `81.82` | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"` |
| `VER-013` | `PASS` | `0` | `414.81` | `/usr/bin/python3 -m unittest discover -s tests (compared against base_sha e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 in Clean-Room worktree)` |

## Подробные выводы проверок

### VER-001 (PASS, rc=0)
```text
All checks passed!
```

### VER-002 (PASS, rc=0)
```text
2 files already formatted
```

### VER-003 (PASS, rc=0)
```text
............................................................................................ [ 94%]
.....                                                                    [100%]
97 passed, 52 subtests passed in 83.16s (0:01:23)
```

### VER-004 (PASS, rc=0)
```text
version 1.40.2 errors 0 warnings 800 new_warnings 0
```

### VER-005 (PASS, rc=0)
```text
............................................................................................ [ 94%]
.....                                                                    [100%]
97 passed, 52 subtests passed in 83.06s (0:01:23)

[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:45 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:45 sqlite-schema-mismatch cid=82188e72
[agy-bridge] 12:30:45 sqlite-off cid=82188e72 reason=schema
[agy-bridge] 12:30:45 sqlite-open-fail cid=82188e72 err=OperationalError cold=0
[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:45 sqlite-schema-mismatch cid=82188e72
[agy-bridge] 12:30:45 sqlite-off cid=82188e72 reason=schema
[agy-bridge] 12:30:45 sqlite-open-fail cid=82188e72 err=OperationalError cold=0
[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:45 sqlite-off cid=82188e72 reason=db_error
[agy-bridge] 12:30:45 sqlite-open-fail cid=82188e72 err=DatabaseError cold=0
[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:45 breaker state=OPEN probe_gen=0
[agy-bridge] 12:30:45 breaker state=CLOSED probe_gen=1
[agy-bridge] 12:30:45 breaker state=OPEN probe_gen=1
[agy-bridge] 12:30:45 breaker state=OPEN probe_gen=2
[agy-bridge] 12:30:45 breaker state=CLOSED probe_gen=5
.[agy-bridge] 12:30:45 exec model=m effort=low effort_source=default prompt_bytes=10 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:30:45 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:45 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:46 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:46 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:46 hot session failed err='boom', cold fallback tag
[agy-bridge] 12:30:46 exec model=m effort=low effort_source=default prompt_bytes=27 tools=1 resume=0 sess=agentic tag
[agy-bridge] 12:30:46 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:46 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:46 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:47 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:47 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.6 err='' tag
[agy-bridge] 12:30:47 exec model=m effort=low effort_source=default prompt_bytes=10 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:30:47 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:47 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:47 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:48 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:48 retry-budget-exhausted state=agy_error tag
[agy-bridge] 12:30:48 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=0.7 err='boom' tag
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=13
[agy-bridge] 12:30:48 sqlite_transcript_divergence cid=82188e72 step=3 len_prev=13 len_new=13
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=divergence
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 compat state=SHADOW reason=divergence
[agy-bridge] 12:30:48 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=3 len_new=3
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:30:48 compat state=SHADOW reason=binary_identity
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 turn_mode cid=fa92a264 mode=SHADOW
[agy-bridge] 12:30:48 sqlite-gen cid=fa92a264 step=3
[agy-bridge] 12:30:48 tail-emit cid=fa92a264 step=3 len=25
[agy-bridge] 12:30:48 compat state=LIVE
[agy-bridge] 12:30:48 turn_mode cid=57172100 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=57172100 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=57172100 step=3 len=17
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=40
[agy-bridge] 12:30:48 compat state=LIVE
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=0 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=1 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=2 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=4 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=5 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=6 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=7 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=8 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=9 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=10 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=11 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=12 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=13 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=14 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=15 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=16 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=17 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=18 len=6
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=19 len=6
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=flag
.[agy-bridge] 12:30:48 sqlite-off cid=../x reason=cid
[agy-bridge] 12:30:48 turn_mode cid=../x mode=OFF
[agy-bridge] 12:30:48 sqlite-off cid=a/b reason=cid
[agy-bridge] 12:30:48 turn_mode cid=a/b mode=OFF
[agy-bridge] 12:30:48 sqlite-off cid=zz-not-h reason=cid
[agy-bridge] 12:30:48 turn_mode cid=zz-not-h mode=OFF
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=15
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=12
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=6
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=5
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=5 len=3
[agy-bridge] 12:30:48 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=6 len_new=6
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=0 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=1 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=2 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=4 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=5 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=6 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=7 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=8 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=9 len=5
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=10 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=11 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=12 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=13 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=14 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=15 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=16 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=17 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=18 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=19 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=20 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=21 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=22 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=23 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=24 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=25 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=26 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=27 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=28 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=29 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=30 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=31 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=32 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=33 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=34 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=35 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=36 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=37 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=38 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=39 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=40 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=41 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=42 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=43 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=44 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=45 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=46 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=47 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=48 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=49 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=50 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=51 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=52 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=53 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=54 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=55 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=56 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=57 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=58 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=59 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=60 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=61 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=62 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=63 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=64 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=65 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=66 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=67 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=68 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=69 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=70 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=71 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=72 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=73 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=74 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=75 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=76 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=77 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=78 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=79 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=80 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=81 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=82 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=83 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=84 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=85 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=86 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=87 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=88 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=89 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=90 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=91 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=92 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=93 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=94 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=95 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=96 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=97 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=98 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=99 len=6
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=100 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=101 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=102 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=103 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=104 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=105 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=106 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=107 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=108 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=109 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=110 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=111 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=112 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=113 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=114 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=115 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=116 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=117 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=118 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=119 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=120 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=121 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=122 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=123 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=124 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=125 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=126 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=127 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=128 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=129 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=130 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=131 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=132 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=133 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=134 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=135 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=136 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=137 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=138 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=139 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=140 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=141 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=142 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=143 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=144 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=145 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=146 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=147 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=148 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=149 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=150 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=151 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=152 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=153 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=154 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=155 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=156 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=157 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=158 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=159 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=160 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=161 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=162 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=163 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=164 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=165 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=166 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=167 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=168 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=169 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=170 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=171 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=172 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=173 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=174 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=175 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=176 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=177 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=178 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=179 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=180 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=181 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=182 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=183 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=184 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=185 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=186 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=187 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=188 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=189 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=190 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=191 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=192 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=193 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=194 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=195 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=196 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=197 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=198 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=199 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=200 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=201 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=202 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=203 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=204 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=205 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=206 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=207 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=208 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=209 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=210 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=211 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=212 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=213 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=214 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=215 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=216 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=217 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=218 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=219 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=220 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=221 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=222 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=223 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=224 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=225 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=226 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=227 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=228 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=229 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=230 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=231 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=232 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=233 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=234 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=235 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=236 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=237 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=238 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=239 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=240 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=241 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=242 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=243 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=244 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=245 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=246 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=247 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=248 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=249 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=250 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=251 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=252 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=253 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=254 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=255 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=256 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=257 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=258 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=259 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=260 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=261 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=262 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=263 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=264 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=265 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=266 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=267 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=268 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=269 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=270 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=271 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=272 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=273 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=274 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=275 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=276 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=277 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=278 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=279 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=280 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=281 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=282 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=283 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=284 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=285 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=286 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=287 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=288 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=289 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=290 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=291 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=292 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=293 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=294 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=295 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=296 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=297 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=298 len=7
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=299 len=7
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=17
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=1
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=20
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=47
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=20
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:30:48 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=3 len_new=5
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=540
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=3 len=540
[agy-bridge] 12:30:48 sqlite-gen cid=82188e72 step=5
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=5 len=2780
[agy-bridge] 12:30:48 sqlite-emit cid=82188e72 step=5 len=2781
.[agy-bridge] 12:30:48 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:48 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:48 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:48 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:48 tail-emit cid=82188e72 step=3 len=22
[agy-bridge] 12:30:48 reasoning-emit cid=82188e72 n=1 len=22 ok=1
[agy-bridge] 12:30:49 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:49 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=1.4 err='Individual quota reached' tag
.[agy-bridge] 12:30:49 exec model=m effort=low effort_source=default prompt_bytes=29 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:30:49 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:49 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:49 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:49 tail-emit cid=82188e72 step=3 len=22
[agy-bridge] 12:30:49 reasoning-emit cid=82188e72 n=1 len=22 ok=1
[agy-bridge] 12:30:50 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:50 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=1.4 err='Individual quota reached' tag
.[agy-bridge] 12:30:50 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:51 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:51 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:51 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:51 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:51 transient failure state=agy_error rc=1 err='boom', retry 1 tag
[agy-bridge] 12:30:51 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:51 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:51 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:51 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:52 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:52 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.5 err='' tag
.[agy-bridge] 12:30:52 turn_mode cid=82188e72 mode=LIVE
........[agy-bridge] 12:30:52 init conversation=c1 tools=0 permission_mode=
[agy-bridge] 12:30:52 reasoning-emit cid=c1 n=1 len=8 ok=1
[agy-bridge] 12:30:52 reasoning-emit cid=c1 n=2 len=7 ok=1
[agy-bridge] 12:30:52 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:52 done model=m rc=1 state=agy_error conversation=c1 turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='Individual quota reached' tag
[agy-bridge] 12:30:52 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:52 transient failure state=agy_error rc=1 err='Individual quota reached', retry 1 tag
[agy-bridge] 12:30:52 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:52 done model=m rc=1 state=agy_error conversation=c1 turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='Individual quota reached' tag
..[agy-bridge] 12:30:52 init conversation=c1 tools=0 permission_mode=
[agy-bridge] 12:30:52 reasoning-emit cid=c1 n=1 len=1 ok=1
...[agy-bridge] 12:30:52 watchdog idle_timeout pgid=424242 idle>=300s
.[agy-bridge] 12:30:52 breaker state=OPEN probe_gen=0
..[agy-bridge] 12:30:52 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:52 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
[agy-bridge] 12:30:52 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:53 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:53 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:53 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:53 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:30:53 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:30:54 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:54 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.[agy-bridge] 12:30:54 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:54 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:30:54 sqlite-emit cid=82188e72 step=3 len=13
[agy-bridge] 12:30:54 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:54 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:54 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:54 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:54 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:30:54 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:30:55 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:55 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.[agy-bridge] 12:30:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:55 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
.[agy-bridge] 12:30:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:55 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:55 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:55 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:55 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:55 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:30:55 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:30:56 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:56 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
[agy-bridge] 12:30:56 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:56 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:56 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:56 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:56 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:56 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:30:56 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:30:57 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:57 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.1 err='' tag
.[agy-bridge] 12:30:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:30:57 sqlite-off cid=82188e72 reason=db_error
[agy-bridge] 12:30:57 sqlite-open-fail cid=82188e72 err=DatabaseError cold=0
[agy-bridge] 12:30:57 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:57 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:30:57 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:57 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:58 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:30:58 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:30:58 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:58 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.Источник hung: таймаут 0.1s, пропущен
..page.close() завис дольше 0.1s, пропущен
page.close() не удался: Target closed
.[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 drain cid=82188e72 ms=351 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:59 drain cid=82188e72 ms=353 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:59 drain cid=82188e72 ms=353 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:59 drain cid=82188e72 ms=354 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:30:59 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:30:59 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:30:59 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:30:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:30:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:30:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:30:59 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:30:59 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:00 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:00 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:00 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:00 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:00 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:00 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:00 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:00 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:00 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:00 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:00 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:00 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:00 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:00 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:00 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:00 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:00 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:00 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:00 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:00 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:00 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:00 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:00 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:00 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:00 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:00 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:00 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:00 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:00 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:00 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:00 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:00 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:01 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:01 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:02 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:02 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:02 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:02 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:02 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:02 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:02 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:02 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:02 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:02 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:02 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:02 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:31:02 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:31:03 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
.[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 drain cid=82188e72 ms=350 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:03 drain cid=82188e72 ms=352 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:03 drain cid=82188e72 ms=350 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:03 drain cid=82188e72 ms=352 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:03 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:03 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:04 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:04 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:04 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:04 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:04 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:04 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:04 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:04 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:04 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:04 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:04 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:04 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:04 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:04 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:04 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:04 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=356 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:05 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:31:05 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:31:06 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:06 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:06 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:06 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:06 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:06 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:06 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:06 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
.[agy-bridge] 12:31:06 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:06 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:06 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:06 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:07 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:07 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:31:07 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:07 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:07 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:07 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:08 drain cid=82188e72 ms=502 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:08 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
.[agy-bridge] 12:31:08 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:31:08 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:08 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:08 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:08 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:08 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
...........[agy-bridge] 12:31:10 watchdog_ps_degraded rid=- turn_id=- pgid=19991 reason=rc_<MagicMock name='_run_ps().returncode' id='4402622624'>
.[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=env
.[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:10 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:10 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:10 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:31:10 sqlite-off cid=82188e72 reason=flag
...[agy-bridge] 12:31:52 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:31:52 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:52 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:52 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:31:52 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:31:52 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:52 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:52 sqlite-emit cid=82188e72 step=3 len=4
[agy-bridge] 12:31:52 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=4 len_new=4
[agy-bridge] 12:31:52 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:31:52 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:52 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:52 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:31:52 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=65 tools=0 resume=1 sess=plain client=127.0.0.1:59312 ua=-
[agy-bridge] 12:31:52 turn_mode cid=57172100 mode=OFF
[agy-bridge] 12:31:52 sqlite-off cid=57172100 reason=flag
[agy-bridge] 12:31:52 cid-busy-fresh cid=57172100
[agy-bridge] 12:31:52 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=79 tools=0 resume=0 sess=plain client=127.0.0.1:59313 ua=-
[agy-bridge] 12:31:52 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:52 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:31:52 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:31:52 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:31:53 drain cid=fa92a264 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:53 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59313 ua=-
[agy-bridge] 12:31:54 drain cid=57172100 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:54 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.8 err='' client=127.0.0.1:59312 ua=-
.[agy-bridge] 12:31:54 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:54 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:31:54 sqlite-emit cid=82188e72 step=3 len=15
[agy-bridge] 12:31:54 sqlite-emit cid=82188e72 step=3 len=7
.[agy-bridge] 12:31:54 tail-emit cid=82188e72 step=2 len=9
.[agy-bridge] 12:31:54 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:31:54 sqlite-gen cid=82188e72 step=4
[agy-bridge] 12:31:54 sqlite-emit cid=82188e72 step=4 len=9
.[agy-bridge] 12:31:54 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:54 tail-emit cid=82188e72 step=3 len=5
.[agy-bridge] 12:31:54 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=89 tools=1 resume=0 sess=agentic client=127.0.0.1:59320 ua=-
[agy-bridge] 12:31:54 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:54 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:54 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:55 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:55 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' client=127.0.0.1:59320 ua=-
[agy-bridge] 12:31:55 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=88 tools=0 resume=0 sess=plain client=127.0.0.1:59323 ua=-
[agy-bridge] 12:31:55 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:31:55 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:31:55 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:31:55 drain cid=fa92a264 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:55 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59323 ua=-
[agy-bridge] 12:31:55 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=48 tools=1 resume=1 sess=agentic client=127.0.0.1:59324 ua=-
[agy-bridge] 12:31:55 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:55 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:56 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:56 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:56 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59324 ua=-
.[agy-bridge] 12:31:56 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=89 tools=1 resume=0 sess=agentic client=127.0.0.1:59351 ua=-
[agy-bridge] 12:31:57 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:57 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:57 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:57 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:57 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59351 ua=-
[agy-bridge] 12:31:57 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=31 tools=1 resume=1 sess=agentic client=127.0.0.1:59359 ua=-
[agy-bridge] 12:31:57 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:57 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:31:57 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=86 tools=0 resume=0 sess=plain client=127.0.0.1:59360 ua=-
[agy-bridge] 12:31:57 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:57 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:31:57 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:31:57 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:31:58 drain cid=fa92a264 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:58 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59360 ua=-
[agy-bridge] 12:31:59 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:31:59 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.9 err='' client=127.0.0.1:59359 ua=-
.[agy-bridge] 12:31:59 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=78 tools=0 resume=0 sess=plain client=127.0.0.1:59366 ua=-
[agy-bridge] 12:31:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:31:59 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:31:59 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:32:00 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:00 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' client=127.0.0.1:59366 ua=-
[agy-bridge] 12:32:00 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=78 tools=0 resume=0 sess=plain client=127.0.0.1:59376 ua=-
[agy-bridge] 12:32:00 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:32:00 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:32:00 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:32:01 drain cid=fa92a264 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:01 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59376 ua=-
[agy-bridge] 12:32:01 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=107 tools=0 resume=0 sess=plain client=127.0.0.1:59379 ua=-
[agy-bridge] 12:32:01 init conversation=57172100 tools=0 permission_mode=x
[agy-bridge] 12:32:01 turn_mode cid=57172100 mode=OFF
[agy-bridge] 12:32:01 sqlite-off cid=57172100 reason=flag
[agy-bridge] 12:32:01 drain cid=57172100 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:01 done model=gemini-3.8-flash rc=0 state=done conversation=57172100 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59379 ua=-
[agy-bridge] 12:32:01 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=107 tools=0 resume=0 sess=plain client=127.0.0.1:59382 ua=-
[agy-bridge] 12:32:02 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:32:02 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:32:02 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:32:02 drain cid=fa92a264 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:02 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:59382 ua=-
.[agy-bridge] 12:32:02 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:32:02 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=523
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=287
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=278
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=331
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=737
.[agy-bridge] 12:32:02 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:32:02 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:32:02 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=800
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=700
.[agy-bridge] 12:32:02 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=3 len=10
[agy-bridge] 12:32:02 sqlite-gen cid=82188e72 step=7
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=7 len=10
[agy-bridge] 12:32:02 sqlite-emit cid=82188e72 step=7 len=13
.[agy-bridge] 12:32:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:32:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:32:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:32:03 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:32:03 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:32:03 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:32:04 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
[agy-bridge] 12:32:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=1 resume=1 sess=plain tag
[agy-bridge] 12:32:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:32:04 sqlite-off cid=82188e72 reason=env
[agy-bridge] 12:32:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:32:05 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:32:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.1 err='' tag
..............
----------------------------------------------------------------------
Ran 97 tests in 81.528s

OK
```

### VER-006 (PASS, rc=0)
```text
OK
```

### VER-007 (PASS, rc=0)
```text
OK 51 ids, all asserted
```

### VER-008 (PASS, rc=0)
```text
OK
```

### VER-009 (PASS, rc=0)
```text
OK
```

### VER-010 (PASS, rc=0)
```text
.                                                                        [100%]
1 passed, 96 deselected in 42.23s

.
----------------------------------------------------------------------
Ran 1 test in 41.515s

OK
```

### VER-011 (DEFERRED_L3, rc=0)
```text
DEFERRED_L3: executes on live 127.0.0.1:9887 immediately after Council ACCEPT and BEFORE opening/merging MR (per teamlead-gate Step 5).
```

### VER-012 (PASS, rc=0)
```text
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:55 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:55 sqlite-schema-mismatch cid=82188e72
[agy-bridge] 12:34:55 sqlite-off cid=82188e72 reason=schema
[agy-bridge] 12:34:55 sqlite-open-fail cid=82188e72 err=OperationalError cold=0
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:55 sqlite-schema-mismatch cid=82188e72
[agy-bridge] 12:34:55 sqlite-off cid=82188e72 reason=schema
[agy-bridge] 12:34:55 sqlite-open-fail cid=82188e72 err=OperationalError cold=0
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:55 sqlite-off cid=82188e72 reason=db_error
[agy-bridge] 12:34:55 sqlite-open-fail cid=82188e72 err=DatabaseError cold=0
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:55 breaker state=OPEN probe_gen=0
[agy-bridge] 12:34:55 breaker state=CLOSED probe_gen=1
[agy-bridge] 12:34:55 breaker state=OPEN probe_gen=1
[agy-bridge] 12:34:55 breaker state=OPEN probe_gen=2
[agy-bridge] 12:34:55 breaker state=CLOSED probe_gen=5
.[agy-bridge] 12:34:55 exec model=m effort=low effort_source=default prompt_bytes=10 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:34:55 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:55 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:34:55 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:34:56 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:34:56 hot session failed err='boom', cold fallback tag
[agy-bridge] 12:34:56 exec model=m effort=low effort_source=default prompt_bytes=27 tools=1 resume=0 sess=agentic tag
[agy-bridge] 12:34:56 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:34:56 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:56 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:34:56 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:34:56 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.5 err='' tag
[agy-bridge] 12:34:56 exec model=m effort=low effort_source=default prompt_bytes=10 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:34:56 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:56 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:34:56 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:34:57 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:34:57 retry-budget-exhausted state=agy_error tag
[agy-bridge] 12:34:57 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=0.7 err='boom' tag
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=13
[agy-bridge] 12:34:57 sqlite_transcript_divergence cid=82188e72 step=3 len_prev=13 len_new=13
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=divergence
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 compat state=SHADOW reason=divergence
[agy-bridge] 12:34:57 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=3 len_new=3
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:34:57 compat state=SHADOW reason=binary_identity
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 turn_mode cid=fa92a264 mode=SHADOW
[agy-bridge] 12:34:57 sqlite-gen cid=fa92a264 step=3
[agy-bridge] 12:34:57 tail-emit cid=fa92a264 step=3 len=25
[agy-bridge] 12:34:57 compat state=LIVE
[agy-bridge] 12:34:57 turn_mode cid=57172100 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=57172100 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=57172100 step=3 len=17
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=SHADOW
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=40
[agy-bridge] 12:34:57 compat state=LIVE
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=0 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=1 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=2 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=4 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=5 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=6 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=7 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=8 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=9 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=10 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=11 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=12 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=13 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=14 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=15 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=16 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=17 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=18 len=6
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=19 len=6
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=flag
.[agy-bridge] 12:34:57 sqlite-off cid=../x reason=cid
[agy-bridge] 12:34:57 turn_mode cid=../x mode=OFF
[agy-bridge] 12:34:57 sqlite-off cid=a/b reason=cid
[agy-bridge] 12:34:57 turn_mode cid=a/b mode=OFF
[agy-bridge] 12:34:57 sqlite-off cid=zz-not-h reason=cid
[agy-bridge] 12:34:57 turn_mode cid=zz-not-h mode=OFF
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=15
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=12
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=6
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=5
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=5 len=3
[agy-bridge] 12:34:57 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=6 len_new=6
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=0 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=1 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=2 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=4 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=5 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=6 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=7 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=8 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=9 len=5
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=10 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=11 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=12 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=13 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=14 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=15 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=16 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=17 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=18 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=19 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=20 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=21 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=22 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=23 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=24 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=25 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=26 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=27 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=28 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=29 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=30 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=31 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=32 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=33 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=34 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=35 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=36 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=37 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=38 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=39 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=40 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=41 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=42 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=43 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=44 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=45 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=46 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=47 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=48 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=49 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=50 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=51 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=52 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=53 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=54 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=55 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=56 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=57 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=58 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=59 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=60 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=61 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=62 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=63 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=64 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=65 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=66 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=67 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=68 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=69 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=70 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=71 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=72 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=73 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=74 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=75 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=76 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=77 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=78 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=79 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=80 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=81 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=82 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=83 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=84 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=85 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=86 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=87 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=88 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=89 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=90 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=91 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=92 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=93 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=94 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=95 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=96 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=97 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=98 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=99 len=6
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=100 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=101 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=102 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=103 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=104 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=105 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=106 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=107 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=108 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=109 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=110 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=111 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=112 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=113 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=114 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=115 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=116 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=117 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=118 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=119 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=120 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=121 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=122 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=123 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=124 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=125 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=126 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=127 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=128 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=129 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=130 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=131 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=132 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=133 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=134 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=135 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=136 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=137 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=138 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=139 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=140 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=141 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=142 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=143 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=144 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=145 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=146 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=147 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=148 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=149 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=150 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=151 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=152 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=153 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=154 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=155 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=156 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=157 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=158 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=159 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=160 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=161 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=162 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=163 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=164 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=165 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=166 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=167 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=168 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=169 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=170 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=171 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=172 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=173 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=174 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=175 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=176 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=177 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=178 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=179 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=180 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=181 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=182 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=183 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=184 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=185 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=186 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=187 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=188 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=189 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=190 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=191 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=192 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=193 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=194 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=195 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=196 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=197 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=198 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=199 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=200 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=201 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=202 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=203 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=204 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=205 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=206 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=207 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=208 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=209 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=210 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=211 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=212 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=213 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=214 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=215 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=216 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=217 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=218 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=219 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=220 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=221 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=222 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=223 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=224 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=225 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=226 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=227 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=228 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=229 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=230 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=231 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=232 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=233 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=234 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=235 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=236 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=237 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=238 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=239 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=240 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=241 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=242 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=243 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=244 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=245 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=246 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=247 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=248 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=249 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=250 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=251 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=252 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=253 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=254 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=255 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=256 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=257 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=258 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=259 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=260 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=261 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=262 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=263 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=264 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=265 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=266 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=267 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=268 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=269 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=270 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=271 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=272 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=273 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=274 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=275 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=276 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=277 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=278 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=279 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=280 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=281 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=282 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=283 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=284 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=285 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=286 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=287 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=288 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=289 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=290 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=291 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=292 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=293 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=294 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=295 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=296 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=297 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=298 len=7
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=299 len=7
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=17
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=1
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=20
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=47
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=20
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:34:57 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=3 len_new=5
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=540
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=3 len=540
[agy-bridge] 12:34:57 sqlite-gen cid=82188e72 step=5
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=5 len=2780
[agy-bridge] 12:34:57 sqlite-emit cid=82188e72 step=5 len=2781
.[agy-bridge] 12:34:57 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:34:57 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:34:57 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:57 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:34:57 tail-emit cid=82188e72 step=3 len=22
[agy-bridge] 12:34:57 reasoning-emit cid=82188e72 n=1 len=22 ok=1
[agy-bridge] 12:34:58 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:34:58 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=1.3 err='Individual quota reached' tag
.[agy-bridge] 12:34:58 exec model=m effort=low effort_source=default prompt_bytes=29 tools=1 resume=1 sess=agentic tag
[agy-bridge] 12:34:58 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:34:58 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:34:59 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:34:59 tail-emit cid=82188e72 step=3 len=22
[agy-bridge] 12:34:59 reasoning-emit cid=82188e72 n=1 len=22 ok=1
[agy-bridge] 12:35:00 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:00 done model=m rc=1 state=agy_error conversation=82188e72 turns=None tool_events=0 out_bytes=0 wall_s=1.4 err='Individual quota reached' tag
.[agy-bridge] 12:35:00 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:00 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:00 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:00 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:01 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:01 transient failure state=agy_error rc=1 err='boom', retry 1 tag
[agy-bridge] 12:35:01 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:01 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:01 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:01 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:01 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:01 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.5 err='' tag
.[agy-bridge] 12:35:01 turn_mode cid=82188e72 mode=LIVE
........[agy-bridge] 12:35:02 init conversation=c1 tools=0 permission_mode=
[agy-bridge] 12:35:02 reasoning-emit cid=c1 n=1 len=8 ok=1
[agy-bridge] 12:35:02 reasoning-emit cid=c1 n=2 len=7 ok=1
[agy-bridge] 12:35:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:02 done model=m rc=1 state=agy_error conversation=c1 turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='Individual quota reached' tag
[agy-bridge] 12:35:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:02 transient failure state=agy_error rc=1 err='Individual quota reached', retry 1 tag
[agy-bridge] 12:35:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:02 done model=m rc=1 state=agy_error conversation=c1 turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='Individual quota reached' tag
..[agy-bridge] 12:35:02 init conversation=c1 tools=0 permission_mode=
[agy-bridge] 12:35:02 reasoning-emit cid=c1 n=1 len=1 ok=1
...[agy-bridge] 12:35:02 watchdog idle_timeout pgid=424242 idle>=300s
.[agy-bridge] 12:35:02 breaker state=OPEN probe_gen=0
..[agy-bridge] 12:35:02 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:02 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
[agy-bridge] 12:35:02 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:02 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:35:02 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:02 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:02 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:35:02 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:35:03 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:03 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.[agy-bridge] 12:35:03 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:03 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:03 sqlite-emit cid=82188e72 step=3 len=13
[agy-bridge] 12:35:03 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:03 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:35:03 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:03 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:03 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:35:03 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:35:04 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:04 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.[agy-bridge] 12:35:04 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:04 sqlite-open-fail cid=82188e72 err=OperationalError cold=1
.[agy-bridge] 12:35:04 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:04 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:04 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:35:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:05 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:35:05 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:35:05 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:05 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
[agy-bridge] 12:35:05 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:05 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:06 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:35:06 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:06 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:06 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:35:06 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:35:07 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:07 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.[agy-bridge] 12:35:07 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:07 sqlite-off cid=82188e72 reason=db_error
[agy-bridge] 12:35:07 sqlite-open-fail cid=82188e72 err=DatabaseError cold=0
[agy-bridge] 12:35:07 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:07 sqlite-off cid=82188e72 reason=cid_busy
[agy-bridge] 12:35:07 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:07 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:07 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:35:07 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:35:08 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:08 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.2 err='' tag
.Источник hung: таймаут 0.1s, пропущен
..page.close() завис дольше 0.1s, пропущен
page.close() не удался: Target closed
.[agy-bridge] 12:35:08 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:08 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:08 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:08 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:08 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:08 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:08 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:08 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:08 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:08 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:08 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:08 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:08 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:08 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:08 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:08 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:08 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:08 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:08 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:08 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:08 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:08 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:08 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:08 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:09 drain cid=82188e72 ms=352 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=352 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=354 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=354 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:09 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:09 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:09 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:09 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:09 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:09 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:09 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:09 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:09 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:09 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:09 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:09 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:09 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:09 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:09 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:09 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:09 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:09 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:09 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:09 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:09 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:10 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:10 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:10 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:10 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:10 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:10 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:10 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:10 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:10 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:10 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:10 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:10 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:10 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:10 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:10 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:10 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:11 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:11 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:11 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:11 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:11 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:11 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:11 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:11 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:11 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:11 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:11 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:11 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:11 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:11 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:11 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:11 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:11 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:11 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:11 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:11 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:11 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:11 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:11 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:11 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:12 tail-emit cid=82188e72 step=3 len=24
[agy-bridge] 12:35:12 reasoning-emit cid=82188e72 n=1 len=24 ok=1
[agy-bridge] 12:35:12 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:12 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
.[agy-bridge] 12:35:12 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:12 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:12 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:12 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:12 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:12 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:12 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:12 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:12 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:12 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:12 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:12 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:13 drain cid=82188e72 ms=354 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=354 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=355 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=353 emitted=1 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:13 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:13 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:13 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:13 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:13 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:13 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:13 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:13 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:13 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:13 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:13 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:13 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:13 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:13 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:13 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:13 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:13 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:13 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:13 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:13 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:13 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:13 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:13 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:13 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:13 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:13 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:13 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:13 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:13 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:14 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:14 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:14 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:14 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:14 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:14 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:14 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:14 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:15 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:15 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:15 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:15 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:15 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:15 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:15 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:15 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:15 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:15 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:15 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:15 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:15 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:15 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:15 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:15 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:15 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:15 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:15 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:15 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:15 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:15 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:15 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:15 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:15 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:15 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:15 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:15 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:15 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:15 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:15 tail-emit cid=82188e72 step=3 len=29
[agy-bridge] 12:35:15 reasoning-emit cid=82188e72 n=1 len=29 ok=1
[agy-bridge] 12:35:15 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:15 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:16 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:16 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:16 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:16 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:16 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:16 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
.[agy-bridge] 12:35:16 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:16 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:16 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:16 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:16 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:16 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
[agy-bridge] 12:35:16 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:16 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:16 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:16 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:17 drain cid=82188e72 ms=503 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:17 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' tag
.[agy-bridge] 12:35:17 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:35:17 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:35:17 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:17 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:18 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:35:18 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' tag
...........[agy-bridge] 12:35:20 watchdog_ps_degraded rid=- turn_id=- pgid=66025 reason=rc_<MagicMock name='_run_ps().returncode' id='4427587440'>
.[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=env
.[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:35:20 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:35:20 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:35:20 sqlite-emit cid=82188e72 step=3 len=3
[agy-bridge] 12:35:20 sqlite-off cid=82188e72 reason=flag
...[agy-bridge] 12:36:01 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:36:01 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:01 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:01 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:36:01 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:36:01 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:01 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:01 sqlite-emit cid=82188e72 step=3 len=4
[agy-bridge] 12:36:01 sqlite_snapshot_divergence cid=82188e72 step=3 len_prev=4 len_new=4
[agy-bridge] 12:36:01 sqlite-off cid=82188e72 reason=divergence
.[agy-bridge] 12:36:01 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:01 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:01 sqlite-emit cid=82188e72 step=3 len=3
.[agy-bridge] 12:36:01 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=65 tools=0 resume=1 sess=plain client=127.0.0.1:60283 ua=-
[agy-bridge] 12:36:01 turn_mode cid=57172100 mode=OFF
[agy-bridge] 12:36:01 sqlite-off cid=57172100 reason=flag
[agy-bridge] 12:36:02 cid-busy-fresh cid=57172100
[agy-bridge] 12:36:02 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=79 tools=0 resume=0 sess=plain client=127.0.0.1:60284 ua=-
[agy-bridge] 12:36:02 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:02 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:36:02 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:36:02 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:36:02 drain cid=fa92a264 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:02 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60284 ua=-
[agy-bridge] 12:36:03 drain cid=57172100 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:03 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.9 err='' client=127.0.0.1:60283 ua=-
.[agy-bridge] 12:36:04 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:04 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:04 sqlite-emit cid=82188e72 step=3 len=15
[agy-bridge] 12:36:04 sqlite-emit cid=82188e72 step=3 len=7
.[agy-bridge] 12:36:04 tail-emit cid=82188e72 step=2 len=9
.[agy-bridge] 12:36:04 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:04 sqlite-gen cid=82188e72 step=4
[agy-bridge] 12:36:04 sqlite-emit cid=82188e72 step=4 len=9
.[agy-bridge] 12:36:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:04 tail-emit cid=82188e72 step=3 len=5
.[agy-bridge] 12:36:04 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=89 tools=1 resume=0 sess=agentic client=127.0.0.1:60289 ua=-
[agy-bridge] 12:36:04 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:04 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:04 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:04 drain cid=82188e72 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:04 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' client=127.0.0.1:60289 ua=-
[agy-bridge] 12:36:04 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=88 tools=0 resume=0 sess=plain client=127.0.0.1:60291 ua=-
[agy-bridge] 12:36:05 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:36:05 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:36:05 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:36:05 drain cid=fa92a264 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:05 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60291 ua=-
[agy-bridge] 12:36:05 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=48 tools=1 resume=1 sess=agentic client=127.0.0.1:60293 ua=-
[agy-bridge] 12:36:05 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:05 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:05 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:06 drain cid=82188e72 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:06 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60293 ua=-
.[agy-bridge] 12:36:06 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=89 tools=1 resume=0 sess=agentic client=127.0.0.1:60298 ua=-
[agy-bridge] 12:36:06 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:06 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:06 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:07 drain cid=82188e72 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:07 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.8 err='' client=127.0.0.1:60298 ua=-
[agy-bridge] 12:36:07 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=31 tools=1 resume=1 sess=agentic client=127.0.0.1:60300 ua=-
[agy-bridge] 12:36:07 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:07 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:07 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=86 tools=0 resume=0 sess=plain client=127.0.0.1:60301 ua=-
[agy-bridge] 12:36:07 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:07 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:36:07 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:36:07 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:36:08 drain cid=fa92a264 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:08 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60301 ua=-
[agy-bridge] 12:36:09 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:09 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=2.0 err='' client=127.0.0.1:60300 ua=-
.[agy-bridge] 12:36:09 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=78 tools=0 resume=0 sess=plain client=127.0.0.1:60310 ua=-
[agy-bridge] 12:36:09 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:09 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:09 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:10 drain cid=82188e72 ms=351 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:10 done model=gemini-3.8-flash rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60310 ua=-
[agy-bridge] 12:36:10 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=78 tools=0 resume=0 sess=plain client=127.0.0.1:60318 ua=-
[agy-bridge] 12:36:10 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:36:10 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:36:10 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:36:10 drain cid=fa92a264 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:10 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60318 ua=-
[agy-bridge] 12:36:10 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=107 tools=0 resume=0 sess=plain client=127.0.0.1:60323 ua=-
[agy-bridge] 12:36:10 init conversation=57172100 tools=0 permission_mode=x
[agy-bridge] 12:36:10 turn_mode cid=57172100 mode=OFF
[agy-bridge] 12:36:10 sqlite-off cid=57172100 reason=flag
[agy-bridge] 12:36:11 drain cid=57172100 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:11 done model=gemini-3.8-flash rc=0 state=done conversation=57172100 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60323 ua=-
[agy-bridge] 12:36:11 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=107 tools=0 resume=0 sess=plain client=127.0.0.1:60326 ua=-
[agy-bridge] 12:36:11 init conversation=fa92a264 tools=0 permission_mode=x
[agy-bridge] 12:36:11 turn_mode cid=fa92a264 mode=OFF
[agy-bridge] 12:36:11 sqlite-off cid=fa92a264 reason=flag
[agy-bridge] 12:36:12 drain cid=fa92a264 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:12 done model=gemini-3.8-flash rc=0 state=done conversation=fa92a264 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60326 ua=-
.[agy-bridge] 12:36:12 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:12 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=523
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=287
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=278
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=331
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=737
.[agy-bridge] 12:36:12 turn_mode cid=82188e72 mode=LIVE
.[agy-bridge] 12:36:12 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:12 sqlite-gen cid=82188e72 step=3
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=800
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=700
.[agy-bridge] 12:36:12 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=3 len=10
[agy-bridge] 12:36:12 sqlite-gen cid=82188e72 step=7
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=7 len=10
[agy-bridge] 12:36:12 sqlite-emit cid=82188e72 step=7 len=13
.[agy-bridge] 12:36:12 exec model=m effort=low effort_source=default prompt_bytes=2 tools=0 resume=0 sess=plain tag
[agy-bridge] 12:36:12 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:12 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:12 sqlite-off cid=82188e72 reason=flag
[agy-bridge] 12:36:12 tail-emit cid=82188e72 step=3 len=23
[agy-bridge] 12:36:12 reasoning-emit cid=82188e72 n=1 len=23 ok=1
[agy-bridge] 12:36:13 drain cid=82188e72 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:13 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.1 err='' tag
[agy-bridge] 12:36:13 exec model=m effort=low effort_source=default prompt_bytes=2 tools=1 resume=1 sess=plain tag
[agy-bridge] 12:36:13 turn_mode cid=82188e72 mode=OFF
[agy-bridge] 12:36:13 sqlite-off cid=82188e72 reason=env
[agy-bridge] 12:36:13 init conversation=82188e72 tools=0 permission_mode=x
[agy-bridge] 12:36:14 drain cid=82188e72 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 12:36:14 done model=m rc=0 state=done conversation=82188e72 turns=None tool_events=0 out_bytes=10 wall_s=1.1 err='' tag
..............
----------------------------------------------------------------------
Ran 97 tests in 81.653s

OK
```

### VER-013 (PASS, rc=0)
```text
base_sha (e00da0621fc95f7c63cd1565f4a5d1fd490c8d66): Ran 899 tests in 337.225s, FAILED (failures=2 in tests/test_muse_bridge_killpg.py::test_t00_models_and_health_include_wonder_models_400k due to external ~/.dsh/profiles/desktop/cordis.patch.yml)
candidate: Ran 974 tests in 414.814s (+75 new tests in tests/test_agy_bridge_resilience.py, 97/97 PASS), FAILED (failures=2 — identical 2 pre-existing failures in tests/test_muse_bridge_killpg.py).
Delta: +75 passed, 0 new failures, 0 new errors.
```
