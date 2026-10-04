# Evaluation data protocol

This protocol names the eight scenario types for the pilot in [PROJECT_PLAN.md](../../PROJECT_PLAN.md). The checked list is [scenario-catalog.json](scenario-catalog.json).

The catalog status is `defined_not_collected`. No evaluation clip is stored in this repository, and the catalog collected count remains 0. Nothing in this directory is footage, a mask, a model prediction, a coverage measurement, or an accuracy result. The review screen does not read this protocol and does not analyze video. The evaluation intake API reads the scenario list only to accept or reject a local registration.

## Pilot shape

The pilot is 48 clips: 8 scenario types, 2 takes of each type, and 3 locations. `negative_control` is one of the eight, so that count already includes continuous negative footage for a later false-alert rate. It is not a ninth type.

Each clip has one primary question. Other visible waste may be labeled item by item, so more than one category can appear in a recording. A mixed scene is not its own scenario type. Stage 4 still requires the product to allow leftover, moved, newly deposited, and unresolved waste in one scene. This collection list does not add a separate mixed-scene type.

## Recording scope

Clips in this pilot are daylight recordings from a stationary camera, with litter that is separated and clearly visible.

These stay out of the pilot until a later extension: night scenes, moving cameras, tiny distant objects, and dense piles.

## Partitions

The three partitions are `development`, `tuning`, and `testing`. Assign each location to exactly one partition before any analysis. Keep each whole recording, and every derivative of it, in that location's partition. Do not move a clip because a result was inconvenient.

## Labels

Labels written for these clips are human staging labels. The catalog field `label_source` is `human_staging_label`. A future model prediction, a tracking ID, a coverage figure, and a person's correction stay separate records. This protocol does not create those records.

A tracking ID is not an object identity. A new ID does not mean a new deposit.

## Scenario types

### leftover — Leftover waste

Waste stays inside the monitoring region, in the same place, from before cleanup through the reviewed endpoint, and the endpoint view of it is not blocked.

Supported statement: the item remained in place and may be called leftover from that continuity.

Do not treat a new tracking ID as a new deposit. Do not treat endpoint coverage that matches a moved clip as proof of the same history.

### moved — Moved waste

An item inside the monitoring region changes position during the cleanup window. The move is visible, and the item is still visible at the reviewed endpoint.

Supported statement: the item was relocated.

Stage at least one leftover take and one moved take so the visible waste area at the reviewed endpoint can be similar. Coverage does not decide which history is which.

Do not treat a new tracking ID as a new deposit.

### newly_deposited — Newly deposited waste

The reviewed cleanup endpoint is marked. Waste that was not present at that endpoint appears afterward, and the arrival is visible.

Supported statement: that later item is newly deposited. The earlier endpoint stays as reviewed.

Do not relabel the earlier cleanup as a failure because waste is visible later. Do not treat a new tracking ID as the reason it is new.

### visible_removal — Visible removal

An item is inside the region before cleanup. During the cleanup window a person or tool takes it out of the region, the removal is not blocked, and the item is absent at the reviewed endpoint.

Supported statement: the item is not remaining because the removal was visible. This is not one of the four labels for waste that is still in question. Absence by itself is not the evidence.

Do not report waste mass or disposal quality. Do not treat a later clip where the item merely disappears as the same outcome.

### departure_without_removal — Departure without removal

An item leaves the monitoring region or the frame, no pickup or carrying-out is visible, and the item is absent afterward.

Supported statement: the item left the view. The outcome is unresolved for cleanup and for proper disposal.

Do not confirm cleanup. Do not confirm proper disposal. Pair at least one take with a visible-removal take: both can end with the item absent, and only the visible removal supports removal.

### occluded_transition — Occluded transition

Waste is visible, a blocker such as a vehicle or person hides the decisive change inside the monitoring region, and the region is visible again with more than one origin still possible.

Supported statement: the attribution stays unresolved. Competing origins stay listed.

Do not fill in one origin. If the blockage makes the before and after frames incomparable, the coverage comparison is unavailable. Do not supply a number.

### association_switch — Association switch

Two or more similar items are visible and cross, overlap, or otherwise create a point where a tracker could switch identities.

Supported statement: a new tracking ID is not a new deposit. If the recording shows which item is which, the label follows that visible continuity. If it does not, the attribution stays unresolved and the alternatives stay listed.

Do not choose a single origin when the crossing leaves more than one possible.

### negative_control — Negative control

The monitoring region has no litter appearance, movement, departure, or deposit for the whole clip. The camera stays stationary and the scene stays in daylight.

Supported statement: no litter event is asserted.

Do not add an event the recording does not show. Do not publish a coverage percentage for this clip from the catalog. A later measurement, if masks exist, is a separate record.

## Comparison pairs

These pairs are staging instructions inside the eight types, not extra clips.

| Pair | Types | What must stay distinct |
| --- | --- | --- |
| Similar endpoint coverage | `leftover`, `moved` | Visible area at the endpoint may match. The histories must not. |
| Item absent | `visible_removal`, `departure_without_removal` | Both can end with the item out of view. Only a visible removal supports removal. |

## What a registered clip records

Intake can store one local recording at a time. The original file stays in the local data directory and is not committed. A `registration_kind` of `fixture` is a dry run or a test registration and is not a collected pilot clip. A `pilot` registration counts only in that local data directory. Intake does not edit `collected_clip_count` in the catalog. Each record needs:

- clip id, scenario type, location id, partition, and take
- confirmation that the clip is daylight and the camera is stationary
- the monitoring region, in the same normalized frame coordinates the review workspace uses
- cleanup start and end, with the reviewed endpoint kept separate from later deposits
- an item history: when each item is visible, moves, leaves, or is blocked, and the human label for that item
- whether the before and after frames are comparable
- label source `human_staging_label`
- limitations, including any moment that must stay unresolved

Do not put private recordings or local databases in Git.

## What remains outside this slice

Scenario names, partition rules, and local intake are in place. The evaluation footage itself has not been collected. Still required before stage 2 can be called complete: collect the controlled set, integrate a waste-specific segmentation candidate behind an interface, retain masks with model version, timestamps, and sampling interval, compare masks with independent annotations, exercise failed or unavailable inference, and measure missed brief events, runtime, and peak memory. Laptop-speed claims wait on a benchmark of the target laptop. Intake does not do that work and does not produce those measurements.

No coverage is calculated here. Coverage, when it exists later, is the union of waste-mask pixels inside the monitoring region divided by the monitoring-region pixels, and only for comparable frames. A zero before-coverage makes relative reduction undefined. This document does not contain those measurements.
