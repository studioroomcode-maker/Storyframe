#!/usr/bin/env python3
# P3-3: 조명 추정 애니메이션 가드
#
# 핵심 아이디어:
#   셀쉐이딩 애니메이션은 그라디언트 없음 → rimLightStrength ≈ 0
#   → Silhouette 점수 폭락, Flat 점수 과도 상승
#   → 실제로는 방향성 조명(Chiaroscuro/Rembrandt)이지만 Flat으로 잘못 분류
#
# 구현:
#   1. estimateLighting 시그니처에 contentMode 파라미터 추가
#   2. isAnimLighting 체크 추가
#   3. 애니메이션 전용 rimLightStrength 보정 (그라디언트 대신 밝기 비율 사용)
#   4. Silhouette: 애니메이션에서 rim 없이도 어두운 피사체 + 밝은 배경으로 감지
#   5. Flat 점수: 애니메이션에서 modelingAsym 가중치 낮춤 (균일 채색은 의도된 것)
#   6. 두 호출부에 contentMode 전달

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. 함수 시그니처 변경
# ─────────────────────────────────────────────────────────────────────
old_lighting_sig = b"function estimateLighting(colorAnalysis, composition, faceAnalysis, edgeMap, pixels, w, h, poseAnalysis) {\r\n"
new_lighting_sig = b"function estimateLighting(colorAnalysis, composition, faceAnalysis, edgeMap, pixels, w, h, poseAnalysis, contentMode) {\r\n"
assert old_lighting_sig in content, "estimateLighting signature not found"
content = content.replace(old_lighting_sig, new_lighting_sig, 1)
print("1. estimateLighting: contentMode param added")

# ─────────────────────────────────────────────────────────────────────
# 2. isAnimLighting 선언 + 애니메이션 전용 rim 보정 추가
#    rimLightStrength 계산 직후에 삽입
# ─────────────────────────────────────────────────────────────────────
old_rim_line = (
    b"  const subjectShadowRatio = subjectStats?.shadowRatio ?? shadowRatio;\r\n"
    b"  const subjectHighlightRatio = subjectStats?.highlightRatio ?? highlightRatio;\r\n"
)
new_rim_line = (
    b"  const subjectShadowRatio = subjectStats?.shadowRatio ?? shadowRatio;\r\n"
    b"  const subjectHighlightRatio = subjectStats?.highlightRatio ?? highlightRatio;\r\n"
    b"\r\n"
    b"  // P3-3: Animation lighting guard\r\n"
    b"  // Cel-shaded animation has hard edges (no soft gradient), so gradient-based\r\n"
    b"  // rim light = 0. Use brightness ratio heuristic instead.\r\n"
    b"  const isAnimLighting = contentMode && contentMode.isAnimation && contentMode.confidence > 0.40;\r\n"
    b"  // For animation: replace gradient-based rimLightStrength with perimeter brightness ratio\r\n"
    b"  const effRimLightStrength = isAnimLighting\r\n"
    b"    ? clamp(((perimMax / 255) - (subjectStats?.avgBrightness ?? centerBri / 255)) * 2.5, 0, 1)\r\n"
    b"    : rimLightStrength;\r\n"
)
assert old_rim_line in content, "rim line anchor not found"
content = content.replace(old_rim_line, new_rim_line, 1)
print("2. isAnimLighting + effRimLightStrength added")

# ─────────────────────────────────────────────────────────────────────
# 3. isBacklit: effRimLightStrength 사용
# ─────────────────────────────────────────────────────────────────────
old_isbacklit = (
    b"  const isBacklit = (\r\n"
    b"    (centerBri / (perimMax + 1)) < 0.72\r\n"
    b"    && highlightRatio > 0.08\r\n"
    b"  ) || rimLightStrength > 0.62;\r\n"
)
new_isbacklit = (
    b"  const isBacklit = (\r\n"
    b"    (centerBri / (perimMax + 1)) < 0.72\r\n"
    b"    && highlightRatio > 0.08\r\n"
    b"  ) || effRimLightStrength > 0.62;\r\n"
)
assert old_isbacklit in content, "isBacklit not found"
content = content.replace(old_isbacklit, new_isbacklit, 1)
print("3. isBacklit: uses effRimLightStrength")

# ─────────────────────────────────────────────────────────────────────
# 4. Silhouette 점수: effRimLightStrength 사용 + 애니메이션 보정
# ─────────────────────────────────────────────────────────────────────
old_silhouette = (
    b"  scores['Silhouette'] =\r\n"
    b"    (isBacklit ? 1.25 : 0) +\r\n"
    b"    rimLightStrength * 0.65 +\r\n"
    b"    clamp((0.55 - (subjectStats?.avgBrightness ?? centerBri / 255)) * 3.4, 0, 1) * 0.75 +\r\n"
    b"    clamp((subjectRing?.avgBrightness ?? perimMax / 255) - (subjectStats?.avgBrightness ?? centerBri / 255), 0, 1) * 0.7;\r\n"
)
new_silhouette = (
    b"  scores['Silhouette'] =\r\n"
    b"    (isBacklit ? 1.25 : 0) +\r\n"
    b"    effRimLightStrength * 0.65 +\r\n"
    b"    clamp((0.55 - (subjectStats?.avgBrightness ?? centerBri / 255)) * 3.4, 0, 1) * 0.75 +\r\n"
    b"    clamp((subjectRing?.avgBrightness ?? perimMax / 255) - (subjectStats?.avgBrightness ?? centerBri / 255), 0, 1) * 0.7;\r\n"
)
assert old_silhouette in content, "silhouette score not found"
content = content.replace(old_silhouette, new_silhouette, 1)
print("4. Silhouette: effRimLightStrength applied")

# ─────────────────────────────────────────────────────────────────────
# 5. Flat 점수: 애니메이션에서 modelingAsym 가중치 낮춤
#    셀쉐이딩은 의도적으로 균일해서 modelingAsym ≈ 0 → Flat이 과도하게 높음
#    애니메이션에서 Flat 판단은 contrastRatio에 더 의존해야 함
# ─────────────────────────────────────────────────────────────────────
old_flat = (
    b"  scores['Flat'] =\r\n"
    b"    clamp((0.30 - contrastRatio) * 5.2, 0, 1) * 1.0 +\r\n"
    b"    clamp((0.10 - modelingAsym) * 8, 0, 1) * 0.65 +\r\n"
    b"    clamp((1.8 - keyFillRatio) * 0.8, 0, 1) * 0.55 +\r\n"
    b"    (lightingHardness === 'Soft' ? 0.18 : 0);\r\n"
)
new_flat = (
    b"  // Animation: modelingAsym is near 0 by default (cel-shading), so\r\n"
    b"  // reduce its contribution and rely more on contrastRatio for Flat detection\r\n"
    b"  const flatModelingWeight = isAnimLighting ? 0.25 : 0.65;  // lower for animation\r\n"
    b"  scores['Flat'] =\r\n"
    b"    clamp((0.30 - contrastRatio) * 5.2, 0, 1) * 1.0 +\r\n"
    b"    clamp((0.10 - modelingAsym) * 8, 0, 1) * flatModelingWeight +\r\n"
    b"    clamp((1.8 - keyFillRatio) * 0.8, 0, 1) * 0.55 +\r\n"
    b"    (lightingHardness === 'Soft' ? 0.18 : 0);\r\n"
)
assert old_flat in content, "flat score not found"
content = content.replace(old_flat, new_flat, 1)
print("5. Flat score: reduced modelingAsym weight for animation")

# ─────────────────────────────────────────────────────────────────────
# 6. 호출부 2곳에 contentMode 전달
# ─────────────────────────────────────────────────────────────────────
old_call1 = b"  let lighting = estimateLighting(colorAnalysis, composition, faceAnalysis, edgeMap, pixels, w, h, poseAnalysis);\r\n"
new_call1 = b"  let lighting = estimateLighting(colorAnalysis, composition, faceAnalysis, edgeMap, pixels, w, h, poseAnalysis, contentMode);\r\n"
assert old_call1 in content, "lighting call 1 not found"
content = content.replace(old_call1, new_call1, 1)
print("6a. estimateLighting call 1: contentMode added")

old_call2 = b"        const vLight = estimateLighting(vColor, vc, vfa, ve, vpx, vw, vh, vpa);\r\n"
new_call2 = b"        const vLight = estimateLighting(vColor, vc, vfa, ve, vpx, vw, vh, vpa, contentMode);\r\n"
assert old_call2 in content, "lighting call 2 not found"
content = content.replace(old_call2, new_call2, 1)
print("6b. estimateLighting call 2: contentMode added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP3-3 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
