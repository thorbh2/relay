"""Tests for RELAY (direct runner). AI verify_milestone() validated live on studionet."""
from pathlib import Path
import json

CONTRACT = str(Path(__file__).resolve().parents[1] / "contracts" / "relay.py")
GEN = 10 ** 18

C_FUNDING = 0; C_FUNDED = 1; C_COMPLETED = 2; C_FAILED = 3
M_LOCKED = 0; M_SUBMITTED = 1

MS = json.dumps([
    {"desc": "Ship the MVP web app", "amount": 4 * GEN},
    {"desc": "Reach 100 active users", "amount": 6 * GEN},
])


def _open(r, vm, who, title="Build an open-source tool", summary="A useful public tool", ms=MS):
    vm.sender = who
    return r.open_campaign(title, summary, ms)


def test_open_campaign(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    cid = _open(r, direct_vm, direct_alice)
    assert cid == 0
    c = r.get_campaign(0)
    assert c["status"] == C_FUNDING
    assert int(c["goal"]) == 10 * GEN
    assert c["ms_total"] == 2
    assert int(r.get_milestone(0, 0)["amount"]) == 4 * GEN


def test_open_requires_title(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("a title is required"):
        r.open_campaign("", "summary", MS)


def test_open_rejects_bad_json(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("milestones must be valid JSON"):
        r.open_campaign("t", "s", "not json{")


def test_open_requires_a_milestone(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("at least one milestone"):
        r.open_campaign("t", "s", "[]")


def test_pledge_accumulates(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 3 * GEN
    r.pledge(0)
    direct_vm.value = 0
    c = r.get_campaign(0)
    assert int(c["raised"]) == 3 * GEN
    assert c["status"] == C_FUNDING


def test_pledge_reaching_goal_funds(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * GEN
    r.pledge(0)
    direct_vm.value = 0
    assert r.get_campaign(0)["status"] == C_FUNDED


def test_pledge_requires_value(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 0
    with direct_vm.expect_revert("pledge some GEN"):
        r.pledge(0)


def test_submit_requires_funded(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("campaign is not funded"):
        r.submit_milestone(0, "https://proof.dev")


def test_submit_only_creator(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * GEN
    r.pledge(0)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("only the creator can submit"):
        r.submit_milestone(0, "https://proof.dev")


def test_submit_then_state(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * GEN
    r.pledge(0)
    direct_vm.value = 0
    direct_vm.sender = direct_alice
    r.submit_milestone(0, "https://github.com/me/mvp")
    m = r.get_milestone(0, 0)
    assert m["status"] == M_SUBMITTED
    assert m["proof_url"] == "https://github.com/me/mvp"


def test_refund_only_after_fail(deploy, direct_vm, direct_alice, direct_bob):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice)
    direct_vm.sender = direct_bob
    direct_vm.value = 10 * GEN
    r.pledge(0)
    direct_vm.value = 0
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("refunds only after a campaign fails"):
        r.refund(0)


def test_multiple_campaigns(deploy, direct_vm, direct_alice):
    r = deploy(CONTRACT)
    _open(r, direct_vm, direct_alice, title="Campaign A")
    _open(r, direct_vm, direct_alice, title="Campaign B")
    assert r.get_campaign_count() == 2
    assert r.get_campaign(1)["title"] == "Campaign B"
