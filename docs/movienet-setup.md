# MovieNet → StoryFrame 벤치마크 구축 가이드

MovieNet(46K 샷 어노테이션)을 활용해 StoryFrame의 shotSize·movement 인식 정확도를 측정합니다.

## MovieNet이 제공하는 것

| 항목 | StoryFrame 매핑 |
|------|----------------|
| ECS (Extreme Close-up Shot) | ECU |
| CS (Close-up Shot) | CU |
| MS (Medium Shot) | MS |
| FS (Full Shot) | FS |
| LS (Long Shot) | LS |
| Static | Static |
| Push | Push-in |
| Pull | Pull-out |
| Motion | (ambiguous → 제외) |

**없는 것**: framing, angle, lensType, dof, lightingType, lightingCondition, composition
→ 이 필드는 다른 소스(Pexels 등)로 보완 필요

---

## Step 1. OpenDataLab 계정 및 CLI 설치

```bash
pip install opendatalab
odl login
# 브라우저로 https://opendatalab.com/ 가입 후 로그인
```

---

## Step 2. 데이터 다운로드

**어노테이션만 (필수, ~53MB 압축)**
```bash
odl get OpenDataLab/MovieNet --split annotations
```

**키프레임 이미지 (선택, 240p)**
```bash
# 전체 다운로드 (대용량 주의)
odl get OpenDataLab/MovieNet --split keyframe_240P

# 특정 영화만 (권장)
odl get OpenDataLab/MovieNet --split keyframe_240P --filter "tt0111161*"
```

다운로드 후 폴더 구조:
```
MovieNet/
  annotations/
    shot_type/       ← 이 폴더가 핵심
      tt0111161.json
      tt0468569.json
      ...
  keyframe_240P/
    tt0111161/
      0001.jpg
      0002.jpg
      ...
```

---

## Step 3. 벤치마크 변환

```bash
# 기본 (이미지 없이 레이블만, 150개)
python scripts/movienet_to_storyframe.py \
    --annotations ./MovieNet/annotations \
    --output ./dataset/curated/benchmark \
    --count 150 \
    --split benchmark

# 키프레임 포함 (이미지도 복사)
python scripts/movienet_to_storyframe.py \
    --annotations ./MovieNet/annotations \
    --keyframes   ./MovieNet/keyframe_240P \
    --output      ./dataset/curated/benchmark \
    --count 150 \
    --split benchmark

# dev 세트 (700개)
python scripts/movienet_to_storyframe.py \
    --annotations ./MovieNet/annotations \
    --keyframes   ./MovieNet/keyframe_240P \
    --output      ./dataset/curated/dev \
    --count 700 \
    --split dev \
    --seed 123
```

결과물:
```
dataset/
  curated/benchmark/
    movienet_tt0111161_0001.jpg
    ...
  labels/
    benchmark.json   ← StoryFrame 벤치마크 레이블
```

---

## Step 4. StoryFrame에서 분석

1. StoryFrame 앱에서 벤치마크 이미지 폴더를 프로젝트로 로드
2. 씬 자동 분석 실행
3. **'평가용 프로젝트 저장'** 클릭 → `project.json` 내보내기

---

## Step 5. 정확도 평가

```bash
npm run benchmark:evaluate -- \
    --benchmark dataset/labels/benchmark.json \
    --detected  project.json
```

출력 예시:
```
Per-field accuracy
- shot: 72% (108/150)
- movement: 85% (127/150)
```

---

## 한계 및 주의사항

1. **MovieNet은 5단계 샷사이즈만 제공** — BCU, MCU, Cowboy, MLS, ELS 등은 직접 레이블 필요
2. **movement=motion은 ambiguous** — 자동으로 제외됨 (Pan/Tilt/Tracking 구분 불가)
3. **라이선스**: MovieNet은 non-commercial research 전용. 데이터셋 계획(`cinematography-dataset-plan.md`)의 licensing rule 준수 필수
4. 실제 영화 장면이므로 `lightingCondition`, `dof` 등은 수동 검수 후 추가 가능
