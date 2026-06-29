# Relay V2

Milestone-gated crowdfunding escrow.

The repository includes the public app, deployment metadata and the GenLayer contract that links delivery evidence to release decisions.

## Relay Brief

Relay V2 (# v0.2.16), 21306 bytes, schema-valid milestone escrow contract with legacy open_campaign/pledge/submit_milestone/verify_milestone/refund compatibility, GenLayer web + LLM proof verification, audit-log views, challenge filings, appeal filings, backer position views, campaign digest, quality score and frontend bootstrap.

The important files are:

- `contracts/relay_v2.py` - GenLayer contract source
- `deployment.json` - Studionet address, deploy transaction and smoke transaction hashes
- `index.html` and `app.js` - static frontend
- `README.md` - this operator and reviewer guide

## Deployment Evidence

- Network: studionet (61999)
- Contract: [0xC2602425c2324f577754fdb17cae714Ce30b6Af5](https://explorer-studio.genlayer.com/contracts/0xC2602425c2324f577754fdb17cae714Ce30b6Af5)
- Deploy tx: [0x5b4c268e...0a89e7](https://explorer-studio.genlayer.com/tx/0x5b4c268e780fd7a8f1514f243e2d81457f554b3792d8ffd2444e11e3600a89e7)
- Deployed at: 2026-06-24T17:44:10.737Z
- Smoke writes recorded: 4

## Escrow Mechanics

Typical flow: `open_campaign` -> `submit_milestone` -> `file_milestone_challenge` -> `file_campaign_appeal` -> `pledge` -> `verify_milestone` -> `refund`

Useful reads: `get_campaign_count`, `get_campaign`, `get_milestone`, `get_contract_stats`, `get_quality_score`, `get_frontend_bootstrap`, `get_audit_count`, `get_audit_log`

- Primary source: `contracts/relay_v2.py` (21,306 bytes)
- Public write/action methods: 8
- Read methods: 14
- GenLayer features: LLM adjudication, append-only collections

## Smoke Trail

- open_campaign: [0xf49d6873...dc44aa](https://explorer-studio.genlayer.com/tx/0xf49d68735a3779d40b48266c1849308d5a42a37bc37fad65eb61982ac4dc44aa)
- pledge: [0x14aa9a67...da630c](https://explorer-studio.genlayer.com/tx/0x14aa9a6708cb39c7750a730dc77b16aeace539d3a4ab55c120c4302200da630c)
- submit_milestone: [0x901da77f...191973](https://explorer-studio.genlayer.com/tx/0x901da77f2645c2c17dabb14d03b035938e20862f1db5c345f2392d1a58191973)
- verify_milestone: [0x5e970956...deccdb](https://explorer-studio.genlayer.com/tx/0x5e970956cf397f57293b12534c7c6959e0310d9d671a1c9af23692d78fdeccdb)

## Inspect The App

```powershell
cd C:\Users\aspronim\Desktop\design-skills
npm run preview:start
npm run preview:project -- 12-relay
```

Open http://localhost:8080/12-relay/.

## Shipping Notes

```powershell
cd C:\Users\aspronim\Desktop\design-skills
npm run publish:project -- -Project 12-relay -Repo https://github.com/aspro45/<repo-name>.git
```

## Security Notes

- This repository should contain no decrypted wallet material.
- The Studionet deployer private key stays in the local encrypted vault.
- Vercel deployment should use the project folder only.

- QA notes: Fresh Relay redeploy replaced the earlier smaller V2. Contract keeps the existing crowdfunding frontend shape while adding audit/challenge/appeal/read surfaces. Private key remains encrypted vault-only.
