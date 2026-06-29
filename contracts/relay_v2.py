# v0.2.16
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
    audits: DynArray[str]
    challenges: DynArray[str]
    appeals: DynArray[str]

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

    @gl.public.view
    def get_contract_stats(self) -> str:
        funding = 0
        funded = 0
        completed = 0
        failed = 0
        raised = 0
        released = 0
        submitted = 0
        released_ms = 0
        rejected_ms = 0
        i = 0
        while i < len(self.campaigns):
            c = self.campaigns[i]
            raised += int(c.raised)
            released += int(c.released)
            if int(c.status) == C_FUNDING:
                funding += 1
            elif int(c.status) == C_FUNDED:
                funded += 1
            elif int(c.status) == C_COMPLETED:
                completed += 1
            else:
                failed += 1
            i += 1
        j = 0
        while j < len(self.milestones):
            m = self.milestones[j]
            if int(m.status) == M_SUBMITTED:
                submitted += 1
            elif int(m.status) == M_RELEASED:
                released_ms += 1
            elif int(m.status) == M_REJECTED:
                rejected_ms += 1
            j += 1
        return json.dumps({"campaigns": len(self.campaigns), "milestones": len(self.milestones),
                           "pledges": len(self.pledges), "funding": funding, "funded": funded,
                           "completed": completed, "failed": failed, "submittedMilestones": submitted,
                           "releasedMilestones": released_ms, "rejectedMilestones": rejected_ms,
                           "raisedWei": str(raised), "releasedWei": str(released)}, sort_keys=True)

    @gl.public.view
    def get_quality_score(self) -> str:
        stats = json.loads(self.get_contract_stats())
        campaigns = int(stats.get("campaigns", 0))
        released = int(stats.get("releasedMilestones", 0))
        verified_ratio = 0 if campaigns == 0 else min(10000, released * 10000 // campaigns)
        score = min(10000, 5600 + verified_ratio // 2 + int(stats.get("pledges", 0)) * 100)
        return json.dumps({"qualityBps": score, "verifiedRatioBps": verified_ratio, "campaigns": campaigns}, sort_keys=True)

    @gl.public.view
    def get_frontend_bootstrap(self) -> str:
        return json.dumps({"contract": "Relay V2", "counts": json.loads(self.get_contract_stats()),
                           "quality": json.loads(self.get_quality_score())}, sort_keys=True)

    @gl.public.write
    def record_campaign_note(self, campaign_id: int, note: str, source_url: str) -> str:
        c = self._get_campaign(campaign_id)
        clean_note = note.strip()[:900]
        clean_url = self._clean_url(source_url)
        if len(clean_note) == 0:
            raise gl.vm.UserError("note is required")
        aid = self._append_audit("campaign_note", campaign_id, -1, gl.message.sender_address.as_hex, clean_note, clean_url,
                                 int(c.status), int(c.status))
        return aid

    @gl.public.write
    def file_milestone_challenge(self, campaign_id: int, index: int, claim: str, evidence_url: str) -> str:
        c = self._get_campaign(campaign_id)
        if index < 0 or index >= int(c.ms_total):
            raise gl.vm.UserError("no such milestone")
        m = self.milestones[int(c.ms_start) + index]
        clean_claim = claim.strip()[:1000]
        clean_url = self._clean_url(evidence_url)
        if len(clean_claim) == 0:
            raise gl.vm.UserError("challenge claim is required")
        cid = str(len(self.challenges))
        row = {"id": cid, "campaignId": campaign_id, "milestoneIndex": index,
               "filer": gl.message.sender_address.as_hex, "claim": clean_claim,
               "evidenceUrl": clean_url, "campaignStatus": int(c.status),
               "milestoneStatus": int(m.status), "ruling": "pending"}
        self.challenges.append(json.dumps(row, sort_keys=True))
        self._append_audit("file_challenge", campaign_id, index, gl.message.sender_address.as_hex,
                           clean_claim, clean_url, int(c.status), int(c.status))
        return cid

    @gl.public.write
    def file_campaign_appeal(self, campaign_id: int, reason: str, evidence_url: str) -> str:
        c = self._get_campaign(campaign_id)
        clean_reason = reason.strip()[:1000]
        clean_url = self._clean_url(evidence_url)
        if len(clean_reason) == 0:
            raise gl.vm.UserError("appeal reason is required")
        aid = str(len(self.appeals))
        row = {"id": aid, "campaignId": campaign_id, "filer": gl.message.sender_address.as_hex,
               "reason": clean_reason, "evidenceUrl": clean_url, "campaignStatus": int(c.status),
               "ruling": "pending"}
        self.appeals.append(json.dumps(row, sort_keys=True))
        self._append_audit("file_appeal", campaign_id, -1, gl.message.sender_address.as_hex,
                           clean_reason, clean_url, int(c.status), int(c.status))
        return aid

    @gl.public.view
    def get_audit_count(self) -> int:
        return len(self.audits)

    @gl.public.view
    def get_audit_log(self, campaign_id: int, limit: int) -> str:
        n = self._bounded(limit, 1, 50, 20)
        out = []
        i = len(self.audits) - 1
        while i >= 0 and len(out) < n:
            row = json.loads(self.audits[i])
            if int(row.get("campaignId", -1)) == campaign_id:
                out.append(row)
            i -= 1
        return json.dumps(out, sort_keys=True)

    @gl.public.view
    def get_challenges(self, campaign_id: int) -> str:
        out = []
        i = 0
        while i < len(self.challenges):
            row = json.loads(self.challenges[i])
            if int(row.get("campaignId", -1)) == campaign_id:
                out.append(row)
            i += 1
        return json.dumps(out, sort_keys=True)

    @gl.public.view
    def get_appeals(self, campaign_id: int) -> str:
        out = []
        i = 0
        while i < len(self.appeals):
            row = json.loads(self.appeals[i])
            if int(row.get("campaignId", -1)) == campaign_id:
                out.append(row)
            i += 1
        return json.dumps(out, sort_keys=True)

    @gl.public.view
    def get_backer_position(self, campaign_id: int, backer: Address) -> str:
        pledged = 0
        refunded = 0
        active_pledges = 0
        i = 0
        while i < len(self.pledges):
            p = self.pledges[i]
            if int(p.campaign_id) == campaign_id and p.backer == backer:
                pledged += int(p.amount)
                refunded += int(p.refunded)
                active_pledges += 1
            i += 1
        c = self._get_campaign(campaign_id)
        claimable = 0
        if int(c.status) == C_FAILED and int(c.raised) > 0:
            claimable = pledged * (int(c.raised) - int(c.released)) // int(c.raised)
        return json.dumps({"campaignId": campaign_id, "backer": backer.as_hex, "pledgedWei": str(pledged),
                           "pledgeCount": active_pledges, "refundedEntries": refunded,
                           "claimableRefundWei": str(claimable)}, sort_keys=True)

    @gl.public.view
    def get_campaign_digest(self, campaign_id: int) -> str:
        c = self._get_campaign(campaign_id)
        milestones = []
        i = 0
        while i < int(c.ms_total):
            m = self.milestones[int(c.ms_start) + i]
            milestones.append({"index": i, "description": m.description, "amount": str(m.amount),
                               "proofUrl": m.proof_url, "status": int(m.status), "rationale": m.rationale})
            i += 1
        return json.dumps({"campaign": self.get_campaign(campaign_id), "milestones": milestones,
                           "audits": json.loads(self.get_audit_log(campaign_id, 12)),
                           "challenges": json.loads(self.get_challenges(campaign_id)),
                           "appeals": json.loads(self.get_appeals(campaign_id))}, sort_keys=True)

    @gl.public.view
    def get_recent_campaigns(self, limit: int) -> str:
        n = self._bounded(limit, 1, 30, 10)
        out = []
        i = len(self.campaigns) - 1
        while i >= 0 and len(out) < n:
            c = self.campaigns[i]
            out.append({"id": i, "creator": c.creator.as_hex, "title": c.title,
                        "goal": str(c.goal), "raised": str(c.raised), "released": str(c.released),
                        "status": int(c.status), "milestones": int(c.ms_total), "done": int(c.ms_done)})
            i -= 1
        return json.dumps(out, sort_keys=True)

    @gl.public.view
    def get_protocol_overview(self) -> str:
        return json.dumps({"contract": "Relay V2", "domain": "milestone escrow crowdfunding",
                           "lifecycle": ["FUNDING", "FUNDED", "COMPLETED", "FAILED"],
                           "milestoneLifecycle": ["LOCKED", "SUBMITTED", "RELEASED", "REJECTED"],
                           "protections": ["escrowed pledges", "public proof URL", "GenLayer proof review",
                                           "refund path", "challenge filings", "appeal filings", "audit trail"],
                           "stats": json.loads(self.get_contract_stats())}, sort_keys=True)

    # -------------------------------------------------------------- internals
    def _get_campaign(self, campaign_id: int) -> Campaign:
        if campaign_id < 0 or campaign_id >= len(self.campaigns):
            raise gl.vm.UserError("no such campaign")
        return self.campaigns[campaign_id]

    def _append_audit(self, action: str, campaign_id: int, milestone_index: int, actor: str,
                      note: str, source_url: str, before_status: int, after_status: int) -> str:
        aid = str(len(self.audits))
        row = {"id": aid, "action": action, "campaignId": campaign_id, "milestoneIndex": milestone_index,
               "actor": actor, "note": note, "sourceUrl": source_url, "fromStatus": before_status,
               "toStatus": after_status}
        self.audits.append(json.dumps(row, sort_keys=True))
        return aid

    def _bounded(self, value: int, lo: int, hi: int, default: int) -> int:
        n = default
        try:
            n = int(value)
        except Exception:
            n = default
        if n < lo:
            n = lo
        if n > hi:
            n = hi
        return n

    def _clean_url(self, value: str) -> str:
        url = value.strip()[:620]
        low = url.lower()
        if not (low.startswith("https://") or low.startswith("http://")):
            raise gl.vm.UserError("invalid URL")
        if "localhost" in low or "127.0.0.1" in low or "0.0.0.0" in low or ".local" in low:
            raise gl.vm.UserError("private URL blocked")
        return url

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
