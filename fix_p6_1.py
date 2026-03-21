# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# P6-1: 샷 사이즈 경로 임계값 통일
#
# 핵심 수정:
#   1. 포즈 경로 교차검증(crossConf)에서 face 임계값 정렬
#      - proportionFactor 적용 (adjFh2)
#      - 임계값 포즈 경로와 일치: 0.8→0.72, 0.6→0.55, 0.4→0.38, 0.26→0.22
#   2. Face-only 독립 경로 임계값도 동일하게 정렬
#      - 두 경로 전환 시 샷 카테고리 점프 방지

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()
original = content

# ─────────────────────────────────────────────────────────────────────
# 1. 포즈 교차검증 블록: adjFh2 추가 + 정렬된 임계값
# ─────────────────────────────────────────────────────────────────────
old_cross = (
    b"    if (faceAnalysis?.count > 0 && !isGroupShot) {\r\n"
    b"      const fh2 = faceAnalysis.maxHeightRatio;\r\n"
    b"      const fa2 = faceAnalysis.largestAreaRatio;\r\n"
    b"      let fType = 'MS';\r\n"
    b"      if (fh2 > 0.8 || fa2 > 0.5) fType = 'ECU';\r\n"
    b"      else if (fh2 > 0.6 || fa2 > 0.3) fType = 'BCU';\r\n"
    b"      else if (fh2 > 0.4 || fa2 > 0.17) fType = 'CU';\r\n"
    b"      else if (fh2 > 0.26 || fa2 > 0.095) fType = 'MCU';\r\n"
    b"      else if (fh2 > 0.17 || fa2 > 0.055) fType = 'MS';\r\n"
    b"      else if (fh2 > 0.11 || fa2 > 0.028) fType = 'Cowboy';\r\n"
    b"      else if (fh2 > 0.075 || fa2 > 0.016) fType = 'MLS';\r\n"
    b"      else if (fh2 > 0.05 || fa2 > 0.008) fType = 'FS';\r\n"
    b"      else if (fh2 > 0.03 || fa2 > 0.004) fType = 'LS';\r\n"
    b"      else fType = 'ELS';\r\n"
)
new_cross = (
    b"    if (faceAnalysis?.count > 0 && !isGroupShot) {\r\n"
    b"      const fh2 = faceAnalysis.maxHeightRatio;\r\n"
    b"      const fa2 = faceAnalysis.largestAreaRatio;\r\n"
    b"      // Apply same animation correction for consistent cross-validation\r\n"
    b"      const adjFh2 = proportionFactor > 1.0 ? fh2 / proportionFactor : fh2;\r\n"
    b"      let fType = 'MS';\r\n"
    b"      // Aligned thresholds matching pose path adjustedFaceH scale\r\n"
    b"      if (adjFh2 >= 0.72 || fa2 > 0.5) fType = 'ECU';\r\n"
    b"      else if (adjFh2 >= 0.55 || fa2 > 0.3) fType = 'BCU';\r\n"
    b"      else if (adjFh2 >= 0.38 || fa2 > 0.17) fType = 'CU';\r\n"
    b"      else if (adjFh2 >= 0.22 || fa2 > 0.095) fType = 'MCU';\r\n"
    b"      else if (adjFh2 >= 0.15 || fa2 > 0.055) fType = 'MS';\r\n"
    b"      else if (adjFh2 >= 0.10 || fa2 > 0.028) fType = 'Cowboy';\r\n"
    b"      else if (adjFh2 >= 0.07 || fa2 > 0.016) fType = 'MLS';\r\n"
    b"      else if (adjFh2 >= 0.045 || fa2 > 0.008) fType = 'FS';\r\n"
    b"      else if (adjFh2 >= 0.025 || fa2 > 0.004) fType = 'LS';\r\n"
    b"      else fType = 'ELS';\r\n"
)
assert old_cross in content, "cross-validation block not found"
content = content.replace(old_cross, new_cross, 1)
print("1. Pose cross-check: adjFh2 + aligned thresholds (0.8->0.72, 0.6->0.55, 0.4->0.38, 0.26->0.22)")

# ─────────────────────────────────────────────────────────────────────
# 2. Face-only 독립 경로 임계값 정렬
# ─────────────────────────────────────────────────────────────────────
old_thresholds = (
    b"    if (faceHeight > 0.8 || faceArea > 0.5) type = 'ECU';\r\n"
    b"    else if (faceHeight > 0.6 || faceArea > 0.3) type = 'BCU';\r\n"
    b"    else if (faceHeight > 0.4 || faceArea > 0.17) type = 'CU';\r\n"
    b"    else if (faceHeight > 0.26 || faceArea > 0.095) type = 'MCU';\r\n"
    b"    else if (faceHeight > 0.17 || faceArea > 0.055) type = 'MS';\r\n"
    b"    else if (faceHeight > 0.11 || faceArea > 0.028) type = 'Cowboy';\r\n"
    b"    else if (faceHeight > 0.075 || faceArea > 0.016) type = 'MLS';\r\n"
    b"    else if (faceHeight > 0.05 || faceArea > 0.008) type = 'FS';\r\n"
    b"    else if (faceHeight > 0.03 || faceArea > 0.004) type = 'LS';\r\n"
    b"    else type = 'ELS';\r\n"
)
new_thresholds = (
    b"    // Thresholds aligned to pose path adjustedFaceH scale (prevents jump on path switch)\r\n"
    b"    if (faceHeight >= 0.72 || faceArea > 0.5) type = 'ECU';\r\n"
    b"    else if (faceHeight >= 0.55 || faceArea > 0.3) type = 'BCU';\r\n"
    b"    else if (faceHeight >= 0.38 || faceArea > 0.17) type = 'CU';\r\n"
    b"    else if (faceHeight >= 0.22 || faceArea > 0.095) type = 'MCU';\r\n"
    b"    else if (faceHeight >= 0.15 || faceArea > 0.055) type = 'MS';\r\n"
    b"    else if (faceHeight >= 0.10 || faceArea > 0.028) type = 'Cowboy';\r\n"
    b"    else if (faceHeight >= 0.07 || faceArea > 0.016) type = 'MLS';\r\n"
    b"    else if (faceHeight >= 0.045 || faceArea > 0.008) type = 'FS';\r\n"
    b"    else if (faceHeight >= 0.025 || faceArea > 0.004) type = 'LS';\r\n"
    b"    else type = 'ELS';\r\n"
)
assert old_thresholds in content, "face-only thresholds not found"
content = content.replace(old_thresholds, new_thresholds, 1)
print("2. Face-only path: thresholds aligned to pose path scale")

# ─────────────────────────────────────────────────────────────────────
# 3. FACE_BOUNDS도 정렬된 임계값으로 업데이트
# ─────────────────────────────────────────────────────────────────────
old_bounds = b"    const FACE_BOUNDS = [0.8, 0.6, 0.4, 0.26, 0.17, 0.11, 0.075, 0.05, 0.03];\r\n"
new_bounds = b"    const FACE_BOUNDS = [0.72, 0.55, 0.38, 0.22, 0.15, 0.10, 0.07, 0.045, 0.025];\r\n"
assert old_bounds in content, "FACE_BOUNDS not found"
content = content.replace(old_bounds, new_bounds, 1)
print("3. FACE_BOUNDS: updated to match aligned thresholds")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP6-1 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
