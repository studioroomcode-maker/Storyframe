#!/usr/bin/env python3
"""
Multi-Source Benchmark Builder
================================
MovieNet + HuggingFace + HISTORIAN 3개 소스를 합쳐
StoryFrame 벤치마크/dev/holdout 세트를 구축합니다.

사용법:
  python scripts/build_benchmark.py \
      --movienet-annotations ./MovieNet/annotations \
      --movienet-keyframes   ./MovieNet/keyframe_240P \
      --historian-dataset    ./historian_tiny \
      --historian-frames     (--extract-frames 플래그 추가 시 ffmpeg 필요) \
      --hf                   (HuggingFace 자동 다운로드) \
      --output               ./dataset \
      --benchmark-size 150 \
      --dev-size 700

결과:
  dataset/
    curated/
      benchmark/  ← 이미지들
      dev/
      holdout/
    labels/
      benchmark.json
      dev.json
      holdout.json
      combined_stats.json
"""

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path
from collections import Counter


def run_script(script: str, args_list: list[str]) -> bool:
    cmd = [sys.executable, script] + args_list
    print(f"\n{'='*60}")
    print(f"실행: {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd)
    return result.returncode == 0


def merge_label_files(label_files: list[Path], output_path: Path, split: str):
    """여러 소스의 레이블 JSON을 하나로 병합합니다."""
    all_records = []
    for lf in label_files:
        if not lf.exists():
            print(f"  [건너뜀] {lf} 없음")
            continue
        data = json.loads(lf.read_text(encoding="utf-8"))
        records = data.get("records", data if isinstance(data, list) else [])
        all_records.extend(records)
        print(f"  {lf.name}: {len(records)}개")

    # 중복 제거
    seen_ids = set()
    unique = []
    for r in all_records:
        rid = r.get("id", "")
        if rid not in seen_ids:
            seen_ids.add(rid)
            unique.append(r)

    merged = {
        "version": 1,
        "split": split,
        "source": "combined",
        "count": len(unique),
        "records": unique,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n병합 완료: {len(unique)}개 → {output_path}")
    return unique


def print_stats(records: list[dict], title: str):
    print(f"\n{'─'*50}")
    print(f"{title}")
    print(f"{'─'*50}")
    print(f"총 레코드: {len(records)}")

    source_dist = Counter(r.get("source", "unknown") for r in records)
    print("\n소스별:")
    for src, cnt in sorted(source_dist.items()):
        print(f"  {src:45s}: {cnt}")

    shot_dist = Counter(
        r.get("labels", {}).get("shotSize", "") for r in records if r.get("labels", {}).get("shotSize")
    )
    print("\nshotSize 분포:")
    for cls, cnt in sorted(shot_dist.items()):
        bar = "█" * min(cnt, 40)
        print(f"  {cls:20s}: {cnt:4d} {bar}")

    move_dist = Counter(
        r.get("labels", {}).get("movement", "") for r in records if r.get("labels", {}).get("movement")
    )
    print("\nmovement 분포:")
    for cls, cnt in sorted(move_dist.items()):
        bar = "█" * min(cnt, 40)
        print(f"  {cls:20s}: {cnt:4d} {bar}")


def main():
    parser = argparse.ArgumentParser(
        description="다중 소스 → StoryFrame 벤치마크 통합 빌더"
    )
    # 소스 선택
    parser.add_argument("--hf", action="store_true",
                        help="HuggingFace types-of-film-shots 포함")
    parser.add_argument("--movienet-annotations", default=None,
                        help="MovieNet annotations 경로")
    parser.add_argument("--movienet-keyframes", default=None,
                        help="MovieNet keyframe_240P 경로 (선택)")
    parser.add_argument("--historian-dataset", default=None,
                        help="HISTORIAN 데이터셋 경로")
    parser.add_argument("--extract-frames", action="store_true",
                        help="HISTORIAN: ffmpeg로 키프레임 추출")

    # 세트 크기
    parser.add_argument("--benchmark-size", type=int, default=150)
    parser.add_argument("--dev-size",       type=int, default=500)
    parser.add_argument("--holdout-size",   type=int, default=150)

    parser.add_argument("--output", required=True,
                        help="dataset 루트 경로")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    scripts_dir  = Path(__file__).parent
    output_dir   = Path(args.output)
    labels_dir   = output_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    per_source_bench  = args.benchmark_size  // max(1, sum([args.hf, bool(args.movienet_annotations), bool(args.historian_dataset)]))
    per_source_dev    = args.dev_size        // max(1, sum([args.hf, bool(args.movienet_annotations), bool(args.historian_dataset)]))
    per_source_hold   = args.holdout_size    // max(1, sum([args.hf, bool(args.movienet_annotations), bool(args.historian_dataset)]))

    bench_files   = []
    dev_files     = []
    holdout_files = []

    # ── HuggingFace ──────────────────────────────────────────────────────────
    if args.hf:
        print("\n[소스 1/3] HuggingFace types-of-film-shots")
        for split, size, file_list in [
            ("benchmark", per_source_bench, bench_files),
            ("dev",       per_source_dev,   dev_files),
            ("holdout",   per_source_hold,  holdout_files),
        ]:
            lf = labels_dir / f"{split}_hf.json"
            img_dir = output_dir / "curated" / split
            run_script(
                str(scripts_dir / "hf_to_storyframe.py"),
                ["--output", str(img_dir),
                 "--labels-out", str(lf),
                 "--count", str(size),
                 "--split", split,
                 "--seed", str(args.seed)]
            )
            file_list.append(lf)

    # ── MovieNet ─────────────────────────────────────────────────────────────
    if args.movienet_annotations:
        print("\n[소스 2/3] MovieNet")
        for split, size, file_list in [
            ("benchmark", per_source_bench, bench_files),
            ("dev",       per_source_dev,   dev_files),
            ("holdout",   per_source_hold,  holdout_files),
        ]:
            lf = labels_dir / f"{split}_movienet.json"
            img_dir = output_dir / "curated" / split
            script_args = [
                "--annotations", args.movienet_annotations,
                "--output", str(img_dir),
                "--labels-out", str(lf),
                "--count", str(size),
                "--split", split,
                "--seed", str(args.seed),
            ]
            if args.movienet_keyframes:
                script_args += ["--keyframes", args.movienet_keyframes]
            run_script(str(scripts_dir / "movienet_to_storyframe.py"), script_args)
            file_list.append(lf)

    # ── HISTORIAN ────────────────────────────────────────────────────────────
    if args.historian_dataset:
        print("\n[소스 3/3] HISTORIAN")
        for split, size, file_list in [
            ("benchmark", per_source_bench, bench_files),
            ("dev",       per_source_dev,   dev_files),
            ("holdout",   per_source_hold,  holdout_files),
        ]:
            lf = labels_dir / f"{split}_historian.json"
            img_dir = output_dir / "curated" / split
            script_args = [
                "--dataset", args.historian_dataset,
                "--output", str(img_dir),
                "--labels-out", str(lf),
                "--count", str(size),
                "--split", split,
                "--seed", str(args.seed),
            ]
            if args.extract_frames:
                script_args.append("--extract-frames")
            run_script(str(scripts_dir / "historian_to_storyframe.py"), script_args)
            file_list.append(lf)

    # ── 병합 ─────────────────────────────────────────────────────────────────
    print("\n\n[병합] 모든 소스 통합 중 ...")

    bench_records   = merge_label_files(bench_files,   labels_dir / "benchmark.json",   "benchmark")
    dev_records     = merge_label_files(dev_files,     labels_dir / "dev.json",         "dev")
    holdout_records = merge_label_files(holdout_files, labels_dir / "holdout.json",     "holdout")

    # 통계
    print_stats(bench_records,   "[ BENCHMARK 세트 ]")
    print_stats(dev_records,     "[ DEV 세트 ]")
    print_stats(holdout_records, "[ HOLDOUT 세트 ]")

    # 통합 통계 저장
    stats = {
        "benchmark": len(bench_records),
        "dev":       len(dev_records),
        "holdout":   len(holdout_records),
        "total":     len(bench_records) + len(dev_records) + len(holdout_records),
        "shotSize_dist_benchmark": dict(
            Counter(r.get("labels", {}).get("shotSize", "") for r in bench_records)
        ),
    }
    (labels_dir / "combined_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n{'='*60}")
    print("데이터셋 구축 완료!")
    print(f"{'='*60}")
    print(f"  benchmark : {len(bench_records)}개  → {labels_dir}/benchmark.json")
    print(f"  dev       : {len(dev_records)}개  → {labels_dir}/dev.json")
    print(f"  holdout   : {len(holdout_records)}개  → {labels_dir}/holdout.json")
    print(f"\n평가 실행:")
    print(f"  npm run benchmark:evaluate -- \\")
    print(f"      --benchmark {labels_dir}/benchmark.json \\")
    print(f"      --detected  <storyframe_project.json>")


if __name__ == "__main__":
    main()
