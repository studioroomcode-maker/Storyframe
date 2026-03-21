#!/usr/bin/env python3
# P4-2: DOF 정확도 개선 (62% -> 72%+ 목표)
#
# 핵심 수정:
#   1. 'Normal' 타입 -> 'Moderate' (공식 DOF 타입으로 통일)
#   2. Wide shot에서 Deep focus 기본값 강화 (LS/ELS는 자연스럽게 Deep)
#   3. 기본 fallback confidence 0.50 -> 0.54 + 근거 추가
#   4. Very-shallow threshold: portraitDOF 조건 완화 (더 유연하게 감지)
#   5. Moderate/Deep 경계: sharpnessRatio 1.10-1.18 구간에서 Wide shot은 Deep

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. Animation guard return: 'Normal' -> 'Moderate'
#    (공식 DOF 타입 목록에 없는 'Normal' 사용 중 -> 'Moderate'로 통일)
# ─────────────────────────────────────────────────────────────────────
old_anim_normal = (
    b"      return {\r\n"
    b"        type: 'Normal', confidence: 0.55,\r\n"
    b"        detail: 'Animation frame without explicit depth blur rendering - defaulting to Normal DOF.',\r\n"
    b"        focusPlane: 'pan-focus', separation: 0\r\n"
    b"      };\r\n"
)
new_anim_normal = (
    b"      return {\r\n"
    b"        type: 'Moderate', confidence: 0.54,\r\n"
    b"        detail: 'Animation frame without explicit depth blur rendering - DOF not applicable (cel animation).',\r\n"
    b"        focusPlane: 'pan-focus', separation: 0\r\n"
    b"      };\r\n"
)
assert old_anim_normal in content, "animation normal return not found"
content = content.replace(old_anim_normal, new_anim_normal, 1)
print("1. Animation DOF: 'Normal' -> 'Moderate'")

# ─────────────────────────────────────────────────────────────────────
# 2. Deep focus: Wide shot 보너스 추가
#    LS/ELS/Establishing은 자연스럽게 Deep focus (f/8+ equivalent)
# ─────────────────────────────────────────────────────────────────────
old_deep = (
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
new_deep = (
    b"  // Uniform sharpness, high overall detail, wide or landscape shot\r\n"
    b"  // Animation: uniform sharpness means NO DOF, not Deep focus (optical lens effect)\r\n"
    b"  // Wide shots: lower sharpnessRatio threshold (LS/ELS naturally have Deep focus)\r\n"
    b"  const deepRatioThresh = isWide ? 1.20 : 1.14;  // Wide shots can still have slight ratio\r\n"
    b"  const deepSharpThresh = isWide ? 6.5 : 8.0;    // Wide shots don't need as high overall sharpness\r\n"
    b"  if (sharpnessRatio < deepRatioThresh && overallSharpness > deepSharpThresh && !isAnimDOF) {\r\n"
    b"    const baseConf = isWide ? 0.68 : 0.64;\r\n"
    b"    const conf = clamp(baseConf + (overallSharpness - deepSharpThresh) * 0.025, baseConf, 0.86);\r\n"
    b"    return {\r\n"
    b"      type: 'Deep', confidence: conf,\r\n"
    b"      detail: `Sharpness stays broadly even across the frame (overall ${Math.round(overallSharpness * 10) / 10}), which fits deep focus${isWide ? ' - expected for wide-angle shots' : ''}.`,\r\n"
    b"      focusPlane: 'pan-focus', separation: 0\r\n"
    b"    };\r\n"
    b"  }"
)
assert old_deep in content, "deep focus not found"
content = content.replace(old_deep, new_deep, 1)
print("2. Deep focus: wide shot threshold relaxed")

# ─────────────────────────────────────────────────────────────────────
# 3. Default fallback: 0.50 confidence에 근거 추가 + Wide 기본값 Deep
# ─────────────────────────────────────────────────────────────────────
old_default = (
    b"  // Default\r\n"
    b"  return {\r\n"
    b"    type: overallSharpness > 7 ? 'Deep' : 'Moderate',\r\n"
    b"    confidence: 0.50,\r\n"
    b"    detail: overallSharpness > 7\r\n"
    b"      ? 'Overall sharpness stays fairly even, so the fallback leans toward deep focus.'\r\n"
    b"      : 'Depth cues are mixed, so the fallback stays at moderate depth of field.',\r\n"
    b"    focusPlane: overallSharpness > 7 ? 'pan-focus' : focusPlane,\r\n"
    b"    separation\r\n"
    b"  };\r\n"
    b"}"
)
new_default = (
    b"  // Default fallback: wide shots lean Deep, others lean Moderate\r\n"
    b"  const fallbackType = (isWide || overallSharpness > 7) ? 'Deep' : 'Moderate';\r\n"
    b"  const fallbackConf = isWide ? 0.56 : 0.50;\r\n"
    b"  return {\r\n"
    b"    type: fallbackType,\r\n"
    b"    confidence: fallbackConf,\r\n"
    b"    detail: fallbackType === 'Deep'\r\n"
    b"      ? `Overall sharpness is even${isWide ? ' (wide shot default)' : ''}, suggesting deep focus.`\r\n"
    b"      : 'Depth cues are mixed, so the fallback stays at moderate depth of field.',\r\n"
    b"    focusPlane: fallbackType === 'Deep' ? 'pan-focus' : focusPlane,\r\n"
    b"    separation\r\n"
    b"  };\r\n"
    b"}"
)
assert old_default in content, "default fallback not found"
content = content.replace(old_default, new_default, 1)
print("3. Default fallback: wide shot default + better confidence")

# ─────────────────────────────────────────────────────────────────────
# 4. Soft-focus fallback: 0.54 -> 0.56, 근거 개선
# ─────────────────────────────────────────────────────────────────────
old_soft_fallback = (
    b"  if (overallSharpness < 5.0 && sharpnessRatio < 1.35) {\r\n"
    b"    return {\r\n"
    b"      type: 'Soft-focus', confidence: 0.54,\r\n"
    b"      detail: 'Overall detail is low across the frame, which reads closer to a soft-focus look.',\r\n"
    b"      focusPlane: 'pan-focus', separation: 0\r\n"
    b"    };\r\n"
    b"  }"
)
new_soft_fallback = (
    b"  if (overallSharpness < 5.0 && sharpnessRatio < 1.35 && !isAnimDOF) {\r\n"
    b"    return {\r\n"
    b"      type: 'Soft-focus', confidence: clamp(0.54 + (5.0 - overallSharpness) * 0.04, 0.54, 0.70),\r\n"
    b"      detail: `Overall detail is low (${overallSharpness.toFixed(1)}) with even distribution, suggesting soft-focus treatment.`,\r\n"
    b"      focusPlane: 'pan-focus', separation: 0\r\n"
    b"    };\r\n"
    b"  }"
)
assert old_soft_fallback in content, "soft-focus fallback not found"
content = content.replace(old_soft_fallback, new_soft_fallback, 1)
print("4. Soft-focus fallback: scaled confidence + animation guard")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP4-2 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
