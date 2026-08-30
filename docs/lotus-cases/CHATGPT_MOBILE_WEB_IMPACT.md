# ChatGPT mobile-web human-impact scorecard

**Verdict:** `LOW_SEVERITY_HUMAN_REVIEW`  
**Case:** `chatgpt-mobile-web-public-2026-07-21`  
**Scorecard SHA-256:** `af78900ccf7d744576a4ef8335b67a0939c3304780cc08f7570898bbe7f3a1e9`

## Executive decision

The public signed-out ChatGPT mobile-web baseline passed the tested route, horizontal-layout, compact-height, primary-control, login-layout, stability and event-delivery checks.

The audit found no demonstrated public user-blocking defect, no broken login state and no security issue.

One low-severity engineering diagnostic remains:

- the public mobile login page repeatedly emits one opaque first-party `console.error`;
- the login choices remain visible and usable in the passive state;
- no uncaught page error or visible user impact was established.

## Evidence chain

- LiminalQA PR `#106`, exact source head `2407be212e19a393fcd0d8dd33d9fe444aea663b`
- Baseline run `29783360123`
- Focused diagnostic run `29783766882`
- Pythia PR `#239`, exact head `cf15c07e7087f399db1b459c4850f5b4261c9b43`
- Pythia verdict `ALLOW_BOUNDED_DIAGNOSTIC`
- CML PR `#216`, exact head `29f31980c2ba229a38c4a3530eb4930e14dd3fa5`
- CML pack `17bda596a7530302a35eeed0336907dd96e35c1349f5694e246d1cc0b147e75b`

## Human-impact order

| Rank | Finding | Evidence | Human impact | Repair direction |
|---:|---|---|---|---|
| 1 | Opaque first-party console error on public mobile login | `P3-diagnostic` | No visible user impact was established. The cost is diagnostic noise and reduced observability if the Error lacks an explicit code or message. | Resolve through first-party source maps; emit an explicit error code/message or remove unintended logging. |

## Confirmed public passes

1. All five public home profiles returned HTTP `200`.
2. No horizontal document overflow was detected.
3. The composer remained visible at `412×915` and `412×520`.
4. Critical mobile controls exposed `44×44` CSS-pixel boxes in the tested state.
5. The mobile login layout retained provider, email and Continue choices.
6. Public-home CLS remained between `0` and `0.0004`.
7. Mobile event endpoints returned successful HTTP `200/204` responses.

These are scoped passes, not a universal product-quality claim.

## Architecture observation

A distinct signed-out mobile-user-agent branch is confirmed. At the same mobile viewport, desktop and Android mobile user-agents received different headings, header structure and CTA state.

This is not a defect. It matters because mobile fixes, accessibility reviews and experiments require branch-specific evidence rather than viewport-only assumptions.

## Harms explicitly rejected

The evidence does not support:

- mobile event delivery failure;
- composer obstruction;
- duplicate visible headings;
- a confirmed touch-target accessibility failure;
- broken public mobile login;
- authentication unavailability;
- lost user data or telemetry;
- a security vulnerability;
- native Android/iOS application defects;
- authenticated chat defects.

## What remains outside the audit

The actual signed-in mobile chat product still requires authorised evidence for:

- long conversation scrolling and return to latest;
- streaming, stop and recovery;
- multiline composer with a real virtual keyboard;
- attachments, camera, images and file preview;
- sidebar history, search and deep links;
- Search sources, widgets, Projects and Work;
- settings, memory, workspace and billing;
- offline/online recovery;
- TalkBack, browser zoom and external keyboard.

## Recommended human decision

1. Treat the public signed-out entry as a scoped pass.
2. Route the one P3 console diagnostic to first-party engineering, without external defect or security language.
3. Keep the rejected detector signals closed.
4. Authorise a separate signed-in mobile-web product audit before making conclusions about the chat experience after login.

## Authority boundary

The scorecard is advisory. It does not log in, submit a prompt, access a private chat, contact OpenAI, approve an external report, claim a vulnerability, deploy, deliver or merge.

Machine-readable scorecard: `docs/lotus-cases/chatgpt-mobile-web-impact-v1.json`.
