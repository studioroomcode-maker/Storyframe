# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# P5-2b: 샷 사이즈 face-only 경로 - 애니메이션 비율 보정 + 경계 신뢰도 패널티

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# Build patterns using actual Korean text (Python 3 UTF-8 source)
old_detail = '      detail: `얼굴 높이 ${Math.round(faceHeight * 100)}%, 면적 ${Math.round(faceArea * 100)}%로 ${type} 구도에 가깝습니다.`\r\n'.encode('utf-8')
new_detail = '      detail: `얼굴 높이 ${Math.round(rawFaceHeight * 100)}%(보정 ${Math.round(faceHeight * 100)}%), 면적 ${Math.round(faceArea * 100)}%로 ${type} 구도에 가깝습니다.`\r\n'.encode('utf-8')

assert old_detail in content, "detail line not found"
count_before = content.count(old_detail)
print(f"  detail line found {count_before} time(s)")

# Build old block: from faceArea line through closing brace
old_block_str = (
    "  if (faceAnalysis?.count > 0) {\r\n"
    "    const faceArea = faceAnalysis.largestAreaRatio;\r\n"
    "    const faceHeight = faceAnalysis.maxHeightRatio;\r\n"
    "    let type = 'MS';\r\n"
    "\r\n"
    "    if (faceHeight > 0.8 || faceArea > 0.5) type = 'ECU';\r\n"
    "    else if (faceHeight > 0.6 || faceArea > 0.3) type = 'BCU';\r\n"
    "    else if (faceHeight > 0.4 || faceArea > 0.17) type = 'CU';\r\n"
    "    else if (faceHeight > 0.26 || faceArea > 0.095) type = 'MCU';\r\n"
    "    else if (faceHeight > 0.17 || faceArea > 0.055) type = 'MS';\r\n"
    "    else if (faceHeight > 0.11 || faceArea > 0.028) type = 'Cowboy';\r\n"
    "    else if (faceHeight > 0.075 || faceArea > 0.016) type = 'MLS';\r\n"
    "    else if (faceHeight > 0.05 || faceArea > 0.008) type = 'FS';\r\n"
    "    else if (faceHeight > 0.03 || faceArea > 0.004) type = 'LS';\r\n"
    "    else type = 'ELS';\r\n"
    "\r\n"
    "    return {\r\n"
    "      type,\r\n"
    "      confidence: clamp(faceAnalysis.confidence + 0.04, 0.62, 0.94),\r\n"
    "      detail: `얼굴 높이 ${Math.round(faceHeight * 100)}%, 면적 ${Math.round(faceArea * 100)}%로 ${type} 구도에 가깝습니다.`\r\n"
    "    };\r\n"
    "  }\r\n"
)

new_block_str = (
    "  if (faceAnalysis?.count > 0) {\r\n"
    "    const faceArea = faceAnalysis.largestAreaRatio;\r\n"
    "    const rawFaceHeight = faceAnalysis.maxHeightRatio;\r\n"
    "    // Animation proportion correction (face-only path): cel animation characters have\r\n"
    "    // disproportionately large heads - correct before threshold comparison\r\n"
    "    const faceAnimFactor = (contentMode?.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40)\r\n"
    "      ? clamp(1.0 + (contentMode.confidence - 0.40) * 2.2, 1.0, 1.8)\r\n"
    "      : 1.0;\r\n"
    "    const faceHeight = faceAnimFactor > 1.0 ? rawFaceHeight / faceAnimFactor : rawFaceHeight;\r\n"
    "    let type = 'MS';\r\n"
    "\r\n"
    "    if (faceHeight > 0.8 || faceArea > 0.5) type = 'ECU';\r\n"
    "    else if (faceHeight > 0.6 || faceArea > 0.3) type = 'BCU';\r\n"
    "    else if (faceHeight > 0.4 || faceArea > 0.17) type = 'CU';\r\n"
    "    else if (faceHeight > 0.26 || faceArea > 0.095) type = 'MCU';\r\n"
    "    else if (faceHeight > 0.17 || faceArea > 0.055) type = 'MS';\r\n"
    "    else if (faceHeight > 0.11 || faceArea > 0.028) type = 'Cowboy';\r\n"
    "    else if (faceHeight > 0.075 || faceArea > 0.016) type = 'MLS';\r\n"
    "    else if (faceHeight > 0.05 || faceArea > 0.008) type = 'FS';\r\n"
    "    else if (faceHeight > 0.03 || faceArea > 0.004) type = 'LS';\r\n"
    "    else type = 'ELS';\r\n"
    "\r\n"
    "    // Boundary uncertainty: confidence penalty when near classification threshold\r\n"
    "    const FACE_BOUNDS = [0.8, 0.6, 0.4, 0.26, 0.17, 0.11, 0.075, 0.05, 0.03];\r\n"
    "    const nearFaceBound = FACE_BOUNDS.some(b => Math.abs(faceHeight - b) < 0.025);\r\n"
    "    const faceBoundPenalty = nearFaceBound ? -0.05 : 0;\r\n"
    "\r\n"
    "    return {\r\n"
    "      type,\r\n"
    "      confidence: clamp(faceAnalysis.confidence + 0.04 + faceBoundPenalty, 0.58, 0.94),\r\n"
    "      detail: `얼굴 높이 ${Math.round(rawFaceHeight * 100)}%(보정 ${Math.round(faceHeight * 100)}%), 면적 ${Math.round(faceArea * 100)}%로 ${type} 구도에 가깝습니다.`\r\n"
    "    };\r\n"
    "  }\r\n"
)

old_block = old_block_str.encode('utf-8')
new_block = new_block_str.encode('utf-8')

assert old_block in content, "face-only block not found!"
content = content.replace(old_block, new_block, 1)
print("1. Face-only path: animation proportion correction + boundary penalty added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP5-2b done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
