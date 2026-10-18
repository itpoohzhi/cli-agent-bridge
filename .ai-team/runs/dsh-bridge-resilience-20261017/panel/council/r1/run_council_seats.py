import os, sys, subprocess, time

round_dir = "/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/panel/council/r1"
artifact_path = "/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/code-review-package.md"
launch_seat = "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/launch_seat.py"

seats = [
    (1, "gemini-4-argon-high", "agy", f"{round_dir}/brief-k1.md"),
    (2, "muse-wonder-full-1.0", "muse", f"{round_dir}/brief-k2.md"),
    (3, "claude-sonnet-5-5-high", "claude-p", f"{round_dir}/brief-k3.md"),
]

procs = []
print(f"Starting all {len(seats)} seats in parallel...")
t0 = time.time()
for seat, slot, transport, brief in seats:
    cmd = [
        "python3", "-I", launch_seat,
        "--round-dir", round_dir,
        "--seat", str(seat),
        "--slot", slot,
        "--transport", transport,
        "--brief", brief,
        "--artifact-path", artifact_path,
    ]
    p = subprocess.Popen(cmd)
    procs.append((seat, slot, transport, p))
    print(f"Spawned seat {seat} ({slot} / {transport}), PID={p.pid}")

print("All seats spawned. Waiting for completion...")
failures = 0
for seat, slot, transport, p in procs:
    rc = p.wait()
    dt = time.time() - t0
    print(f"Seat {seat} ({slot} / {transport}) finished with RC={rc} after {dt:.1f}s")
    if rc != 0:
        failures += 1

print(f"All done! Total elapsed: {time.time()-t0:.1f}s, failures={failures}")
sys.exit(failures)
