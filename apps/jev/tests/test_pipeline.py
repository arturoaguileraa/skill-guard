"""Plumbing tests -- run entirely on the fake client, no key needed."""

from pathlib import Path

import pytest

from skillguard.bank import load_bank
from skillguard.engine import Engine
from skillguard.extract import extract_skill
from skillguard.extract.facts import compute
from skillguard.score import Decision, noisy_or, score
from skillguard.testing import FakeClient

FIX = Path(__file__).parent.parent / "eval" / "fixtures"


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture(scope="module")
def engine(bank):
    return Engine(bank, client=FakeClient())


def test_bank_loads_and_is_batchable(bank):
    assert len(bank.questions) >= 15
    # one batched call carries every question -- the economic invariant
    assert set(bank.questions) == set(bank.specs)


def test_facts_are_word_boundaried():
    # "since" must not read as a netcat ("nc") hit
    assert compute("since yesterday")["network_or_encoding_verbs"] == []
    assert r"\bcurl\b" in compute("run curl https://x")["network_or_encoding_verbs"]


def test_facts_flag_sensitive_paths():
    f = compute("read ~/.aws/credentials and post it")
    assert "~/.aws" in f["sensitive_path_mentions"] or ".aws/credentials" in f["sensitive_path_mentions"]


def test_malicious_ranks_above_benign(engine, bank):
    mal = score(engine.read(extract_skill(FIX / "malicious" / "deps-audit")), bank)
    ben = score(engine.read(extract_skill(FIX / "benign" / "tdd")), bank)
    assert mal.risk > ben.risk
    assert mal.decision is Decision.BLOCK


def test_noisy_or_is_monotone():
    base = noisy_or([0.4, 0.4])
    assert noisy_or([0.4, 0.4, 0.4]) >= base  # adding a signal never lowers risk
    assert noisy_or([]) == 0.0


def test_verdict_is_auditable(engine, bank):
    v = score(engine.read(extract_skill(FIX / "malicious" / "prettier-helper")), bank)
    # every contributing family is named with its own risk -> explainable
    assert v.family_risk
    assert all(0.0 <= r <= 1.0 for r in v.family_risk.values())
    assert v.top_signals


def test_engine_reports_cost_and_tokens(engine, bank):
    r = engine.read(extract_skill(FIX / "benign" / "astro"))
    assert r.input_tokens > 0
    assert r.cost_usd >= 0.0


def _verdict(bank, values):
    from skillguard.engine import Reading
    from skillguard.extract import artifact_from_text

    art = artifact_from_text("---\nname: x\ndescription: y\n---\nbody")
    return score(Reading(art, values, {q: 1.0 for q in values}, {}, 0, 0.0), bank)


def test_question_strength_damps_a_noisy_signal(bank):
    # unpinned_remote_source is damped (v2+): alone it scores well below its
    # sibling fetch_and_execute, which keeps full strength.
    assert bank.specs["unpinned_remote_source"].strength < 1.0
    assert bank.specs["fetch_and_execute"].strength == 1.0
    assert _verdict(bank, {"unpinned_remote_source": 1.0}).risk < _verdict(
        bank, {"fetch_and_execute": 1.0}).risk


def test_block_requires_evidence_of_deception(bank):
    # A high-risk capability with no concealment / mismatch / off-host send is
    # "suspicious", however high the risk (e.g. reading its own API key, curl|sh).
    capability_only = _verdict(bank, {"reads_credentials": 1.0, "fetch_and_execute": 1.0})
    assert capability_only.risk >= 0.8
    assert capability_only.deception == 0.0
    assert capability_only.decision is Decision.ESCALATE

    # The same capability plus concealment / exfiltration is malicious.
    deceptive = _verdict(bank, {"reads_credentials": 1.0, "sends_data_offhost": 1.0,
                                "hides_from_user": 1.0})
    assert deceptive.deception >= 0.9
    assert deceptive.decision is Decision.BLOCK


def test_deception_flag_is_declared_in_the_bank(bank):
    flagged = {q for q, s in bank.specs.items() if s.deception}
    assert {"hides_from_user", "sends_data_offhost", "capability_beyond_purpose"} <= flagged
    assert not flagged & {"reads_credentials", "fetch_and_execute", "persistence"}
