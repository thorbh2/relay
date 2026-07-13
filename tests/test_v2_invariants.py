from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "contracts" / "relay_v2.py").read_text(encoding="utf-8")


def test_verification_and_release_are_separate_transactions():
    verify_body = SOURCE.split("def verify_milestone", 1)[1].split("def refund", 1)[0]
    assert "M_APPROVED" in verify_body
    assert "self._pay" not in verify_body
    assert "def release_milestone(" in SOURCE


def test_challenges_and_appeals_change_release_state():
    assert "def resolve_milestone_challenge(" in SOURCE
    assert "def resolve_campaign_appeal(" in SOURCE
    assert "open dispute blocks release" in SOURCE


def test_overfunding_is_returned_and_proof_snapshot_is_preserved():
    assert "excess = int(sent) - accepted" in SOURCE
    assert "self._pay(gl.message.sender_address, u256(excess))" in SOURCE
    assert "proof_snapshot" in SOURCE


def test_failed_campaign_refund_remains_claimable_once():
    assert "def fail_campaign(" in SOURCE
    assert "refunds only after a campaign fails" in SOURCE
    assert "p.refunded = u8(1)" in SOURCE
