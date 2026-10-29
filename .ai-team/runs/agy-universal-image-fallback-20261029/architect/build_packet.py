"""Generate architecture run artifacts only; never write product/test files."""
import ast
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUN = ROOT / '.ai-team/runs/agy-universal-image-fallback-20261029'
BASE = '012da99905ec27a6133afb4f3e768ff9b4426a8f'
OLD_BASE = '5a19559426de7508d525e2bd465eff648665a6a7'
ANALYSIS = ROOT / 'analysis/agy-universal-image-fallback'
TEST = 'tests/test_agy_bridge_resilience.py'
SERVER = 'bridges/agy-bridge/server.py'
FLEET = 'bridges/agy-bridge/fleet.json'

def dump(rel, value):
    p = RUN / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())

def py(code):
    return 'PYTHONDONTWRITEBYTECODE=1 python3 -B -c ' + shlex.quote(code)

ha = (ANALYSIS / 'handoff-architect.md').read_text()
hq = (ANALYSIS / 'handoff-qa.md').read_text()
ledger = (ANALYSIS / 'evidence-ledger.md').read_text()
frozen = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in sorted(ANALYSIS.glob('*.md'))}
base_test = subprocess.check_output(['git', 'show', BASE + ':' + TEST], cwd=ROOT)
assert (ROOT / TEST).read_bytes() == base_test
prefix_hash = sha(base_test)

requirements = []
for m in re.finditer(r'^- (REQ-\d{2}): (.+)$', ha, re.M):
    requirements.append({'id': m[1], 'statement': m[2]})
contracts = []
for m in re.finditer(r'^(CON-\d{2}) — (.+)$', ha, re.M):
    contracts.append({'id': m[1], 'baseline': m[2]})
invariants = []
for m in re.finditer(r'^- (INV-\d{2}): (.+)$', ha, re.M):
    invariants.append({'id': m[1], 'statement': m[2]})
acceptance = []
for m in re.finditer(r'^(AC-\d{2}) / (.+)$', hq, re.M):
    acceptance.append({'id': m[1], 'oracle': m[2]})
scenarios = []
for m in re.finditer(r'^(SCN-(?:uf\d{2}|B\d{2}|R\d{2}|I\d{2})) / (.+)$', hq, re.M):
    scenarios.append({'id': m[1], 'oracle': m[2]})
assert len(requirements) == 6 and len(contracts) == 6 and len(invariants) == 12
assert len(acceptance) == 8 and len(scenarios) == 15

# Frozen verification: all commands run from repository root AFTER implementation.
ver = []
def add(num, reqs, cmd, expected, owner='Verifier'):
    ver.append({'id': f'VER-{num:03d}', 'requirement_ids': reqs, 'kind': 'command', 'command': 'run-guarded -- env ' + cmd,
                'expected': expected, 'environment': 'cwd=repo_root; after Coder, independent clean-room worktree; unset AGY_IMAGE_FALLBACK_ENABLED except scoped tests; PYTHONDONTWRITEBYTECODE=1. Not executed during Stage2.', 'owner': owner})
add(1, ['REQ-04'], 'uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py', 'exit 0; no lint errors; never use --fix on frozen baseline')
add(2, ['REQ-04'], 'uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py', 'exit 0; no formatting writes to original prefix')
execution = '''import importlib.util, os, sys, unittest
os.environ.pop("AGY_IMAGE_FALLBACK_ENABLED", None)
sys.path.insert(0, "tests"); sys.path.insert(0, ".")
spec=importlib.util.spec_from_file_location("agy_frozen_suite", "tests/test_agy_bridge_resilience.py")
m=importlib.util.module_from_spec(spec); sys.modules[spec.name]=m; spec.loader.exec_module(m)
classes=[c for n,c in vars(m).items() if isinstance(c,type) and issubclass(c,unittest.TestCase) and (n.startswith("Image") or n in {"AcceptanceOracleTests","UniversalImageFallbackTests"})]
assert any(c.__name__=="UniversalImageFallbackTests" for c in classes), "Missing universal tests"
loader=unittest.TestLoader(); suite=unittest.TestSuite(loader.loadTestsFromTestCase(c) for c in classes)
assert suite.countTestCases()>=56, suite.countTestCases()
result=unittest.TextTestRunner(verbosity=2).run(suite); assert result.wasSuccessful()
print("UNIVERSAL_AND_LEGACY_EXECUTION_PASS")'''
add(3, [f'REQ-{i:02d}' for i in range(1,7)], py(execution), '>=56 tests: all 46 legacy image-related methods plus UniversalImageFallbackTests uf01..uf10 execute and pass; not AST-only')
typecheck = f"""import collections, io, json, subprocess, tarfile, tempfile
from pathlib import Path
root=Path.cwd(); temp_base_dir=Path.home()/"work/tmp"; temp_base_dir.mkdir(parents=True,exist_ok=True)
args=["uvx","basedpyright@1.40.2","--outputjson","bridges/agy-bridge/server.py","tests/test_agy_bridge_resilience.py"]
def diagnostics(cwd):
 r=subprocess.run(args,cwd=cwd,capture_output=True,text=True)
 assert r.returncode in (0,1),(r.returncode,r.stderr)
 d=json.loads(r.stdout); assert "generalDiagnostics" in d,d
 c=collections.Counter()
 for x in d["generalDiagnostics"]:
  f=str(Path(x["file"]).relative_to(cwd)); c[(f,x.get("severity"),x.get("rule"),x["message"])]+=1
 return c
with tempfile.TemporaryDirectory(prefix="agy-type-baseline-",dir=temp_base_dir) as tmp:
 old=Path(tmp); archive=subprocess.check_output(["git","archive",{BASE!r}])
 with tarfile.open(fileobj=io.BytesIO(archive)) as tf: tf.extractall(old,filter="data")
 before=diagnostics(old); after=diagnostics(root); delta=after-before
 assert not delta,dict(delta)
 print("TYPECHECK_NO_NEW_DIAGNOSTICS_PASS","baseline",sum(before.values()),"candidate",sum(after.values()))"""
add(4, ['REQ-04'], py(typecheck), 'same pinned basedpyright executable checks archived BASE and candidate; exact multiset file/severity/rule/message delta is empty; inherited diagnostics recorded, no baseline suppression')
add(5, [f'REQ-{i:02d}' for i in range(1,7)], 'PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider', 'exit 0; full repository suite including all agy/strict tests. No pyproject.toml exists; use pinned uvx, do not invent uv run project config.')
cmd6 = f'''import hashlib, subprocess
from pathlib import Path
p={TEST!r}; old=subprocess.check_output(["git","show",{BASE!r}+":"+p]); new=Path(p).read_bytes()
assert len(old)==249933 and hashlib.sha256(old).hexdigest()=={prefix_hash!r}
assert new[:len(old)]==old, "Baseline prefix changed"
for b in [{BASE!r},{OLD_BASE!r}]:
 rows=subprocess.check_output(["git","diff","--numstat",b,"--",p],text=True).splitlines()
 assert all(row.split()[1]=="0" for row in rows), rows
subprocess.run(["python3","-B","-m","unittest","discover","-s","tests","-p","test_images_strict.py","-q"],check=True)
print("APPEND_ONLY_STRICT_PASS",len(old))'''
add(6, ['REQ-04'], py(cmd6), 'whole baseline blob is exact prefix; 0 deleted lines against both baselines; test_images_strict.py executes successfully', 'Teamlead')
cmd7 = '''import ast, re
from pathlib import Path
t=ast.parse(Path("tests/test_agy_bridge_resilience.py").read_text())
expected={f"{p}{i:02}" for p,n in [("img",10),("hist",10),("life",5),("log",2),("res",3),("ao",10),("uf",10)] for i in range(1,n+1)}
found=set(); uf=set()
for f in ast.walk(t):
 if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith("test_") and any(isinstance(a,ast.Assert) or isinstance(a,ast.Call) and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id=="self" and a.func.attr.startswith("assert") for a in ast.walk(f)):
  ids={k for k in expected if re.search(r"(?:^|_)"+k+r"(?:_|$)",f.name)}; found.update(ids)
for c in t.body:
 if isinstance(c,ast.ClassDef) and c.name=="UniversalImageFallbackTests":
  assert c.lineno>6008, c.lineno
  uf={f"uf{i:02}" for f in c.body if isinstance(f,ast.FunctionDef) for i in range(1,11) if re.match(f"test_uf{i:02}_",f.name)}
assert not expected-found, sorted(expected-found)
assert uf=={f"uf{i:02}" for i in range(1,11)},uf
print("QA_ASSERT_COVERAGE_PASS",len(expected))'''
add(7, ['REQ-01','REQ-02','REQ-03','REQ-04','REQ-06'], py(cmd7), 'all 40 inherited QA IDs + uf01..uf10 have assertion-bearing test methods; appended UniversalImageFallbackTests exists; execution independently VER003/005', 'Teamlead')
cmd8 = f'''import hashlib, subprocess
from pathlib import Path
base={BASE!r}; allowed={{{SERVER!r},{TEST!r}}}
paths=set(subprocess.check_output(["git","diff","--name-only",base,"--"],text=True).splitlines())|set(subprocess.check_output(["git","ls-files","--others","--exclude-standard"],text=True).splitlines())
paths={{p for p in paths if not p.startswith(".ai-team/runs/") and p not in {set(frozen)!r}}}
assert paths<=allowed,paths-allowed
assert Path({FLEET!r}).read_bytes()==subprocess.check_output(["git","show",base+":"+{FLEET!r}])
frozen={frozen!r}
for p,h in frozen.items(): assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
tracked=subprocess.check_output(["git","ls-files"],text=True).splitlines(); assert not any(Path(p).name=="dynamic_config.json" for p in tracked)
print("SCOPE_FROZEN_PASS")'''
add(8, [f'REQ-{i:02d}' for i in range(1,7)], py(cmd8), 'only two permitted product paths; fleet byte-identical; all five Stage1 hashes unchanged; production dynamic config not tracked', 'Teamlead')
cmd9 = '''import ast,sys
from pathlib import Path
t=ast.parse(Path("bridges/agy-bridge/server.py").read_text()); funcs={n.name:n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
required={"_read_image_fallback_flag","_is_image_fallback_enabled","_image_gate_universal","_strip_media_from_messages","_flatten_content_stripped","_messages_to_stripped_prompt","_log_token"}
assert required<=funcs.keys(),required-funcs.keys()
r=funcs["_reset_sqlite_guards_for_tests"]
assert any(isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=="_image_fallback_flag_cache" for x in n.targets) and ast.literal_eval(n.value)==(0.0,False) for n in ast.walk(r)),"cache reset"
imports={a.name.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}|{n.module.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module}
assert imports<=set(sys.stdlib_module_names)|{"core"},imports-set(sys.stdlib_module_names)-{"core"}
seen=set(); todo=[n for n in funcs if "image" in n or "media" in n or "stripped" in n]
while todo:
 n=todo.pop()
 if n in seen: continue
 seen.add(n)
 for c in ast.walk(funcs[n]):
  if isinstance(c,ast.Call):
   name=ast.unparse(c.func)
   assert not any(x in name for x in ["urlopen","urlretrieve","urllib.request","HTTPConnection","HTTPSConnection"]),name
   if isinstance(c.func,ast.Name) and c.func.id in funcs: todo.append(c.func.id)
print("STATIC_IMAGE_SECURITY_CONTRACT_PASS")'''
add(9, ['REQ-01','REQ-02','REQ-03','REQ-06'], py(cmd9), 'named helper/cache reset/static no-fetch boundary passes; actual guard ordering, prompts, delivery, CID and reserve behavior must also pass uf03..uf10 under VER003')
cmd10 = f'''import hashlib,json
from pathlib import Path
root=Path.home()/".dsh/bridges/agy-bridge"; cfg=json.loads((root/"dynamic_config.json").read_text())
assert cfg.get("IMAGE_INPUT_ENABLED") is True and cfg.get("IMAGE_FALLBACK_ENABLED") is True
assert hashlib.sha256((root/"server.py").read_bytes()).hexdigest()==hashlib.sha256(Path({SERVER!r}).read_bytes()).hexdigest()
assert (root/"fleet.json").read_bytes()==Path({FLEET!r}).read_bytes()
r=json.loads(Path(".ai-team/runs/agy-universal-image-fallback-20261029/teamlead/live-acceptance.json").read_text())
assert r["status"]=="PASS" and r["existing_owner_chat"] is True
assert r["candidate_server_sha256"]==hashlib.sha256(Path({SERVER!r}).read_bytes()).hexdigest()
needed={{"image_then_text_fallback_then_history","previously_text_only_model","cold_and_hot","explicit_cid","repeat_and_parallel","sse_completion_no_error","cleanup_before_retry","flag_rollback_reload","resource_profile","side_effect_safe_failure"}}
assert needed<=set(r["scenarios_passed"]),needed-set(r["scenarios_passed"])
assert r["unverified"]==[] and r["evidence_refs"] and all(isinstance(x,str) and x for x in r["evidence_refs"])
print("LIVE_RELEASE_RECEIPT_PRESENT_CONFIG_AND_HASH_PASS")'''
add(10, ['REQ-01','REQ-02','REQ-03','REQ-05','REQ-06'], py(cmd10), 'deployed server SHA/fleet pair and both strict JSON booleans true; independently collected same-owner-chat live receipt covers all listed scenarios and resource profile. Receipt presence is NOT itself proof: Teamlead must inspect referenced evidence.', 'Teamlead')

P = {
 'schema_version':'1.0','protocol':'AP/v1','task_id':'agy-universal-image-fallback','run_id':RUN.name,
 'criticality':'S2','profile':'python-aisdlc-gcge','status':'APPROVED',
 'approval_scope':'Author-finalized reversible design and mechanical schema/integrity gate only. No external council verdict, resource acceptance, Coder authorization or production acceptance is implied.',
 'baseline':{'branch':'feat/agy-universal-image-fallback','commit':BASE,'test_prefix_bytes':len(base_test),'test_prefix_lines':len(base_test.splitlines()),'test_prefix_sha256':prefix_hash,'test_line_discrepancy':'Owner specified 1..6009; actual baseline contains 6008 lines. Preserve the ENTIRE 249933-byte blob verbatim, including trailing newline and __main__ guard; append only.'},
 'requirement_ids':[x['id'] for x in requirements], 'requirements':requirements,
 'evidence':[], 'risk_triggers':['security','trust-boundary'], 'assumptions':[], 'decisions':[],
 'quality_scenarios':[], 'boundaries':[], 'contract_deltas':[], 'views':[], 'risks':[],
 'verification_surface':ver, 'protected_paths':[FLEET,'analysis/agy-universal-image-fallback/', '.ai-team/runs/'+RUN.name+'/architecture/', '.ai-team/runs/'+RUN.name+'/teamlead/verification-surface.json', '.ai-team/runs/'+RUN.name+'/task.json', '.ai-team/runs/'+RUN.name+'/plans/architect-01.json'],
 'materialization':[], 'approval':{'status':'NOT_REQUIRED','decision_ids':[],'approved_by':None,'evidence_ref':None},
 'independent_review':{'required':False,'status':'PENDING','reviewer':None,'evidence_ref':None,'scope':'S2 schema does not require S3 review. teamlead-with-architect still REQUIRES independent external three-family ARCH_PANEL proof before Coder; none claimed here.'},
 'open_questions':[], 'deferred':['Product implementation and append-only tests are Coder work after external ARCH_PANEL PASS.','Production deployment/config writes/restart and existing DSH chat live acceptance are release work.','Full pixel decoder and audio/video/document decoders are outside this change.','Unknown production SLA/RPS/quota/memory/CPU/FD numbers are NOT measured or fabricated; resource acceptance remains blocked.'],
 'source_contracts':contracts,'invariants':invariants,'acceptance_criteria':acceptance,'test_scenarios':scenarios,
 'frozen_inputs':frozen,
}
for i,m in enumerate(re.finditer(r'^\[(F-\d+)\] (.+)$',ledger,re.M),1):
 P['evidence'].append({'id':f'EVD-{i:03d}','kind':'document','ref':'analysis/agy-universal-image-fallback/evidence-ledger.md#'+m[1],'claim':m[2],'source_id':m[1]})
P['evidence'].append({'id':'EVD-100','kind':'code','ref':SERVER+':do_GET / _cid_release / Run.__init__ / _run_once; '+TEST+':test_ao06_health_has_four_additive_fields_and_keeps_existing_ones','claim':'Direct gap checks: health.images is bool, no _log_token or log.info logger exists, _cid_release(cid,turn_id) is owner-safe, no local conv_id in _run_once; Run gets new CLI conversation when conversation_id empty; baseline6008lines/249933bytes.'})

# Five decisions are detailed executable design contracts, not implementation code.
def decision(n,title,question,choice,drivers,alternatives,consequences,verids,details):
 P['decisions'].append({'id':f'AD-{n:03d}','title':title,'status':'APPROVED','kind':'two-way','question':question,'choice':choice,'alternatives':alternatives,'drivers':drivers,'consequences':consequences,'approval_required':False,'confirmation':{'kind':'test','command':ver[2]['command'],'expected':'Independent execution VER003 plus '+', '.join(verids)+' must pass after implementation.'},'verification_ids':verids,'details':details})

decision(1,'Universal Policy Flag & Dynamic Config Activation','How to enable universal acceptance without changing legacy strict fixtures?',
 'An independent fail-closed IMAGE_FALLBACK_ENABLED controls universal policy; IMAGE_INPUT_ENABLED continues to control staging. Capture universal once per accepted request and recheck input after slot acquisition.',
 ['REQ-01','REQ-02','REQ-04','REQ-05','CON-04','INV-01','INV-09','RISK-05'],
 ['Universal enabled by default: rejected because it breaks strict baseline and res03/hist05/life02.','Reuse IMAGE_INPUT_ENABLED as universal: rejected because _ImgEnv sets only this flag and must remain strict.'],
 ['No fleet mutation or fake proofs.','Rollback universal=false restores strict behavior for new requests; in-flight requests retain captured universal policy.','Input disable propagates on next post-slot check subject to its existing <=1s cache; accepted running CLI is not retroactively cancelled.'],
 ['VER-003','VER-006','VER-008','VER-010'],{
 'names':{'config':'IMAGE_FALLBACK_ENABLED','env':'AGY_IMAGE_FALLBACK_ENABLED','reader':'_read_image_fallback_flag()','predicate':'_is_image_fallback_enabled()','cache':'_image_fallback_flag_cache = (0.0, False)','ttl_s':1.0},
 'reader_contract':'Bounded read of DYNAMIC_CONFIG_PATH; reject missing/unreadable/oversize/invalid JSON/non-object; only data.get("IMAGE_FALLBACK_ENABLED") is True enables. Strings, integers, null and missing key are False. No env parsing inside JSON reader.',
 'env_contract':'Read env every predicate call, strip whitespace and lowercase. Nonempty 1/true/yes=>True; 0/false/no=>False; other nonempty token=>False (including on/off for NEW flag). Empty/unset falls through to JSON. Env overrides cache immediately and does not mutate JSON; no production global env export in test runner.',
 'cache_contract':'Monotonic TTL<1.0s serves cached config; age>=1.0s rereads; bounded dedicated lock _image_fallback_flag_lock protects tuple. Initialize (0.0,False); reset under that lock inside _reset_sqlite_guards_for_tests(); independent from old input, SHA and SQLite caches. Cold cache always reads current fixture path. Existing _ImgEnv/_Fixture tests need no edits.',
 'policy_matrix':[
  {'universal':False,'input_enabled':False,'images':'legacy strict reject','response':'400 image_input_not_supported for image requests; pure text unchanged'},
  {'universal':False,'input_enabled':True,'images':'legacy _image_gate proof/SHA/efforts gate','response':'legacy admission/retry same files, all old error outcomes unchanged'},
  {'universal':True,'input_enabled':False,'images':'no staging, strip all media from full history','response':'real pure-text attempt1; collect/flag_disabled event; HTTP200 iff text backend succeeds'},
  {'universal':True,'input_enabled':True,'images':'optimistic known catalog + valid effort + all safety checks; no model proof eligibility','response':'valid raster attached attempt1; validation/recheck/spool failure strips before attempt1; runtime guard strips before attempt2'}],
 'universal_gate':'_image_gate_universal(model_id,effort) validates catalog membership and declared valid model effort and current input flag; never calls _image_proof_reason/_file_sha256 nor uses images.status/proof/agy_binary_sha256/efforts_proven/formats proof. Unknown model/invalid effort remain ingress400, never rescued by media fallback. Startup fleet schema remains unchanged.',
 'collector_contract':'_collect_images(messages,model_id,effort,universal=False): default strict exactly preserves existing path/order/taxonomy. universal=True uses complete media classification, canonical image aliases and _image_gate_universal, then same limits/role/dataURL/base64/MIME/signature checks. No _stage_images before slot. Any ImageReject discards ALL collected entries; no partially valid image subset is sent.',
 'safety_limits':{'images_max':16,'per_image_bytes_max':20971520,'total_image_bytes_max':20971520,'http_body_bytes_max':33554432,'allowed_roles':['user'],'mime':['image/png','image/jpeg','image/gif','image/webp'],'encoding':'data:<allowed-mime>;base64,<strict-base64>; signature must match declared MIME','remote_reads':'forbidden including HTTP(S), file:// and relative paths','proof_is_not_safety':'Signature-only validation retained; no new pixel decoder.'},
 'production_activation':{'path':'~/.dsh/bridges/agy-bridge/dynamic_config.json','required_projection':{'IMAGE_INPUT_ENABLED':True,'IMAGE_FALLBACK_ENABLED':True},'status':'PLANNED_NOT_APPLIED_STAGE2','procedure':'After architecture and code council acceptance deploy candidate server only, verify unchanged fleet SHA, preserve unrelated config keys and atomically set both strict JSON booleans true in DEPLOYED ROOT. Code replacement needs managed bridge restart; flag toggles reload <=1s without restart. Read back flags and effective capability; then existing owner DSH chat must pass VER010 live scenarios. Never add tracked dynamic_config.json.','owner_override':'Current owner explicitly selects local dynamic_config.json plus env override; this is scoped exception to general GigaRC/no-new-env preference, not a claim that GigaRC is integrated.'}
})

decision(2,'Complete Media Normalization & Stripping Contract','How to remove media from all history and both prompt representations without payload leakage?',
 'Pure non-mutating content normalization classifies media by type AND payload keys before considering text. Precompute stripped full-history prompt in ctx before any session delta selection.',
 ['REQ-06','INV-02','INV-03','INV-04','INV-07','AC-04','AC-07'],
 ['Set images=[] only: rejected, leaves [image N], full_prompt attachments and old CID.','str(content)/text-first generic renderer: rejected, exposes media dict.text and inline payloads.'],
 ['No in-place edits to caller messages or test fixtures.','Plain textual URLs are preserved verbatim; only structured attachment payloads are removed.','Normal universal raster rendering omits other media, fallback rendering replaces it with stable placeholders.'],
 ['VER-003','VER-007','VER-009'],{
 'helper_contracts':{'_flatten_content_stripped(content)':'Return safe string with unchanged ordinary text order and newline joining; None=>empty; recognized image=>[image omitted]; other recognized media=>[media omitted]; unknown dict/object never str(dict).','_strip_media_from_messages(messages)':'Return fresh JSON-safe message list with roles/order/name/tool-call protocol metadata preserved, content replaced by safe string, nested content structures copied/normalized without mutation. Do not use copy.deepcopy on hot path: normalization is deep by visiting content recursively once.','_messages_to_stripped_prompt(messages)':'Render normalized messages through existing role/tool message envelope with images=[] and no image counter-driven media parts; zero generated [attachments], generated [image N], media paths/URLs/base64. Existing user text is not censored.'},
 'classification_order':['If structured object is image type or has image payload key, emit image placeholder BEFORE looking at text, even type=text plus image_url.','Else if other media type or media payload key, emit media placeholder BEFORE looking at text.','Else known text type/plain text value -> string text only; dict(text) supported only if safe string. Never serialize nested text object.','Lists process entries in order; plain strings pass through; None/numbers/unknown structured objects omitted; unknown object-only message gets [media omitted] to keep safe nonempty context.'],
 'image_types':['image_url','image','input_image'], 'image_payload_keys':['image_url','image'],
 'other_media_types':['input_audio','audio','video','video_url','file','document','inlineData','inline_data','fileData','file_data'],
 'other_media_payload_keys':['input_audio','audio','video','video_url','file','document','inlineData','inline_data','fileData','file_data'],
 'dict_content':'Identical handling to list parts: recognized media types/keys win; type=text with safe str text yields that text. Dict is never rendered via str(content).',
 'aliases_for_optimistic_collection':'Classify image aliases across list and dict content. Canonicalize on a private normalized copy to type=image_url with image_url={url:...}; URL source is string image_url/image payload or payload.url, including type=input_image with image_url string. Prefer image_url key over image if both; malformed/missing URL is ImageReject -> whole-request stripped fallback, never guessed local/file or raw base64. Preserve original role/msg_index and global image numbering. Type=image_url lacking payload remains an invalid image candidate, not silently dropped.',
 'normal_universal_render':'For universal normal/optimistic render only: retain canonical validated raster image references and text; silently omit other media parts, including their text keys, and never serialize unknown dicts. If there are ONLY non-image media/unknown structured parts and no raster, use stripped placeholders and text-only admission (stage=collect reason=unsupported_media). Mixed valid raster + non-image media retains valid raster, excludes non-image media without forcing downgrade.',
 'idempotency':'For normalized list N: _strip_media_from_messages(N)==N; repeated normalization yields byte-identical rendered prompt. Placeholder strings are ordinary safe strings: never wrapped/replaced/appended again.',
 'nonempty':'Each image/media-only message retains its [image omitted]/[media omitted] marker; never becomes empty and never causes generated Reply with exactly: PONG. Truly empty/non-media requests retain existing behavior.',
 'ctx_contract':'Always store ctx["stripped_full_prompt"]=_messages_to_stripped_prompt(original messages). ctx["universal_fallback"] is admission snapshot. For any actual downgrade assign BOTH ctx["prompt"] and ctx["full_prompt"] from stripped_full_prompt, ctx["images"]=[], ctx["img_dir"]=None. Never recompute from original _messages_to_prompt(messages,[]) during downgrade.',
 'resumed_contract':'If any current or historical media was stripped, force cold text turn with full stripped history; do not resume dirty explicit or cached CID. This conservative choice is owner-permitted. Normal universal with valid raster may still use existing resumed slice numbering; stripped_full_prompt was computed from the full original history before selecting that slice.',
 'strict_isolation':'When universal=False continue existing collector/render paths exactly, including existing strict truncated PNG and same-files retry assertions; new normalizer does not redefine strict inputs.'
})

decision(3,'Three Safe Downgrade Points','Where exactly does fallback override strict early exits and retry branches?',
 'Central bounded media-to-text state transition at admission, post-slot/spool, and runtime attempt1, before both legacy retry paths. Keep all response and resource ownership invariants.',
 ['REQ-02','REQ-03','INV-05','INV-06','INV-07','INV-08','INV-09','INV-11'],
 ['Only generic transient retry: rejected, misses timeouts, hot early continue, flag and spool failures.','Always replay same image attachments on failure: rejected by owner text-only fallback contract.'],
 ['Exactly at most2 CLI executions/request; degradation reserve is request-scoped and unavailable to generic retries.','Failures after client delivery, client_gone and state done never trigger this fallback.','External side effects can occur before delivery; no exactly-once promise.'],
 ['VER-003','VER-005','VER-009','VER-010'],{
 'point1_collect':{'when':'do_POST after normal auth/body/model/effort validation, before slot, spool or response','logic':['Capture universal flag. Detect structured media throughout history using AD002. Precompute stripped_full_prompt.','universal and media and input_disabled -> log stage=collect reason=flag_disabled, images=[], img_dir=None, use stripped full history as prompt/full_prompt, prohibit resume.','universal and input_enabled -> _collect_images(...,universal=True); any ImageReject -> log stage=collect reason=rejected.reason, code sanitized separately if logged, images=[], img_dir=None; both prompts stripped; prohibit resume; no image-derived HTTP400.','Non-image media without raster -> use markers and pure text as AD002; mixed valid raster/media -> optimistic raster only.','strict -> retain exact existing exception->400 path, reason taxonomy and normal legacy render.','No valid images means do not allocate/spool img_dir. Any preallocated path is only metadata and never passed to Run.']},
 'point2_post_slot':{'when':'_run_once after acquire, before register/mkdir/stage/Run','logic':['If images and universal snapshot true: recheck _is_image_input_enabled ONLY; do not perform strict proof/SHA check. If False, log post_slot/flag_disabled and execute downgrade transition; continue attempt1 as text.','If !universal keep _image_gate recheck and existing image_reject terminal state exactly.','Register only the own actual img_dir under _active_lock before mkdir. _stage_images exception ImageSpoolError in universal -> log spool/image_spool_error; cleanup partial dir and registry, img_registered=False, img_dir=None; downgrade both prompts/CID/images; proceed attempt1 text with add_dir=None.','Strict spool failure remains image_spool_error500/no spawn. No broad catch of programming errors as media fallback.']},
 'downgrade_transition_order':['Close any completed Run before deleting files (existing finally run.close). Snapshot old image count, old CID and session key for sanitized event and own CAS invalidation.','Call _cleanup_img_dir(own img_dir) if non-null; unregister under _active_lock using existing helper. Clear local img_dir and images, img_registered=False; ctx images=[], img_dir=None. Cleanup helper is idempotent; no cleanup of another request directory.','For any nonempty old/resume/explicit CID: if sess_key exists, _session_invalidate(sess_key,old_cid) (compare-and-swap); always _cid_release(old_cid,str(ctx.get("turn_id") or "")) for own claim. Set ctx.hot_resumed=False, ctx.conversation_id="" and any local resume_conv_id=None. Plain turns with sess_key=None never mutate session store.','The brief conv_id=str(uuid.uuid4()) means allocate a fresh logical conversation if implementation has such local; this HEAD has none. Contract is zero old --resume CID and Run conversation_id="" so CLI creates NEW conversation, not pass a fabricated resume ID.','Set both ctx.prompt and ctx.full_prompt to ctx.stripped_full_prompt. Keep model/effort/cwd/tool protocol and acquired slot; subsequent Run.add_dir=None.','Commit only successful new text session under existing ownership rules; CAS cannot remove a concurrently replaced store value. Outer do_POST ownership cleanup remains idempotent for already released old CID.'],
 'point3_runtime':{'placement':'Immediately after attempt1 _execute returns and run.close() completes, before hot_resumed early continue (baseline3280..3295) AND before transient/_retry_take branch (3297..3310). Existing done break may precede guard because guard excludes done.',
 'guard':'attempt==1 AND ctx.universal_fallback AND bool(images) AND img_dir is not None (actually attached Run) AND out.state not in (done,client_gone) AND NOT delivered',
 'delivery':'delivered_reasoning=bool(out.get("delivered_reasoning")) OR bool(ctx.get("stream") and out.get("reasoning")); delivered=bool(out.get("text")) OR bool(out.get("tool_calls")) OR delivered_reasoning. No delivered_reasoning field exists in this HEAD; do not accidentally ignore already emitted SSE reasoning. JSON buffered reasoning alone is not delivered. Empty role delta/keepalive is not delivery.',
 'actions':['Emit runtime/state sanitized event exactly once, count BEFORE clearing images.','Execute full downgrade transition including immediate cleanup and full history reset before text constructor.','Call _retry_take() exactly once; consume one token if available. If unavailable, consume the one per-request media-degradation reserve; do not decrement global balance below0, replenish global bucket, loop, or fail this text retry.','Always sleep pause=_rng()*RETRY_PAUSE_CAP_S (equivalent to _retry_pause_s(1)); then continue into attempt2, add_dir=None, images=[], no old CID.','No third attempt; failed second text run preserves normal JSON/SSE error. No fallback for state done even nonzero rc/empty text (RISK03), client_gone or any delivered output.']},
 'reserve_budget':{'capacity':'1 fallback token per request ONLY after eligible image-attached attempt1; never reusable and never generic.','maximum':'generic+reserve still <=1 retry per request because fixed (1,2) loop. Slot retained across pause/retry; active CLI <=MAX_CONCURRENT (default4), body admission remains unchanged.','owner_override':'Owner explicitly requires degradation even when _retry_tenths<RETRY_COST_TENTHS. Therefore generic formula floor(.2*N)+3 is preserved for strict/generic-only traffic, but NOT claimed for universal fallback traffic. Total retries <= min(N, floor(.2*N)+3 + N_media_degradation_reserve). Worst all-image-fail batch reaches2N attempts; RISK08 quota and capacity must be measured before production acceptance.'},
 'exclusions':'LauncherUnavailable preflight, constructor OSError before a real attached _execute, auth/framing/invalid model/invalid effort/admission/queue failures remain existing errors; do not synthesize successful text result or emit second HTTP headers. No general Exception catch or transport refactor in this patch.',
 'error_semantics':'200 means real text completion success. Failed text retry -> existing502/504/etc JSON or SSE error event+DONE. SSE initial200 alone never proves success. Keep legacy _error_body mapping for done/bad rc/empty text, missing executable, and queue overload.',
 'lifecycle':'Cleanup of img_dir/partial spool before downgrade; outer finally releases slot exactly once. If physical deletion fails, report safe cleanup error and NEVER reattach or falsely assert deletion; existing orphan sweep remains recovery. Cancellation/client_gone skips all retries and closes Run/resources.'
})

decision(4,'Observability & Discoverability','How to report optimistic support while keeping strict health/models types and proofs intact?',
 'Preserve existing boolean images fields; effective supports=universal&&input_enabled for all catalog models, otherwise strict predicate. Add a separate structured image_fallback object, never replace health.images with a dict.',
 ['REQ-01','REQ-04','REQ-05','CON-05','INV-10','AC-08'],
 ['Rewrite fleet proofs as confirmed: rejected by ao10 and evidence semantics.','Replace /health.images bool with dict: rejected by actual code/test_ao01 type semantics.'],
 ['Optimistic acceptance is distinguished from historical proof.','No fleet.json or old _model_supports_images strict semantics changes.','No auth/payload/prompt/path leakage in new events.'],
 ['VER-003','VER-006','VER-008','VER-009','VER-010'],{
 'as_is_checks':{'test_ao01':'With universal false, /v1/models data.images true ONLY gemini-4-argon and gemini-3.8-flash under _ImgEnv; aggregate images is True; health.images is True identity assertion.','test_ao06_health':'test_ao06_health_has_four_additive_fields_and_keeps_existing_ones at line2764 checks presence of old health keys and sqlite reasoning fields; does not license changing images type.','test_ao10':'Static fleet binary/version/default limits/proofs and text-only unsupported entries unchanged byte-for-byte.'},
 'effective_predicate':'At GET request start read universal,input once. If universal=True, effective_images(mid)=input_enabled and mid in FLEET_MODELS. If universal=False, effective_images(mid)=_model_supports_images(mid) exactly as now. _model_supports_images itself remains strict so no proof consumers silently change.',
 'models':'Each data row retains id/object/owned_by/created/context_length/images boolean. Universal+input true => every catalog data.images=True, top-level images=any(effective flags). Add top-level image_fallback object for both policy states; never relabel static images.status/proof as confirmed.',
 'health':'Keep health["images"] boolean any(effective support) and existing image_input_mode string/sqlite fields. Add health["image_fallback"]={"fallback_enabled":bool,"input_enabled":bool,"mode":"universal"|"strict","acceptance":"optimistic"|"proof-gated"|"text-only","method":"workspace-read","limits":copy of IMAGE_LIMITS,"models":[effective supported catalog IDs]}. Same object on /v1/models. acceptance=text-only iff universal and input disabled, otherwise optimistic iff universal, else proof-gated. Brief suggestion health["images"]["fallback_enabled"] is inapplicable to actual bool schema.',
 'log_contract':{'event':'image_fallback','template':'image_fallback stage=%s reason=%s model=%s attempt=%d images=%d','stages':['collect','post_slot','spool','runtime'],'attempts':'collect/post_slot/spool =>1 upcoming attempt; runtime=>1 failed attached attempt','reason':'flag_disabled; ImageReject.reason; image_spool_error; unsupported_media; runtime state token','sanitizer':'Introduce _log_token(value,max_len=64): only ASCII identifier chars A-Za-z0-9_.- survive, all others _, length capped64; empty->unknown. Stage from finite allowlist, model validated catalog, reason/state sanitized. Counts coerced bounded integers; code if extra uses same sanitizer.','sink':'HEAD uses _log(str) -> stderr + _mask_secrets; no log.info object exists. Preserve native sink and emit exact formatted event via _log helper (semantically INFO), no new logger dependency. If log.info introduced locally, it MUST route through same masking/sink; no requirement to rewire logging.','never':['auth keys','base64 payload','URLs','prompts','file paths','raw exception repr'],'frequency':'Exactly one event per actual downgrade transition, no fallback event for strict path/pure-text or simply omitted audio beside valid raster. Strict reject/proof logs unchanged.'}
})

decision(5,'Test Suite Append-Only Architecture uf01..uf10','How to prove new policy and retry contracts without weakening strict coverage?',
 'Append UniversalImageFallbackTests at EOF, retaining entire baseline file bytes. Use import discovery, true raster fixtures and local flag patches; freeze assertion, execution and full suite commands independently.',
 ['REQ-04','AC-01','AC-02','SCN-uf01','SCN-uf10','SCN-B01','SCN-B02','SCN-R01','SCN-R02','SCN-I01'],
 ['Edit legacy _ImgEnv/_Fixture/tests to expect universal behavior: rejected, changes frozen strict baseline.','AST ID presence only: rejected, not evidence of behavior execution.'],
 ['Existing __main__ guard remains; direct python tests/file.py would miss appended classes, so VER003/005 use import/discovery.','No suite-wide environment override enables universal.','Red regressions before product fix, then green full legacy+universal execution; future tests are not executed or claimed Stage2.'],
 ['VER-001','VER-002','VER-003','VER-004','VER-005','VER-006','VER-007','VER-008'],{
 'prefix':{'path':TEST,'bytes':len(base_test),'sha256':prefix_hash,'deleted_lines_allowed':0,'preserve':'Entire BASE blob is a prefix; additions strictly after byte249933. This includes all old tests/helpers/__main__, stronger than a diff numstat check.'},
 'new_class':'UniversalImageFallbackTests(unittest.TestCase)',
 'test_methods':[
 {'name':'test_uf01_all_catalog_models_and_efforts_optimistic','scenarios':['SCN-uf01','SCN-B01'],'assertions':'Every catalog model x declared effort, true raster PNG/JPEG/GIF/WebP fixture; runtime proof/SHA/status/efforts_proven corrupted or absent without startup schema violation; no strict gate invocation, attachment/files/add-dir attempt1 and real successful JSON/SSE. Catalog negatives remain ingress errors.'},
 {'name':'test_uf02_image_rejections_strip_all_media','scenarios':['SCN-uf02','SCN-B01','SCN-B02'],'assertions':'Whole taxonomy incl malformed alias/dict content, MIME/base64/magic/roles/16vs17/size cap±1, mixed invalid+valid image; one stripped run/no partial staging/no fetch; media failure no400; auth/JSON/body413/model/effort/admission503 retain errors.'},
 {'name':'test_uf03_policy_matrix_recheck_and_cache','scenarios':['SCN-uf03'],'assertions':'Four policy states, missing/false/malformed/string/int/null/oversize config; env token map, TTL boundary, reset; input flip while queued strips before mkdir/Run, SHA flip ignored universal; rollback/re-enable without restart and slots restored.'},
 {'name':'test_uf04_spool_failures_downgrade_before_attempt1','scenarios':['SCN-uf04','SCN-R02'],'assertions':'mkdir/EACCES/ENOSPC/second-file/O_EXCL errors, registry and actual partial cleanup; one text constructor, no attach; unsafe permissions never broaden; cleanup-error branch accurately logged and not reattached.'},
 {'name':'test_uf05_runtime_retry_cold_text_with_empty_budget','scenarios':['SCN-uf05','SCN-R01'],'assertions':'Each eligible agy/pump/timeout/idle/first-token state with zero/30 tenths; two runs only, immediate file cleanup before second constructor, add_dir=None, both prompts stripped, jitter invoked and tokens consumed only if available. Second failure truthful, done excluded, no third.'},
 {'name':'test_uf06_hot_and_explicit_cid_cold_reset','scenarios':['SCN-uf06','SCN-R02'],'assertions':'Three-turn tools history, early hot agy_error must hit media guard before hot continue; CAS invalidate matching CID only, release(cid,turn_id), no resume on retry; postslot/spool/collect also cold after media removal; next history turn works.'},
 {'name':'test_uf07_media_normalization_is_complete','scenarios':['SCN-uf07','SCN-I01'],'assertions':'All specified media types+keys incl snake_case and video_url, dict and list content, media.text taint, unknown dict not serialized; mixed raster/audio optimistic retains raster only; media-only placeholders nonempty; original input unchanged.'},
 {'name':'test_uf08_delivery_and_non_media_failures_do_not_replay','scenarios':['SCN-uf08'],'assertions':'Delivered text/tool_calls/SSE reasoning/client_gone ->one run cleanup; JSON buffered reasoning/empty SSE delta allow guarded retry; done badrc/empty output no image retry; missing launcher/OSError no double headers/fake success.'},
 {'name':'test_uf09_full_history_idempotency_and_reentry','scenarios':['SCN-uf09','SCN-I01'],'assertions':'Normalization fixed point, exact role/text/Unicode/order/ordinary URL preservation, old images/latest-image-only/no-assistant/history hot↔cold, both prompts no generated attachments/imageN/base64. Next request re-evaluates policy, no permanent deny.'},
 {'name':'test_uf10_observability_isolation_and_lifecycle','scenarios':['SCN-uf10','SCN-R01','SCN-R02'],'assertions':'strict→universal→strict and reverse; bool capabilities+additive policy fields and no fake fleet proof; safe logs counts/stages/no secrets; two simultaneous distinct requests, same-key CAS replacement, active sweep, cancellation/repeated fallbacks restore slots/dirs/FD/children. Production receipt only release VER010, no unit claim.'}],
 'fixture_policy':'New helpers/classes are appended ONLY; use _ImgEnv then write BOTH config keys because env.flag rewrites file. Context-managed env patch/new cache reset restores state. No process-wide fallback env in test execution. Use actual small decodable raster corpus embedded as fixtures; no Pillow/new dependency; existing magic-only strict fixtures unchanged.',
 'counts':'Baseline146 methods total,46 image-related (36 Image*+10 AcceptanceOracleTests), inherited VER007 IDs40 because duplicate log01 and5 f-methods are not represented by those40. Preserve all146 methods and execute full project suite.',
 'boundaries':'Use small patched caps for individual/total boundary corpus, but real HTTP body/admission boundary tests remain; no gratuitous16x20MiB allocation.',
 'red_green':'Coder first appends regression tests and records failing universal assertions against BASE, then fixes server only. Existing tests may not be edited for lint/type/format convenience.'
})

# Structured trace and ancillary views.
map_req={1:['VER-003','VER-007','VER-009','VER-010'],2:['VER-003','VER-005','VER-009','VER-010'],3:['VER-003','VER-005','VER-009','VER-010'],4:['VER-001','VER-002','VER-003','VER-004','VER-005','VER-006','VER-007','VER-008'],5:['VER-003','VER-008','VER-010'],6:['VER-003','VER-007','VER-009','VER-010']}
for i,x in enumerate(requirements,1):x['verification_ids']=map_req[i]
for i,x in enumerate(contracts,1):x.update({'decision_ids':{1:['AD-003'],2:['AD-001','AD-002'],3:['AD-003'],4:['AD-001'],5:['AD-004'],6:['AD-003']}[i],'verification_ids':['VER-003','VER-010']})
for i,x in enumerate(invariants,1):x.update({'decision_ids':{1:['AD-001'],2:['AD-002'],3:['AD-002','AD-003'],4:['AD-002','AD-003'],5:['AD-003'],6:['AD-003'],7:['AD-003'],8:['AD-003'],9:['AD-003'],10:['AD-004'],11:['AD-003'],12:['AD-001','AD-003']}[i],'verification_ids':['VER-003','VER-009']})
for x in acceptance:x['verification_ids']={'AC-01':['VER-006'],'AC-02':['VER-003','VER-005','VER-007'],'AC-03':['VER-003'],'AC-04':['VER-003','VER-009'],'AC-05':['VER-003'],'AC-06':['VER-010'],'AC-07':['VER-003'],'AC-08':['VER-003','VER-010']}[x['id']]
for x in scenarios:x['verification_ids']=['VER-003']+(['VER-010'] if x['id'] in {'SCN-uf06','SCN-uf10','SCN-R01','SCN-R02'} else [])

risk_defs=[
 ('RISK-01','Backend/native-tool side effects may precede failure even without client delivery.','Bounded one text retry; no exactly-once claim; delivered tool/text/reasoning forbids retry; live safe read-only failure oracle; do not run destructive duplicate tool action.',['VER-003','VER-010']),
 ('RISK-02','Text retry/backend/auth/queue can still fail despite media-safe admission.','Only successful real text completion returns200; preserve actual JSON/SSE failures and no double headers.',['VER-003','VER-005']),
 ('RISK-03','done badrc/empty output and constructor exceptions do not match owner runtime guard.','Exclude done and pre-execute constructor errors; preserve mapping and one header response; test explicitly uf08.',['VER-003']),
 ('RISK-04','Pixel decoder can break magic-only strict fixtures or admit decompression bombs.','No new pixel decoder; signature and byte safety unchanged; real decodable positive corpus does not assert arbitrary pixel validity.',['VER-003','VER-006']),
 ('RISK-05','Flag cache leaks fixture/policy state or hot CID survives stripping.','Independent cache reset; consistent universal snapshot, input recheck, env contexts, full stripped prompts and owner-safe CID reset.',['VER-003','VER-009']),
 ('RISK-06','Checkout, deployed runtime and config diverge.','Pair hash readback, actual deployed ROOT booleans; controlled code restart then dynamic rollback and same-owner live receipt.',['VER-008','VER-010']),
 ('RISK-07','Universal mode accidentally bypasses body/connection/admission safety.','Ingress auth/framing/model/effort/body limits run before media fallback unchanged; whole-request strip never means unlimited parsing/fetching.',['VER-003','VER-005','VER-009']),
 ('RISK-08','No measured quota/RPS/p99/memory/CPU/FD budget, plus reserve allows up to2N CLI executions.','Record all46 HL fields with UNKNOWN facts; no capacity PASS; require release resource measurement and owner quota/SLA before production acceptance. Do not claim generic retry bound for universal reserve.',['VER-003','VER-010'])]
for i,(source,scenario,mit,checks) in enumerate(risk_defs,1):P['risks'].append({'id':f'RISK-{i:03d}','source_id':source,'scenario':scenario,'probability':'medium','impact':'high','mitigation':mit,'verification_ids':checks})
P['assumptions']=[
 {'id':'ASM-001','source_id':'ASSUMP-01','class':'continuable','status':'ASSUMED','statement':'Owner200 requirement is media-safe admission plus a real text attempt, not guaranteed backend availability. Successful text gives200; independent protocol/admission/launcher/second failure remain truthful errors. User direct guard excludes done/client_gone.','evidence_ids':['EVD-100'],'verification_ids':['VER-003','VER-010']},
 {'id':'ASM-002','source_id':'ASSUMP-02','class':'continuable','status':'ASSUMED','statement':'Valid decodable raster describes positive test corpus. Universal safety retains signature-only validation and no pixel decoder/dependency; this is not a proof that every signature-bearing file decodes safely.','evidence_ids':['EVD-100'],'verification_ids':['VER-003','VER-006']}]

quality=[('reliability','media validation, spool or attached CLI fails','local fake and existing owner DSH chat','do_POST/_run_once','clean downgrade and real text attempt','eligible runtime exactly2 runs; pre-stage exactly1 text run; never add-dir on downgrade',['VER-003','VER-010']),('compatibility','fallback policy absent or false','same process strict/universal ordering','strict image path and fleet','preserve all legacy behavior','146 baseline tests remain,46 image tests pass,0 deleted lines and exact249933byte prefix',['VER-003','VER-005','VER-006','VER-008']),('privacy','malicious media.text/url/inline payload reaches renderer/log','all history mixed types/dict content','normalizer/log sink','classify before text, bounded sanitize tokens','0 structured media payload/paths/URLs in generated fallback context or fallback logs; preserve ordinary user text',['VER-003','VER-009']),('operability','enable or rollback policy','production deployed ROOT','flags/health/models','JSON TTL and effective explicit observability','TTL<=1s next check, strict bool health, all catalog images true iff universal+input; no restart for flags',['VER-003','VER-010']),('testability','future fix weakens legacy coverage','independent clean-room candidate','frozen suite and scope','assertions plus actual execution','40+10 ID AST assertion coverage plus full execution, unchanged fleet/five inputs',['VER-003','VER-006','VER-007','VER-008']),('performance','batch image failures exhaust generic retry budget','4 default active CLI slots,32 admitted connections; effective runtime limits not measured','reserve and slot lifecycle','one bounded media retry; no new pool or third attempt','<=2 executions/request, unchanged active cap; CPU/RSS/FD/p99 measurement REQUIRED, no invented numeric load pass',['VER-003','VER-010'])]
for i,(q,stim,env,artifact,response,measure,checks) in enumerate(quality,1):P['quality_scenarios'].append({'id':f'QA-{i:03d}','quality':q,'source':'DSH client / release owner','stimulus':stim,'environment':env,'artifact':artifact,'response':response,'response_measure':measure,'verification_ids':checks})

boundaries=[('Ingress policy','Authenticate/frame/validate body and catalog effort before universal media handling',['existing HTTPHandler','FLEET_MODELS','bounded body admission'],['image gate may not waive auth/model/effort/body/slot rules']),('Media normalization/collection','Classify safely, enforce raster byte limits and build two prompt forms',['AD002 private normalized copies','existing byte validator'],['network/file payload reads','str(media dict)','changing caller payload']),('Spool lifecycle','Register own directory after slot, secure permissions, immediate cleanup on downgrade',['existing _stage_images/_cleanup_img_dir','_active_lock'],['pre-slot writes','foreign directory cleanup','add-dir on text retry']),('Retry/session controller','Close Run, guard delivery, reset CID via CAS, bounded reserve',['existing Run','_session_invalidate','_cid_release(cid,turn_id)','_retry_take'],['third attempt','resume old explicit CID after stripping','invalidating concurrently replaced session']),('Observability/config','Expose effective optimistic support while preserving proof evidence',['bounded local JSON','existing masked _log sink','strict boolean API fields'],['fleet mutation','logging content/paths/auth','confusing optimistic eligibility with proof']),('Verification/release','Enforce frozen independent tests and paired deployed evidence',['VER001..010','external3family architecture/code councils'],['Coder editing verification contract','Stage2 production write/acceptance claim'])]
for i,(component,responsibility,allowed,forbidden) in enumerate(boundaries,1):P['boundaries'].append({'id':f'BND-{i:03d}','component':component,'responsibility':responsibility,'allowed_dependencies':allowed,'forbidden_dependencies':forbidden,'verification_ids':['VER-003','VER-008'] if i<6 else ['VER-006','VER-007','VER-010']})
for i,(typ,producer,consumer,change,compat,checks) in enumerate([
 ('behavior','agy do_POST','DSH','With universal=true media failures strip to text instead of strict image400/spool500; eligible image attempt failure gets one text retry.','Explicitly requested REQ01..03; flag absent/false exactly old behavior.',['VER-003','VER-005']),
 ('api','GET /v1/models and /health','DSH capability consumers','Existing images booleans use effective optimistic eligibility in universal+input; additive image_fallback object.','Keep bool schema and all old fields; strict expected model set unchanged, fleet proof untouched.',['VER-003','VER-008','VER-010']),
 ('data','deployed local dynamic_config.json','agy runtime flags','Add strict boolean IMAGE_FALLBACK_ENABLED with independent env/TTL/defaultfalse.','Owner explicit local JSON override; old config without key strict; no tracked config/new dependency.',['VER-003','VER-010'])],1):P['contract_deltas'].append({'id':f'CD-{i:03d}','type':typ,'producer':producer,'consumer':consumer,'change':change,'compatibility':compat,'verification_ids':checks})
P['views']=[{'id':'VIEW-001','type':'dynamic','question':'Where are the three downgrade points and what survives attempt2?','artifact_ref':'architecture/architecture-packet.json#/runtime_view'}, {'id':'VIEW-002','type':'dfd','question':'Which trust boundary prevents payload leakage/fetch and filesystem cross-request deletion?','artifact_ref':'architecture/architecture-packet.json#/threat_model'},{'id':'VIEW-003','type':'deployment','question':'Why is checkout config not production activation?','artifact_ref':'architecture/architecture-packet.json#/evolution'}]
P['runtime_view']={'flow':['HTTP validation -> capture universal/input -> full stripped prompt','collect: disabled/invalid -> media-free cold text; valid raster -> optimistic image metadata','slot acquired -> input recheck -> register/stage; flag/spool failure -> cleanup/CID reset -> text attempt1','Run(image attempt1) -> close -> done/client_gone/delivered stop','eligible undelivered failure -> runtime guard BEFORE hot/transient -> log/cleanup/CAS+claim release/prompts stripped','budget token OR one request reserve -> jitter -> Run(text attempt2,add_dir=None,no old --resume)','success new CID commit or truthful failure -> slot release exactly once -> JSON completion/SSE terminal'],'no_transport_rewrite':True}
P['threat_model']={'required':True,'assets':['auth key','user text/media base64','private file paths','other requests CID/slot/spool','backend capacity'],'trust_boundaries':['untrusted structured content -> validated local raster bytes','private spool -> CLI add-dir sandbox','one request/session owner -> shared registry/session map','private request -> structured stderr logs','checkout -> deployed runtime'], 'threats':[]}
for i,(scenario,mit,checks) in enumerate([
 ('SSRF/local file exfil via image URL, inline object or media.text','Never fetch URL; bounded dataURL raster validation; image/media classification before text; unknown structured payload never str(dict).',['VER-003','VER-009']),
 ('Secret/base64/path disclosure through fallback log or full_prompt','Safe identifiers only, preserve masked native log sink; both prompts replaced with precomputed stripped full history.',['VER-003','VER-009']),
 ('Cross-request CID/dir deletion or retained dirty resume','Private directory identity, owner-safe _cid_release(cid,turn_id), CAS matching invalidation; no plain store writes; concurrency/sweep interleaving tests.',['VER-003','VER-010']),
 ('Resource exhaustion through invalid images and unlimited fallbacks','Same max16/20MiB/body/admission caps, no pre-slot spool, two attempts maximum, reserve single-use; release profile cannot be waived by local suite.',['VER-003','VER-005','VER-010'])],1):P['threat_model']['threats'].append({'id':f'THREAT-{i:03d}','scenario':scenario,'mitigation':mit,'verification_ids':checks})
P['pre_mortem']=['If hot agy_error branch runs first, retry retains attachments: uf06 and runtime ordering evidence are mandatory.','If only ctx.prompt changed, full_prompt reintroduces old media: uf05/06/09 inspect BOTH prompts before next Run.','If generic bucket exhausted, fallback silently omitted: uf05 tests0tenths with one reserve and jitter.','If health.images becomes dict, strict ao01 identity breaks: keep boolean and add image_fallback object.','If normalization checks text first, media.text leaks: all media forms include tainted text in uf07.','If new config enabled globally in test environment, strict suite changes behavior: process runner unsets new env and every new fixture restores scoped state.']
P['evolution']={
 'compatibility':'No storage/schema migration. universal flag absent/false preserves strict gates, proofs, retries and error semantics; bool API images fields retained; no changes fleet/default constants. Explicitly requested behavior activates only when flagtrue.',
 'migration':'No persisted data migration; runtime server is a separate regular file from checkout. Deployed JSON is untracked, update only specified booleans preserving unrelated keys. Existing dirty image CIDs are invalidated only on their own downgrade; no blanket store wipe.',
 'rollout':'Stage2 author packet -> mechanical gate -> EXTERNAL3-family ARCH_PANEL proof -> Coder append regressions+server fix -> independent VER001..009/full suite -> external code council ACCEPT -> managed runtime server deployment/restart -> both flags true -> VER010 evidence in EXISTING owner DSH conversation. Stage2 does none of deployment/flags/live acceptance.',
 'rollback':'Set IMAGE_FALLBACK_ENABLED=false in deployed JSON or immediate envfalse; TTL<=1s next evaluation; preserve IMAGE_INPUT_ENABLED as deliberate strict staging choice. Captured in-flight policy completes its bounded path, not retroactively mutated. If rollback code, restore backed-up server and verify fleet pair via managed restart. Config-only rollback needs no restart.',
 'mixed_versions':'Old server ignores unknown fallback key and remains strict; new server missing key remains strict. Do not advertise activation solely from JSON or health; deployed hash + real request evidence required. Env override must be accounted for independently.'}
P['reuse_brief']={'reference':['analysis/agy-image-input-fix/','evidence-ledger F109/F117/F202/F313/F314/F315','existing _collect_images/_stage_images/_cleanup_img_dir/_session_invalidate/_cid_release and _ImgEnv fake HTTP corpus'], 'KEEP':['body and slot admission','size-before-decode','secure staging/active registry/sweep','cwd/argv','strict gate/proof and same-files retry','delivery guard','native JSON/SSE protocol','whole baseline tests'], 'CHANGE':['independent policy','safe normalization','three targeted downgrade transitions','one bounded media reserve','effective observability','explicit deployed activation'], 'BLOCKER':'Literal old flow requires400/spool500 and retains images on retry; sibling text-first placeholder renderer is unsafe for media.text/dict-content. Adapt existing machinery; do not build a new transport.'}

# All 46 inherited envelope fields: known values are caps/defaults, never measured load.
fields={}
for m in re.finditer(r'^- ([^:]+): (.+)$',ha,re.M):
 if m[1] in {'P_steady','P_hpa_max','maxSurge_pct','maxSurge_abs','maxUnavailable_pct','maxUnavailable_abs','P_terminating_overlap','P_live','P_avail_min','W','N_proc','N_proc_steady','N_proc_avail_min','CPU_limit_per_pod','κ_skew','u_bg_worker','U_pod_sidecars','Mem_limit_per_pod','Mem_rss_worker_max','Mem_shared_max','RPS_peak','A_max','SLA_p99_s','N_entities_max','Limit_dep_share[d]','Limit_dep_rps[d]','W_fetchers[d]','J_init_s[d]','J_pod_s[d]','T_poll_s[d]','K_calls[d]','T_base_s[d]','T_cap_s[d]','Max_stale_age_s[c]','Min_healthy_ratio','B_retry_max','min_reserve_retry_rps','FD_worker','ulimit_n','λ_new_conn_per_pod(s)','C_active_in_scope(s)','N_pods_in_scope(s)','Port_range_size(s)','T_hold_s(s)','SNAT_ips_count(s)','HOTPATH_MODULES'}:
  fields[m[1]]={'value_status':'KNOWN_DEFAULT_OR_CAP' if m[1] in {'A_max','N_entities_max','T_base_s[d]','T_cap_s[d]','Max_stale_age_s[c]','B_retry_max','HOTPATH_MODULES'} else 'UNKNOWN_OR_PARTIAL','source':'analysis/agy-universal-image-fallback/handoff-architect.md#HL-ENV','statement':m[2]}
assert len(fields)==46,len(fields)
fields['W']['statement']='UNKNOWN effective OS worker process count; Stage1 reports MAX_CONCURRENT=4 execution slots, which is NOT proc/pod W. Do not substitute slots for process multiplicity.'
fields['A_max']['design_value']=2
fields['Max_stale_age_s[c]']['design_value_s']={'image_input':1.0,'image_fallback':1.0}
fields['min_reserve_retry_rps']['statement']='No timed global replenishment introduced. New reserve is1 per eligible request, not a fabricated measured req/s. Distinguish generic strict .2/request budget from universal reserve amplification.'
stop_codes=['HL-ENV-01']+[f'{g}-I{i}' for g in ['C-MULT','S-HERD','H-CPU','R-BULK'] for i in range(1,6)]
P['resource_envelope']={'schema':'HL-ENV/v1','fields':fields,'status':'BLOCKED_UNMEASURED_PRODUCTION','memory_closure':'W*Mem_rss_worker_max+Mem_shared_max<=0.80*Mem_limit_per_pod UNPROVEN: missing effective process and private/shared RSS/quota. Body caps are not RSS proof; include queued encoded copies and both original/stripped prompts.', 'no_na_claim':'No N/A waiver based on small diff or missing k8s. Local threaded HTTP+CLI topology is distinct; no pod/quota values invented. Future candidate transitive caller/callee graph and actual diff required before declaring N/A.', 'stop_codes':[{'id':c,'status':'NOT_PROVEN','acceptance_ref':'~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md#7.2','verification_ids':['VER-003','VER-010']} for c in stop_codes], 'additional_gates':{'T-LIFE/v1':'own Run close, registry cleanup,slot/CID ownership tests and live scenario required','O-EXIT/v1':'keep one done/terminal response per request, new fallback event does not replace existing done','M-SEM/v1':'model/effort/cwd session isolation and never bypass ingress catalog/auth'}, 'explicit_owner_override':'Owner mandates one media degradation attempt despite empty generic bucket; genericR-BULK-I2 inequality NOT asserted for universal requests. All remaining capacity/latency/FD claims remain unproven; no council or author may label them measured PASS.', 'failure_matrix':[
 {'dependency':'local config read','path':'control/request TTL','timeout':'bounded file max existing DYNAMIC_CONFIG_MAX_BYTES; no network','bulkhead':'per-flag cache lock','failure':'fail-closed fallback flag ->strict; input flagoff in universal ->text-only'},
 {'dependency':'spool FS','path':'hot/post-slot','timeout':'existing local FS behavior; no new unsupported hard deadline claim','bulkhead':'same execution slot, no new pool','failure':'typed ImageSpoolError->strip/CID reset/text; strict500 unchanged'},
 {'dependency':'agy CLI/upstream','path':'hot','timeout':'existing queue900s/execution1800s/firstevent120s defaults; NOT SLA','bulkhead':'MAX_CONCURRENT default4, bounded body admission32; effective values release evidence required','failure':'eligible attempt1->1text retry; delivery/client_gone/done exclusions; second failure truthful; no new global breaker or routing architecture'},
 {'dependency':'log sink','path':'hot transition','timeout':'existing synchronous stderr, not measured nonblocking latency','bulkhead':'existing _log','failure':'sanitize exact fields, no content; no fabricated dropped_total/async telemetry architecture'}], 'production_acceptance_blockers':['Measured quota/RPS/p99 and parent+child RSS/CPU/FD/ports closure with preserved admitted-body bounds','Disposition of inherited queue-waiter/deadline constraints vs live SLA, without pretending local tests satisfy highload gates','Reserve worst-case2N amplification safe for actual owner workload','21 deterministic HL/C-MULT/S-HERD/H-CPU/R-BULK oracle evidence or validated transitive non-applicability; none issued Stage2']}
P['handoff_state']={'next_role':'Parent orchestrator: independent architecture panel, not Coder yet','architecture_authoring':'FINALIZED','external_arch_panel':'NOT_RUN','product_implementation':'NOT_STARTED','production_activation':'NOT_APPLIED','live_acceptance':'NOT_RUN','capacity_acceptance':'BLOCKED_UNMEASURED_PRODUCTION','warning':'Mechanical schema/fingerprint PASS is not council ACCEPT or proof that unresolved capacity gates pass. Do not start Coder without valid external architecture panel proof; do not promote to production without resource/live gates.'}
P['owner_questions']=['ASSUMP-01/02 are continuable explicit assumptions: real successful text200, no fabricated backend success; decodable positive corpus with signature-only validation. No answer required to finish this design.','For production capacity acceptance supply measured/contractual p99 SLA, peak workload and upstream quotas; missing facts remain blocking release evidence, not invented numbers.']
P['tooling_deviations']=['Requested skill and validator locations omit universal/; actual files found via skill INDEX and read from canonical universal paths.','Actual role validator uses positional PLAN --phase before|after; before-fingerprint argument unsupported. Supplied plans/architect-01.before.json is worktree schema2.0, not a role plan; retained immutable; separate initial role plan provided.','Actual arch validator needs --packet,--run-dir,--role-plan,--repo-root,--fingerprint-before,--fingerprint-after,--task,--receipt; prints PASS: ARCH_GATE rather than ARCH_GATE_VALID. No wrapper/verifier-output spoof created.','Supplied fingerprint includes .ai-team/runs artifacts and concurrent log writes. Original retained; derive product projection by excluding ONLY .ai-team/runs/** from ORIGINAL manifest, recomputing digest, comparing current identically scoped snapshot. No fresh/rebased baseline.','Existing health.images bool and _cid_release(cid,turn_id) override inaccurate proposed shapes/signature; all external behavior design remains as requested.','Actual test baseline is6008lines; entire blob is immutable, not guessed6009 line count.']

plan=json.loads((RUN/'plans/architect-01.initial.json').read_text())
for s in plan['steps']:
 s['status']='DONE'
 s['actual_evidence']={'RP-01':'Read all5 Stage1 inputs; retained F-* lineage and frozen SHA256; directly checked health bool/CID owner signature/Run fresh semantics/validator CLI; no broad re-discovery.','RP-02':'AP AD001..005 contains four-state matrix, complete type/key normalization, three ordered downgrade transitions, exact delivery predicate/reserve/CID cleanup and all REQ/CON/INV/RISK/ASSUMP/AC/SCN lineage.','RP-03':'Ten concrete VER001..010 frozen; VER006 both zero-deleted baselines+whole prefix+strict execution; VER00740+10 asserted IDs, VER003 full new+legacy execution and VER005 full repository suite; live gate evidence still required.','RP-04':'Only authorized run-artifacts generated with linked plan SHA; baseline projection verified unchanged before writing. External validator result receipts are produced after generation and are not preclaimed here.'}[s['id']]
plan['deviations']=P['tooling_deviations']+['All product/test execution is downstream; Stage2 runs validators/fingerprint only. Resource/live PASS and panel votes are not fabricated.']
dump('plans/architect-01.json',plan)
P['role_plan']={'path':'plans/architect-01.json','sha256':sha((RUN/'plans/architect-01.json').read_bytes())}
dump('architecture/architecture-packet.json',P)
packet_hash=sha((RUN/'architecture/architecture-packet.json').read_bytes())
dump('teamlead/verification-surface.json',{'architecture_packet_sha256':packet_hash,'verifications':ver,'live_gate_note':'VER010 checks presence/readback only; Teamlead independently executes/inspects real same-owner DSH chat evidence. No receipt or resource PASS exists at Stage2.'})
task_path=RUN/'task.json'
task=json.loads(task_path.read_text()) if task_path.exists() else {'schema_version':'1.2','task_id':P['task_id'],'run_id':RUN.name,'criticality':'S2','repo_root':str(ROOT),'branch':P['baseline']['branch'],'base_commit':BASE,'entry':'full','scope':'Stage2 architecture only; no product/test/runtime writes'}
task['architecture_gate']={'packet_sha256':packet_hash,'verification_surface_sha256':canonical(ver),'protected_paths_sha256':canonical(P['protected_paths']),'allowed_files':[SERVER,TEST],'forbidden_paths':[FLEET,'analysis/**','bridges/*/dynamic_config.json','bridges/agy-bridge/start.sh','core/**','server.py','tests/test_images_strict.py','pyproject.toml','uv.lock','requirements*.txt','.github/**'],'contract_hash':canonical({'requirements':requirements,'contracts':contracts,'invariants':invariants,'decisions':P['decisions'],'acceptance_criteria':acceptance,'test_scenarios':scenarios}),'verification_surface_ref':'teamlead/verification-surface.json','contract_hash_algorithm':'sha256 canonical JSON UTF8 ensure_ascii=False sort_keys=True separators=(comma,colon) over packet keys requirements,source_contracts as contracts,invariants,decisions,acceptance_criteria,test_scenarios','panel_pass_required_before_coder':True,'stage2_product_fingerprint_baseline_ref':'fingerprints/architect-before.product.json','original_fingerprint_ref':'fingerprints/architect-before.json'}
dump('task.json',task)
print('GENERATED',packet_hash,'VER',len(ver),'REQ',len(requirements),'CON',len(contracts),'INV',len(invariants),'AC',len(acceptance),'SCN',len(scenarios),'HL_FIELDS',len(fields))
