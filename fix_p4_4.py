#!/usr/bin/env python3
# P4-4: 프레이밍 confidence 메트릭 추가 + OTS 감지 개선
#
# 핵심 수정:
#   1. estimateFraming: 문자열 반환 -> { type, confidence } 객체 반환
#      - count 기반 분류: Single/Two-shot/Three-shot/Crowd = 명확 (0.82-0.92)
#      - OTS: 겹치는 조건 = 약한 신호 (0.64), 양쪽 다 명확 = 강한 신호 (0.80)
#      - Empty: 0.70 (얼굴/포즈 없음 = 어느 정도 확실)
#   2. 출력에 framingConf 필드 추가
#   3. OTS 감지: area 임계값 0.03->0.02로 완화 (작은 얼굴도 감지)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. estimateFraming 함수: 객체 반환으로 변경
# ─────────────────────────────────────────────────────────────────────
old_framing_func = (
    b"function estimateFraming(faceAnalysis, poseAnalysis, composition) {\r\n"
    b"  const faceCount = faceAnalysis?.count || 0;\r\n"
    b"  const poseCount = poseAnalysis?.count || 0;\r\n"
    b"  const count = Math.max(faceCount, poseCount);\r\n"
    b"\r\n"
    b"  if (!count) return composition.hasFace ? 'Single' : 'Empty';\r\n"
    b"  if (count > 3) return 'Crowd';\r\n"
    b"  if (count === 3) return 'Three-shot';\r\n"
    b"\r\n"
    b"  const faceBoxes = faceAnalysis?.boxes || [];\r\n"
    b"  if (count >= 2) {\r\n"
    b"    const edgeFace = faceBoxes.find(box =>\r\n"
    b"      box.area > 0.03\r\n"
    b"      && box.height > 0.2\r\n"
    b"      && (box.cx < 0.2 || box.cx > 0.8)\r\n"
    b"    );\r\n"
    b"    const centerFace = faceBoxes.find(box =>\r\n"
    b"      box.height > 0.12\r\n"
    b"      && box.cx > 0.3\r\n"
    b"      && box.cx < 0.7\r\n"
    b"    );\r\n"
    b"    if (edgeFace && centerFace) return 'OTS';\r\n"
    b"\r\n"
    b"    const poses = poseAnalysis?.poses || [];\r\n"
    b"    const edgePose = poses.find(pose =>\r\n"
    b"      pose.widthRatio > 0.2\r\n"
    b"      && (pose.centerX < 0.2 || pose.centerX > 0.8)\r\n"
    b"    );\r\n"
    b"    const centerPose = poses.find(pose => pose.centerX > 0.3 && pose.centerX < 0.7);\r\n"
    b"    if (edgePose && centerPose) return 'OTS';\r\n"
    b"\r\n"
    b"    return count === 2 ? 'Two-shot' : 'Three-shot';\r\n"
    b"  }\r\n"
    b"\r\n"
    b"  if (faceAnalysis?.framing === 'OTS') return 'OTS';\r\n"
    b"  return 'Single';\r\n"
    b"}"
)
new_framing_func = (
    b"function estimateFraming(faceAnalysis, poseAnalysis, composition) {\r\n"
    b"  const faceCount = faceAnalysis?.count || 0;\r\n"
    b"  const poseCount = poseAnalysis?.count || 0;\r\n"
    b"  const count = Math.max(faceCount, poseCount);\r\n"
    b"  const fr = (type, confidence) => ({ type, confidence });\r\n"
    b"\r\n"
    b"  if (!count) return fr(composition.hasFace ? 'Single' : 'Empty', composition.hasFace ? 0.60 : 0.70);\r\n"
    b"  if (count > 3) return fr('Crowd', 0.88);\r\n"
    b"  if (count === 3) return fr('Three-shot', 0.86);\r\n"
    b"\r\n"
    b"  const faceBoxes = faceAnalysis?.boxes || [];\r\n"
    b"  if (count >= 2) {\r\n"
    b"    // OTS: one face at edge (small, background) + one face at center (larger, foreground)\r\n"
    b"    const edgeFace = faceBoxes.find(box =>\r\n"
    b"      box.area > 0.02        // relaxed from 0.03\r\n"
    b"      && box.height > 0.18   // relaxed from 0.20\r\n"
    b"      && (box.cx < 0.22 || box.cx > 0.78)\r\n"
    b"    );\r\n"
    b"    const centerFace = faceBoxes.find(box =>\r\n"
    b"      box.height > 0.10      // relaxed from 0.12\r\n"
    b"      && box.cx > 0.28\r\n"
    b"      && box.cx < 0.72\r\n"
    b"    );\r\n"
    b"    if (edgeFace && centerFace) {\r\n"
    b"      // Confidence based on how distinct the edge/center separation is\r\n"
    b"      const separation = Math.abs(edgeFace.cx - centerFace.cx);\r\n"
    b"      return fr('OTS', clamp(0.64 + separation * 0.6, 0.64, 0.84));\r\n"
    b"    }\r\n"
    b"\r\n"
    b"    const poses = poseAnalysis?.poses || [];\r\n"
    b"    const edgePose = poses.find(pose =>\r\n"
    b"      pose.widthRatio > 0.15   // relaxed from 0.20\r\n"
    b"      && (pose.centerX < 0.22 || pose.centerX > 0.78)\r\n"
    b"    );\r\n"
    b"    const centerPose = poses.find(pose => pose.centerX > 0.28 && pose.centerX < 0.72);\r\n"
    b"    if (edgePose && centerPose) return fr('OTS', 0.64);\r\n"
    b"\r\n"
    b"    return fr(count === 2 ? 'Two-shot' : 'Three-shot', 0.84);\r\n"
    b"  }\r\n"
    b"\r\n"
    b"  if (faceAnalysis?.framing === 'OTS') return fr('OTS', 0.60);\r\n"
    b"  // Single subject: confidence based on detection strength\r\n"
    b"  const singleConf = faceAnalysis?.count > 0\r\n"
    b"    ? clamp(0.72 + (faceAnalysis.largestAreaRatio ?? 0) * 2.0, 0.72, 0.90)\r\n"
    b"    : 0.62;\r\n"
    b"  return fr('Single', singleConf);\r\n"
    b"}"
)
assert old_framing_func in content, "estimateFraming not found"
content = content.replace(old_framing_func, new_framing_func, 1)
print("1. estimateFraming: returns { type, confidence } object")

# ─────────────────────────────────────────────────────────────────────
# 2. 호출부: framing 객체에서 .type 추출 + framingConf 저장
# ─────────────────────────────────────────────────────────────────────
old_framing_call = b"  const framing = estimateFraming(faceAnalysis, poseAnalysis, composition);\r\n"
new_framing_call = (
    b"  const framingResult = estimateFraming(faceAnalysis, poseAnalysis, composition);\r\n"
    b"  const framing = framingResult.type;\r\n"
    b"  const framingConf = framingResult.confidence;\r\n"
)
assert old_framing_call in content, "framing call not found"
content = content.replace(old_framing_call, new_framing_call, 1)
print("2. Framing call: framingConf extracted")

# ─────────────────────────────────────────────────────────────────────
# 3. 출력 객체에 framingConf 추가
# ─────────────────────────────────────────────────────────────────────
old_framing_output = (
    b"    framing:            learnLabel('framing')   || framing,\r\n"
    b"    lensType:           learnLabel('lensType')  || lens.type,\r\n"
)
new_framing_output = (
    b"    framing:            learnLabel('framing')   || framing,\r\n"
    b"    framingConf:        L['framing'] ? clamp(0.72 + (L['framing'].sim - 0.80) * 1.1, 0.72, 0.94) : framingConf,\r\n"
    b"    lensType:           learnLabel('lensType')  || lens.type,\r\n"
)
assert old_framing_output in content, "framing output not found"
content = content.replace(old_framing_output, new_framing_output, 1)
print("3. framingConf added to output object")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP4-4 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
