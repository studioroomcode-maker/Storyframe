#!/usr/bin/env python3
# P5-3: Eye-level vs Shoulder-level 분리 개선
#
# 핵심 수정:
#   1. eyeScore: Wide/LS/ELS 샷 타입 보너스 +0.12
#      → 광각/풀샷은 대부분 아이레벨, 숄더레벨과 혼동 방지
#   2. shoulderScore: subjectY 중심 0.56 → 0.57 (약간 더 아래쪽으로)
#      + MCU/CU 보너스에 subjectY 조건 추가
#      (숄더레벨 = 카메라 아래에서 살짝 올려봄 → 피사체가 중심보다 약간 위에 있어야 함)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. eyeScore: Wide shot bonus
# ─────────────────────────────────────────────────────────────────────
old_eye = (
    b"    const eyeScore =\r\n"
    b"      clamp(1 - Math.abs(subjectY - 0.50) / 0.17, 0, 1) * 0.40 +\r\n"
    b"      clamp(1 - Math.abs(effVertBias) / 0.15, 0, 1) * 0.28 +\r\n"
    b"      clamp(1 - Math.abs(centroidY - 0.50) / 0.16, 0, 1) * 0.18 +\r\n"
    b"      (Math.abs(rowTop - rowBot) < 0.08 ? 0.14 : 0);\r\n"
)
new_eye = (
    b"    const eyeScore =\r\n"
    b"      clamp(1 - Math.abs(subjectY - 0.50) / 0.17, 0, 1) * 0.40 +\r\n"
    b"      clamp(1 - Math.abs(effVertBias) / 0.15, 0, 1) * 0.28 +\r\n"
    b"      clamp(1 - Math.abs(centroidY - 0.50) / 0.16, 0, 1) * 0.18 +\r\n"
    b"      (Math.abs(rowTop - rowBot) < 0.08 ? 0.14 : 0) +\r\n"
    b"      // Wide/establishing shots are almost always eye-level in narrative filmmaking\r\n"
    b"      (['LS', 'ELS', 'FS', 'MLS', 'Establishing'].includes(shotType) ? 0.12 : 0);\r\n"
)
assert old_eye in content, "eyeScore not found"
content = content.replace(old_eye, new_eye, 1)
print("1. eyeScore: wide/LS/ELS bonus +0.12 added")

# ─────────────────────────────────────────────────────────────────────
# 2. shoulderScore: center 0.56->0.57, MCU bonus conditioned on subjectY
# ─────────────────────────────────────────────────────────────────────
old_shoulder = (
    b"    const shoulderScore =\r\n"
    b"      clamp(1 - Math.abs(subjectY - 0.56) / 0.14, 0, 1) * 0.40 +\r\n"
    b"      clamp(1 - Math.abs(effVertBias - 0.04) / 0.12, 0, 1) * 0.22 +\r\n"
    b"      (['MCU', 'CU', 'BCU', 'MS', 'Cowboy'].includes(shotType) ? 0.24 : 0) +\r\n"
    b"      (faceH > 0.12 && faceH < 0.40 ? 0.14 : 0);\r\n"
)
new_shoulder = (
    b"    const shoulderScore =\r\n"
    b"      clamp(1 - Math.abs(subjectY - 0.57) / 0.14, 0, 1) * 0.40 +\r\n"  # 0.56->0.57
    b"      clamp(1 - Math.abs(effVertBias - 0.04) / 0.12, 0, 1) * 0.22 +\r\n"
    b"      // MCU/CU bonus only when subject is at/below center (camera slightly lower = looking up)\r\n"
    b"      (['MCU', 'CU', 'BCU', 'MS', 'Cowboy'].includes(shotType) && subjectY >= 0.46 ? 0.24 : 0) +\r\n"
    b"      (faceH > 0.12 && faceH < 0.40 ? 0.14 : 0);\r\n"
)
assert old_shoulder in content, "shoulderScore not found"
content = content.replace(old_shoulder, new_shoulder, 1)
print("2. shoulderScore: center 0.56->0.57, MCU bonus requires subjectY >= 0.46")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP5-3 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
