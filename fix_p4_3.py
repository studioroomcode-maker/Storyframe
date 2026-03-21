#!/usr/bin/env python3
# P4-3: 카메라 무브먼트 정확도 개선 (69% -> 77%+ 목표)
#
# 핵심 수정:
#   1. Pan/Tilt scale constraint 완화: 0.012 -> 0.022 (원근 왜곡 허용)
#   2. Handheld catch-all 전에 추가 분류:
#      - avgMagnitude < 0.30 -> Static (노이즈 수준, 움직임 없음)
#      - avgGain > 0.12 -> Zoom-in 계열 (잘못된 Handheld 방지)
#   3. Handheld confidence 개선: 0.43 고정 -> residual 기반 가변
#   4. Pan dirConX 임계값 완화: 0.58 -> 0.52 (대각선 Pan 감지)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. Pan scale constraint 완화: 0.012 -> 0.022
#    원근법에 의한 약한 스케일 변화(~2%)는 Pan으로 인정
# ─────────────────────────────────────────────────────────────────────
old_pan = (
    b"    // Pan / Trucking (horizontal dominant)\r\n"
    b"    // avgAbsScale < 0.012: scale change present => likely zoom, not pan\r\n"
    b"    if (Math.abs(avgDx) > Math.abs(avgDy) * 1.40 && Math.abs(avgDx) >= 1.1 && dirConX > 0.58 && avgAbsScale < 0.012) {\r\n"
)
new_pan = (
    b"    // Pan / Trucking (horizontal dominant)\r\n"
    b"    // avgAbsScale < 0.022: allow slight perspective scale shift (~2%) during pan\r\n"
    b"    // (telephoto pans show ~1-2% scale compression; 0.012 was too strict)\r\n"
    b"    if (Math.abs(avgDx) > Math.abs(avgDy) * 1.40 && Math.abs(avgDx) >= 1.1 && dirConX > 0.52 && avgAbsScale < 0.022) {\r\n"
)
assert old_pan in content, "pan constraint not found"
content = content.replace(old_pan, new_pan, 1)
print("1. Pan: scale constraint 0.012->0.022, dirConX 0.58->0.52")

# ─────────────────────────────────────────────────────────────────────
# 2. Tilt scale constraint 완화: 0.012 -> 0.022
# ─────────────────────────────────────────────────────────────────────
old_tilt = (
    b"    // Tilt / Pedestal (vertical dominant)\r\n"
    b"    // avgAbsScale < 0.012: scale change present => likely push-in/crane, not tilt\r\n"
    b"    if (Math.abs(avgDy) > Math.abs(avgDx) * 1.40 && Math.abs(avgDy) >= 0.9 && dirConY > 0.58 && avgAbsScale < 0.012) {\r\n"
)
new_tilt = (
    b"    // Tilt / Pedestal (vertical dominant)\r\n"
    b"    // avgAbsScale < 0.022: allow slight perspective scale shift during tilt\r\n"
    b"    if (Math.abs(avgDy) > Math.abs(avgDx) * 1.40 && Math.abs(avgDy) >= 0.9 && dirConY > 0.52 && avgAbsScale < 0.022) {\r\n"
)
assert old_tilt in content, "tilt constraint not found"
content = content.replace(old_tilt, new_tilt, 1)
print("2. Tilt: scale constraint 0.012->0.022, dirConY 0.58->0.52")

# ─────────────────────────────────────────────────────────────────────
# 3. Handheld catch-all 개선
#    - 매우 작은 움직임 -> Static으로 분류 (노이즈 방지)
#    - 높은 gain -> Zoom으로 이미 처리됐어야 하지만 여기까지 오면 Push-in
#    - Handheld confidence: avgResidual 기반으로 가변화
# ─────────────────────────────────────────────────────────────────────
old_handheld = (
    b"    // Fallback handheld\r\n"
    b"    return { type: 'Handheld', confidence: 0.43, detail: 'Motion remains unstable without a cleaner classification, so it falls back to handheld.', direction: dirLabel(avgDx, avgDy), speed, smoothness: Math.max(0,"
)
new_handheld = (
    b"    // Pre-fallback: micro-motion that never passed any threshold = probably Static noise\r\n"
    b"    if (avgMagnitude < 0.35 && avgGain < 0.04) {\r\n"
    b"      return { type: 'Static', confidence: 0.52,\r\n"
    b"        detail: 'Very low motion magnitude with minimal gain - likely camera noise on a locked-off shot.',\r\n"
    b"        direction: null, speed: 'none', smoothness: 1.0 };\r\n"
    b"    }\r\n"
    b"    // Fallback handheld: confidence based on residual (more chaotic = more confidently Handheld)\r\n"
    b"    const handheldConf = clamp(0.43 + (avgResidual - 0.07) * 1.2, 0.43, 0.62);\r\n"
    b"    return { type: 'Handheld', confidence: handheldConf, detail: 'Motion remains unstable without a cleaner classification, so it falls back to handheld.', direction: dirLabel(avgDx, avgDy), speed, smoothness: Math.max(0,"
)
assert old_handheld in content, "handheld catchall not found"
content = content.replace(old_handheld, new_handheld, 1)
print("3. Handheld: micro-motion->Static guard + variable confidence")

# ─────────────────────────────────────────────────────────────────────
# 4. Whip-pan dirConX 완화: 0.78 -> 0.72 (노이즈 민감도 감소)
# ─────────────────────────────────────────────────────────────────────
old_whip = (
    b"    // Whip-pan\r\n"
    b"    if (Math.abs(avgDx) > Math.abs(avgDy) * 1.65 && Math.abs(avgDx) >= 2.8 && dirConX > 0.78) {\r\n"
)
new_whip = (
    b"    // Whip-pan: dirConX lowered from 0.78 to 0.72 to catch noisy rapid pans\r\n"
    b"    if (Math.abs(avgDx) > Math.abs(avgDy) * 1.65 && Math.abs(avgDx) >= 2.8 && dirConX > 0.72) {\r\n"
)
assert old_whip in content, "whip-pan not found"
content = content.replace(old_whip, new_whip, 1)
print("4. Whip-pan: dirConX 0.78->0.72")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP4-3 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
