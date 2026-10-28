Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-10`, `iteration: 2`) и должен непосредственно внести точечное исправление в `server.py` и обновить артефакты `plans/coder-10.before.json`, `plans/coder-10.json`, `handoffs/coder-10.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-10`, вход `fix-from-gate`, `teamlead_cycle: 7`, `iteration: 2`) в изолированном клоне `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`.

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `target_files`:
  1. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py`
  2. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
  3. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py`
- `prior_findings`:
  - Лог падения `Clean-Room L2`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён.

## Причина падения `Clean-Room L2` (`CG-HTTP-CLOSE-RACE`)
В `test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body` (на `server.py:2685`, `chunk = resp.read1(65536)`) возникла гонка потоков Python 3.14 `http.client`:
1. Сторожевой поток `_watch_serve_connection` (`server.py:2602-2614`) при наступлении `deadline` вызывает:
   - `sock.shutdown(socket.SHUT_RDWR)`
   - и сразу `conn.close()` из фонового потока!
2. Вызов `conn.close()` из фонового потока закрывает `HTTPResponse` (`self.__response.close()`), который обнуляет `resp.fp = None` в момент, когда основной поток внутри `resp.read1(65536)` уже получил пустой буфер после `shutdown` и вызывает `self._close_conn()`:
   ```
   File ".../http/client.py", line 706, in read1
     self._close_conn()
   File ".../http/client.py", line 443, in _close_conn
     fp.close()
   AttributeError: 'NoneType' object has no attribute 'close'
   ```
3. Более того, в `_watch_serve_connection` (`server.py:2607-2613`) фоновый поток НЕ должен вызывать не потокобезопасный `conn.close()` на объекте `HTTPConnection`, с которым параллельно работает основной поток! Фоновому потоку достаточно разбудить блокирующий системный вызов сокета через `sock.shutdown(socket.SHUT_RDWR)` (и при необходимости `sock.close()` только если `conn.sock` ещё не обёрнут в `HTTPResponse`, либо просто `sock.shutdown(socket.SHUT_RDWR)` + выставить флажок `timed_out` в разделяемом списке/событии, а `active_conn.close()` всегда выполняется основным потоком в `finally`!).
4. А если `resp.read1(65536)` при асинхронном закрытии сокета сторожем возвращает `b""` (или бросает `AttributeError`/`ValueError` из-за закрытого `fp`) ПОСЛЕ срабатывания сторожа (когда `deadline is not None and time.monotonic() >= deadline` или `is_client_gone()`), `_serve_http` на строках `2683-2696` НЕ должен молча выходить из `while not resp.isclosed():` по `if not chunk: break` как будто тело успешно дочитано до конца! Перед `if not chunk: break` (и сразу после `chunk = resp.read1(65536)`) нужно вызвать `check_phase()` (а также перехватить `(AttributeError, ValueError)` вокруг `resp.read1(65536)` и вызвать `check_phase()` / поднять `TimeoutError("serve http deadline expired")`), чтобы прерванное дедлайном капающее тело ВСЕГДА бросало `TimeoutError` (подкласс `OSError`), а не возвращало усечённый ответ или `AttributeError`!

## Точное задание для `coder-10`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-10.before.json` (`iteration: 2`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.json"`, `trigger_ids: ["CG-HTTP-CLOSE-RACE"]`, шаги `RP-01..RP-03` со статусом `"PENDING"`) и провалидируй через `validate_role_plan.py --phase before`.
2. В `bridges/opencode-zen-bridge/server.py`:
   - В `_watch_serve_connection` (`server.py:2593-2618`): убери не потокобезопасный вызов `conn.close()` из фонового потока `watch()`. Вместо `conn.close()` в `watch()` вызывай `sock.shutdown(socket.SHUT_RDWR)` (и `sock.close()` в `try...except OSError: pass`) на `sock = conn.sock or phase_socket[0]`.
   - В `_serve_http` (`server.py:2674-2696`):
     - Вокруг `resp = active_conn.getresponse()` и `chunk = resp.read1(65536)` перехватывай `(AttributeError, ValueError)` (которые `http.client` может бросить при конкурентном закрытии сокета сторожем) и в обработчике вызывай `check_phase()` (или поднимай `TimeoutError("serve http deadline expired")`).
     - Внутри цикла чтения тела `while not resp.isclosed():` сразу после `chunk = resp.read1(65536)` вызывай `check_phase()` ДО `if not chunk: break`, чтобы если `shutdown(SHUT_RDWR)` от сторожа привёл к возврату `b""` (EOF), `_serve_http` гарантированно выбросил `TimeoutError` / `BrokenPipeError`, а не вернул неполное тело как успешный ответ!
3. Отформатируй изменённый диапазон `server.py` строго через:
   `uvx --from ruff==0.17.2 ruff format --config bridges/opencode-zen-bridge/ruff.toml --no-cache --range=2590:1-2715:999 bridges/opencode-zen-bridge/server.py`
4. Запусти `VER-004` (код в `bridges/opencode-zen-bridge/server.py` на строках `2593-2713` УЖЕ содержит твоё исправление `CG-HTTP-CLOSE-RACE`, а `/Users/aazhiry1/work/cli-agent-bridge/coder-10-20261027/deadline-20.log` УЖЕ подтвердил `20/20 PASS`; если `uvx` обращается в сеть, передавай `--offline`):
   ```bash
   python3 - <<'VER004'
import ast, collections, hashlib, json, re, subprocess, tempfile
from pathlib import Path
root = Path.cwd().resolve()
bridge = root / 'bridges/opencode-zen-bridge'
files = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']
assert all(f.is_file() for f in files), 'all three target files must exist after Stage3'
ruff = ['uvx','--from','ruff==0.17.2','ruff']
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
def changed_ranges(file):
    rel = str(file.relative_to(root))
    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)
    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.
    result = []
    for line in diff.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            start = int(m.group(1)); count = int(m.group(2) or '1')
            if count: result.append((start, start + count - 1))
    return result

# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.
FROZEN = {
    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',
    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',
    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',
}
baseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)
def frozen_slices(raw):
    lines = raw.splitlines(keepends=True)
    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}
    assert set(nodes)==set(FROZEN)
    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}
baseline_slices = frozen_slices(baseline_raw)
def assert_frozen(candidate=files[0]):
    candidate_slices = frozen_slices(candidate.read_bytes())
    for name, expected in FROZEN.items():
        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)
        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)
        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)
    return candidate_slices
candidate_slices = assert_frozen()
server_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)
for line in server_diff.splitlines():
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if not match: continue
    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:
        for name,(lo,hi,_) in table.items():
            # Zero-count insert/delete anchors represent the boundary after start.
            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)
            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)
# Public module constant/read API remains intact; compatibility test file is frozen.
tree = ast.parse(files[0].read_bytes())
assignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]
assert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'
assert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)
assert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))
assert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'
helper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "sys.argv[1:2] == ['--serve-helper']"), None)
assert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'
heavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}
def imported_names(node):
    if isinstance(node, ast.Import): return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom): return {node.module}
    return set()
assert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])
assert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)
assert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'
assert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))
run(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)

ranges = {f: changed_ranges(f) for f in files[:2]}
# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.
run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)
for f in files[:2]:
    for start, end in ranges[f]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)
assert_frozen()
# Exercise actual write-mode range formatting only on a disposable copy.
with tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:
    formatted_copy = Path(format_dir) / 'server.py'
    formatted_copy.write_bytes(files[0].read_bytes())
    for start, end in ranges[files[0]]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)
    assert formatted_copy.read_bytes() == files[0].read_bytes()
    assert_frozen(formatted_copy)
    assert_frozen()
    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})
# Full-file lint on all three. Only inherited E402 import site is excepted on server.
lint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)
assert lint.returncode in (0,1), lint.stderr
findings = json.loads(lint.stdout)
lines = files[0].read_text().splitlines()
assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings
assert sum(x['code']=='E402' for x in findings) <= 1
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)
# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.
project = None
try:
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:
        project = Path(tmp.name)
        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)
    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)
    assert b.returncode in (0,1), b.stderr
    report = json.loads(b.stdout)
    ds = report['generalDiagnostics']
    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds
    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}
    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}
    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']
    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))
    print('BASEDPYRIGHT summary',report['summary'])
    print('SERVER dict(counts)',dict(counts))
    print('SERVER warningCount',len(warnings(files[0])))
    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)
    assert len(warnings(files[0]))<=720, len(warnings(files[0]))
    assert len(warnings(files[1]))<=194, len(warnings(files[1]))
    # New test file: zero warnings as well as zero errors, thus zero Any.
    assert not byfile[files[2]], byfile[files[2]]
    for f in files[:2]:
        for x in byfile[f]:
            line = x['range']['start']['line']+1
            if any(lo<=line<=hi for lo,hi in ranges[f]):
                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x
    # Do not introduce Any annotations/type ignores in added code in either legacy file.
    for f in files[:2]:
        src = f.read_text().splitlines()
        for lo,hi in ranges[f]:
            for line in src[lo-1:hi]:
                assert not re.search(r'\bAny\b|type:\s*ignore|pyright:\s*ignore|#\s*noqa|#\s*fmt:\s*off',line), (f,line)
    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)
    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))
finally:
    if project is not None: project.unlink(missing_ok=True)
VER004
   ```
   и прогони `uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body`.
5. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-10.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-10.json` (`round_id: "coder-10"`, `iteration: 2`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй через `validate_role_plan.py --phase after` и `validate_handoff.py coder --role-plan /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-10.json --root /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`.
