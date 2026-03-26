#!/usr/bin/env python3
"""
HuggingFace types-of-film-shots → StoryFrame Benchmark Converter
=================================================================

데이터셋: szymonrucinski/types-of-film-shots
라이선스: CC-BY-4.0
크기: ~148MB, 925개 이미지
다운로드: pip install datasets → 자동

카테고리 매핑:
  closeUp      → CU
  detail       → INSERT   (물체/디테일 클로즈업)
  extremeLongShot → ELS
  fullShot     → FS
  longShot     → LS
  mediumCloseUp → MCU
  mediumShot   → MS
  ambiguous    → (제외)

사용:
  pip install datasets pillow
  python scripts/hf_to_storyframe.py --output ./dataset/curated/benchmark --count 150
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path
import random

LABEL_MAP = {
    "closeUp":        "CU",
    "detail":         "INSERT",
    "extremeLongShot":"ELS",
    "fullShot":       "FS",
    "longShot":       "LS",
    "mediumCloseUp":  "MCU",
    "mediumShot":     "MS",
    "ambiguous":      None,   # 제외
}

# HF ClassLabel 인덱스 → 문자열 (데이터셋 기준)
IDX_TO_NAME = {
    0: "ambiguous",
    1: "closeUp",
    2: "detail",
    3: "extremeLongShot",
    4: "fullShot",
    5: "longShot",
    6: "mediumCloseUp",
    7: "mediumShot",
}


def load_hf_dataset():
    try:
        from datasets import load_dataset
    except ImportError:
        print("[오류] datasets 라이브러리가 없습니다. 설치:", file=sys.stderr)
        print("  pip install datasets pillow", file=sys.stderr)
        sys.exit(1)

    print("[다운로드] szymonrucinski/types-of-film-shots ...")
    ds = load_dataset("szymonrucinski/types-of-film-shots", split="train")
    print(f"[로드] 총 {len(ds)}개 샘플")
    return ds


def balanced_sample(dataset, count: int, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)

    # label 필드 처리: int 또는 str 모두 대응
    buckets: dict[str, list] = defaultdict(list)
    for i, row in enumerate(dataset):
        raw_label = row.get("label", row.get("class", ""))
        if isinstance(raw_label, int):
            label_str = IDX_TO_NAME.get(raw_label, "ambiguous")
        else:
            label_str = str(raw_label)

        sf_label = LABEL_MAP.get(label_str)
        if sf_label is None:
            continue  # ambiguous 제외

        buckets[sf_label].append({"idx": i, "row": row, "hf_label": label_str, "sf_label": sf_label})

    print("\n전체 분포:")
    for cls, items in sorted(buckets.items()):
        print(f"  {cls:20s}: {len(items)}")

    # 균형 샘플링
    per_class = max(1, count // len(buckets))
    selected = []
    for items in buckets.values():
        take = min(per_class, len(items))
        selected.extend(rng.sample(items, take))

    remaining = count - len(selected)
    if remaining > 0:
        pool = [x for items in buckets.values() for x in items if x not in selected]
        selected.extend(rng.sample(pool, min(remaining, len(pool))))

    rng.shuffle(selected)
    return selected[:count]


def save_image(row, dest_path: Path):
    """PIL Image를 파일로 저장."""
    try:
        img = row.get("image")
        if img is None:
            return False
        if hasattr(img, "save"):
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(dest_path), "JPEG", quality=92)
            return True
        # bytes 형식
        if isinstance(img, (bytes, bytearray)):
            from PIL import Image
            import io
            Image.open(io.BytesIO(img)).save(str(dest_path), "JPEG", quality=92)
            return True
    except Exception as e:
        print(f"  [경고] 이미지 저장 실패: {e}", file=sys.stderr)
    return False


def to_storyframe_record(index: int, item: dict, split: str,
                          image_saved: bool, output_dir: Path) -> dict:
    sf_label = item["sf_label"]
    sample_id = f"hf_filmshots_{index:04d}"
    rel_path = f"dataset/curated/{split}/{sample_id}.jpg"

    return {
        "id": sample_id,
        "split": split,
        "source": "huggingface_types-of-film-shots",
        "source_url": "https://huggingface.co/datasets/szymonrucinski/types-of-film-shots",
        "license": "CC-BY-4.0",
        "media_type": "image",
        "file_path": rel_path,
        "notes": f"HF label: {item['hf_label']}",
        "labels": {
            "shotSize":          sf_label,
            "framing":           "",
            "movement":          "Static",  # 스틸 이미지이므로
            "lensType":          "",
            "angle":             "",
            "dof":               "",
            "lightingType":      "",
            "lightingCondition": "",
            "composition":       "",
        },
        "flags": {
            "ambiguous_shotSize":       False,
            "ambiguous_lens":           False,
            "ambiguous_lighting":       False,
            "exclude_from_benchmark":   not image_saved,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="HuggingFace types-of-film-shots → StoryFrame 벤치마크"
    )
    parser.add_argument("--output", required=True,
                        help="출력 이미지 디렉터리 (예: ./dataset/curated/benchmark)")
    parser.add_argument("--labels-out", default=None,
                        help="레이블 JSON 경로 (기본: output/../../labels/benchmark.json)")
    parser.add_argument("--count", type=int, default=150)
    parser.add_argument("--split", default="benchmark",
                        choices=["benchmark", "dev", "holdout"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-images", action="store_true",
                        help="이미지 저장 생략 (레이블만 생성)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels_out = Path(args.labels_out) if args.labels_out else \
                 output_dir.parent.parent / "labels" / f"{args.split}_hf.json"
    labels_out.parent.mkdir(parents=True, exist_ok=True)

    ds = load_hf_dataset()
    print(f"\n[샘플링] {args.count}개 균형 선택 ...")
    selected = balanced_sample(ds, args.count, seed=args.seed)
    print(f"  선택: {len(selected)}개")

    sf_records = []
    saved_count = 0
    for i, item in enumerate(selected):
        img_path = output_dir / f"hf_filmshots_{i:04d}.jpg"
        image_saved = False
        if not args.no_images:
            image_saved = save_image(item["row"], img_path)
            if image_saved:
                saved_count += 1

        sf_rec = to_storyframe_record(i, item, args.split, image_saved, output_dir)
        sf_records.append(sf_rec)

    output_json = {
        "version": 1,
        "split": args.split,
        "source": "huggingface_types-of-film-shots",
        "count": len(sf_records),
        "records": sf_records,
    }
    labels_out.write_text(
        json.dumps(output_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n[완료]")
    print(f"  레코드: {len(sf_records)}개")
    print(f"  이미지 저장: {saved_count}개")
    print(f"  레이블 JSON: {labels_out}")

    dist = Counter(r["labels"]["shotSize"] for r in sf_records)
    print("\n샷사이즈 분포:")
    for cls, cnt in sorted(dist.items()):
        print(f"  {cls:20s}: {cnt}")

    print("\n다음 단계:")
    print("  1. StoryFrame 앱에서 이미지 폴더 로드 후 씬 분석")
    print("  2. '평가용 프로젝트 저장'으로 project.json 내보내기")
    print(f"  3. npm run benchmark:evaluate -- --benchmark {labels_out} --detected project.json")


if __name__ == "__main__":
    main()
