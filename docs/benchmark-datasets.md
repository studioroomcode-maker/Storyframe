# StoryFrame 벤치마크 데이터셋 가이드

Papers With Code 및 연구 데이터셋에서 수집한 소스를 기반으로
StoryFrame 인식 정확도를 측정하는 벤치마크 파이프라인입니다.

---

## 사용 가능한 데이터셋 요약

| 소스 | 크기 | 라이선스 | shotSize | movement | 이미지 포함 |
|------|------|----------|----------|----------|------------|
| **HuggingFace types-of-film-shots** | 925장 | CC-BY-4.0 | 7종 | - | ✅ 자동 |
| **MovieNet (MovieShots)** | 46K 샷 | Research | 5종 | 4종 | 계정 필요 |
| **HISTORIAN (tiny)** | 10K 샷 | CC-BY-4.0 | 표준 | 8종 | ffmpeg 필요 |
| **CineScale** | 792K 프레임 | Research | 9종 | - | 저자 문의 |
| **CineScale2** | 25K 프레임 | Research | - | angle/level | 저자 문의 |

---

## 카테고리 매핑표

### shotSize 매핑

| 원본 라벨 | 소스 | StoryFrame |
|----------|------|-----------|
| closeUp | HuggingFace | CU |
| detail | HuggingFace | INSERT |
| extremeLongShot | HuggingFace | ELS |
| fullShot | HuggingFace | FS |
| longShot | HuggingFace | LS |
| mediumCloseUp | HuggingFace | MCU |
| mediumShot | HuggingFace | MS |
| ECS | MovieNet | ECU |
| CS | MovieNet | CU |
| MS | MovieNet | MS |
| FS | MovieNet | FS |
| LS | MovieNet | LS |
| ECU/CU/MCU/MS/MLS/FS/LS/ELS | HISTORIAN | 동일 |

### movement 매핑

| 원본 라벨 | 소스 | StoryFrame |
|----------|------|-----------|
| static | MovieNet/HISTORIAN | Static |
| push | MovieNet | Push-in |
| pull | MovieNet | Pull-out |
| motion | MovieNet | (제외 - ambiguous) |
| pan | HISTORIAN | Pan |
| tilt | HISTORIAN | Tilt |
| zoom_in / zoom | HISTORIAN | Zoom-in |
| zoom_out | HISTORIAN | Zoom-out |
| dolly / tracking | HISTORIAN | Tracking |
| handheld | HISTORIAN | Handheld |
| crane | HISTORIAN | Crane |

---

## 즉시 시작: HuggingFace만 사용 (가장 빠름)

```bash
pip install datasets pillow

python scripts/hf_to_storyframe.py \
    --output ./dataset/curated/benchmark \
    --count 150 \
    --split benchmark
```

레이블 자동 생성: `dataset/labels/benchmark_hf.json`

---

## 전체 파이프라인 (3개 소스 통합)

### 1단계: 준비

```bash
# HuggingFace + HISTORIAN만 사용 (계정 불필요)
pip install datasets pillow

# HISTORIAN tiny 다운로드 (425MB, CC-BY-4.0)
# 브라우저에서 직접: https://zenodo.org/records/6184281
# 또는:
curl -L -o historian_tiny.zip \
  "https://zenodo.org/records/6184281/files/historian_dataset_v1_tiny_pre.zip"
unzip historian_tiny.zip -d ./historian_tiny
```

### 2단계: 통합 빌드

```bash
# HuggingFace + HISTORIAN 조합 (이미지 추출 포함)
python scripts/build_benchmark.py \
    --hf \
    --historian-dataset ./historian_tiny \
    --extract-frames \
    --output ./dataset \
    --benchmark-size 150 \
    --dev-size 500 \
    --holdout-size 150

# MovieNet도 추가 (계정 있는 경우)
python scripts/build_benchmark.py \
    --hf \
    --movienet-annotations ./MovieNet/annotations \
    --movienet-keyframes   ./MovieNet/keyframe_240P \
    --historian-dataset    ./historian_tiny \
    --extract-frames \
    --output ./dataset \
    --benchmark-size 150 \
    --dev-size 700
```

### 3단계: StoryFrame에서 분석

1. StoryFrame 앱 실행
2. `dataset/curated/benchmark/` 폴더의 이미지를 프로젝트로 로드
3. 씬 자동 분석 실행
4. **'평가용 프로젝트 저장'** → `project.json` 내보내기

### 4단계: 정확도 평가

```bash
npm run benchmark:evaluate -- \
    --benchmark dataset/labels/benchmark.json \
    --detected  project.json
```

---

## 데이터 한계

| 필드 | HuggingFace | MovieNet | HISTORIAN | 비고 |
|------|-------------|----------|-----------|------|
| shotSize | ✅ 7종 | ✅ 5종 | ✅ 표준 | BCU, Cowboy, MLS 부족 |
| movement | ❌ | ✅ 4종 | ✅ 8종 | Handheld/Drone 부족 |
| angle | ❌ | ❌ | ❌ | CineScale2 필요 |
| lensType | ❌ | ❌ | ❌ | 수동 레이블 필요 |
| dof | ❌ | ❌ | ❌ | 수동 레이블 필요 |
| lightingType | ❌ | ❌ | ❌ | 수동 레이블 필요 |
| lightingCondition | ❌ | ❌ | ❌ | 수동 레이블 필요 |
| framing | ❌ | ❌ | ❌ | 수동 레이블 필요 |
| composition | ❌ | ❌ | ❌ | 수동 레이블 필요 |

**결론**: 자동화 데이터셋으로는 `shotSize`와 `movement` 개선에 집중하고,
나머지 필드는 Pexels 등에서 수동 수집·레이블링 필요.

---

## 스크립트 목록

| 스크립트 | 용도 |
|---------|------|
| `scripts/hf_to_storyframe.py` | HuggingFace 변환 (이미지 자동 다운로드) |
| `scripts/movienet_to_storyframe.py` | MovieNet 변환 (계정 필요) |
| `scripts/historian_to_storyframe.py` | HISTORIAN 변환 (ffmpeg로 키프레임 추출) |
| `scripts/build_benchmark.py` | 3개 소스 통합 빌더 |
| `scripts/evaluate-benchmark.js` | 벤치마크 평가 (기존) |
