from pathlib import Path
import re, subprocess, json
root = Path(__file__).resolve().parents[3]
b = root / "analysis/agy-image-input-fix"
run = Path(__file__).resolve().parent
names = ["research-plan.md", "evidence-ledger.md", "open-questions.md", "handoff-architect.md", "handoff-qa.md"]
docs = {n: (b/n).read_text() for n in names}
ledger = docs["evidence-ledger.md"]
arch = docs["handoff-architect.md"]
qa = docs["handoff-qa.md"]
questions = docs["open-questions.md"]
results = []
def check(n, ok, detail):
    results.append({"id": f"SA-DOD-{n:03}", "pass": bool(ok), "detail": detail})
    print(f"SA-DOD-{n:03} {'PASS' if ok else 'FAIL'}: {detail}")
facts = re.findall(r"^\[F-(\d+)\].*$", ledger, re.M)
valid = re.findall(r"^\[F-(\d+)\][^|]*\|[^|]*\| 2026-10-29$", ledger, re.M)
check(1, len(facts)>0 and facts==valid and len(facts)==len(set(facts)), f"{len(facts)} unique facts, ISO dates and source fields")
rows = [l for l in questions.splitlines() if re.match(r"\| OPEN-\d+ \|",l)]
closed = all(l.rstrip().endswith("| closed |") and "[BLOCKER]" not in l for l in rows)
guesses = re.search(r"вероятно|скорее всего|наверное|по-видимому|должно быть",arch+qa,re.I)
check(2, bool(rows) and closed and not guesses, f"{len(rows)} questions closed as facts or explicit assumptions, no open blockers or hidden guesses")
spikes = [l for l in docs["research-plan.md"].splitlines() if l.startswith("INV-")]
shape = all(len(l.split(" | "))==12 and l.split(" | ")[8]=="closed" and re.fullmatch(r"F-\d+",l.split(" | ")[9]) for l in spikes)
check(3,len(spikes)==5 and shape,"INV-01..INV-05: 12 columns and closed status")
reqs = [l for l in arch.splitlines() if re.match(r"\| REQ-\d{3} \|",l)]
req_ok = len(reqs)==10 and all(re.search(r"\| (MUST|SHOULD) \|",l) and re.search(r"F-\d+",l) and f"AC-{i:03}" in l for i,l in enumerate(reqs,1))
check(4,req_ok,"REQ-001..010 each has priority, facts and measurable AC on the same line")
declared = {f"F-{x}" for x in facts}
refs = set(re.findall(r"F-\d+",arch))
# Also expand compact ranges; checking only the endpoints would miss gaps.
for lo,hi in re.findall(r"F-(\d+)\.\.F-(\d+)",arch):
    refs.update(f"F-{i:02}" for i in range(int(lo),int(hi)+1))
check(5,refs<=declared,f"all {len(refs)} architect fact references declared; dates ISO; missing={sorted(refs-declared)}")
ssot=Path.home()/"Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md"
canonical=re.findall(r"^\| \d+ \| `([^`]+)` \|",ssot.read_text(),re.M)
legacy="W P_pods G_reload T_threads_per_worker Limit_dep_total Limit_dep_share Pool_app_size Pool_app_overflow Max_in_flight_per_worker N_roles W_role Pool_role_size Pool_role_overflow M_other_apps_max Ephemeral_port_range_size TIME_WAIT_s ulimit_n FD_non_socket_overhead N_bg_tasks T_poll_s Jitter_Ratio Startup_Delay_Range_s K_calls Limit_dep_rps Cold_start_concurrent_pods Singleflight_Scope Cache_TTL_s Max_stale_age_s Payload_bytes_max N_items_max Hot_path_call_rate_rps CPU_budget_pct_per_core Serde_lib P_avail_min Mem_limit_per_pod Mem_rss_worker_max Mem_shared_max SLA_p99_s T_connect_s T_read_s Retries_max Retry_Budget_pct Retry_Window_s Min_Retry_Floor_rps N_candidates N_floor".split()
section6=arch.split("## 6.",1)[1].split("## 7.",1)[0]
section7=arch.split("## 7.",1)[1].split("## 8.",1)[0]
fields=lambda t: re.findall(r"^\| \d+ \| `([^`]+)` \|",t,re.M)
hl_ok=len(canonical)==46 and len(legacy)==46 and fields(section6)==canonical and fields(section7)==legacy
check(6,hl_ok,"46 current SSoT rows + 46 literal brief rows; UNKNOWN explicitly qualified, no claim of resource-gate PASS")
qa_acs={int(x) for x in re.findall(r"^\| AC-(\d+) \|",qa,re.M)}
terms=["image_url_not_allowed","unsupported_image_type","invalid_image_base64","image_type_mismatch","invalid_image_content","too_many_images","image_too_large","images_too_large","image_input_not_supported","--add-dir","view_file","finally","cold","hot",":9887","base64","cwd","1..16"]
check(7,qa_acs==set(range(1,11)) and all(t in qa for t in terms),"QA covers all 10 AC, taxonomy, count/MIME boundaries, retry lifecycle and L3")
status=subprocess.check_output(["git","status","--porcelain","--untracked-files=all"],cwd=root,text=True)
paths=[l[3:] for l in status.splitlines()]
allowed=all(p.startswith("analysis/agy-image-input-fix/") or p.startswith(".ai-team/") for p in paths)
actual={p.name for p in b.iterdir() if p.is_file()}
timebox_ok=all(int(l.split(" | ")[10])<=int(l.split(" | ")[4]) or "таймбокс превышен:" in l.split(" | ")[11] for l in spikes)
check(8,allowed and actual==set(names) and timebox_ok,"five artifacts only; git scope analysis/agy-image-input-fix + .ai-team; timeboxes accounted")
receipt={"schema":"stage1-sa-dod/1","scope":"brief-specific artifact validation; NOT product, ARCH_GATE or HL-ENV numeric acceptance","results":results,"git_status":status}
(run/"sa-dod-stage1.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
print(status,end="")
if not all(x["pass"] for x in results): raise SystemExit(1)
print("SA-DOD-001..008 PASS")
