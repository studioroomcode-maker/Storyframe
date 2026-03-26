# Cinematography Dataset Plan

## Goal

Build a legally safer, practically useful dataset for improving StoryFrame recognition on:

- `shotSize`
- `framing`
- `movement`
- `lensType`
- `angle`
- `dof`
- `lightingType`
- `lightingCondition`
- `composition`

The dataset should serve two separate purposes:

1. `benchmark`: fixed, manually verified evaluation set
2. `tuning`: larger set used to refine heuristics and confidence thresholds

Do not mix these two sets.

## Recommended Data Sources

Use sources in this order:

1. `self-shot / self-owned footage`
2. `Pexels` videos and images
3. `Pixabay` videos and images
4. `WordPress Photo Directory`
5. `Openverse` only after verifying the original license
6. `Wikimedia Commons` only after verifying the file-specific license

Use research-only cinematography datasets as references, not as the default training pool:

- `CineScale`
- `CineScale2`
- `CineTechBench`

## Licensing Rule

Only add an asset if all three are true:

1. The source page is saved in metadata.
2. The license is explicitly recorded.
3. You can explain why reuse for your private dataset is allowed.

If any of those are missing, do not ingest the asset.

## Target Size

Start with a small but clean set.

### Phase A: Benchmark

- `150` still frames or clips total
- `15-20` examples per major class family
- balanced across source types
- manually reviewed twice

### Phase B: Tuning

- `800-1,500` samples total
- more tolerant of ambiguity
- can include soft labels and exclusions

## Split Strategy

Use three splits:

- `benchmark`: never touched during tuning
- `dev`: used to tune thresholds and rules
- `holdout`: checked only after a batch of changes

Recommended ratio for the larger set:

- `70%` dev
- `15%` validation
- `15%` holdout

Keep near-duplicate images and adjacent clip frames in the same split.

## Folder Layout

```text
dataset/
  raw/
    pexels/
    pixabay/
    wordpress/
    commons/
    selfshot/
  curated/
    benchmark/
    dev/
    holdout/
  labels/
    benchmark.json
    dev.json
    holdout.json
  manifests/
    sources.csv
```

## Label Policy

Labels must match the app taxonomy exactly.

### shotSize

Allowed values:

- `ECU`
- `BCU`
- `CU`
- `MCU`
- `MS`
- `Cowboy`
- `MLS`
- `FS`
- `LS`
- `ELS`
- `Establishing`
- `INSERT`

Rule:

- label by subject occupancy and visible body coverage
- if the frame is too ambiguous between two adjacent classes, mark it as `ambiguous_shotSize`

### framing

Allowed values:

- `Single`
- `Two-shot`
- `Three-shot`
- `OTS`
- `POV`
- `Crowd`
- `Empty`

### movement

Allowed values:

- `Static`
- `Pan`
- `Whip-pan`
- `Tilt`
- `Push-in`
- `Pull-out`
- `Tracking`
- `Trucking`
- `Arc`
- `Crane`
- `Pedestal`
- `Handheld`
- `Steadicam`
- `Zoom-in`
- `Zoom-out`
- `Dolly-zoom`
- `Rack-focus`
- `Drone`

Rule:

- label movement only for clips, not single stills
- use `Static` for still benchmark images unless there is trustworthy clip context

### lensType

Allowed values:

- `Ultra-wide(<16mm)`
- `Wide(16-35mm)`
- `Normal(35-60mm)`
- `Telephoto(60-135mm)`
- `Super-telephoto(>135mm)`
- `Macro`

Rule:

- do not try to infer exact focal length
- prefer family-level labels only
- if evidence is weak, exclude from lens benchmark instead of forcing a label

### angle

Allowed values:

- `Overhead`
- `High`
- `Eye-level`
- `Shoulder-level`
- `Low`
- `Worms-eye`
- `Dutch`
- `Aerial`

### dof

Allowed values:

- `Deep`
- `Moderate`
- `Shallow`
- `Very-shallow`

Rule:

- judge optical or rendered separation, not just blur-like texture

### lightingType

Allowed values:

- `Natural`
- `Artificial`
- `Mixed`
- `Practical`

### lightingCondition

Allowed values:

- `High-key`
- `Low-key`
- `Silhouette`
- `Chiaroscuro`
- `Flat`
- `Rembrandt`

Rule:

- label this from the subject, not from background mood alone

### composition

Allowed values:

- `Rule-of-thirds`
- `Center-framed`
- `Symmetrical`
- `Leading-lines`
- `Frame-within-frame`
- `Negative-space`
- `Golden-ratio`

## Record Schema

Use one record per sample.

```json
{
  "id": "pexels_000123",
  "split": "benchmark",
  "source": "pexels",
  "source_url": "https://example.com/asset",
  "license": "Pexels License",
  "media_type": "image",
  "file_path": "dataset/curated/benchmark/pexels_000123.jpg",
  "notes": "single subject, clear rembrandt face lighting",
  "labels": {
    "shotSize": "CU",
    "framing": "Single",
    "movement": "",
    "lensType": "Normal(35-60mm)",
    "angle": "Eye-level",
    "dof": "Shallow",
    "lightingType": "Practical",
    "lightingCondition": "Rembrandt",
    "composition": "Center-framed"
  },
  "flags": {
    "ambiguous_shotSize": false,
    "ambiguous_lens": false,
    "ambiguous_lighting": false,
    "exclude_from_benchmark": false
  }
}
```

## Review Workflow

Each sample should pass this process:

1. `collector` adds asset and source metadata
2. `labeler A` assigns labels
3. `labeler B` reviews independently
4. disagreements are resolved into:
   - a final label
   - or an exclusion flag

Exclude the sample from benchmark if:

- the source license is unclear
- the frame is near-duplicate of another sample
- the class is fundamentally ambiguous
- the frame requires film-specific knowledge not visible in the image

## Hard-Negative Strategy

Create a separate hard-negative bucket for confusing cases:

- `CU` vs `MCU`
- `LS` vs `ELS`
- `Eye-level` vs `Shoulder-level`
- `Wide` vs `Normal`
- `Practical` vs `Mixed`
- `Low-key` vs `Chiaroscuro`
- `Flat` vs `High-key`
- `Static` vs `Handheld`

These should be over-represented in `dev`, but not dominate `benchmark`.

## Weekly Collection Target

Recommended weekly target:

- `30` new benchmark candidates
- `80` new tuning samples
- `20` hard negatives

At the end of each week:

1. export a StoryFrame project JSON from the app
2. run the benchmark evaluator
3. inspect top confusions
4. change only a small number of thresholds at once

## Evaluation Workflow

From the app:

1. create or import benchmark labels
2. click `평가용 프로젝트 저장`
3. save the exported file

From the terminal:

```powershell
npm run benchmark:evaluate -- --project .\your_storyframe_project.json
```

The evaluator prints:

- overall app accuracy
- recognition-only accuracy
- per-field accuracy
- mismatch rows
- common confusion pairs

## Engineering Priorities

Based on the current recognizer, improve in this order:

1. `shotSize`
2. `angle`
3. `lightingCondition`
4. `movement`
5. `dof`
6. `lightingType`
7. `lensType`

Reason:

- `shotSize` is the easiest to stabilize with subject occupancy
- `lensType` is the least reliable from a single frame
- `lighting` improves only if subject-centric labeling is strict

## Success Thresholds

Use realistic targets:

- `shotSize`: `85%+`
- `angle`: `80%+`
- `movement`: `75%+`
- `lightingCondition`: `72%+`
- `lightingType`: `75%+`
- `dof`: `72%+`
- `lensType`: `65-75%`

For `lensType`, prefer better abstention over fake precision.

## Non-Negotiables

- never train on data with unclear rights
- never tune on the benchmark split
- never force a label when evidence is weak
- never change multiple field heuristics without rerunning the benchmark
