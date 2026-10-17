Perform a fast pre-launch `brief-review` for Code Council round `panel/council/r1` in `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/panel/council/r1/`.
Verify:
1. `manifest.json` has 3 distinct model families (`claude-sonnet-5-5-high`, `gemini-4-argon-high`, `gpt-6.1-sol-high`), valid `artifact_path` and `artifact_sha256` (`45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed`).
2. `brief-k1.md`, `brief-k2.md`, `brief-k3.md` contain exact paths, the matching `artifact_sha256`, clear evaluation criteria, and no unredacted secrets.
Do NOT spawn subagents and do NOT modify files; just read `manifest.json` and `brief-k1.md` and output a short review ending with `VERDICT: READY`.
