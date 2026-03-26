#!/usr/bin/env python3
"""
MovieNet → StoryFrame Benchmark Converter
==========================================

MovieNet(https://movienet.github.io/) 어노테이션을 StoryFrame 벤치마크 JSON 형식으로 변환합니다.

## 사전 준비 (OpenDataLab 계정 필요)

1. pip install opendatalab
2. odl login   (OpenDataLab 계정으로 로그인)
3. 아래 명령으로 필요한 데이터만 다운로드:

   # 샷 어노테이션만 (작음 ~53MB)
   odl get OpenDataLab/MovieNet --split annotations

   # 키프레임 이미지 (240p, 대용량)
   odl get OpenDataLab/MovieNet --split keyframe_240P

4. 다운로드 후 이 스크립트 실행:
   python scripts/movienet_to_storyframe.py \
       --annotations ./MovieNet/annotations \
       --keyframes   ./MovieNet/keyframe_240P \
       --output      ./dataset/curated/benchmark \
       --count 150   --split benchmark

## MovieNet → StoryFrame 카테고리 매핑

  shotSize:
    ECS → ECU    (Extreme Close-up)
    CS  → CU     (Close-up)
    MS  → MS     (Medium Shot)
    FS  → FS     (Full Shot)
    LS  → LS     (Long Shot)

  movement:
    static → Static
    push   → Push-in
    pull   → Pull-out
    motion → (ambiguous — angle에 따라 Pan/Tilt/Tracking 중 선택)

주의: MovieNet은 5단계 shotSize / 4단계 movement만 제공합니다.
      ECU/BCU/MCU/Cowboy/MLS/ELS/Establishing/INSERT 등은 직접 보완 필요.
"""

import argparse
import json
import os
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

# ── 카테고리 매핑 ────────────────────────────────────────────────────────────

SHOT_SIZE_MAP = {
    "ECS": "ECU",
    "CS":  "CU",
    "MS":  "MS",
    "FS":  "FS",
    "LS":  "LS",
    # 소문자 대응
    "ecs": "ECU",
    "cs":  "CU",
    "ms":  "MS",
    "fs":  "FS",
    "ls":  "LS",
    # 풀네임 대응
    "extreme close-up": "ECU",
    "close-up":         "CU",
    "medium shot":      "MS",
    "full shot":        "FS",
    "long shot":        "LS",
}

MOVEMENT_MAP = {
    "static": "Static",
    "push":   "Push-in",
    "pull":   "Pull-out",
    # motion은 ambiguous → 별도 처리
    "motion": None,  # None = 제외 또는 별도 버킷
}

SPLIT_OPTIONS = {"benchmark", "dev", "holdout"}


# ── 어노테이션 로더 ──────────────────────────────────────────────────────────

def load_movienet_annotations(annotations_dir: Path) -> list[dict]:
    """
    MovieNet 어노테이션 디렉터리에서 샷 레코드를 모두 로드합니다.

    지원 형식:
      1. shot_type/{movie_id}.json  — 공식 JSON 형식
      2. shot_type.csv              — CSV 형식 (movie_id, shot_id, scale, movement)
    """
    records = []

    # 1) JSON 형식
    json_dir = annotations_dir / "shot_type"
    if json_dir.is_dir():
        for json_file in sorted(json_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                movie_id = json_file.stem
                shots = data if isinstance(data, list) else data.get("shots", [])
                for shot in shots:
                    records.append({
                        "movie_id": movie_id,
                        "shot_id":  str(shot.get("shot_id", shot.get("id", ""))),
                        "scale":    str(shot.get("scale", shot.get("shot_scale", ""))).upper(),
                        "movement": str(shot.get("movement", shot.get("shot_movement", ""))).lower(),
                    })
            except Exception as e:
                print(f"  [경고] {json_file.name} 파싱 실패: {e}", file=sys.stderr)

    # 2) CSV 형식
    csv_file = annotations_dir / "shot_type.csv"
    if csv_file.is_file():
        import csv
        with csv_file.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append({
                    "movie_id": row.get("movie_id", ""),
                    "shot_id":  row.get("shot_id", ""),
                    "scale":    row.get("scale", row.get("shot_scale", "")).upper(),
                    "movement": row.get("movement", row.get("shot_movement", "")).lower(),
                })

    if not records:
        print("[오류] 어노테이션을 찾지 못했습니다.", file=sys.stderr)
        print("  예상 경로:", annotations_dir / "shot_type", file=sys.stderr)
        sys.exit(1)

    print(f"[로드] 총 {len(records):,}개 샷 어노테이션")
    return records


# ── 키프레임 경로 탐색 ───────────────────────────────────────────────────────

def find_keyframe(keyframes_dir: Path, movie_id: str, shot_id: str) -> Path | None:
    """MovieNet 키프레임 이미지 경로를 찾습니다."""
    candidates = [
        keyframes_dir / movie_id / f"{shot_id}.jpg",
        keyframes_dir / movie_id / f"{shot_id}_0.jpg",
        keyframes_dir / movie_id / f"shot_{shot_id}.jpg",
        keyframes_dir / f"{movie_id}_{shot_id}.jpg",
    ]
    for path in candidates:
        if path.is_file():
            return path
    # glob fallback
    matches = list(keyframes_dir.glob(f"{movie_id}/{shot_id}*.jpg"))
    return matches[0] if matches else None


# ── 샘플 선택 (클래스 균형) ──────────────────────────────────────────────────

def balanced_sample(records: list[dict], count: int, seed: int = 42) -> list[dict]:
    """
    shotSize 클래스별로 균형 잡힌 샘플을 선택합니다.
    motion(ambiguous)은 별도 처리 버킷으로 분리됩니다.
    """
    rng = random.Random(seed)

    # 유효한 레코드만 추출
    valid = []
    for r in records:
        ss = SHOT_SIZE_MAP.get(r["scale"])
        mv = MOVEMENT_MAP.get(r["movement"])
        # motion은 제외 (ambiguous)
        if ss and mv is not None:
            valid.append({**r, "_shotSize": ss, "_movement": mv})

    # 클래스별 버킷
    buckets: dict[str, list] = defaultdict(list)
    for r in valid:
        buckets[r["_shotSize"]].append(r)

    print(f"  유효 레코드: {len(valid):,}개 (motion 제외)")
    for cls, items in sorted(buckets.items()):
        print(f"  {cls}: {len(items):,}개")

    # 클래스별 균등 할당
    per_class = max(1, count // len(buckets))
    selected = []
    for cls_records in buckets.values():
        take = min(per_class, len(cls_records))
        selected.extend(rng.sample(cls_records, take))

    # 부족하면 추가로 채움
    remaining = count - len(selected)
    if remaining > 0:
        pool = [r for r in valid if r not in selected]
        selected.extend(rng.sample(pool, min(remaining, len(pool))))

    rng.shuffle(selected)
    return selected[:count]


# ── StoryFrame 레코드 생성 ───────────────────────────────────────────────────

def to_storyframe_record(
    index: int,
    record: dict,
    split: str,
    keyframe_path: Path | None,
    output_dir: Path,
) -> dict:
    """MovieNet 샷 레코드를 StoryFrame 벤치마크 레코드로 변환합니다."""
    shot_size = record["_shotSize"]
    movement  = record["_movement"]
    movie_id  = record["movie_id"]
    shot_id   = record["shot_id"]

    sample_id = f"movienet_{movie_id}_{shot_id}"
    rel_path  = f"dataset/curated/{split}/{sample_id}.jpg"

    # 키프레임 복사
    if keyframe_path and keyframe_path.is_file():
        dest = output_dir / f"{sample_id}.jpg"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(keyframe_path, dest)

    return {
        "id": sample_id,
        "split": split,
        "source": "movienet",
        "source_url": f"https://opendatalab.com/OpenDataLab/MovieNet",
        "license": "MovieNet Research License (non-commercial research use)",
        "media_type": "image",
        "file_path": rel_path,
        "notes": f"MovieNet {movie_id} shot {shot_id} | scale={record['scale']} movement={record['movement']}",
        "labels": {
            "shotSize":          shot_size,
            "framing":           "",   # MovieNet에 없음 — 수동 보완 필요
            "movement":          movement,
            "lensType":          "",   # MovieNet에 없음
            "angle":             "",   # MovieNet에 없음
            "dof":               "",   # MovieNet에 없음
            "lightingType":      "",   # MovieNet에 없음
            "lightingCondition": "",   # MovieNet에 없음
            "composition":       "",   # MovieNet에 없음
        },
        "flags": {
            "ambiguous_shotSize": False,
            "ambiguous_lens":     False,
            "ambiguous_lighting": False,
            "exclude_from_benchmark": False,
        },
    }


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="MovieNet 어노테이션을 StoryFrame 벤치마크 JSON으로 변환"
    )
    parser.add_argument("--annotations", required=True,
                        help="MovieNet annotations 디렉터리 경로")
    parser.add_argument("--keyframes", default=None,
                        help="MovieNet keyframe_240P 디렉터리 경로 (선택)")
    parser.add_argument("--output", required=True,
                        help="출력 이미지 디렉터리 (benchmark/dev/holdout 등)")
    parser.add_argument("--labels-out", default=None,
                        help="레이블 JSON 출력 경로 (기본: output/../labels/benchmark.json)")
    parser.add_argument("--count", type=int, default=150,
                        help="샘플 수 (기본 150 = benchmark 권장)")
    parser.add_argument("--split", default="benchmark",
                        choices=list(SPLIT_OPTIONS),
                        help="데이터 분할 (기본: benchmark)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    annotations_dir = Path(args.annotations)
    keyframes_dir   = Path(args.keyframes) if args.keyframes else None
    output_dir      = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_out = Path(args.labels_out) if args.labels_out else \
                 output_dir.parent.parent / "labels" / f"{args.split}.json"
    labels_out.parent.mkdir(parents=True, exist_ok=True)

    # 1. 어노테이션 로드
    records = load_movienet_annotations(annotations_dir)

    # 2. 균형 샘플 선택
    print(f"\n[샘플링] {args.count}개 선택 (split={args.split})")
    selected = balanced_sample(records, args.count, seed=args.seed)
    print(f"  선택됨: {len(selected)}개")

    # 3. StoryFrame 레코드 변환
    sf_records = []
    missing_kf = 0
    for i, rec in enumerate(selected):
        kf_path = None
        if keyframes_dir:
            kf_path = find_keyframe(keyframes_dir, rec["movie_id"], rec["shot_id"])
            if kf_path is None:
                missing_kf += 1

        sf_rec = to_storyframe_record(i, rec, args.split, kf_path, output_dir)
        sf_records.append(sf_rec)

    # 4. 레이블 JSON 저장
    output_json = {
        "version": 1,
        "split": args.split,
        "source": "movienet",
        "count": len(sf_records),
        "records": sf_records,
    }
    labels_out.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 5. 결과 요약
    print(f"\n[완료]")
    print(f"  레코드 수:         {len(sf_records)}")
    print(f"  레이블 JSON:       {labels_out}")
    print(f"  이미지 디렉터리:   {output_dir}")
    if keyframes_dir:
        print(f"  키프레임 누락:     {missing_kf}개")

    # 클래스 분포 출력
    from collections import Counter
    dist = Counter(r["labels"]["shotSize"] for r in sf_records)
    print("\n샷사이즈 분포:")
    for cls, cnt in sorted(dist.items()):
        print(f"  {cls:15s}: {cnt}")

    print("\n다음 단계:")
    print("  1. 이미지를 StoryFrame 앱에서 열고 씬 분석 실행")
    print("  2. '평가용 프로젝트 저장' 으로 project.json 내보내기")
    print("  3. npm run benchmark:evaluate -- --benchmark", labels_out,
          "--detected project.json")


if __name__ == "__main__":
    main()
