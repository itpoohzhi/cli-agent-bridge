# Clean-Room L2 & Verifier Execution Evidence (`agy-image-input-fix-20261029`)

- **Generated At (UTC):** `2026-10-29T13:07:09.269120+00:00`
- **Base SHA:** `5a19559426de7508d525e2bd465eff648665a6a7`
- **Clean-Room Worktree:** `/var/folders/2f/c42p3_k11d9252tg83blw_mc0000gn/T/agy-image-cleanroom-limla3vr/wt`
- **`bridges/agy-bridge/fleet.json` SHA-256:** `fe2564ea0eb1f17d681f8ccfb7224b4b44eb4c999cb5ac1cad518736a92b5baf`
- **`bridges/agy-bridge/server.py` SHA-256:** `3227e8ef769c5ebda5b4aa5647bbd651f4a9b28c784122c61c3e1f638be9e357`
- **`tests/test_agy_bridge_resilience.py` SHA-256:** `f318d60537ad862b11313d303644ace3ff5ae74e5d581ceeba86bcf7bddeeff5`
- **`architecture/architecture-packet.json` SHA-256:** `ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`
- **`teamlead/verification-surface.json` SHA-256:** `860cb91f65f95578f3c383652702cfa48a85877df16fccba3f62282fbe8034e9`

## Verification Gate Results (`VER-001..VER-010`)

| ID | Status | Exit Code | Duration (s) | Summary |
|---|---|---|---|---|
| `VER-001` | `PASS` | `0` | `0.15` | `All checks passed!` |
| `VER-002` | `PASS` | `0` | `0.13` | `2 files already formatted` |
| `VER-003` | `PASS` | `0` | `119.95` | `146 passed, 142 subtests passed in 119.29s (0:01:59)` |
| `VER-004` | `PASS` | `0` | `8.53` | `PASS: version 1.40.2 server_py_errors=0 new_errors=0 new_warnings=0 (warnings 791 vs baseline 804)` |
| `VER-005` | `PASS` | `0` | `114.67` | `OK` |
| `VER-006` | `PASS` | `0` | `10.18` | `OK` |
| `VER-007` | `PASS` | `0` | `0.16` | `QA_ASSERT_COVERAGE_PASS 40` |
| `VER-008` | `PASS` | `0` | `0.13` | `SCOPE_FROZEN_PASS` |
| `VER-009` | `PASS` | `0` | `0.13` | `IMAGE_STDLIB_SECURITY_PASS` |
| `VER-010` | `DEFERRED_L3` | `None` | `0.0` | `Deferred to Wave 6 live L3 verification on 127.0.0.1:9887 after Council ACCEPT` |

### VER-001 (`PASS`, `exit_code=0`, `0.15s`)
```bash
uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
All checks passed!
```

### VER-002 (`PASS`, `exit_code=0`, `0.13s`)
```bash
uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
2 files already formatted
```

### VER-003 (`PASS`, `exit_code=0`, `119.95s`)
```bash
PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py
```
```text
.......................................................................................... [ 61%]
........................................................ [100%]
146 passed, 142 subtests passed in 119.29s (0:01:59)
```

### VER-004 (`PASS`, `exit_code=0`, `8.53s`)
```bash
uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
{
  "version": "1.40.2",
  "candidate_summary": {
    "filesAnalyzed": 2,
    "errorCount": 1,
    "warningCount": 791,
    "informationCount": 0,
    "timeInSec": 2.476
  },
  "baseline_summary": {
    "filesAnalyzed": 2,
    "errorCount": 1,
    "warningCount": 804,
    "informationCount": 0,
    "timeInSec": 2.164
  },
  "server_py_errors": 0,
  "new_errors_vs_baseline": 0,
  "new_warnings_vs_baseline": 0,
  "pre_existing_test_error": [
    {
      "file": "test_agy_bridge_resilience.py",
      "line": 2905,
      "rule": "reportOperatorIssue",
      "message": "Operator \"+\" not supported for types \"object\" and \"Literal['&immutable=1']\""
    }
  ]
}
PASS: version 1.40.2 server_py_errors=0 new_errors=0 new_warnings=0 (warnings 791 vs baseline 804)
```

### VER-005 (`PASS`, `exit_code=0`, `114.67s`)
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"
```
```text
[agy-bridge] 16:03:32 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60564 ua=-
[agy-bridge] 16:03:32 init conversation=73cfa943 tools=0 permission_mode=x
[agy-bridge] 16:03:32 turn_mode cid=73cfa943 mode=OFF
[agy-bridge] 16:03:32 sqlite-off cid=73cfa943 reason=flag
[agy-bridge] 16:03:32 drain cid=73cfa943 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:32 done model=gemini-4-argon rc=0 state=done conversation=73cfa943 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60564 ua=-
[agy-bridge] 16:03:32 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60565 ua=-
[agy-bridge] 16:03:32 init conversation=41c3c935 tools=0 permission_mode=x
[agy-bridge] 16:03:32 turn_mode cid=41c3c935 mode=OFF
[agy-bridge] 16:03:32 sqlite-off cid=41c3c935 reason=flag
[agy-bridge] 16:03:33 drain cid=41c3c935 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:33 done model=gemini-3.8-flash rc=0 state=done conversation=41c3c935 turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60565 ua=-
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.7-flash model_len=16 client=127.0.0.1:60568
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.6-flash model_len=16 client=127.0.0.1:60569
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.1-pro model_len=14 client=127.0.0.1:60570
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:60571
[agy-bridge] 16:03:33 image_reject detail=image_input_disabled
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60572
[agy-bridge] 16:03:33 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=63 tools=0 resume=0 sess=plain client=127.0.0.1:60573 ua=-
[agy-bridge] 16:03:33 init conversation=c352d97e tools=0 permission_mode=x
[agy-bridge] 16:03:33 turn_mode cid=c352d97e mode=OFF
[agy-bridge] 16:03:33 sqlite-off cid=c352d97e reason=flag
[agy-bridge] 16:03:33 drain cid=c352d97e ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:33 done model=gemini-4-argon rc=0 state=done conversation=c352d97e turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60573 ua=-
[agy-bridge] 16:03:33 image_reject detail=image_input_disabled
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60577
.[agy-bridge] 16:03:34 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=2801 tools=0 resume=0 sess=plain client=127.0.0.1:60579 ua=-
[agy-bridge] 16:03:34 init conversation=dc364503 tools=0 permission_mode=x
[agy-bridge] 16:03:34 turn_mode cid=dc364503 mode=OFF
[agy-bridge] 16:03:34 sqlite-off cid=dc364503 reason=flag
[agy-bridge] 16:03:34 drain cid=dc364503 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:35 done model=gemini-4-argon rc=0 state=done conversation=dc364503 turns=None tool_events=0 out_bytes=10 wall_s=0.6 err='' client=127.0.0.1:60579 ua=-
[agy-bridge] 16:03:35 image_reject detail=too_many_images
[agy-bridge] 16:03:35 reject reason=too_many_images model=gemini-4-argon model_len=14 client=127.0.0.1:60580
.[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60582
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60583
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60584
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60585
[agy-bridge] 16:03:35 image_reject detail=unsupported_mime
[agy-bridge] 16:03:35 reject reason=unsupported_image_type model=gemini-4-argon model_len=14 client=127.0.0.1:60586
[agy-bridge] 16:03:35 image_reject detail=unknown_magic
[agy-bridge] 16:03:35 reject reason=unsupported_image_type model=gemini-4-argon model_len=14 client=127.0.0.1:60587
[agy-bridge] 16:03:35 image_reject detail=invalid_base64
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60588
[agy-bridge] 16:03:35 image_reject detail=empty_payload
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60589
[agy-bridge] 16:03:35 image_reject detail=invalid_base64
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60590
[agy-bridge] 16:03:35 image_reject detail=mime_mismatch
[agy-bridge] 16:03:35 reject reason=image_type_mismatch model=gemini-4-argon model_len=14 client=127.0.0.1:60591
[agy-bridge] 16:03:35 image_reject detail=mime_mismatch
[agy-bridge] 16:03:35 reject reason=image_type_mismatch model=gemini-4-argon model_len=14 client=127.0.0.1:60592
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60593
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60594
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60595
[agy-bridge] 16:03:35 image_reject detail=malformed_data_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60596
[agy-bridge] 16:03:35 image_reject detail=malformed_data_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60597
[agy-bridge] 16:03:35 image_reject detail=non_user_image
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60598
[agy-bridge] 16:03:35 image_reject detail=too_many_images
[agy-bridge] 16:03:35 reject reason=too_many_images model=gemini-4-argon model_len=14 client=127.0.0.1:60599
[agy-bridge] 16:03:35 image_reject detail=image_too_large
[agy-bridge] 16:03:35 reject reason=image_too_large model=gemini-4-argon model_len=14 client=127.0.0.1:60600
[agy-bridge] 16:03:35 image_reject detail=images_too_large
[agy-bridge] 16:03:35 reject reason=images_too_large model=gemini-4-argon model_len=14 client=127.0.0.1:60601
[agy-bridge] 16:03:35 image_reject detail=input_not_image
[agy-bridge] 16:03:35 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:60602
[agy-bridge] 16:03:35 image_proof_invalid model=gemini-4-argon reason=impl_version_mismatch
[agy-bridge] 16:03:35 image_reject detail=image_proof_invalid
[agy-bridge] 16:03:35 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60603
[agy-bridge] 16:03:35 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=22 tools=0 resume=0 sess=plain client=127.0.0.1:60604 ua=-
[agy-bridge] 16:03:35 init conversation=8fd64ba6 tools=0 permission_mode=x
[agy-bridge] 16:03:35 turn_mode cid=8fd64ba6 mode=OFF
[agy-bridge] 16:03:35 sqlite-off cid=8fd64ba6 reason=flag
[agy-bridge] 16:03:36 drain cid=8fd64ba6 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:36 done model=gemini-4-argon rc=0 state=done conversation=8fd64ba6 turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60604 ua=-
..[agy-bridge] 16:03:36 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=1 resume=0 sess=agentic client=127.0.0.1:60610 ua=-
[agy-bridge] 16:03:36 init conversation=f824fb0b tools=0 permission_mode=x
[agy-bridge] 16:03:36 turn_mode cid=f824fb0b mode=OFF
[agy-bridge] 16:03:36 sqlite-off cid=f824fb0b reason=flag
[agy-bridge] 16:03:37 drain cid=f824fb0b ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:37 done model=gemini-4-argon rc=0 state=done conversation=f824fb0b turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60610 ua=-
.[agy-bridge] 16:03:37 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60613 ua=-
[agy-bridge] 16:03:37 init conversation=091751fb tools=0 permission_mode=x
[agy-bridge] 16:03:37 turn_mode cid=091751fb mode=OFF
[agy-bridge] 16:03:37 sqlite-off cid=091751fb reason=flag
[agy-bridge] 16:03:38 drain cid=091751fb ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 done model=gemini-4-argon rc=0 state=done conversation=091751fb turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60613 ua=-
[agy-bridge] 16:03:38 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 init conversation=1e6dba27 tools=0 permission_mode=x
[agy-bridge] 16:03:38 turn_mode cid=1e6dba27 mode=OFF
[agy-bridge] 16:03:38 sqlite-off cid=1e6dba27 reason=flag
[agy-bridge] 16:03:38 drain cid=1e6dba27 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 transient failure state=agy_error rc=1 err='boom', retry 1 client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 init conversation=3a4fd18a tools=0 permission_mode=x
[agy-bridge] 16:03:38 turn_mode cid=3a4fd18a mode=OFF
[agy-bridge] 16:03:38 sqlite-off cid=3a4fd18a reason=flag
[agy-bridge] 16:03:38 drain cid=3a4fd18a ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 done model=gemini-4-argon rc=1 state=agy_error conversation=3a4fd18a turns=None tool_events=0 out_bytes=0 wall_s=0.9 err='boom' client=127.0.0.1:60614 ua=-
..[agy-bridge] 16:03:39 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60634 ua=-
[agy-bridge] 16:03:39 init conversation=0b193fbb tools=0 permission_mode=x
[agy-bridge] 16:03:39 turn_mode cid=0b193fbb mode=OFF
[agy-bridge] 16:03:39 sqlite-off cid=0b193fbb reason=flag
[agy-bridge] 16:03:41 drain cid=0b193fbb ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=0 state=done conversation=0b193fbb turns=None tool_events=0 out_bytes=10 wall_s=1.6 err='' client=127.0.0.1:60634 ua=-
.[agy-bridge] 16:03:41 exec model=gemini-4-argon effort=low effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain tag
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=1 state=agy_error conversation=- turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='e' tag
[agy-bridge] 16:03:41 exec model=gemini-4-argon effort=low effort_source=default prompt_bytes=390 tools=0 resume=1 sess=agentic tag
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=1 state=agy_error conversation=- turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='e' tag
..[agy-bridge] 16:03:42 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 16:03:42 sqlite-open-fail cid=82188e72 err=OperationalErro
```

### VER-006 (`PASS`, `exit_code=0`, `10.18s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess; d=subprocess.check_output(["git","diff","--numstat","5a19559426de7508d525e2bd465eff648665a6a7","--","tests/test_agy_bridge_resilience.py"],text=True).splitlines(); assert all(int(l.split()[1])==0 for l in d); subprocess.run(["/usr/bin/python3","-B","-m","unittest","discover","-s","tests","-p","test_images_strict.py"],check=True)'
```
```text
2026-10-29T13:05:26Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61032 ua=-
2026-10-29T13:05:26Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:26Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:26Z done model=claude-sonnet-5-5 rc=1 state=client_gone sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.0 err='' client=127.0.0.1:61032 ua=-
.2026-10-29T13:05:27Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:27Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='', retry 1 client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='', retry 2 client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:28Z done model=claude-sonnet-5-5 rc=1 state=done sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.3 err='' client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z http "POST /v1/chat/completions HTTP/1.1" 502 -
.2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='Exec failed', retry 1 client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='Exec failed', retry 2 client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:28Z done model=claude-sonnet-5-5 rc=1 state=done sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.5 err='Exec failed' client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z http "POST /v1/chat/completions HTTP/1.1" 502 -
.2026-10-29T13:05:29Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61053 ua=-
2026-10-29T13:05:29Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:29Z usage sess=sid-a273 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:29Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-a273 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61053 ua=-
2026-10-29T13:05:29Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:30Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61057 ua=-
2026-10-29T13:05:30Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:30Z usage sess=sid-429f raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:30Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-429f resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61057 ua=-
2026-10-29T13:05:30Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:30Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=1353 images=16 image_bytes=1144 image_types=image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png client=127.0.0.1:61065 ua=-
2026-10-29T13:05:30Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:30Z usage sess=sid-04c5 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:30Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-04c5 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61065 ua=-
2026-10-29T13:05:30Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:31Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=1150 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61069 ua=-
2026-10-29T13:05:31Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:31Z usage sess=sid-5dd5 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:31Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-5dd5 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61069 ua=-
2026-10-29T13:05:31Z http "POST /v1/chat/completions HTTP/1.1" 200 -
...2026-10-29T13:05:32Z reject reason=too_many_images model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61076
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z reject reason=image_too_large model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61077
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z reject reason=images_too_large model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61078
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=549 images=2 image_bytes=1400 image_types=image/png,image/png client=127.0.0.1:61079 ua=-
2026-10-29T13:05:32Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:32Z usage sess=sid-764a raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:32Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-764a resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61079 ua=-
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61087
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61088
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61089
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61090
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61091
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_base64 model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61092
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_base64 model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61093
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_type_mismatch model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61094
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61095
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61096
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61097
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61098
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61099
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61100
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61101
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61102
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61103
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61104
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
.2026-10-29T13:05:34Z reject reason=image_input_not_supported model=gemini-3.8-flash model_len=16 client=127.0.0.1:61107
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:34Z reject reason=image_input_not_supported model=glm-5.3 model_len=7 client=127.0.0.1:61108
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 400 -
.2026-10-29T13:05:34Z exec model=deepseek-v4.1-flash effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=493 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61110 ua=-
2026-10-29T13:05:34Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:34Z usage sess=sid-0e4e raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:34Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-0e4e resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61110 ua=-
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:35Z exec model=deepseek-v4.1-flash effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=17 client=127.0.0.1:61116 ua=-
2026-10-29T13:05:35Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:35Z usage sess=sid-a5fc raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:35Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-a5fc resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61116 ua=-
2026-10-29T13:05:35Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:36Z exec model=deepseek-v4.1-flash effort=max effort_source=request autonomy=high autonomy_source=default prompt_bytes=493 images=1 image_bytes=64 ima
```

### VER-007 (`PASS`, `exit_code=0`, `0.16s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,re; from pathlib import Path; t=ast.parse(Path("tests/test_agy_bridge_resilience.py").read_text()); expected={f"{p}{i:02}" for p,n in [("img",10),("hist",10),("life",5),("log",2),("res",3),("ao",10)] for i in range(1,n+1)}; found=set();
for f in ast.walk(t):
 if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith("test_") and any(isinstance(a,ast.Assert) or isinstance(a,ast.Call) and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id=="self" and a.func.attr.startswith("assert") for a in ast.walk(f)):
  found.update(k for k in expected if re.search(r"(?:^|_)"+k+r"(?:_|$)",f.name))
assert not expected-found,sorted(expected-found); print("QA_ASSERT_COVERAGE_PASS",len(expected))'
```
```text
QA_ASSERT_COVERAGE_PASS 40
```

### VER-008 (`PASS`, `exit_code=0`, `0.13s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess,hashlib; from pathlib import Path; b="5a19559426de7508d525e2bd465eff648665a6a7"; expected={"bridges/agy-bridge/fleet.json","bridges/agy-bridge/server.py","tests/test_agy_bridge_resilience.py"}; names=subprocess.check_output(["git","diff","--name-only",b,"HEAD"],text=True).splitlines(); actual={n for n in names if not n.startswith((".ai-team/","analysis/"))}; assert actual==expected,(actual,expected); tracked=subprocess.check_output(["git","ls-files"],text=True).splitlines(); assert not any(Path(n).name=="dynamic_config.json" for n in tracked); frozen={'"'"'research-plan'"'"': '"'"'67f3bfffc4e9df6b95ee8571c34ded4a397ad164f86787b3b935fe51dcf1243a'"'"', '"'"'evidence-ledger'"'"': '"'"'aba34816b5cf6425d4fbf19187a09edd5f7158797e442d488d68626576f887a9'"'"', '"'"'open-questions'"'"': '"'"'63fe13ce25d80cb7bad68d25a57c8d1d6e58847b5b8be79dc395b555c55e5b76'"'"', '"'"'handoff-architect'"'"': '"'"'6c22f4a0ab4fc71d2e7cd88e1fe7d2df8c327193eb75bfc9d922af68a4710a8f'"'"', '"'"'handoff-qa'"'"': '"'"'007cdac728cdd6754c6617cd749ed3361f0d19c9e1adae16a3c31a90ee352cee'"'"'};
for n,h in frozen.items(): assert hashlib.sha256(Path("analysis/agy-image-input-fix",n+".md").read_bytes()).hexdigest()==h,n
print("SCOPE_FROZEN_PASS")'
```
```text
SCOPE_FROZEN_PASS
```

### VER-009 (`PASS`, `exit_code=0`, `0.13s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,sys; from pathlib import Path; s=Path("bridges/agy-bridge/server.py").read_text(); t=ast.parse(s); allowed=set(getattr(sys,"stdlib_module_names",()))|{"core"}; assert allowed-{"core"},"Use Python >=3.10 for stdlib inventory"; roots={a.name.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}|{n.module.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module}; assert roots<=allowed,roots-allowed; vals=[ast.literal_eval(n.value) for n in ast.walk(t) if isinstance(n,ast.Assign) and any(isinstance(a,ast.Name) and a.id=="IMPLEMENTED_METHODS" for a in n.targets)]; assert vals==[{"workspace-read":1}],vals; assert all(v in s for v in ["IMAGE_INPUT_ENABLED","AGY_IMAGE_INPUT_ENABLED","--add-dir"]); helpers={n.name:n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}; todo=[n for n in helpers if "image" in n or "data_url" in n]; seen=set();
while todo:
 n=todo.pop()
 if n in seen: continue
 seen.add(n); f=helpers[n]
 for a in ast.walk(f):
  if isinstance(a,ast.Call):
   name=ast.unparse(a.func); assert not any(v in name for v in ["urlopen","urlretrieve","urllib.request","http.client","HTTPConnection","HTTPSConnection"]),name
   if isinstance(a.func,ast.Name) and a.func.id in helpers: todo.append(a.func.id)
print("IMAGE_STDLIB_SECURITY_PASS")'
```
```text
IMAGE_STDLIB_SECURITY_PASS
```

### VER-010 (`DEFERRED_L3`, `exit_code=None`, `0.0s`)
```bash
Manual L3 verification on :9887
```
```text
Deferred to Wave 6 live L3 verification on 127.0.0.1:9887 after Council ACCEPT
```
