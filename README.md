# Relay

Relay is a GenLayer milestone escrow protocol for campaigns, backer pledges, proof submission and AI-assisted milestone verification.

This repository is a public proof package: it includes the product UI, the deployed GenLayer Studionet contract source, deployment metadata, finalized smoke transactions, and test evidence. Local wallet secrets are not included.

## Live System

| Surface | Link |
| --- | --- |
| App | https://relay-zeta-blush.vercel.app |
| GitHub | https://github.com/thorbh2/relay |
| Contract | https://explorer-studio.genlayer.com/contracts/0xC2602425c2324f577754fdb17cae714Ce30b6Af5 |
| Deploy tx | https://explorer-studio.genlayer.com/tx/0x5b4c268e780fd7a8f1514f243e2d81457f554b3792d8ffd2444e11e3600a89e7 |
| Vercel inspect | https://vercel.com/aspros-projects-07dbbeb8/relay/GRkuu313spKSkWgMuaicd2ne3m7u |

## Why Relay Exists

Milestone-gated crowdfunding escrow. Backers pledge GEN, creators submit public proof URLs, GenLayer verifies the milestone, and the contract releases only the verified tranche or enables refunds on failure.

The frontend keeps the original product experience, while the contract adds a reviewable on-chain lifecycle: source records, GenLayer reasoning, challenge and appeal paths, indexed reads, and an audit trail that can be inspected after deployment.

## Contract Architecture

| Area | Detail |
| --- | --- |
| Contract | `contracts/relay_v2.py` |
| Size | 21306 bytes |
| Network | GenLayer Studionet, chain id `61999` |
| Write methods | multiple |
| Read methods | multiple |
| GenLayer features | live web rendering, LLM execution, validator-comparative consensus |
| Deployment wallet | 0xA7c1997c7EE6A23091892313F46395f388aee700 |
| Contract address | 0xC2602425c2324f577754fdb17cae714Ce30b6Af5 |

Architecture note:

> Relay V2 (# v0.2.16), 21306 bytes, schema-valid milestone escrow contract with legacy open_campaign/pledge/submit_milestone/verify_milestone/refund compatibility, GenLayer web + LLM proof verification, audit-log views, challenge filings, appeal filings, backer position views, campaign digest, quality score and frontend bootstrap.

Core smoke flow:

```text
open_campaign
  -> pledge
  -> submit_milestone
  -> verify_milestone
```

## Verification Trail

| Step | Transaction |
| --- | --- |
| Open Campaign | https://explorer-studio.genlayer.com/tx/0xf49d68735a3779d40b48266c1849308d5a42a37bc37fad65eb61982ac4dc44aa |
| Pledge | https://explorer-studio.genlayer.com/tx/0x14aa9a6708cb39c7750a730dc77b16aeace539d3a4ab55c120c4302200da630c |
| Submit Milestone | https://explorer-studio.genlayer.com/tx/0x901da77f2645c2c17dabb14d03b035938e20862f1db5c345f2392d1a58191973 |
| Verify Milestone | https://explorer-studio.genlayer.com/tx/0x5e970956cf397f57293b12534c7c6959e0310d9d671a1c9af23692d78fdeccdb |

Test result:

```text
Schema valid
4 smoke writes finalized
14/14
Static frontend bundled for standalone Vercel deployment
```

## Frontend

Relay ships as a standalone static app:

- wallet connection through the bundled browser client
- GenLayer reads through `genlayer-js`
- writes routed through the connected EVM wallet
- local `shared/` client files included so Vercel does not depend on the private workspace router
- deployed contract address pinned in `app.js` and `deployment.json`

## Run Locally

From the private workspace:

```powershell
cd <private-workspace-root>
npm run preview:start
npm run preview:project -- 12-relay
```

Open:

```text
http://localhost:8080/12-relay/
```

## Publish / Redeploy

```powershell
cd <private-workspace-root>
npm run publish:project -- -Project 12-relay -Repo https://github.com/thorbh2/relay.git
```

Vercel production redeploy from a clean project folder:

```powershell
npx --yes vercel@latest --prod --yes
```

## Repository Safety

This public repository intentionally excludes local secrets:

- no private keys
- no vault files
- no `.env` files
- no `.vercel` project state
- no local dashboard data

Public files include frontend code, contract source, deployment metadata, tests, and non-sensitive proof links.
