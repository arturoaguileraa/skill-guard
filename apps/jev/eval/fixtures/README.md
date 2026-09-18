# Detector test fixtures

Synthetic artifacts used to measure SkillGuard. They are **inert test cases**,
in the spirit of the EICAR test file: every network destination is a reserved
example domain, no payload does real work, and each file carries the marker
`SKILLGUARD-FIXTURE`. They exist to exercise a detector, not to be run.

- `malicious/` — exhibits one attack pattern each, labeled by family.
- `hard_negative/` — **benign** artifacts that trip every keyword heuristic:
  they read credential files, run `curl`, and talk about exfiltration, but do so
  for legitimate, stated reasons. These are the fixtures that separate a real
  detector from a regex. A scanner that flags `hard_negative/` is unusable.
