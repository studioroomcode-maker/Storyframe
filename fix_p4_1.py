#!/usr/bin/env python3
# P4-1: 조명 조건 정확도 개선 (58% -> 70%+ 목표)
#
# 핵심 수정:
#   1. Silhouette: isBacklit 보너스 1.25 -> 피사체 밝기 체크 추가 (밝은 피사체 = High-key, 어두운 피사체 = Silhouette)
#   2. High-key vs Flat 경계: brightness > 0.62일 때 High-key 추가 보너스
#   3. Low-key vs Chiaroscuro: subjectHighlightRatio 임계값 0.08 -> 0.13으로 올려 Chiaroscuro 더 엄격하게
#   4. Rembrandt: 얼굴 없을 때 modelingAsym 기반 약한 Rembrandt 감지 추가
#   5. Flat 점수: contrastRatio 매우 낮을 때 추가 보너스 (명확한 Flat 판별 강화)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. Silhouette: 피사체 밝기 반영 (밝은 피사체는 Silhouette 아님)
#    isBacklit ? 1.25 : 0  ->  밝은 피사체면 0.3으로 감소
# ─────────────────────────────────────────────────────────────────────
old_silhouette = (
    b"  scores['Silhouette'] =\r\n"
    b"    (isBacklit ? 1.25 : 0) +\r\n"
    b"    effRimLightStrength * 0.65 +\r\n"
    b"    clamp((0.55 - (subjectStats?.avgBrightness ?? centerBri / 255)) * 3.4, 0, 1) * 0.75 +\r\n"
    b"    clamp((subjectRing?.avgBrightness ?? perimMax / 255) - (subjectStats?.avgBrightness ?? centerBri / 255), 0, 1) * 0.7;\r\n"
)
new_silhouette = (
    b"  // Silhouette fix: isBacklit alone is not enough - subject must actually be dark.\r\n"
    b"  // Backlit + bright subject = High-key/Rim, not Silhouette.\r\n"
    b"  const subjectIsDark = (subjectStats?.avgBrightness ?? centerBri / 255) < 0.40;\r\n"
    b"  const backlitBonus = isBacklit ? (subjectIsDark ? 1.25 : 0.30) : 0;\r\n"
    b"  scores['Silhouette'] =\r\n"
    b"    backlitBonus +\r\n"
    b"    effRimLightStrength * 0.65 +\r\n"
    b"    clamp((0.55 - (subjectStats?.avgBrightness ?? centerBri / 255)) * 3.4, 0, 1) * 0.75 +\r\n"
    b"    clamp((subjectRing?.avgBrightness ?? perimMax / 255) - (subjectStats?.avgBrightness ?? centerBri / 255), 0, 1) * 0.7;\r\n"
)
assert old_silhouette in content, "silhouette not found"
content = content.replace(old_silhouette, new_silhouette, 1)
print("1. Silhouette: subject brightness check added")

# ─────────────────────────────────────────────────────────────────────
# 2. High-key: brightness > 0.62 추가 보너스 (명확한 High-key 강화)
#    + Flat과 구분: low shadow AND high brightness -> High-key wins
# ─────────────────────────────────────────────────────────────────────
old_highkey = (
    b"  scores['High-key'] =\r\n"
    b"    clamp((avgBrightness - 0.54) * 4.2, 0, 1) * 1.0 +\r\n"
    b"    clamp((0.24 - shadowRatio) * 5.2, 0, 1) * 0.8 +\r\n"
    b"    clamp((0.34 - contrastRatio) * 4.5, 0, 1) * 0.6 +\r\n"
    b"    (lightingContrast === 'Low' ? 0.22 : 0);\r\n"
)
new_highkey = (
    b"  scores['High-key'] =\r\n"
    b"    clamp((avgBrightness - 0.54) * 4.2, 0, 1) * 1.0 +\r\n"
    b"    clamp((0.24 - shadowRatio) * 5.2, 0, 1) * 0.8 +\r\n"
    b"    clamp((0.34 - contrastRatio) * 4.5, 0, 1) * 0.6 +\r\n"
    b"    (lightingContrast === 'Low' ? 0.22 : 0) +\r\n"
    b"    // Extra bonus for clearly bright frames (disambiguate from borderline Flat)\r\n"
    b"    clamp((avgBrightness - 0.62) * 5.0, 0, 1) * 0.20 +\r\n"
    b"    // Penalty when frame is borderline bright but has significant modeling asymmetry (-> Rembrandt/Chiaroscuro)\r\n"
    b"    (modelingAsym > 0.18 && avgBrightness < 0.64 ? -0.12 : 0);\r\n"
)
assert old_highkey in content, "high-key score not found"
content = content.replace(old_highkey, new_highkey, 1)
print("2. High-key: brightness bonus + modeling asymmetry penalty added")

# ─────────────────────────────────────────────────────────────────────
# 3. Flat: contrastRatio 매우 낮을 때 확실한 Flat (0.15 이하 = 확실)
# ─────────────────────────────────────────────────────────────────────
old_flat = (
    b"  // Animation: modelingAsym is near 0 by default (cel-shading), so\r\n"
    b"  // reduce its contribution and rely more on contrastRatio for Flat detection\r\n"
    b"  const flatModelingWeight = isAnimLighting ? 0.25 : 0.65;  // lower for animation\r\n"
    b"  scores['Flat'] =\r\n"
    b"    clamp((0.30 - contrastRatio) * 5.2, 0, 1) * 1.0 +\r\n"
    b"    clamp((0.10 - modelingAsym) * 8, 0, 1) * flatModelingWeight +\r\n"
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
    b"    (lightingHardness === 'Soft' ? 0.18 : 0) +\r\n"
    b"    // Strong Flat signal: very low contrast (< 0.15) with no backlighting\r\n"
    b"    (contrastRatio < 0.15 && !isBacklit ? 0.20 : 0);\r\n"
)
assert old_flat in content, "flat score not found"
content = content.replace(old_flat, new_flat, 1)
print("3. Flat: low-contrast bonus added")

# ─────────────────────────────────────────────────────────────────────
# 4. Chiaroscuro: subjectHighlightRatio 임계값 강화 (Low-key와 구분)
#    0.08 -> 0.13으로 올려야 Low-key에서 Chiaroscuro로 잘못 점프 방지
# ─────────────────────────────────────────────────────────────────────
old_chiaroscuro = (
    b"  scores['Chiaroscuro'] =\r\n"
    b"    clamp((subjectShadowRatio - 0.22) * 4.2, 0, 1) * 0.8 +\r\n"
    b"    clamp((subjectHighlightRatio - 0.08) * 5.5, 0, 1) * 0.7 +\r\n"
    b"    clamp((contrastRatio - 0.34) * 4.5, 0, 1) * 1.0 +\r\n"
    b"    clamp((keyFillRatio - 3.1) * 0.22, 0, 1) * 0.7 +\r\n"
    b"    (lightingHardness === 'Hard' ? 0.35 : 0);\r\n"
)
new_chiaroscuro = (
    b"  scores['Chiaroscuro'] =\r\n"
    b"    clamp((subjectShadowRatio - 0.22) * 4.2, 0, 1) * 0.8 +\r\n"
    b"    // Raised threshold: 0.13 (was 0.08) to better separate from Low-key\r\n"
    b"    // Chiaroscuro needs BOTH deep shadows AND bright highlights (high contrast subject)\r\n"
    b"    clamp((subjectHighlightRatio - 0.13) * 5.5, 0, 1) * 0.7 +\r\n"
    b"    clamp((contrastRatio - 0.34) * 4.5, 0, 1) * 1.0 +\r\n"
    b"    clamp((keyFillRatio - 3.1) * 0.22, 0, 1) * 0.7 +\r\n"
    b"    (lightingHardness === 'Hard' ? 0.35 : 0);\r\n"
)
assert old_chiaroscuro in content, "chiaroscuro not found"
content = content.replace(old_chiaroscuro, new_chiaroscuro, 1)
print("4. Chiaroscuro: highlight threshold raised 0.08->0.13")

# ─────────────────────────────────────────────────────────────────────
# 5. Rembrandt: 얼굴 없을 때도 방향성 비대칭 강하면 약한 점수 부여
# ─────────────────────────────────────────────────────────────────────
old_rembrandt = (
    b"  scores['Rembrandt'] = hasFace\r\n"
    b"    ? clamp((modelingAsym - 0.10) * 5.5, 0, 1) * 0.9 +\r\n"
    b"      clamp((subjectVertBias - 0.05) * 5, 0, 1) * 0.45 +\r\n"
    b"      clamp((keyFillRatio - 2.0) * 0.22, 0, 1) * 0.55 +\r\n"
    b"      clamp((0.72 - (subjectStats?.avgBrightness ?? avgBrightness)) * 1.5, 0, 1) * 0.35\r\n"
    b"    : 0;\r\n"
)
new_rembrandt = (
    b"  // Rembrandt: with face = full scoring; without face = use frame-level asymmetry proxy\r\n"
    b"  // (some shots have strongly lit subjects but face detector fails -> gives 0 unfairly)\r\n"
    b"  const rembrandtBase = hasFace\r\n"
    b"    ? clamp((modelingAsym - 0.10) * 5.5, 0, 1) * 0.9 +\r\n"
    b"      clamp((subjectVertBias - 0.05) * 5, 0, 1) * 0.45 +\r\n"
    b"      clamp((keyFillRatio - 2.0) * 0.22, 0, 1) * 0.55 +\r\n"
    b"      clamp((0.72 - (subjectStats?.avgBrightness ?? avgBrightness)) * 1.5, 0, 1) * 0.35\r\n"
    b"    : // No face: use frame-level modeling asymmetry (weaker signal, lower max score)\r\n"
    b"      clamp((Math.abs(combinedHorizBias) - 0.14) * 4.5, 0, 1) * 0.45 +\r\n"
    b"      clamp((keyFillRatio - 2.5) * 0.20, 0, 1) * 0.40 +\r\n"
    b"      clamp((contrastRatio - 0.28) * 3.0, 0, 1) * 0.35;\r\n"
    b"  scores['Rembrandt'] = rembrandtBase;\r\n"
)
assert old_rembrandt in content, "rembrandt not found"
content = content.replace(old_rembrandt, new_rembrandt, 1)
print("5. Rembrandt: fallback scoring without face added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP4-1 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
