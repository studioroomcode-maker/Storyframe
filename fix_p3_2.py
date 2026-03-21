#!/usr/bin/env python3
# P3-2: DOF 애니메이션 가드
#
# 핵심 아이디어:
#   애니메이션은 광학 렌즈 없음 -> sharpnessRatio 균일해도 "Deep"이 아님
#   애니메이션에서 신뢰할 수 있는 DOF 판단 기준:
#     - sharpnessRatio > 2.2 + zoneVariance > 12 → 의도적으로 bokeh 렌더링됨 (Very-shallow/Shallow OK)
#     - 그 외 → Normal (DOF 없음)
#   Tilt-shift, Macro는 광학 효과 → 애니메이션에서 무효
#
# 구현:
#   1. estimateDOF 시그니처에 contentMode 5번째 파라미터 추가
#   2. 함수 상단에 isAnimScene 체크 + 애니메이션 early-path 추가
#   3. 호출부(line 7864)에 contentMode 전달

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. estimateDOF 함수 시그니처 + 상단에 애니메이션 가드 추가
# ─────────────────────────────────────────────────────────────────────
old_dof_start = (
    b"function estimateDOF(focus, shotSize, faceAnalysis, poseAnalysis) {\r\n"
    b"  const {\r\n"
    b"    centerSharpness, avgPeriphery, sharpnessRatio, overallSharpness,\r\n"
    b"    topSharpness, bottomSharpness, leftSharpness, rightSharpness,\r\n"
    b"    midBandSharpness, outerRingSharpness,\r\n"
    b"    centerBgRatio, centerFgRatio, midVsEdgeRatio, zoneVariance\r\n"
    b"  } = focus;\r\n"
    b"\r\n"
    b"  const shotType    = shotSize?.type || shotSize || '';\r\n"
    b"  const hasFace     = (faceAnalysis?.count ?? 0) > 0;\r\n"
    b"  const faceArea    = faceAnalysis?.largestAreaRatio ?? 0;\r\n"
    b"  const isMacroShot = ['ECU', 'BCU', 'INSERT'].includes(shotType);\r\n"
    b"  const isCloseUp   = ['CU', 'BCU', 'ECU', 'INSERT', 'MCU'].includes(shotType);\r\n"
    b"  const isWide      = ['LS', 'ELS', 'Establishing'].includes(shotType);\r\n"
)
new_dof_start = (
    b"function estimateDOF(focus, shotSize, faceAnalysis, poseAnalysis, contentMode) {\r\n"
    b"  const {\r\n"
    b"    centerSharpness, avgPeriphery, sharpnessRatio, overallSharpness,\r\n"
    b"    topSharpness, bottomSharpness, leftSharpness, rightSharpness,\r\n"
    b"    midBandSharpness, outerRingSharpness,\r\n"
    b"    centerBgRatio, centerFgRatio, midVsEdgeRatio, zoneVariance\r\n"
    b"  } = focus;\r\n"
    b"\r\n"
    b"  const shotType    = shotSize?.type || shotSize || '';\r\n"
    b"  const hasFace     = (faceAnalysis?.count ?? 0) > 0;\r\n"
    b"  const faceArea    = faceAnalysis?.largestAreaRatio ?? 0;\r\n"
    b"  const isMacroShot = ['ECU', 'BCU', 'INSERT'].includes(shotType);\r\n"
    b"  const isCloseUp   = ['CU', 'BCU', 'ECU', 'INSERT', 'MCU'].includes(shotType);\r\n"
    b"  const isWide      = ['LS', 'ELS', 'Establishing'].includes(shotType);\r\n"
    b"\r\n"
    b"  // P3-2: Animation DOF guard.\r\n"
    b"  // Animation has no optical lens, so sharpnessRatio reflects rendering choices,\r\n"
    b"  // NOT focal plane physics. Flat-shaded frames naturally have uniform sharpness\r\n"
    b"  // and look like 'Deep' focus when they are actually 'Normal' (no DOF simulated).\r\n"
    b"  // Tilt-shift and Macro are optical effects that don't exist in animation.\r\n"
    b"  const isAnimDOF = contentMode && contentMode.isAnimation && contentMode.confidence > 0.40;\r\n"
    b"  if (isAnimDOF) {\r\n"
    b"    // Only trust DOF signal if there is a strong explicit blur gradient\r\n"
    b"    // (meaning the animator explicitly rendered bokeh/depth blur)\r\n"
    b"    const explicitBlurRendered = sharpnessRatio > 2.2 && zoneVariance > 12;\r\n"
    b"    if (!explicitBlurRendered) {\r\n"
    b"      // No deliberate DOF rendering detected -> default to Normal\r\n"
    b"      return {\r\n"
    b"        type: 'Normal', confidence: 0.55,\r\n"
    b"        detail: 'Animation frame without explicit depth blur rendering - defaulting to Normal DOF.',\r\n"
    b"        focusPlane: 'pan-focus', separation: 0\r\n"
    b"      };\r\n"
    b"    }\r\n"
    b"    // Explicit blur: allow shallow detection but cap at Shallow (not Very-shallow for most animation)\r\n"
    b"    // Fall through to main logic but constrain: skip Tilt-shift, Macro, Deep, Soft-focus paths below\r\n"
    b"  }\r\n"
)
assert old_dof_start in content, "estimateDOF start not found"
content = content.replace(old_dof_start, new_dof_start, 1)
print("1. estimateDOF: contentMode param + animation early-return added")

# ─────────────────────────────────────────────────────────────────────
# 2. Tilt-shift 경로: 애니메이션에서 skip
# ─────────────────────────────────────────────────────────────────────
old_tilt = (
    b"  if (tiltScore >= 0.80 && sharpnessRatio > 1.28) {\r\n"
    b"    return {\r\n"
    b"      type: 'Tilt-shift', confidence: clamp(0.58 + tiltScore * 0.24, 0.58, 0.84),\r\n"
    b"      detail: 'A narrow horizontal sharp band with soft top and bottom regions fits a tilt-shift or miniature effect.',\r\n"
    b"      focusPlane: 'midground', separation: clamp((sharpnessRatio - 1) / 2, 0, 1)\r\n"
    b"    };\r\n"
    b"  }"
)
new_tilt = (
    b"  if (tiltScore >= 0.80 && sharpnessRatio > 1.28 && !isAnimDOF) {\r\n"
    b"    return {\r\n"
    b"      type: 'Tilt-shift', confidence: clamp(0.58 + tiltScore * 0.24, 0.58, 0.84),\r\n"
    b"      detail: 'A narrow horizontal sharp band with soft top and bottom regions fits a tilt-shift or miniature effect.',\r\n"
    b"      focusPlane: 'midground', separation: clamp((sharpnessRatio - 1) / 2, 0, 1)\r\n"
    b"    };\r\n"
    b"  }"
)
assert old_tilt in content, "tilt-shift path not found"
content = content.replace(old_tilt, new_tilt, 1)
print("2. Tilt-shift: skip for animation")

# ─────────────────────────────────────────────────────────────────────
# 3. Macro 경로: 애니메이션에서 skip
# ─────────────────────────────────────────────────────────────────────
old_macro = (
    b"  if (isMacroShot && sharpnessRatio > 2.7 && avgPeriphery < centerSharpness * 0.32) {\r\n"
    b"    return {\r\n"
    b"      type: 'Macro', confidence: clamp(0.62 + (sharpnessRatio - 2.7) * 0.07, 0.62, 0.90),\r\n"
    b"      detail: `Extreme close framing (${shotType}) with almost all sharpness concentrated at the center fits macro focus.`,\r\n"
    b"      focusPlane: 'foreground', separation: clamp((sharpnessRatio - 1) / 4, 0, 1)\r\n"
    b"    };\r\n"
    b"  }"
)
new_macro = (
    b"  if (isMacroShot && sharpnessRatio > 2.7 && avgPeriphery < centerSharpness * 0.32 && !isAnimDOF) {\r\n"
    b"    return {\r\n"
    b"      type: 'Macro', confidence: clamp(0.62 + (sharpnessRatio - 2.7) * 0.07, 0.62, 0.90),\r\n"
    b"      detail: `Extreme close framing (${shotType}) with almost all sharpness concentrated at the center fits macro focus.`,\r\n"
    b"      focusPlane: 'foreground', separation: clamp((sharpnessRatio - 1) / 4, 0, 1)\r\n"
    b"    };\r\n"
    b"  }"
)
assert old_macro in content, "macro path not found"
content = content.replace(old_macro, new_macro, 1)
print("3. Macro: skip for animation")

# ─────────────────────────────────────────────────────────────────────
# 4. Deep focus 경로: 애니메이션에서 skip (uniform sharpness = Normal, not Deep)
# ─────────────────────────────────────────────────────────────────────
old_deep = (
    b"  // Uniform sharpness, high overall detail, wide or landscape shot\r\n"
    b"  if (sharpnessRatio < 1.14 && overallSharpness > 8.0) {\r\n"
    b"    const conf = clamp(0.64 + (overallSharpness - 8.0) * 0.025, 0.64, 0.84);\r\n"
    b"    return {\r\n"
    b"      type: 'Deep', confidence: conf,\r\n"
    b"      detail: `Sharpness stays broadly even across the frame (overall ${Math.round(overallSharpness * 10) / 10}), which fits deep focus.`,\r\n"
    b"      focusPlane: 'pan-focus', separation: 0\r\n"
    b"    };\r\n"
    b"  }"
)
new_deep = (
    b"  // Uniform sharpness, high overall detail, wide or landscape shot\r\n"
    b"  // Animation: uniform sharpness means NO DOF, not Deep focus (optical lens effect)\r\n"
    b"  if (sharpnessRatio < 1.14 && overallSharpness > 8.0 && !isAnimDOF) {\r\n"
    b"    const conf = clamp(0.64 + (overallSharpness - 8.0) * 0.025, 0.64, 0.84);\r\n"
    b"    return {\r\n"
    b"      type: 'Deep', confidence: conf,\r\n"
    b"      detail: `Sharpness stays broadly even across the frame (overall ${Math.round(overallSharpness * 10) / 10}), which fits deep focus.`,\r\n"
    b"      focusPlane: 'pan-focus', separation: 0\r\n"
    b"    };\r\n"
    b"  }"
)
assert old_deep in content, "deep focus path not found"
content = content.replace(old_deep, new_deep, 1)
print("4. Deep focus: skip for animation (uniform sharpness = Normal, not Deep)")

# ─────────────────────────────────────────────────────────────────────
# 5. 호출부에 contentMode 전달
# ─────────────────────────────────────────────────────────────────────
old_dof_call = b"  const dof = estimateDOF(focusAnalysis, shotSize, faceAnalysis, poseAnalysis);\r\n"
new_dof_call = b"  const dof = estimateDOF(focusAnalysis, shotSize, faceAnalysis, poseAnalysis, contentMode);\r\n"
assert old_dof_call in content, "dof call site not found"
content = content.replace(old_dof_call, new_dof_call, 1)
print("5. estimateDOF call site: contentMode added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP3-2 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
