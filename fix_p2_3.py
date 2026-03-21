#!/usr/bin/env python3
# P2-3: 원근 압축 직접 측정
#
# 핵심 아이디어:
#   망원: 배경이 압축되어 화면 전체에 균등한 디테일 분포 (cornerSharpness ≈ centerSharpness)
#   광각: 중앙에 피사체가 확대되고 코너에 디테일이 적음 (cornerSharpness << centerSharpness)
#
# 구현:
#   1. analyzeFocusRegions에 4개 코너 영역 sharpness 추가 → perspRatio 계산
#   2. estimateLens에서 perspRatio를 teleScore/wideScore에 반영

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. analyzeFocusRegions: 코너 영역 추가 + perspRatio 반환
# ─────────────────────────────────────────────────────────────────────

# Add corner tracking vars to R initialization
old_R_init = (
    b"  const R = {\r\n"
    b"    center: 0, top: 0, bottom: 0, left: 0, right: 0, midBand: 0, outer: 0,\r\n"
    b"    cC: 0, tC: 0, bC: 0, lC: 0, rC: 0, mC: 0, oC: 0\r\n"
    b"  };\r\n"
)
new_R_init = (
    b"  const R = {\r\n"
    b"    center: 0, top: 0, bottom: 0, left: 0, right: 0, midBand: 0, outer: 0,\r\n"
    b"    cC: 0, tC: 0, bC: 0, lC: 0, rC: 0, mC: 0, oC: 0,\r\n"
    b"    corner: 0, cnC: 0  // 4 corners (25%x25%) - perspective compression proxy\r\n"
    b"  };\r\n"
)
assert old_R_init in content, "R init not found"
content = content.replace(old_R_init, new_R_init, 1)

# Add corner accumulation inside the pixel loop
old_outer_line = (
    b"      if (nx < 0.14 || nx > 0.86 || ny < 0.14 || ny > 0.86) { R.outer += e; R.oC++; } // frame edge\r\n"
)
new_outer_line = (
    b"      if (nx < 0.14 || nx > 0.86 || ny < 0.14 || ny > 0.86) { R.outer += e; R.oC++; } // frame edge\r\n"
    b"      // Corners: 4 quadrants of the outer 25%x25% - perspective compression proxy\r\n"
    b"      if ((nx < 0.25 || nx > 0.75) && (ny < 0.25 || ny > 0.75)) { R.corner += e; R.cnC++; }\r\n"
)
assert old_outer_line in content, "outer line not found"
content = content.replace(old_outer_line, new_outer_line, 1)

# Add cornerSharpness variable
old_ors_line = (
    b"  const ors = R.oC  > 0 ? R.outer   / R.oC  : 0; // outermost ring\r\n"
)
new_ors_line = (
    b"  const ors  = R.oC  > 0 ? R.outer  / R.oC  : 0; // outermost ring\r\n"
    b"  const cors = R.cnC > 0 ? R.corner / R.cnC : 0; // corner zone sharpness\r\n"
)
assert old_ors_line in content, "ors line not found"
content = content.replace(old_ors_line, new_ors_line, 1)

# Add perspRatio to return object
old_return_focus = (
    b"    centerBgRatio:  ts  > 0 ? cs / ts  : 1,   // center vs background (top region)\r\n"
    b"    centerFgRatio:  bs  > 0 ? cs / bs  : 1,   // center vs foreground (bottom region)\r\n"
    b"    midVsEdgeRatio: ors > 0 ? mbs / ors : 1,  // horizontal band vs frame edge (tilt-shift)\r\n"
    b"    zoneVariance\r\n"
)
new_return_focus = (
    b"    centerBgRatio:  ts  > 0 ? cs / ts  : 1,   // center vs background (top region)\r\n"
    b"    centerFgRatio:  bs  > 0 ? cs / bs  : 1,   // center vs foreground (bottom region)\r\n"
    b"    midVsEdgeRatio: ors > 0 ? mbs / ors : 1,  // horizontal band vs frame edge (tilt-shift)\r\n"
    b"    // perspRatio: corner detail relative to center\r\n"
    b"    //   High (>0.55): corners retain detail -> possible telephoto compression\r\n"
    b"    //   Low (<0.25): corners much less detailed -> wide/deep focus, or shallow DOF\r\n"
    b"    perspRatio: cs > 0 ? cors / cs : 0.5,\r\n"
    b"    cornerSharpness: cors,\r\n"
    b"    zoneVariance\r\n"
)
assert old_return_focus in content, "return focus not found"
content = content.replace(old_return_focus, new_return_focus, 1)
print("1. analyzeFocusRegions: cornerSharpness + perspRatio added")

# ─────────────────────────────────────────────────────────────────────
# 2. estimateLens: perspRatio 변수 추출 + teleScore/stScore에 반영
# ─────────────────────────────────────────────────────────────────────

# Extract perspRatio in estimateLens setup
old_lens_diag = (
    b"  const diagER           = edgeMap.diagonalEnergyRatio ?? 0;\r\n"
    b"\r\n"
    b"  // Subject at frame edge"
)
new_lens_diag = (
    b"  const diagER           = edgeMap.diagonalEnergyRatio ?? 0;\r\n"
    b"  // perspRatio: corner sharpness / center sharpness (perspective compression proxy)\r\n"
    b"  // High -> telephoto (compressed background retains detail)\r\n"
    b"  // Low  -> wide lens or shallow DOF (corners blurry / less detailed)\r\n"
    b"  const perspRatio       = focus.perspRatio ?? 0.5;\r\n"
    b"\r\n"
    b"  // Subject at frame edge"
)
assert old_lens_diag in content, "lens diag not found"
content = content.replace(old_lens_diag, new_lens_diag, 1)

# Add perspRatio to stScore (super-telephoto)
old_stScore = (
    b"  const stScore =\r\n"
    b"    clamp((sharpnessRatio - 2.0) / 1.2, 0, 1) * 0.35 +\r\n"
    b"    clamp((bgCompression - 1.8) / 1.2, 0, 1) * 0.30 +\r\n"
    b"    (isECU_BCU ? 0.20 : 0) +\r\n"
    b"    (faceH > 0.38 ? clamp((faceH - 0.38) / 0.28, 0, 1) * 0.15 : 0);\r\n"
)
new_stScore = (
    b"  const stScore =\r\n"
    b"    clamp((sharpnessRatio - 2.0) / 1.2, 0, 1) * 0.32 +\r\n"
    b"    clamp((bgCompression - 1.8) / 1.2, 0, 1) * 0.28 +\r\n"
    b"    (isECU_BCU ? 0.18 : 0) +\r\n"
    b"    (faceH > 0.38 ? clamp((faceH - 0.38) / 0.28, 0, 1) * 0.13 : 0) +\r\n"
    b"    clamp((perspRatio - 0.40) / 0.35, 0, 1) * 0.09;  // corner detail retention\r\n"
)
assert old_stScore in content, "stScore not found"
content = content.replace(old_stScore, new_stScore, 1)

# Add perspRatio to teleScore
old_teleScore = (
    b"  const teleScore =\r\n"
    b"    clamp((sharpnessRatio - 1.55) / 0.75, 0, 1) * 0.28 +\r\n"
    b"    clamp((bgCompression - 1.30) / 0.80, 0, 1) * 0.24 +\r\n"
    b"    clamp((radialFalloff - 1.35) / 1.00, 0, 1) * 0.14 +\r\n"
    b"    ((isCU_up || isMid) ? 0.14 : 0) +\r\n"
    b"    (faceH > 0.14 ? clamp((faceH - 0.14) / 0.28, 0, 1) * 0.12 : 0) +\r\n"
    b"    (hvConc > 0.46 ? clamp((hvConc - 0.46) / 0.20, 0, 1) * 0.08 : 0);\r\n"
)
new_teleScore = (
    b"  const teleScore =\r\n"
    b"    clamp((sharpnessRatio - 1.55) / 0.75, 0, 1) * 0.25 +\r\n"
    b"    clamp((bgCompression - 1.30) / 0.80, 0, 1) * 0.22 +\r\n"
    b"    clamp((radialFalloff - 1.35) / 1.00, 0, 1) * 0.14 +\r\n"
    b"    ((isCU_up || isMid) ? 0.14 : 0) +\r\n"
    b"    (faceH > 0.14 ? clamp((faceH - 0.14) / 0.28, 0, 1) * 0.12 : 0) +\r\n"
    b"    (hvConc > 0.46 ? clamp((hvConc - 0.46) / 0.20, 0, 1) * 0.08 : 0) +\r\n"
    b"    clamp((perspRatio - 0.30) / 0.40, 0, 1) * 0.05;  // perspective compression\r\n"
)
assert old_teleScore in content, "teleScore not found"
content = content.replace(old_teleScore, new_teleScore, 1)

# Add perspRatio penalty to wideScore (high perspRatio = not wide)
old_wideScore = (
    b"  const wideScore =\r\n"
    b"    clamp((diagER - 0.16) / 0.14, 0, 1) * 0.28 +\r\n"
    b"    clamp((1.25 - sharpnessRatio) / 0.20, 0, 1) * 0.26 +\r\n"
    b"    clamp((overallSharpness - 8.0) / 4.0, 0, 1) * 0.18 +\r\n"
    b"    (edgeDistortion ? 0.14 : 0) +\r\n"
    b"    (isWide ? 0.10 : 0) +\r\n"
    b"    (hvConc < 0.46 ? clamp((0.46 - hvConc) / 0.15, 0, 1) * 0.04 : 0);\r\n"
)
new_wideScore = (
    b"  const wideScore =\r\n"
    b"    clamp((diagER - 0.16) / 0.14, 0, 1) * 0.28 +\r\n"
    b"    clamp((1.25 - sharpnessRatio) / 0.20, 0, 1) * 0.26 +\r\n"
    b"    clamp((overallSharpness - 8.0) / 4.0, 0, 1) * 0.18 +\r\n"
    b"    (edgeDistortion ? 0.14 : 0) +\r\n"
    b"    (isWide ? 0.10 : 0) +\r\n"
    b"    (hvConc < 0.46 ? clamp((0.46 - hvConc) / 0.15, 0, 1) * 0.04 : 0) +\r\n"
    b"    clamp((0.30 - perspRatio) / 0.20, 0, 1) * 0.06 -  // wide: corners lack detail\r\n"
    b"    clamp((perspRatio - 0.55) / 0.20, 0, 1) * 0.08;   // penalize if corners retain detail (tele)\r\n"
)
assert old_wideScore in content, "wideScore not found"
content = content.replace(old_wideScore, new_wideScore, 1)
print("2. estimateLens: perspRatio integrated into stScore/teleScore/wideScore")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP2-3 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
