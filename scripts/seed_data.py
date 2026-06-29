"""Seed RELAY with real on-chain data on studionet."""
from pathlib import Path
import json

from gltest_cli.config.general import get_general_config
from gltest_cli.config.user import load_user_config
from gltest import get_contract_factory, get_default_account

ROOT = Path(__file__).resolve().parents[1]
ADDR = "0xdbc9B73ed74796b302aDcb5e196d470d86656720"
GEN = 10 ** 18

cfg = load_user_config(str(ROOT / "gltest.config.yaml"))
get_general_config().user_config = cfg

c = get_contract_factory(contract_file_path=str(ROOT / "contracts" / "relay.py")).build_contract(
    ADDR, account=get_default_account()
)

MILESTONES = json.dumps([
    {"desc": "Publish a public project page live on the web", "amount": 4 * GEN},
    {"desc": "Ship the open-source explorer repo with a README and demo", "amount": 6 * GEN},
])


def main():
    if c.get_campaign_count().call() == 0:
        cid = c.open_campaign(args=["Open-source GenLayer explorer",
                                    "A free, open block explorer for GenLayer studionet so anyone can inspect intelligent-contract activity.",
                                    MILESTONES]).transact()
        print("campaign opened")
    else:
        print("campaign already present")

    cam = c.get_campaign(args=[0]).call()
    print("status after open:", cam["status"], "goal:", cam["goal"])

    # pledge to reach the goal (10 GEN) -> FUNDED
    if int(cam["raised"]) < int(cam["goal"]):
        c.pledge(args=[0]).transact(value=10 * GEN)
        print("pledged 10 GEN")

    cam = c.get_campaign(args=[0]).call()
    print("status after pledge:", cam["status"])

    # submit + verify milestone 0 (real AI reads the proof)
    m0 = c.get_milestone(args=[0, 0]).call()
    if int(m0["status"]) == 0 and int(cam["status"]) == 1:
        c.submit_milestone(args=[0, "https://example.com"]).transact()
        print("milestone 0 submitted")
    m0 = c.get_milestone(args=[0, 0]).call()
    if int(m0["status"]) == 1:
        print("verifying milestone 0 (AI)...")
        c.verify_milestone(args=[0]).transact()
        print("milestone 0 verified")

    cam = c.get_campaign(args=[0]).call()
    m0 = c.get_milestone(args=[0, 0]).call()
    print("FINAL campaign status:", cam["status"], "raised:", cam["raised"], "released:", cam["released"])
    print("milestone0 status:", m0["status"], "| reason:", (m0["rationale"] or "")[:90])


if __name__ == "__main__":
    main()
