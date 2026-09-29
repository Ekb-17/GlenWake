# GlenWake project plan

## Governing instruction

> The ZIP is only the first milestone. Build the later features in tested stages, and don't present planned AI features as already working.

This plan describes the cleanup-recording workspace imported into this repository. The staged roadmap below expands the next milestones already listed in its README. It is not a claim that every feature discussed outside this repository has been captured.

## Current baseline — milestone 1

Implemented: local video upload, fixed monitoring rectangle, cleanup start/end markers, manual timestamped observations, reviewer notes, and saving/reopening reviews. The frontend uses React/TypeScript/Vite; the backend uses FastAPI, SQLite, and local video storage.

Validation on 2026-09-29: the existing backend workflow test passed (1 test), and the frontend TypeScript compilation and Vite production build passed. This is limited validation, not a complete browser or AI evaluation.

Not implemented: automated litter segmentation/detection, calculated coverage percentages, automated event attribution, and review revision history. There is no measured AI accuracy to report.

## Staged delivery

All stages after milestone 1 are planned and unimplemented. The acceptance checks below are requirements for future work, not completed checks.

| Stage | Deliverable | Required evidence before declaring it working |
| --- | --- | --- |
| 1 — Manual review baseline | Imported ZIP workflow | Existing API test and frontend build pass; record browser verification separately when performed. |
| 2 — Validate litter segmentation | Integrate a real model and retain frame timestamps, model/version, masks, and inference provenance. Preserve manual review. | Evaluate against independently annotated held-out footage; separate recordings across development/evaluation sets; report dataset size, measured segmentation metrics, failures, and runtime. Test unavailable-model and failed-inference behavior. Define acceptance thresholds before evaluating. |
| 3 — Measure visible coverage | Calculate litter coverage from verified masks within the selected monitoring area; compare suitable before/after frames. | Check known masks and region boundaries; test zero baseline, occlusion, camera movement, and incomparable views. Document numerator, denominator, units, and uncertainty. Withhold results where the comparison is invalid. |
| 4 — Evidence-linked events | Suggest visible events with timestamp/frame evidence and human confirmation or rejection. | Evaluate on labeled events, including occlusion and objects leaving view; report false positives and missed events. Never treat disappearance alone as proof of successful cleanup or assign responsibility without supporting evidence. |
| 5 — Revisions | Preserve original evidence and a history of manual corrections and accepted/rejected AI suggestions. | Test save/reopen, revision ordering, provenance preservation, and editing without silently overwriting earlier evidence. |

The immediate next development stage is stage 2. Model selection, evaluation footage, annotation protocol, and acceptance thresholds remain to be specified and recorded before making performance claims. No model, dataset, or target accuracy has been selected by this document.

## Rules for each implementation stage

1. Deliver one bounded stage at a time, retaining the working manual workflow.
2. Add meaningful tests for the new behavior and its failure cases. Run the backend suite and frontend build for code changes; verify changed browser flows as appropriate.
3. Record what was implemented, commands run, outcomes, evaluation artifacts, and remaining limitations. A successful build alone is not evidence that AI works.
4. Update this plan and the README with the actual status: planned, experimental, or implemented and tested. State the scope of testing.
5. Keep manual observations, model predictions, and calculated measurements distinct in storage and the UI. Preserve source evidence.
6. Do not substitute mock outputs, hardcoded percentages, or plausible guesses for real inference. Label any test fixtures or demos clearly.
7. Show confidence only when a real model supplies a meaningful score; document its meaning and calibration limitations. Model confidence is not measured accuracy.
8. Keep user recordings, local databases, credentials, dependencies, and build output out of source control.

## Checks

From backend after installing requirements-dev.txt:
`python -m unittest discover -s tests -v`

From frontend:
`npm ci`
`npm run build`

See README.md for Windows virtual-environment commands.
