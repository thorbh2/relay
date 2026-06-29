# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
RELAY - Milestone-Gated Crowdfunding
====================================
A creator opens a campaign broken into milestones, each with its own tranche of
the goal. Backers pledge GEN, held in escrow by the contract. Once the goal is
met the campaign is funded - but money is NOT handed over in one lump. For each
milestone the creator submits a public proof URL; the contract reads it against
the milestone description and a validator set agrees (Equivalence Principle)
whether the milestone was genuinely delivered. Only then is that tranche
released. If a milestone fails verification the campaign fails and backers
reclaim their share of whatever has not yet been released. A Kickstarter that
cannot rug.

Campaign status:  FUNDING(0) -> FUNDED(1) -> COMPLETED(2) | FAILED(3)
Milestone status: LOCKED(0) -> SUBMITTED(1) -> RELEASED(2) | REJECTED(3)
"""

from genlayer import *
from dataclasses import dataclass
import json
import typing


C_FUNDING = 0
C_FUNDED = 1
C_COMPLETED = 2
C_FAILED = 3

M_LOCKED = 0
M_SUBMITTED = 1
M_RELEASED = 2
M_REJECTED = 3


@allow_storage
@dataclass
class Campaign:
    creator: Address
    title: str
    summary: str
    goal: u256
    raised: u256
    released: u256
    status: u8
    ms_start: u256
    ms_total: u256
    ms_done: u256


@allow_storage
@dataclass
class Milestone:
    campaign_id: u256
    description: str
    amount: u256
    proof_url: str
    status: u8
    rationale: str


@allow_storage
@dataclass
class Pledge:
    campaign_id: u256
    backer: Address
    amount: u256
    refunded: u8


class Relay(gl.Contract):
    campaigns: DynArray[Campaign]
    milestones: DynArray[Milestone]
    pledges: DynArray[Pledge]

    def __init__(self) -> None:
        pass

    @gl.public.write
    def open_campaign(self, title: str, summary: str, milestones_json: str) -> int:
        if len(title.strip()) == 0:
            raise gl.vm.UserError("a title is required")
        if len(summary.strip()) == 0:
            raise gl.vm.UserError("a summary is required")
        try:
            items = json.loads(milestones_json)
        except (ValueError, TypeError):
            raise gl.vm.UserError("milestones must be valid JSON")
        if not isinstance(items, list) or len(items) == 0:
            raise gl.vm.UserError("at least one milestone is required")
        if len(items) > 10:
            raise gl.vm.UserError("at most 10 milestones")

        cid = len(self.campaigns)
        ms_start = len(self.milestones)
        goal = 0
        for it in items:
            if not isinstance(it, dict):
                raise gl.vm.UserError("each milestone must be an object")
            desc = str(it.get("desc", "")).strip()
            amount = int(it.get("amount", 0))
            if len(desc) == 0:
                raise gl.vm.UserError("each milestone needs a description")
            if amount <= 0:
                raise gl.vm.UserError("each milestone needs a positive amount")
            m = self.milestones.append_new_get()
            m.campaign_id = u256(cid)
            m.description = desc
            m.amount = u256(amount)
            m.proof_url = ""
            m.status = u8(M_LOCKED)
            m.rationale = ""
            goal += amount

        c = self.campaigns.append_new_get()
        c.creator = gl.message.sender_address
        c.title = title
        c.summary = summary
        c.goal = u256(goal)
        c.raised = u256(0)
        c.released = u256(0)
        c.status = u8(C_FUNDING)
        c.ms_start = u256(ms_start)
        c.ms_total = u256(len(items))
        c.ms_done = u256(0)
        return cid

    @gl.public.write.payable
    def pledge(self, campaign_id: int) -> None:
        c = self._get_campaign(campaign_id)
        if c.status != C_FUNDING:
            raise gl.vm.UserError("campaign is not accepting pledges")
        v = gl.message.value
        if v == u256(0):
            raise gl.vm.UserError("pledge some GEN")
        c.raised = c.raised + v
        p = self.pledges.append_new_get()
        p.campaign_id = u256(campaign_id)
        p.backer = gl.message.sender_address
        p.amount = v
        p.refunded = u8(0)
        if c.raised >= c.goal:
            c.status = u8(C_FUNDED)

    @gl.public.write
    def submit_milestone(self, campaign_id: int, proof_url: str) -> None:
        c = self._get_campaign(campaign_id)
        if c.status != C_FUNDED:
            raise gl.vm.UserError("campaign is not funded")
        if gl.message.sender_address != c.creator:
            raise gl.vm.UserError("only the creator can submit")
        if len(proof_url.strip()) == 0:
            raise gl.vm.UserError("a proof URL is required")
        idx = int(c.ms_start) + int(c.ms_done)
        m = self.milestones[idx]
        if m.status != M_LOCKED:
            raise gl.vm.UserError("milestone not awaiting submission")
        m.proof_url = proof_url
        m.status = u8(M_SUBMITTED)

    @gl.public.write
    def verify_milestone(self, campaign_id: int) -> None:
        """Read the submitted proof against the milestone description; validators
        agree whether it was delivered. Pass -> release the tranche."""
        c = self._get_campaign(campaign_id)
        if c.status != C_FUNDED:
            raise gl.vm.UserError("campaign is not funded")
        idx = int(c.ms_start) + int(c.ms_done)
        m = self.milestones[idx]
        if m.status != M_SUBMITTED:
            raise gl.vm.UserError("no submitted milestone to verify")

        title = c.title
        desc = m.description
        url = m.proof_url

        def leader_fn() -> str:
            page = ""
            try:
                page = gl.nondet.web.get(url).body.decode("utf-8")[:6000]
            except Exception:
                page = "(proof page unreachable)"
            prompt = (
                f"Crowdfunding campaign: {title}\n"
                f"Milestone to verify: {desc}\n\n"
                f"Proof page content:\n{page}\n\n"
                "Does the proof page credibly show this specific milestone was "
                "actually delivered? Judge strictly on evidence in the page. Reply "
                'with ONLY JSON: {"delivered": true} if it clearly was, '
                '{"delivered": false} if not, plus a short "reason".'
            )
            return gl.nondet.exec_prompt(prompt)

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            return self._decision_of(leader_res.calldata)[0] == self._decision_of(leader_fn())[0]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        delivered, reason = self._decision_of(result)
        m.rationale = reason[:300]

        if delivered:
            m.status = u8(M_RELEASED)
            c.released = c.released + m.amount
            c.ms_done = u256(int(c.ms_done) + 1)
            self._pay(c.creator, m.amount)
            if int(c.ms_done) >= int(c.ms_total):
                c.status = u8(C_COMPLETED)
        else:
            m.status = u8(M_REJECTED)
            c.status = u8(C_FAILED)

    @gl.public.write
    def refund(self, campaign_id: int) -> None:
        """After a campaign fails, a backer reclaims their share of the funds that
        were never released."""
        c = self._get_campaign(campaign_id)
        if c.status != C_FAILED:
            raise gl.vm.UserError("refunds only after a campaign fails")
        raised = int(c.raised)
        remaining = raised - int(c.released)
        if remaining <= 0:
            raise gl.vm.UserError("nothing left to refund")
        sender = gl.message.sender_address
        owed = 0
        for i in range(len(self.pledges)):
            p = self.pledges[i]
            if int(p.campaign_id) == campaign_id and p.backer == sender and int(p.refunded) == 0:
                share = int(p.amount) * remaining // raised
                owed += share
                p.refunded = u8(1)
        if owed <= 0:
            raise gl.vm.UserError("no refundable pledge for you")
        self._pay(sender, u256(owed))

    # ------------------------------------------------------------------ views
    @gl.public.view
    def get_campaign_count(self) -> int:
        return len(self.campaigns)

    @gl.public.view
    def get_campaign(self, campaign_id: int) -> dict:
        c = self._get_campaign(campaign_id)
        return {
            "creator": c.creator.as_hex,
            "title": c.title,
            "summary": c.summary,
            "goal": str(c.goal),
            "raised": str(c.raised),
            "released": str(c.released),
            "status": int(c.status),
            "ms_total": int(c.ms_total),
            "ms_done": int(c.ms_done),
        }

    @gl.public.view
    def get_milestone(self, campaign_id: int, index: int) -> dict:
        c = self._get_campaign(campaign_id)
        if index < 0 or index >= int(c.ms_total):
            raise gl.vm.UserError("no such milestone")
        m = self.milestones[int(c.ms_start) + index]
        return {
            "description": m.description,
            "amount": str(m.amount),
            "proof_url": m.proof_url,
            "status": int(m.status),
            "rationale": m.rationale,
        }

    # -------------------------------------------------------------- internals
    def _get_campaign(self, campaign_id: int) -> Campaign:
        if campaign_id < 0 or campaign_id >= len(self.campaigns):
            raise gl.vm.UserError("no such campaign")
        return self.campaigns[campaign_id]

    def _decision_of(self, result: typing.Any) -> tuple:
        data = result
        if isinstance(data, str):
            data = self._extract_json(data)
        if not isinstance(data, dict):
            return (False, "")
        raw = data.get("delivered", None)
        reason = str(data.get("reason", ""))
        if isinstance(raw, bool):
            return (raw, reason)
        if isinstance(raw, str):
            return (raw.strip().lower() == "true", reason)
        return (False, reason)

    def _extract_json(self, text: str) -> typing.Any:
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except (ValueError, TypeError):
                return None
        return None

    def _pay(self, recipient: Address, amount: u256) -> None:
        if amount == u256(0):
            return
        _Payee(recipient).emit_transfer(value=amount)


@gl.evm.contract_interface
class _Payee:
    class View:
        pass

    class Write:
        pass
