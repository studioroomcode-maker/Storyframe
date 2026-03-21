#!/usr/bin/env python3
# P2-2: 배경 분리 옵티컬 플로우
#
# 핵심 아이디어:
#   현재 전체 프레임 opticalFlow는 큰 캐릭터가 움직이면 오염됨.
#   → 피사체 영역(bbox) 제외한 배경 픽셀만 비교 (MAD)
#   배경 안정 + 피사체 변화 크면 → Static 카메라 (캐릭터 애니메이션)
#
# 삽입 위치: subStableSize 계산 후, subjectMotionAlignment 블록 전

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

old_insert = (
    b"    const subStableSize = Math.abs(subDS) < 0.06;\r\n"
    b"\r\n"
    b"    // Subject motion alignment check:\r\n"
)
new_insert = (
    b"    const subStableSize = Math.abs(subDS) < 0.06;\r\n"
    b"\r\n"
    b"    // P2-2: Background-region stability check.\r\n"
    b"    // Compare first vs last coarse frame, but ONLY for pixels outside the subject bbox.\r\n"
    b"    // If background pixels are stable (low MAD) but subject region changed a lot,\r\n"
    b"    // it is strong evidence of character animation on a static camera.\r\n"
    b"    let bgStabilityEvidence = null;  // { bgMAD, subjMAD, bgStable, subjActive }\r\n"
    b"    if (subjectPresent && coarseFrames.length >= 2) {\r\n"
    b"      const cf0 = coarseFrames[0];\r\n"
    b"      const cfN = coarseFrames[coarseFrames.length - 1];\r\n"
    b"      const bw = cf0.w, bh = cf0.h;\r\n"
    b"\r\n"
    b"      // Estimate subject bounding box from center + size (heightRatio)\r\n"
    b"      const avgSubCX = subjects.reduce((s, sub) => s + sub.centerX, 0) / subjects.length;\r\n"
    b"      const avgSubCY = subjects.reduce((s, sub) => s + sub.centerY, 0) / subjects.length;\r\n"
    b"      const maxSubSz = Math.max(...subjects.map(sub => sub.size));\r\n"
    b"      const bboxL = Math.max(0,  Math.floor((avgSubCX - maxSubSz * 0.45) * bw));\r\n"
    b"      const bboxR = Math.min(bw, Math.ceil( (avgSubCX + maxSubSz * 0.45) * bw));\r\n"
    b"      const bboxT = Math.max(0,  Math.floor((avgSubCY - maxSubSz * 0.60) * bh));\r\n"
    b"      const bboxB = Math.min(bh, Math.ceil( (avgSubCY + maxSubSz * 0.60) * bh));\r\n"
    b"\r\n"
    b"      let bgDiff = 0, bgCount = 0, subjDiff = 0, subjCount = 0;\r\n"
    b"      for (let y = 0; y < bh; y++) {\r\n"
    b"        for (let x = 0; x < bw; x++) {\r\n"
    b"          const diff = Math.abs(cf0.gray[y * bw + x] - cfN.gray[y * bw + x]);\r\n"
    b"          if (x >= bboxL && x < bboxR && y >= bboxT && y < bboxB) {\r\n"
    b"            subjDiff += diff; subjCount++;\r\n"
    b"          } else {\r\n"
    b"            bgDiff += diff; bgCount++;\r\n"
    b"          }\r\n"
    b"        }\r\n"
    b"      }\r\n"
    b"\r\n"
    b"      const bgMAD   = bgCount   > 0 ? bgDiff   / bgCount   : 0;\r\n"
    b"      const subjMAD = subjCount > 0 ? subjDiff / subjCount : 0;\r\n"
    b"      // bgMAD < 8.0 / 255 ~ 3.1%: background barely changed\r\n"
    b"      // subjMAD > 18.0 / 255 ~ 7.1%: subject changed significantly\r\n"
    b"      const bgStable   = bgMAD   < 8.0;   // very little background change\r\n"
    b"      const subjActive = subjMAD > 18.0;  // subject changed significantly\r\n"
    b"      const bgRatio    = bgCount > 0 ? bgCount / (bw * bh) : 0;  // fraction of frame that is background\r\n"
    b"      if (bgRatio > 0.25) {  // only valid if enough background is visible\r\n"
    b"        bgStabilityEvidence = { bgMAD, subjMAD, bgStable, subjActive,\r\n"
    b"          ratio: subjMAD / Math.max(bgMAD, 0.5), bgRatio };\r\n"
    b"      }\r\n"
    b"    }\r\n"
    b"\r\n"
    b"    // Subject motion alignment check:\r\n"
)
assert old_insert in content, "insertion point not found"
content = content.replace(old_insert, new_insert, 1)
print("1. Background stability check code added")

# ─────────────────────────────────────────────────────────────────────
# 2. subjectMotionAlignment override 블록 뒤에 bgStabilityEvidence 활용 추가
#    bgStable + subjActive + ratio > 2.5 → Static (character animation) override
# ─────────────────────────────────────────────────────────────────────
old_sma_override = (
    b"    // Subject motion alignment override:\r\n"
    b"    // If global flow aligns closely with tracked subject movement,\r\n"
    b"    // the camera is likely static and we're seeing character animation.\r\n"
    b"    if (subjectMotionAlignment < 0.30 && avgResidual > 0.07 && avgGain > 0.05 && avgMagnitude > 0.7) {\r\n"
    b"      const motConf = clamp(0.56 + (0.30 - subjectMotionAlignment) * 0.7, 0.56, 0.78);\r\n"
)
new_sma_override = (
    b"    // Background stability override (P2-2):\r\n"
    b"    // When background pixels are stable but subject region changed a lot,\r\n"
    b"    // this is strong evidence the camera is static and subject is animating.\r\n"
    b"    if (bgStabilityEvidence && bgStabilityEvidence.bgStable && bgStabilityEvidence.subjActive\r\n"
    b"        && bgStabilityEvidence.ratio > 2.5 && bgStabilityEvidence.bgRatio > 0.30) {\r\n"
    b"      const bgConf = clamp(0.60 + (bgStabilityEvidence.ratio - 2.5) * 0.05, 0.60, 0.84);\r\n"
    b"      return { type: 'Static', confidence: bgConf,\r\n"
    b"        detail: `Background pixels are stable (MAD=${bgStabilityEvidence.bgMAD.toFixed(1)}) while subject region changed (MAD=${bgStabilityEvidence.subjMAD.toFixed(1)}) \\u2014 camera is locked, subject is animating.`,\r\n"
    b"        direction: null, speed: 'none', smoothness: 1.0 };\r\n"
    b"    }\r\n"
    b"\r\n"
    b"    // Subject motion alignment override:\r\n"
    b"    // If global flow aligns closely with tracked subject movement,\r\n"
    b"    // the camera is likely static and we're seeing character animation.\r\n"
    b"    if (subjectMotionAlignment < 0.30 && avgResidual > 0.07 && avgGain > 0.05 && avgMagnitude > 0.7) {\r\n"
    b"      const motConf = clamp(0.56 + (0.30 - subjectMotionAlignment) * 0.7, 0.56, 0.78);\r\n"
)
assert old_sma_override in content, "SMA override not found"
content = content.replace(old_sma_override, new_sma_override, 1)
print("2. Background stability override added before SMA override")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP2-2 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
