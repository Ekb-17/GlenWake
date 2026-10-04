# GlenWake project plan

## Development approach

The current application implements the first milestone. Build later features in tested stages. Never present planned or experimental AI features as already working.

## Product and end goal

GlenWake is a video-based cleanup evidence and verification system for campus, street, park, and property supervisors. Its central question is:

**What changed during cleanup, and is the waste visible afterward leftover, moved, newly deposited, or impossible to determine from the recording?**

GlenWake is an independent project focused on recorded video.

The contribution to pursue is honest cleanup attribution when video evidence has gaps. For example, a bag visible after cleanup may have remained throughout, moved from elsewhere, or arrived later. If a van blocks the decisive transition, preserve the supported alternatives and mark the attribution unresolved.

A useful product should make review clearer and more efficient. The technical goal is to test whether evidence-aware attribution reduces old-versus-new mistakes compared with ordinary before/after or tracking approaches. Neither that advantage nor review-time savings has been demonstrated by the current application.

## Finished workflow — planned beyond the current baseline

1. Upload a fixed-camera recording, preserve the original, and show analysis progress.
2. Draw one fixed monitoring region and mark cleanup start/end boundaries.
3. Overlay visible litter masks from a model validated on litter footage; allow endpoint-mask corrections.
4. Measure before/after visible litter coverage within the same region only when frames are comparable.
5. Build timestamped history of appearances, departures from view, movement, blocked views, and uncertain associations.
6. Attribute remaining waste as leftover, moved, newly deposited, or unresolved. Multiple categories may coexist within one scene.
7. Inspect supporting frames and timestamps, jump to relevant moments, review full history, correct mistakes, and retain revisions.
8. Export a reviewed report with assessments, measurements, supporting timestamps, human corrections, conditions, and limitations.

Use a coherent main workspace with video/overlays, an event timeline, and a review panel, plus a compact saved-session list.

Initial scope: uploaded daylight recordings from a stationary camera with separated, clearly visible litter. Night scenes, moving cameras, tiny distant objects, and dense piles are later evaluation extensions.

## Evidence and measurement rules

- A new tracking ID is not evidence of a new deposit. Track IDs are association hypotheses, not proven object identities.
- Preserve competing origins after occlusion; bound alternatives per ambiguous event rather than enumerating every possible video history.
- Disappearance or departure from view is not proof of cleanup or proper disposal.
- Keep the reviewed cleanup endpoint separate from later deposits. New dumping must not silently relabel an earlier cleanup as a failure.
- Corrected associations must recompute dependent assessments while preserving earlier versions and revision reasons.
- Keep observations from people, model predictions, rule-derived attribution, coverage, and confidence distinguishable.
- Coverage = union of waste-mask pixels inside the monitoring region / monitoring-region pixels. Do not substitute bounding-box areas.
- Relative net reduction = (before coverage - after coverage) / before coverage, only with a nonzero baseline and valid comparison. It may be negative; a zero baseline makes relative reduction undefined.
- Coverage measures visible projected image area, not garbage mass, disposal quality, or origin. Example percentages are illustrative arithmetic only.
- Mark measurements unavailable or limited for obstructed views, camera movement, or rearrangements that invalidate comparison. Never fill missing results with plausible numbers.
- Do not use unsupported accuracy, confidence, real-time, originality, or commercial-readiness claims.

## Current implementation — milestone 1

Implemented: local video upload/playback UI, monitoring rectangle, cleanup markers, manual timestamped observations, reviewer notes, and save/reopen persistence. Stack: React/TypeScript/Vite, Python/FastAPI, SQLite, local media files.

Baseline verification: 1 backend workflow test passed; TypeScript compilation and Vite production build passed. These checks are not complete browser testing, AI evaluation, or target-device performance measurements.

Not implemented: automatic litter segmentation, coverage calculations, automatic associations/attribution, revision history, and reviewed report export. No application AI accuracy has been measured.

The eight evaluation scenario types and the location-partition rules are defined in [docs/evaluation/data-protocol.md](docs/evaluation/data-protocol.md). That document is a collection protocol. No clips have been collected, and it is not model output or a measurement.

## Stages and acceptance gates

Stages 2 through 6 are not complete. Retain the working manual workflow throughout. Within stage 2, only the scenario types and partition rules are defined.

| Stage | Work | Gate before claiming completion |
| --- | --- | --- |
| 1 — Manual review | Manual review workspace | Existing API test/build evidence recorded above; browser validation reported separately. |
| 2 — Data and real vision | Define scenarios and partitions; collect controlled footage; integrate a waste-specific segmentation candidate and association baseline; retain masks, versions, timestamps, and sampling intervals. | Compare masks with independent annotations; exercise failed/unavailable inference; measure missed brief events, runtime and peak RAM. Benchmark on the target laptop before making laptop-speed claims. |
| 3 — Visible coverage | Correct endpoint masks and calculate comparable region coverage. | Known-mask and boundary tests; zero baseline, overlaps, occlusion, shifted camera, and incomparable-frame cases; document uncertainty. |
| 4 — Event history and attribution | Maintain competing origins, blocked-view states, cleanup boundaries, and evidence dependencies. | Paired histories distinguish leftover, moved, later deposits, and unresolved cases. Include tracking-ID switches and false cleanup confirmations. Compare with baselines using identical detections. |
| 5 — Corrections and revisions | Inspect full evidence, accept/correct/reject suggestions, recompute dependents, preserve earlier assessments and reasons. | Test persistence, revision order, recomputation, provenance, and protection of the original recording and reviewed endpoint. |
| 6 — Report and evaluation | Export reviewed assessments and evidence references; complete held-out comparisons and a clear demo. | Export matches the selected review revision, retains unresolved cases and limitations, and includes real measurements only. Report failures, coverage of answered cases, and limits of generalization. |

The scenario list for the pilot is the eight types in [docs/evaluation/data-protocol.md](docs/evaluation/data-protocol.md). Stage 2 remains open: no controlled footage has been collected, and no segmentation or association model is integrated. Next work inside this stage is to collect that set under the protocol, then integrate a waste-specific segmentation candidate behind an interface and retain masks, versions, timestamps, and sampling intervals. The stage 2 gate above is still unmet.

## Technical starting points

Keep the existing stack. Add OpenCV/managed FFmpeg media processing when needed. Use one local analysis worker initially to bound memory; record sampling rate and retain original footage for denser reinspection.

YOLO11n-seg adapted to litter is a candidate, not a validated choice. Investigate TACO masks and locally annotated frames; still images alone cannot validate cleanup histories. A waste-specific checkpoint and validation are required. Keep the model behind an interface. ONNX CPU export is a later benchmarked optimization. No mandatory paid per-frame AI API is planned.

Evolve the repository only as needed: API, vision, attribution, and storage modules; experiments for baselines/evaluation; docs for data protocol, model details, and measured limits. Avoid restructuring working code solely to match a proposed layout.

Evidence records should include session/time interval/region, candidate type, possible origins, related item hypotheses, frame references, visibility, model and association versions, sampling interval, assertion source, review status, and revision links/reasons.

## Evaluation plan — goals, not results

The proposed pilot contains 48 clips: eight scenario types × two takes × three locations. Those types, the negative-control clip among them, and the location partitions are specified in [docs/evaluation/data-protocol.md](docs/evaluation/data-protocol.md). Separate development, tuning, and testing by location, keeping each whole recording and all derivatives within one partition. The negative-control type is the continuous footage for a later false-alert rate.

Compare snapshot-only, ordinary temporal tracking, and GlenWake attribution on identical detections. Evaluate human-reviewed observations separately from end-to-end model output. Include paired scenes with similar before/after coverage but different histories, plus hidden transitions that should remain unresolved.

Report event precision/recall, wrong old/new attributions, false cleanup confirmations, answered/unresolved fractions, mask coverage error, latency, and peak RAM. Compare attribution errors at equal answered fractions so excessive abstention cannot masquerade as improvement.

Exploratory target: at least 25% fewer attribution errors than the temporal baseline at the same answered fraction, initially aiming to answer 80% of eligible cases. These are targets, not achieved accuracy or acceptance proof. Set definitions and thresholds before evaluating.

Review-time savings require a separate counterbalanced human comparison with balanced clips, elapsed time, and correct/wrong/unresolved outcomes; avoid participants learning the same clip in another condition.

Synthetic evidence-selection experiments do not establish real-video detection, attribution performance, usability, or originality. Those claims require dedicated evaluation.

## Development discipline

Read this plan and README before changes. Deliver bounded stages with meaningful behavior/failure tests. For code changes, run backend tests and frontend build plus relevant browser checks; record commands, results, limitations, and actual status (planned, experimental, or implemented and tested).

Do not invent outputs or report fixtures as inference. Show model confidence only when meaningful and actually supplied; document calibration limits and distinguish it from measured accuracy. Keep private recordings, local databases, credentials, dependencies, and build output out of Git.

See README for Windows setup and check commands.
