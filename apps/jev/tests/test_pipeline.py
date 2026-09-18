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
