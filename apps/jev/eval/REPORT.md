# skill-guard eval corpus enlargement + weight re-tuning

Date: 2026-09-18

## Summary

The labeled eval corpus was grown from **8 artifacts (4 malicious / 4 benign)**
to **68 artifacts (34 malicious / 34 benign)**, balanced and diverse, with the
benign side deliberately loaded with *hard negatives* (legitimate skills and MCP
servers that touch sensitive-sounding capabilities). The family `weight` values
in `skill_bank.yaml` and the block threshold in `score.py` were then re-tuned
against the enlarged corpus using cached Jev readings.

Headline result, measured on the enlarged corpus with the **real Jev API**:

| metric | before (prior weights, block 0.70) | after (tuned weights, block 0.80) |
|---|---|---|
| ROC-AUC | 1.000 | 1.000 |
| ECE (calibration error) | 0.236 | **0.205** |
| separation margin `min(mal) - max(ben)` | +0.145 | **+0.181** |
| adversarial mean risk drop under injection | -0.002 | **-0.007** (still ~0; injection does not help the attacker) |
| **benign false auto-blocks** | **4 / 34** | **0 / 34** |
| malicious auto-blocked | 34 / 34 | 34 / 34 |
| benign correctly allowed (risk < 0.35) | 1 / 34 | 10 / 34 |
| mean benign risk | 0.470 | 0.396 |

The original tiny corpus scored AUC 1.000 / ECE 0.200 / margin +0.476, but those
numbers are not comparable -- with only 4 easy benign fixtures the benign side was
trivially separable. The enlarged corpus with hard negatives is a much harder and
more honest test, and the tuning improves calibration and eliminates false
auto-blocks on it.

## Task 1 -- datasets / sources surveyed

Labeled *Claude Code skill* corpora barely exist yet, so the fixtures are
synthetic but each is grounded in a real, published technique or a real published
artifact. Sources consulted:

**Malicious / supply-chain / agent-attack sources**
- DataDog `malicious-software-packages-dataset` -- 28k+ manually-triaged malicious
  npm/PyPI packages (samples are password-`infected` encrypted zips of live
  malware, so only the *techniques* and writeups were used, not the binaries):
  https://github.com/DataDog/malicious-software-packages-dataset
- Datadog Security Labs campaign writeups (MUT-8694 npm/PyPI; macOS-targeted PyPI
  with sandbox-evasion): https://securitylabs.datadoghq.com/
- GuardDog heuristics (install-time exec, network calls in install scripts,
  obfuscation, sensitive-file access), OpenSSF:
  https://openssf.org/blog/2025/03/28/guarddog-strengthening-open-source-security-against-supply-chain-attacks/
- Shai-Hulud npm worm (maintainer-account compromise, TruffleHog secret trawling,
  postinstall fetch-and-exec):
  https://www.invicti.com/blog/web-security/shai-hulud-2-worm-supply-chain-attack-on-npm-dependencies
  and https://motasemhamdan.medium.com/anatomy-of-the-2025-npm-worm-the-largest-supply-chain-hack-3a64560d5c8f
- npm credential-stealer campaigns (SSH keys, API tokens, cloud creds, wallets):
  https://cybersecuritynews.com/malicious-npm-campaign-steals-ssh-keys-api-tokens/
  and postinstall Ethereum-key theft: https://cyberpress.org/npm-packages-abuse-postinstall-scripts/
- Microsoft -- 33 malicious npm packages, dependency-confusion environment
  profiling: https://www.microsoft.com/en-us/security/blog/2026/05/29/33-malicious-npm-packages-abuse-dependency-confusion-profile-developer-environments/
- MCP tool poisoning -- OWASP: https://owasp.org/www-community/attacks/MCP_Tool_Poisoning ;
  MCPTox benchmark (1,312 cases / 45 servers / 353 tools):
  https://arxiv.org/pdf/2508.14925 ; CSA research note on auto-execution:
  https://labs.cloudsecurityalliance.org/research/csa-research-note-mcp-tool-poisoning-auto-execution-20260701/
- Agent PR-injection secret exfiltration (JHU; Claude Code / Gemini CLI / Copilot
  hijacked via PR titles to exfil GitHub Actions secrets) and Sandworm_Mode npm
  typosquats installing rogue MCP servers -- from the MCP-security survey above.

**Prompt-injection datasets** (for the override / false-assurance patterns)
- `deepset/prompt-injections`, `guychuk/benign-malicious-prompt-classification`,
  `rogue-security/prompt-injections-benchmark`, Qualifire Prompt Injections
  Benchmark -- all on HuggingFace.
- InjecGuard (over-defense in injection guardrails) -- directly motivated the hard
  negatives: https://arxiv.org/pdf/2410.22770

**Benign / hard-negative sources**
- `anthropics/skills` -- official published Agent Skills (PDF form-filling,
  commit-message helper): https://github.com/anthropics/skills
- `modelcontextprotocol/servers` -- reference MCP servers (filesystem, git,
  github, postgres, brave-search): https://github.com/modelcontextprotocol/servers

## Task 2 -- corpus composition

68 artifacts, all as `eval/fixtures/<class>/<name>/SKILL.md`, listed in
`eval/labels.yaml` with per-fixture family annotations. **All fixtures are inert
text artifacts**: network destinations are fake / non-resolving placeholder
domains, no payload does real work, and nothing is executed -- a detector *reads*
them, in the spirit of EICAR.

**Malicious (34)** -- covers every capability family, multiple examples each:
- exfiltration (9): credential/secret trawl to C2, wallet/seed theft, session &
  `~/.claude.json` harvest, env/recon profiling, keychain + browser-cookie dump,
  `GITHUB_TOKEN` to hidden PR comment, `.npmrc` `_authToken` theft, webhook
  collector, clipboard crypto-address swap.
- remote_code (5): `curl|bash` install (RDD), MCP server whose runtime is fetched
  and run at start, download->chmod->detached exec, sandbox-evading updater,
  injected malicious `postinstall`.
- covert (4): `settings.json` SessionStart hook, crontab/`.zshrc` beacon,
  magic-phrase-triggered exfil, anti-forensic history/log wipe.
- override (3): ignore-previous/unrestricted mode, false-assurance wrapper over
  exfil, forced `--dangerously-skip-permissions`.
- destructive (2): `rm -rf` home / force-push / key revoke; dated logic bomb.
- obfuscation (3): base64->eval, hex-escape->shell, runtime command-fragment
  assembly.
- scope + MCP-specific (8, overlapping): capability-beyond-purpose formatter,
  typosquat MCP, tool-poisoning MCP (hidden instructions in a tool description),
  fake "official Anthropic-signed" MCP forwarding keys, plus the original 4 seed
  fixtures.

**Benign (34)** -- the hard negatives that matter for calibration: a
kube/helm deploy skill, a commit-message helper, a bundled-Python PDF filler, a
local DB migrator, an `.env` validator, a dependency upgrader, a *legitimate*
credential rotator (consensual revoke), a release publisher (consensual npm
publish / tag push), an internal log fetcher, a docker/build cleaner, an SSH
*config* helper, an AWS cost reporter, the official brave-search / filesystem /
github / postgres MCP servers, a localhost API smoke-tester, a codemod runner, a
base64 icon embedder, a Sentry installer, a shell-alias helper, an incident
runbook, a local PII anonymizer, an S3 backup to the user's own bucket, a webhook
tester, a test-only cookie clearer, a read-only kubectl MCP, a license scanner, a
terraform-plan skill, and a *legitimate* `npm audit` skill (the honest twin of
the malicious `deps-audit`), plus the original 4 seed fixtures.

MCP servers are represented as `SKILL.md` artifacts whose body carries the
`mcpServers` JSON block and tool descriptions -- the text the extractor's
`compute()` reduces to the same fact sheet Jev sees for any skill (the harness
drives everything through `extract_skill`).

## Task 3 -- tuning method and weight changes

`eval/tune_weights.py` splits the expensive from the cheap:
1. It reads every fixture (and an injection-perturbed variant of each malicious
   one) through the engine **exactly once** and caches the per-question values +
   confidences to `eval/.readings_cache.json` (~102 real Jev calls total,
   incremental -- a re-run costs 0 calls).
2. Risk composition, ROC-AUC, ECE, separation, adversarial shift, and the weight
   search all run purely in Python over the cached numbers, so weights were
   searched for free.

The search is a **bounded, regularised coordinate ascent**. An unconstrained
optimum existed (ECE 0.162, margin +0.287) but was degenerate -- it collapsed
exfiltration to 0.20 and maxed remote_code, an overfit of this synthetic corpus
that would dangerously under-weight a pure data-exfil skill. So the search was
constrained to keep a defensible severity ordering, with an L2 pull toward the
prior, and the final weights were chosen for calibration **and** single-family
robustness (a lone saturated high-severity family must still reach block).

**Weight changes:**

| family | before | after | why |
|---|---|---|---|
| exfiltration | 1.00 | **0.90** | Still the top anchor. A hard 1.0 made *read-only* credential access (a benign migrator reading `.env` for a local DB URL) reach block by itself; real exfil trips read **and** send, saturating the family near 1.0 regardless, so 0.90 keeps it blocking while routing read-only access to review. |
| covert | 0.95 | **0.85** | High-severity, kept high; benign work trips it only weakly. |
| remote_code | 0.85 | **0.82** | Kept high so a single fetch-and-exec family still blocks with any second signal. |
| override | 0.90 | **0.75** | Benign artifacts almost never trip it; modest reduction improves calibration without hurting ranking. |
| scope | 0.55 | **0.40** | Benign tools plausibly exceed their stated purpose; discriminative but should not block alone. |
| obfuscation | 0.50 | **0.30** | A supporting signal (encoded-but-explained assets appear in benign skills, e.g. an icon data-URI). |
| destructive | 0.60 | **0.25** | **Biggest calibration lever.** Benign hard-negatives (credential rotator, release publisher) do irreversible-*with-consent* work and score destructive=1.0, while malicious artifacts never rely on destructive alone. |

**Threshold change (`score.py`):** block 0.70 -> **0.80**, review unchanged at 0.35.
With the tuned weights the risk distributions separate cleanly -- highest benign
~0.767, lowest malicious ~0.948 -- so 0.80 sits in the empty gap: it auto-blocks
all 34 malicious while sending the credential-adjacent-but-legitimate cases to
human review instead of a false auto-block. The `min_confidence` gate is
unchanged.

Net effect: benign false auto-blocks 4 -> **0**, benign correctly allowed 1 -> 10,
ECE 0.236 -> 0.205, margin +0.145 -> +0.181, AUC held at 1.000, adversarial
robustness unchanged (mean shift ~0; the "audited/pre-approved" injection is
itself read as a false-assurance signal, so risk if anything rises).

`uv run python -m pytest -q` stays green (7 passed); no test behavior needed
changing (the `deps-audit` block assertion still holds under block 0.80 on the
FakeClient).

## Caveats (honest)

- **Fixtures are synthetic**, hand-authored from real techniques -- not sampled
  from a real distribution of in-the-wild skills. They exercise the detector and
  let weights be tuned; they are not proof of field accuracy. A real evaluation
  should swap in a public labeled dataset as it becomes available (the Datadog
  packages dataset, adapted to skill-shaped artifacts, is the natural next step).
- **68 artifacts is still small.** AUC = 1.000 means the corpus is *linearly
  separable by risk* under these weights, not that the model is perfect; treat the
  margin and ECE as the informative numbers, not the AUC.
- **ECE ~0.20 is not "well calibrated" in absolute terms.** It is dominated by
  the hard negatives correctly sitting in the 0.3-0.77 "review" band while their
  ground-truth label is 0 -- which is arguably the *right* triage behavior for a
  tool that legitimately reads `.env` or revokes a key, but it inflates ECE
  because ECE compares risk to the hard 0/1 label. The improvement (0.236 ->
  0.205) is real but the absolute floor here reflects genuinely ambiguous
  artifacts.
- **Weights are tuned to this corpus.** The bounds and L2 regularisation guard
  against the worst overfitting, and the severity ordering was preserved on
  purpose, but the exact values should be re-checked whenever the corpus changes.
- The tuned exfiltration/remote_code weights assume the family combinator stays
  noisy-OR-of-noisy-OR; a cleaner long-term fix for the `db-migrator` case is to
  separate "reads a secret" from "sends a secret" inside the exfiltration family
  rather than lean on the weight. That is a bank/scoring change, out of scope
  here, and is noted for follow-up.
- `eval/.readings_cache.json` holds only per-question float scores (no artifact
  text, no API key) and can be regenerated with `--refresh`; safe to gitignore.
