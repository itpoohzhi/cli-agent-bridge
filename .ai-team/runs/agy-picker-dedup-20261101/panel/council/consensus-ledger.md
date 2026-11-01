# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: 171a1875f650cdc593ecdba1f3a5b3fc015691f7010673e5f3b0b7e34649c9ab

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=22724ddb4137e1ee verdict_sha256=a0018150d513ce9a10bffb3cbcf31550cca7cbc82006e7c3d72a0faf5cb78820
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=a81a0d76407cdf41 verdict_sha256=78b9ba7b695347573d4f014be072c360c1175f0ae37aa23ffc2ac7ad65d616b1
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=a16b03bfc39ed706 verdict_sha256=1bf6ca8ed3d7a8b9aecad642533e83acdaab87f4666d885e37155f983e364676

## Находки

### F-001
- priority: non-blocking
- status: ADOPTED
- debated: true
- text: SK-R1-001 / S3-R1-007: Рекомендация использовать pytest.importorskip('yaml') и автоматическую сверку обоих fleet.json в test_dsh_profile_config.py (зафиксировано в разделе Г итогового вердикта).

### F-002
- priority: non-blocking
- status: REJECTED
- debated: true
- text: SK-R1-002 / S3-R1-006: Дельта glm-5.3-flash-free в diff web/cordis.patch.yml внесена фоновым демоном opencode-zen-bridge под общим sync.lock после снятия бэкапа 23:40 MSK; сама дедупликация AGY/Claude атомарна (cas_post_sha256 зафиксирован).

### F-003
- priority: non-blocking
- status: REJECTED
- debated: true
- text: S3-R1-004 / S3-R1-005: Полный прогон 1732 тестов (9048 subtests) + воспроизведение 18 pre-existing падений на чистом HEAD b442c2e (task-1179.log) + clean-room прогон 6 модулей (225 passed, 134 subtests passed) и живые проверки RT-01..RT-08 полностью закрывают верификацию.
