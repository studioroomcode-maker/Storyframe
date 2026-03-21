#!/usr/bin/env python3
# P5-1: 조명 타입 정확도 개선 (64% -> 74%+ 목표)
#
# 핵심 문제:
#   1. Golden-hour 서브타입이 실내 촬영에서도 Natural 강제 → sunlightCue 검증 추가
#   2. 최후 else 분기: warmBias > 0.06 -> Artificial (실외 자연광 warm도 포함됨)
#      → sunlightCue > 0.45 이면 Natural로 분류
#   3. Practical 임계값(0.58) 너무 높음: 실내 실용 조명 놓침 → 0.50으로 완화

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. lightingMotivation: Practical 임계값 완화 0.58 -> 0.50
# ─────────────────────────────────────────────────────────────────────
old_motivation = (
    b"  let lightingMotivation = 'Studio';\r\n"
    b"  if (practicalCue > 0.58 && practicalCue >= windowCue && practicalCue >= sunlightCue) lightingMotivation = 'Practical';\r\n"
    b"  else if (windowCue > 0.54 && windowCue >= sunlightCue) lightingMotivation = 'Window';\r\n"
    b"  else if (sunlightCue > 0.58 && sunlightCue >= windowCue) lightingMotivation = 'Sunlight';\r\n"
    b"  else if (mixedSourceCue > 0.55) lightingMotivation = 'Mixed-source';\r\n"
    b"  else if (bestCondition === 'High-key' && lightingHardness === 'Soft' && naturalBias > 0.55) lightingMotivation = 'Ambient';\r\n"
)
new_motivation = (
    b"  let lightingMotivation = 'Studio';\r\n"
    b"  // Practical: relaxed from 0.58 to 0.50 to catch dimmer practical lights\r\n"
    b"  if (practicalCue > 0.50 && practicalCue >= windowCue && practicalCue >= sunlightCue) lightingMotivation = 'Practical';\r\n"
    b"  else if (windowCue > 0.54 && windowCue >= sunlightCue) lightingMotivation = 'Window';\r\n"
    b"  else if (sunlightCue > 0.54 && sunlightCue >= windowCue) lightingMotivation = 'Sunlight';\r\n"
    b"  else if (mixedSourceCue > 0.55) lightingMotivation = 'Mixed-source';\r\n"
    b"  else if (bestCondition === 'High-key' && lightingHardness === 'Soft' && naturalBias > 0.55) lightingMotivation = 'Ambient';\r\n"
)
assert old_motivation in content, "lightingMotivation not found"
content = content.replace(old_motivation, new_motivation, 1)
print("1. lightingMotivation: Practical 0.58->0.50, Sunlight 0.58->0.54")

# ─────────────────────────────────────────────────────────────────────
# 2. lightingType decision tree 개선
#    - Golden-hour/Blue-hour 서브타입 → sunlightCue 검증 필요
#    - 최후 else: sunlightCue 높으면 Artificial 아닌 Natural
# ─────────────────────────────────────────────────────────────────────
old_type = (
    b"  let lightingType;\r\n"
    b"  if (lightingMotivation === 'Practical') lightingType = 'Practical';\r\n"
    b"  else if (lightingMotivation === 'Sunlight' || lightingMotivation === 'Window' || ['Golden-hour', 'Blue-hour', 'Overcast'].includes(lightingSubtype)) lightingType = 'Natural';\r\n"
    b"  else if (lightingMotivation === 'Mixed-source' || mixedColorContrast > 0.62) lightingType = 'Mixed';\r\n"
    b"  else if (avgSaturation > 0.25 && (warmBias > 0.08 || coolRatio > 0.28)) lightingType = 'Artificial';\r\n"
    b"  else if (naturalBias > 0.62 && contrastRatio < 0.42) lightingType = 'Natural';\r\n"
    b"  else lightingType = warmBias > 0.06 || coolRatio > 0.30 ? 'Artificial' : 'Mixed';\r\n"
)
new_type = (
    b"  let lightingType;\r\n"
    b"  if (lightingMotivation === 'Practical') lightingType = 'Practical';\r\n"
    b"  else if (lightingMotivation === 'Sunlight' || lightingMotivation === 'Window') lightingType = 'Natural';\r\n"
    b"  // Golden-hour/Blue-hour subtypes: require sunlight cue evidence to avoid indoor warm light misclassification\r\n"
    b"  else if (['Golden-hour', 'Blue-hour', 'Overcast'].includes(lightingSubtype) && (sunlightCue > 0.30 || naturalBias > 0.55)) lightingType = 'Natural';\r\n"
    b"  else if (['Golden-hour', 'Blue-hour', 'Overcast'].includes(lightingSubtype)) lightingType = 'Artificial';  // indoor warm/cool light, not actual golden hour\r\n"
    b"  else if (lightingMotivation === 'Mixed-source' || mixedColorContrast > 0.62) lightingType = 'Mixed';\r\n"
    b"  else if (avgSaturation > 0.25 && (warmBias > 0.08 || coolRatio > 0.28) && sunlightCue < 0.35) lightingType = 'Artificial';\r\n"
    b"  else if (naturalBias > 0.62 && contrastRatio < 0.42) lightingType = 'Natural';\r\n"
    b"  else if (sunlightCue > 0.45) lightingType = 'Natural';  // high sunlight cue even without explicit motivation\r\n"
    b"  else lightingType = warmBias > 0.06 || coolRatio > 0.30 ? 'Artificial' : 'Mixed';\r\n"
)
assert old_type in content, "lightingType not found"
content = content.replace(old_type, new_type, 1)
print("2. lightingType: Golden-hour sunlightCue guard + Natural sunlightCue path added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP5-1 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
