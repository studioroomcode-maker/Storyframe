#!/usr/bin/env python3
# P5-2: 샷 사이즈 경계값 신뢰도 보정 + 애니메이션 face-only 경로 보정
#
# 핵심 문제:
#   1. adjustedFaceH가 경계값 근처(±0.025)일 때 confidence가 너무 높음
#      → 경계 근처에서 -0.06 confidence 패널티
#   2. 애니메이션 proportion correction이 pose 기반 경로에만 적용됨
#      face-only 경로에서도 적용 필요

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. 포즈 기반 conf 계산에 경계 근처 패널티 추가
# ─────────────────────────────────────────────────────────────────────
old_conf = (
    b"    const conf = clamp(\r\n"
    b"      0.56\r\n"
    b"        + Math.min(pose.confidence * 0.22, 0.2)\r\n"
    b"        + Math.min(Math.max(subjectHeight - 0.15, 0) * 0.18, 0.12)\r\n"
    b"        + (faceAnalysis?.count > 0 ? 0.04 : 0)\r\n"
    b"        + (pose.hasMask ? 0.04 : 0)\r\n"
    b"        + crossConf,\r\n"
    b"      0.56, 0.96\r\n"
    b"    );\r\n"
)
new_conf = (
    b"    // Boundary uncertainty: reduce confidence when near a classification threshold\r\n"
    b"    const BOUNDARIES = [0.72, 0.55, 0.38, 0.22];\r\n"
    b"    const nearBoundary = BOUNDARIES.some(b => Math.abs(adjustedFaceH - b) < 0.025);\r\n"
    b"    const boundaryPenalty = nearBoundary ? -0.06 : 0;\r\n"
    b"    const conf = clamp(\r\n"
    b"      0.56\r\n"
    b"        + Math.min(pose.confidence * 0.22, 0.2)\r\n"
    b"        + Math.min(Math.max(subjectHeight - 0.15, 0) * 0.18, 0.12)\r\n"
    b"        + (faceAnalysis?.count > 0 ? 0.04 : 0)\r\n"
    b"        + (pose.hasMask ? 0.04 : 0)\r\n"
    b"        + crossConf\r\n"
    b"        + boundaryPenalty,\r\n"
    b"      0.50, 0.96\r\n"
    b"    );\r\n"
)
assert old_conf in content, "pose conf not found"
content = content.replace(old_conf, new_conf, 1)
print("1. Pose path: boundary penalty added (-0.06 within 0.025 of threshold)")

# ─────────────────────────────────────────────────────────────────────
# 2. face-only 경로 찾기: 애니 proportion correction 추가
# ─────────────────────────────────────────────────────────────────────
old_face_fh = (
    b"  if (poseReliable) {\r\n"
)
# We just need to find where face-only path starts to add proportion correction
# Let's find the face-only section
import sys
idx = content.find(b'  if (poseReliable) {')
section_after = content[idx:]

# Find the face-only section: it uses faceAnalysis after pose check fails
# Look for faceAnalysis path
face_path_start = b"  if (faceAnalysis && faceAnalysis.count > 0 && !poseReliable) {"
if face_path_start in content:
    print("Found face-only path marker (already separated)")
else:
    # Find face-only by its else
    print("2. Skipping (face-only path needs deeper analysis)")

# Alternative: find the face-height based classification after poseReliable block
# Look for the fh variable in face-only section
idx2 = content.find(b'  const fh = faceAnalysis?.maxHeightRatio ?? 0;')
if idx2 > 0:
    print(f"  Face-only section found at offset {idx2}")
    section = content[idx2:idx2+600]
    print(repr(section[:200]))

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP5-2 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No content changes (step 2 skipped)")
