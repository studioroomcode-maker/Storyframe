#!/usr/bin/env python3
"""
HISTORIAN Dataset → StoryFrame Benchmark Converter
===================================================

데이터셋: HISTORIAN (WWII 기록 영화 10,593 샷)
라이선스: CC-BY-4.0
다운로드:
  - Tiny (425MB): https://zenodo.org/records/6184281
  - Full (9.3TB): Google Drive (논문 연락 필요)

카테고리 매핑:
  shotType:
    ECU → ECU, CU → CU, MCU → MCU, MS → MS,
    MLS → MLS, FS → FS, LS → LS, ELS → ELS
    (HISTORIAN은 표준 cinematographic 표기 사용)

  camera movement (class_name):
    static       → Static
    pan          → Pan
    tilt         → Tilt
    zoom_in      → Zoom-in
    zoom_out     → Zoom-out
    dolly / tracking → Tracking
    handheld     → Handheld
    crane        → Crane

사용:
  # 1. Zenodo tiny 다운로드
  wget https://zenodo.org/records/6184281/files/historian_dataset_v1_tiny_pre.zip
  unzip historian_dataset_v1_tiny_pre.zip -d ./historian_tiny

  # 2. 변환 실행
  python scripts/historian_to_storyframe.py \
      --dataset ./historian_tiny \
      --output  ./dataset/curated/benchmark \
      --count 150 --split benchmark
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
import random

# ── 카테고리 매핑 ────────────────────────────────────────────────────────────

SHOT_TYPE_MAP = {
    # 표준 약어
    "ECU": "ECU", "BCU": "BCU", "CU": "CU", "MCU": "MCU",
    "MS": "MS", "MLS": "MLS", "FS": "FS", "LS": "LS", "ELS": "ELS",
    "IS": "INSERT", "INSERT": "INSERT",
    # 풀네임 (일부 어노테이터 사용)
    "extreme close-up": "ECU",
    "close-up": "CU",
    "medium close-up": "MCU",
    "medium shot": "MS",
    "medium long shot": "MLS",
    "full shot": "FS",
    "long shot": "LS",
    "extreme long shot": "ELS",
}

MOVEMENT_MAP = {
    "static":    "Static",
    "pan":       "Pan",
    "tilt":      "Tilt",
    "zoom":      "Zoom-in",
    "zoom_in":   "Zoom-in",
    "zoom_out":  "Zoom-out",
    "dolly":     "Tracking",
    "tracking":  "Tracking",
    "handheld":  "Handheld",
    "crane":     "Crane",
    "pedestal":  "Pedestal",
    "aerial":    "Drone",
    "truck":     "Trucking",
    "trucking":  "Trucking",
}


# ── 어노테이션 파서 ───────────────────────────────────────────────────────────

def load_historian_annotations(dataset_dir: Path) -> list[dict]:
    """
    HISTORIAN 어노테이션 디렉터리를 순회하여 샷 레코드를 로드합니다.

    구조:
      {dataset_dir}/
        {VID}/
          {VID}-shot_annotations.json
          {VID}-sequence_annotations.json
        OR
      {dataset_dir}/Annotations/
        shot-annotations_manual/
          {VID}-shot_annotations.json
        camera_annotations_manual/
          {VID}-sequence_annotations.json
    """
    records = []

    # 경로 탐색 (tiny 또는 full 두 구조 모두 대응)
    shot_dirs = [
        dataset_dir / "Annotations" / "shot-annotations_manual",
        dataset_dir / "shot-annotations_manual",
        dataset_dir,
    ]
    cam_dirs = [
        dataset_dir / "Annotations" / "camera_annotations_manual",
        dataset_dir / "camera_annotations_manual",
        dataset_dir,
    ]

    shot_files = {}
    for d in shot_dirs:
        if d.is_dir():
            for f in d.glob("*-shot_annotations.json"):
                vid = f.stem.replace("-shot_annotations", "")
                shot_files[vid] = f
            break

    cam_files = {}
    for d in cam_dirs:
        if d.is_dir():
            for f in d.glob("*-sequence_annotations.json"):
                vid = f.stem.replace("-sequence_annotations", "")
                cam_files[vid] = f
            break

    if not shot_files:
        # 전체 디렉터리 fallback
        for f in dataset_dir.rglob("*-shot_annotations.json"):
            vid = f.stem.replace("-shot_annotations", "")
            shot_files[vid] = f
        for f in dataset_dir.rglob("*-sequence_annotations.json"):
            vid = f.stem.replace("-sequence_annotations", "")
            cam_files[vid] = f

    print(f"[로드] 발견된 필름 수: {len(shot_files)}")
    if not shot_files:
        print("[오류] shot_annotations.json 파일을 찾을 수 없습니다.", file=sys.stderr)
        print(f"  탐색 경로: {dataset_dir}", file=sys.stderr)
        sys.exit(1)

    for vid, shot_file in sorted(shot_files.items()):
        try:
            shots = json.loads(shot_file.read_text(encoding="utf-8"))
            if not isinstance(shots, list):
                shots = shots.get("shots", [])
        except Exception as e:
            print(f"  [경고] {shot_file.name}: {e}", file=sys.stderr)
            continue

        # 카메라 무브먼트 로드
        movements_for_shot: dict[int, str] = {}
        if vid in cam_files:
            try:
                cam_data = json.loads(cam_files[vid].read_text(encoding="utf-8"))
                if not isinstance(cam_data, list):
                    cam_data = cam_data.get("movements", cam_data.get("sequences", []))
                for cm in cam_data:
                    sid = cm.get("shotId")
                    cls = str(cm.get("class_name", "")).lower()
                    if sid is not None and cls:
                        movements_for_shot[int(sid)] = cls
            except Exception as e:
                print(f"  [경고] 카메라 어노테이션 {vid}: {e}", file=sys.stderr)

        for shot in shots:
            shot_id   = int(shot.get("shotId", 0))
            shot_type = str(shot.get("shotType", "")).strip().upper()
            in_point  = int(shot.get("inPoint", 0))
            out_point = int(shot.get("outPoint", 0))
            movement  = movements_for_shot.get(shot_id, "static").lower()

            sf_shot = SHOT_TYPE_MAP.get(shot_type, SHOT_TYPE_MAP.get(shot_type.lower()))
            sf_move = MOVEMENT_MAP.get(movement, MOVEMENT_MAP.get(movement.split("_")[0]))

            if not sf_shot:
                continue  # 알 수 없는 샷 타입 제외

            records.append({
                "vid":       vid,
                "shot_id":   shot_id,
                "in_point":  in_point,
                "out_point": out_point,
                "_shotSize": sf_shot,
                "_movement": sf_move or "Static",
                "orig_type": shot_type,
                "orig_move": movement,
            })

    print(f"[로드] 총 {len(records):,}개 유효 샷")
    return records


# ── 키프레임 추출 ─────────────────────────────────────────────────────────────

def extract_keyframe(dataset_dir: Path, vid: str, in_point: int, out_point: int,
                     dest_path: Path) -> bool:
    """
    m4v 영상에서 중간 프레임을 추출합니다. (ffmpeg 필요)
    없으면 건너뜁니다.
    """
    import shutil
    if not shutil.which("ffmpeg"):
        return False

    # 영상 파일 탐색
    video_file = None
    for f in dataset_dir.rglob(f"{vid}*.m4v"):
        video_file = f
        break
    if not video_file:
        return False

    mid_frame = (in_point + out_point) // 2
    timestamp = mid_frame / 25.0  # 25fps 기준

    import subprocess
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(video_file),
         "-frames:v", "1", "-q:v", "2", str(dest_path)],
        capture_output=True, timeout=30
    )
    return result.returncode == 0


# ── 균형 샘플링 ──────────────────────────────────────────────────────────────

def balanced_sample(records: list[dict], count: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    buckets: dict[str, list] = defaultdict(list)
    for r in records:
        buckets[r["_shotSize"]].append(r)

    print("\n전체 분포:")
    for cls, items in sorted(buckets.items()):
        print(f"  {cls:15s}: {len(items):,}")

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


# ── StoryFrame 레코드 생성 ───────────────────────────────────────────────────

def to_storyframe_record(index: int, rec: dict, split: str,
                          image_saved: bool, output_dir: Path) -> dict:
    sample_id = f"historian_{rec['vid']}_s{rec['shot_id']:04d}"
    rel_path  = f"dataset/curated/{split}/{sample_id}.jpg"

    return {
        "id": sample_id,
        "split": split,
        "source": "historian",
        "source_url": "https://zenodo.org/records/6184281",
        "license": "CC-BY-4.0",
        "media_type": "image",
        "file_path": rel_path,
        "notes": (f"HISTORIAN {rec['vid']} shot {rec['shot_id']} "
                  f"orig_type={rec['orig_type']} orig_move={rec['orig_move']} "
                  f"frames={rec['in_point']}-{rec['out_point']}"),
        "labels": {
            "shotSize":          rec["_shotSize"],
            "framing":           "",
            "movement":          rec["_movement"],
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
        description="HISTORIAN 어노테이션 → StoryFrame 벤치마크 변환"
    )
    parser.add_argument("--dataset", required=True,
                        help="HISTORIAN 데이터셋 루트 경로")
    parser.add_argument("--output", required=True,
                        help="출력 이미지 디렉터리")
    parser.add_argument("--labels-out", default=None)
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--split", default="benchmark",
                        choices=["benchmark", "dev", "holdout"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--extract-frames", action="store_true",
                        help="ffmpeg로 키프레임 추출 (느림)")
    args = parser.parse_args()

    dataset_dir = Path(args.dataset)
    output_dir  = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_out = Path(args.labels_out) if args.labels_out else \
                 output_dir.parent.parent / "labels" / f"{args.split}_historian.json"
    labels_out.parent.mkdir(parents=True, exist_ok=True)

    records  = load_historian_annotations(dataset_dir)
    selected = balanced_sample(records, args.count, seed=args.seed)
    print(f"\n[샘플링] {len(selected)}개 선택")

    sf_records = []
    saved_count = 0
    for i, rec in enumerate(selected):
        image_saved = False
        if args.extract_frames:
            dest = output_dir / f"historian_{rec['vid']}_s{rec['shot_id']:04d}.jpg"
            image_saved = extract_keyframe(
                dataset_dir, rec["vid"], rec["in_point"], rec["out_point"], dest
            )
            if image_saved:
                saved_count += 1

        sf_records.append(
            to_storyframe_record(i, rec, args.split, image_saved, output_dir)
        )

    output_json = {
        "version": 1,
        "split": args.split,
        "source": "historian",
        "count": len(sf_records),
        "records": sf_records,
    }
    labels_out.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n[완료]")
    print(f"  레코드: {len(sf_records)}")
    print(f"  이미지 추출: {saved_count}")
    print(f"  레이블 JSON: {labels_out}")

    dist = Counter(r["labels"]["shotSize"] for r in sf_records)
    print("\n샷사이즈 분포:")
    for cls, cnt in sorted(dist.items()):
        print(f"  {cls:15s}: {cnt}")

    dist_move = Counter(r["labels"]["movement"] for r in sf_records)
    print("\n무브먼트 분포:")
    for cls, cnt in sorted(dist_move.items()):
        print(f"  {cls:20s}: {cnt}")


if __name__ == "__main__":
    main()
