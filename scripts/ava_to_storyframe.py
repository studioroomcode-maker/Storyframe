#!/usr/bin/env python3
"""
Google AVA Actions → StoryFrame Benchmark Converter
====================================================

데이터셋: AVA Actions v2.2 (CC BY 4.0)
출처: https://research.google.com/ava/
규모: 430개 영화 클립, 1.62M 액션 레이블, 사람 바운딩 박스 포함

## 핵심 아이디어
AVA의 person_box (normalized x1,y1,x2,y2) 크기로 shotSize를 추론합니다.

  박스 높이(y2-y1) 기준:
    > 0.70  →  ECU  (얼굴/목만 보임)
    0.55-0.70 → CU   (어깨 위)
    0.40-0.55 → MCU  (가슴 위)
    0.25-0.40 → MS   (허리 위)
    0.15-0.25 → MLS  (무릎 위)
    0.08-0.15 → FS   (전신)
    < 0.08    → LS   (원거리)

  프레임 내 사람 수 기준:
    1명  → Single
    2명  → Two-shot
    3명  → Three-shot
    4명+ → Crowd

## 사용법

### Step 1: AVA 어노테이션 CSV 다운로드

  # GitHub 방식
  git clone https://github.com/cvdfoundation/ava-dataset
  cd ava-dataset
  bash download_annotations.sh

  # 직접 다운로드 (가장 빠름, ~20MB)
  curl -O "https://storage.googleapis.com/ava-dataset/annotations/ava_train_v2.2.csv"
  curl -O "https://storage.googleapis.com/ava-dataset/annotations/ava_val_v2.2.csv"

### Step 2: (선택) 영상 다운로드 + 키프레임 추출
  bash ava-dataset/download_videos.sh   # 수백GB 주의

  # 또는 특정 영상만
  yt-dlp "https://www.youtube.com/watch?v={video_id}" -o "{video_id}.%(ext)s"

### Step 3: 변환 실행

  # 어노테이션만 (레이블 JSON 생성, 이미지 없음)
  python scripts/ava_to_storyframe.py \
      --annotations ./ava_train_v2.2.csv \
      --output ./dataset/curated/dev \
      --count 500 --split dev

  # 영상 + 키프레임 추출 포함 (ffmpeg 필요)
  python scripts/ava_to_storyframe.py \
      --annotations ./ava_train_v2.2.csv \
      --videos ./ava_videos \
      --output ./dataset/curated/dev \
      --count 500 --split dev --extract-frames
"""

import argparse
import csv
import json
import os
import random
import subprocess
import sys
from collections import defaultdict, Counter
from pathlib import Path


# ── shotSize 추론 ────────────────────────────────────────────────────────────

def infer_shot_size(box_h: float) -> str:
    """
    정규화된 바운딩 박스 높이(0~1)로 shotSize를 추론합니다.
    AVA 박스는 가장 주요 인물 기준입니다.
    """
    if box_h > 0.70:  return "ECU"
    if box_h > 0.55:  return "CU"
    if box_h > 0.40:  return "MCU"
    if box_h > 0.25:  return "MS"
    if box_h > 0.15:  return "MLS"
    if box_h > 0.08:  return "FS"
    return "LS"


def infer_framing(person_count: int) -> str:
    if person_count == 0: return "Empty"
    if person_count == 1: return "Single"
    if person_count == 2: return "Two-shot"
    if person_count == 3: return "Three-shot"
    return "Crowd"


# ── CSV 파싱 ─────────────────────────────────────────────────────────────────

def parse_ava_csv(csv_path: Path) -> dict[tuple, list[dict]]:
    """
    AVA Actions CSV를 (video_id, timestamp) 키로 그룹핑합니다.

    CSV 형식:
      video_id, middle_frame_timestamp,
      entity_box_x1, entity_box_y1, entity_box_x2, entity_box_y2,
      action_id, person_id
    """
    frames: dict[tuple, list[dict]] = defaultdict(list)

    with csv_path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 7:
                continue
            try:
                video_id  = row[0].strip()
                timestamp = float(row[1])
                x1, y1, x2, y2 = float(row[2]), float(row[3]), float(row[4]), float(row[5])
                action_id = int(row[6])
                person_id = row[7].strip() if len(row) > 7 else "0"

                key = (video_id, timestamp)
                frames[key].append({
                    "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    "action_id": action_id,
                    "person_id": person_id,
                })
            except (ValueError, IndexError):
                continue

    print(f"[파싱] {len(frames):,}개 프레임 (비디오×타임스탬프)")
    return frames


def build_records(frames: dict[tuple, list[dict]]) -> list[dict]:
    """각 (video_id, timestamp) 프레임을 StoryFrame 레코드로 변환합니다."""
    records = []
    for (video_id, timestamp), persons in frames.items():
        # 프레임 내 고유 인물 수 (person_id 기준)
        unique_persons = len({p["person_id"] for p in persons})

        # 가장 큰 바운딩 박스 = 주인공 (shotSize 기준)
        max_box_h = max((p["y2"] - p["y1"]) for p in persons)

        shot_size = infer_shot_size(max_box_h)
        framing   = infer_framing(unique_persons)

        records.append({
            "video_id":      video_id,
            "timestamp":     timestamp,
            "person_count":  unique_persons,
            "max_box_h":     max_box_h,
            "_shotSize":     shot_size,
            "_framing":      framing,
        })
    return records


# ── 균형 샘플링 ──────────────────────────────────────────────────────────────

def balanced_sample(records: list[dict], count: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    buckets: dict[str, list] = defaultdict(list)
    for r in records:
        buckets[r["_shotSize"]].append(r)

    print("\n전체 shotSize 분포:")
    for cls, items in sorted(buckets.items()):
        print(f"  {cls:10s}: {len(items):,}")

    per_class = max(1, count // len(buckets))
    selected = []
    for items in buckets.values():
        selected.extend(rng.sample(items, min(per_class, len(items))))

    remaining = count - len(selected)
    if remaining > 0:
        pool = [r for r in records if r not in selected]
        selected.extend(rng.sample(pool, min(remaining, len(pool))))

    rng.shuffle(selected)
    return selected[:count]


# ── 키프레임 추출 ─────────────────────────────────────────────────────────────

def extract_frame(video_dir: Path, video_id: str, timestamp: float, dest: Path) -> bool:
    """ffmpeg으로 지정 타임스탬프의 프레임을 추출합니다."""
    import shutil
    if not shutil.which("ffmpeg"):
        return False

    for ext in ["mp4", "mkv", "webm", "avi"]:
        video_file = video_dir / f"{video_id}.{ext}"
        if video_file.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["ffmpeg", "-y",
                 "-ss", f"{timestamp:.3f}",
                 "-i", str(video_file),
                 "-frames:v", "1", "-q:v", "2",
                 str(dest)],
                capture_output=True, timeout=30
            )
            return result.returncode == 0
    return False


# ── StoryFrame 레코드 ─────────────────────────────────────────────────────────

def to_storyframe_record(index: int, rec: dict, split: str,
                          image_saved: bool, output_dir: Path) -> dict:
    sample_id = f"ava_{rec['video_id']}_{int(rec['timestamp']*1000):08d}"
    rel_path  = f"dataset/curated/{split}/{sample_id}.jpg"
    return {
        "id":         sample_id,
        "split":      split,
        "source":     "ava_actions",
        "source_url": "https://research.google.com/ava/",
        "license":    "CC-BY-4.0",
        "media_type": "image",
        "file_path":  rel_path,
        "notes": (f"AVA video={rec['video_id']} t={rec['timestamp']}s "
                  f"persons={rec['person_count']} box_h={rec['max_box_h']:.3f}"),
        "labels": {
            "shotSize":          rec["_shotSize"],
            "framing":           rec["_framing"],
            "movement":          "",  # AVA에 없음
            "lensType":          "",
            "angle":             "",
            "dof":               "",
            "lightingType":      "",
            "lightingCondition": "",
            "composition":       "",
        },
        "flags": {
            "ambiguous_shotSize":     False,
            "ambiguous_lens":         False,
            "ambiguous_lighting":     False,
            "exclude_from_benchmark": not image_saved,
        },
    }


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Google AVA Actions → StoryFrame 벤치마크 변환"
    )
    parser.add_argument("--annotations", required=True,
                        help="AVA Actions CSV 경로 (ava_train_v2.2.csv 등)")
    parser.add_argument("--videos", default=None,
                        help="AVA 영상 디렉터리 (키프레임 추출 시 필요)")
    parser.add_argument("--output", required=True,
                        help="이미지 출력 디렉터리")
    parser.add_argument("--labels-out", default=None)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--split", default="dev",
                        choices=["benchmark", "dev", "holdout"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--extract-frames", action="store_true",
                        help="ffmpeg으로 키프레임 추출")
    args = parser.parse_args()

    output_dir  = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_out = Path(args.labels_out) if args.labels_out else \
                 output_dir.parent.parent / "labels" / f"{args.split}_ava.json"
    labels_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. CSV 파싱
    frames  = parse_ava_csv(Path(args.annotations))
    records = build_records(frames)
    print(f"[변환] {len(records):,}개 레코드 생성")

    # 2. 샘플링
    selected = balanced_sample(records, args.count, seed=args.seed)
    print(f"\n[샘플링] {len(selected)}개 선택")

    # 3. 변환 + 키프레임 추출
    video_dir   = Path(args.videos) if args.videos else None
    sf_records  = []
    saved_count = 0

    for i, rec in enumerate(selected):
        image_saved = False
        if args.extract_frames and video_dir:
            dest = output_dir / f"ava_{rec['video_id']}_{int(rec['timestamp']*1000):08d}.jpg"
            image_saved = extract_frame(video_dir, rec["video_id"], rec["timestamp"], dest)
            if image_saved:
                saved_count += 1
        sf_records.append(
            to_storyframe_record(i, rec, args.split, image_saved, output_dir)
        )

    # 4. JSON 저장
    output_json = {
        "version": 1,
        "split":   args.split,
        "source":  "ava_actions",
        "count":   len(sf_records),
        "records": sf_records,
    }
    labels_out.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n[완료]")
    print(f"  레코드:    {len(sf_records)}")
    print(f"  이미지:    {saved_count}")
    print(f"  레이블 JSON: {labels_out}")

    print("\nshotSize 분포:")
    for cls, cnt in sorted(Counter(r["labels"]["shotSize"] for r in sf_records).items()):
        print(f"  {cls:10s}: {cnt}")

    print("\nframing 분포:")
    for cls, cnt in sorted(Counter(r["labels"]["framing"] for r in sf_records).items()):
        print(f"  {cls:15s}: {cnt}")

    print("\n다음 단계:")
    print("  1. StoryFrame에서 이미지 폴더 분석 후 project.json 내보내기")
    print(f"  2. npm run benchmark:evaluate -- --benchmark {labels_out} --detected project.json")


if __name__ == "__main__":
    main()
