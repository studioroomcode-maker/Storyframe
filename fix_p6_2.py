#!/usr/bin/env python3
# P6-2: perspRatio 신호 수정 + vignetting 렌즈 스코어 추가
#
# 핵심 수정:
#   1. perspRatio 물리적 해석 수정
#      - 심도 깊은 샷(sharpnessRatio < 1.4)에서 고 perspRatio는 광각 가능성
#      - shallow DOF일 때만 망원 신호로 해석 (perspTeleSignal)
#   2. wideScore 패널티도 shallow DOF일 때만 적용
#   3. vignetting 신호 teleScore + stScore에 추가 (추출됐지만 미사용 변수)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()
original = content

# ─────────────────────────────────────────────────────────────────────
# 1. perspRatio 정의 후 perspTeleSignal 추가
# ─────────────────────────────────────────────────────────────────────
old_persp_def = (
    b"  // perspRatio: corner sharpness / center sharpness (perspective compression proxy)\r\n"
    b"  // High -> telephoto (compressed background retains detail)\r\n"
    b"  // Low  -> wide lens or shallow DOF (corners blurry / less detailed)\r\n"
    b"  const perspRatio       = focus.perspRatio ?? 0.5;\r\n"
)
new_persp_def = (
    b"  // perspRatio: corner sharpness / center sharpness (perspective compression proxy)\r\n"
    b"  // High -> telephoto (compressed background retains detail)\r\n"
    b"  // Low  -> wide lens or shallow DOF (corners blurry / less detailed)\r\n"
    b"  const perspRatio       = focus.perspRatio ?? 0.5;\r\n"
    b"  // perspTeleSignal: perspRatio only reliably indicates telephoto when DOF is shallow\r\n"
    b"  // With deep DOF (sharpnessRatio < 1.4), a wide-angle stopped-down also has high perspRatio\r\n"
    b"  // -> cap the telephoto interpretation when evidence of deep/uniform focus\r\n"
    b"  const perspTeleSignal  = sharpnessRatio > 1.40\r\n"
    b"    ? perspRatio\r\n"
    b"    : Math.min(perspRatio, 0.42);  // cap at neutral when deep DOF\r\n"
)
assert old_persp_def in content, "perspRatio definition not found"
content = content.replace(old_persp_def, new_persp_def, 1)
print("1. perspTeleSignal: DOF-gated perspRatio added")

# ─────────────────────────────────────────────────────────────────────
# 2. stScore: perspRatio -> perspTeleSignal + vignetting 추가
# ─────────────────────────────────────────────────────────────────────
old_st_score = (
    b"    clamp((perspRatio - 0.40) / 0.35, 0, 1) * 0.09;  // corner detail retention\r\n"
)
new_st_score = (
    b"    clamp((perspTeleSignal - 0.40) / 0.35, 0, 1) * 0.09 +  // corner detail (DOF-gated)\r\n"
    b"    (vignetting > 1.20 ? clamp((vignetting - 1.20) / 0.30, 0, 1) * 0.06 : 0);  // lens vignetting\r\n"
)
assert old_st_score in content, "stScore perspRatio line not found"
content = content.replace(old_st_score, new_st_score, 1)
print("2. stScore: perspTeleSignal + vignetting added")

# ─────────────────────────────────────────────────────────────────────
# 3. teleScore: perspRatio -> perspTeleSignal + vignetting 추가
# ─────────────────────────────────────────────────────────────────────
old_tele_score = (
    b"    clamp((perspRatio - 0.30) / 0.40, 0, 1) * 0.05;  // perspective compression\r\n"
)
new_tele_score = (
    b"    clamp((perspTeleSignal - 0.30) / 0.40, 0, 1) * 0.05 +  // perspective compression (DOF-gated)\r\n"
    b"    (vignetting > 1.15 ? clamp((vignetting - 1.15) / 0.35, 0, 1) * 0.08 : 0);  // telephoto vignetting\r\n"
)
assert old_tele_score in content, "teleScore perspRatio line not found"
content = content.replace(old_tele_score, new_tele_score, 1)
print("3. teleScore: perspTeleSignal + vignetting added")

# ─────────────────────────────────────────────────────────────────────
# 4. wideScore: perspRatio 패널티를 shallow DOF일 때만 적용
# ─────────────────────────────────────────────────────────────────────
old_wide_score = (
    b"    clamp((0.30 - perspRatio) / 0.20, 0, 1) * 0.06 -  // wide: corners lack detail\r\n"
    b"    clamp((perspRatio - 0.55) / 0.20, 0, 1) * 0.08;   // penalize if corners retain detail (tele)\r\n"
)
new_wide_score = (
    b"    clamp((0.30 - perspRatio) / 0.20, 0, 1) * 0.06 -  // wide: corners lack detail\r\n"
    b"    // Penalize high perspRatio only with shallow DOF: deep DOF wide-angle also has even sharpness\r\n"
    b"    (sharpnessRatio > 1.40 ? clamp((perspRatio - 0.55) / 0.20, 0, 1) * 0.08 : 0);\r\n"
)
assert old_wide_score in content, "wideScore perspRatio penalty not found"
content = content.replace(old_wide_score, new_wide_score, 1)
print("4. wideScore: perspRatio penalty gated on shallow DOF")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP6-2 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
