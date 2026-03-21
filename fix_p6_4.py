#!/usr/bin/env python3
# P6-4: OTS 감지 사이즈 비율 가드 추가
#
# 핵심 수정:
#   OTS(Over-the-Shoulder)는 전경 큰 얼굴 + 배경 작은 얼굴 구도
#   → 두 얼굴의 높이 비율 확인: edge face(배경)가 center face(전경)보다 작아야 진짜 OTS
#   - sizeRatio < 0.75: edge face가 확실히 작음 → confidence 보너스
#   - sizeRatio >= 0.75: 비슷한 크기 → 일반 Two-shot일 가능성 높음 → 패널티

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()
original = content

old_ots = (
    b"    if (edgeFace && centerFace) {\r\n"
    b"      // Confidence based on how distinct the edge/center separation is\r\n"
    b"      const separation = Math.abs(edgeFace.cx - centerFace.cx);\r\n"
    b"      return fr('OTS', clamp(0.64 + separation * 0.6, 0.64, 0.84));\r\n"
    b"    }\r\n"
)
new_ots = (
    b"    if (edgeFace && centerFace) {\r\n"
    b"      // Confidence based on spatial separation + size ratio\r\n"
    b"      const separation = Math.abs(edgeFace.cx - centerFace.cx);\r\n"
    b"      // OTS: edge (background) face should be notably smaller than center (foreground) face\r\n"
    b"      const sizeRatio = edgeFace.height / Math.max(centerFace.height, 0.01);\r\n"
    b"      const sizeSignal = sizeRatio < 0.75\r\n"
    b"        ? clamp((0.75 - sizeRatio) / 0.35, 0, 0.10)   // bonus: clear foreground/background size gap\r\n"
    b"        : -0.06;                                        // penalty: similar size = probably Two-shot\r\n"
    b"      return fr('OTS', clamp(0.64 + separation * 0.6 + sizeSignal, 0.60, 0.84));\r\n"
    b"    }\r\n"
)
assert old_ots in content, "OTS confidence block not found"
content = content.replace(old_ots, new_ots, 1)
print("1. OTS: size ratio guard added (sizeRatio < 0.75 = bonus, >= 0.75 = penalty)")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP6-4 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
