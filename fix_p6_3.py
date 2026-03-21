#!/usr/bin/env python3
# P6-3: Zoom vs Push-in 분리 개선
#
# 핵심 수정:
#   1. Zoom 감지: magnitude 임계값 1.3 → 1.8 완화
#      (핸드헬드 줌 촬영에서 약한 손 떨림이 Push-in으로 오분류 방지)
#   2. Push-in: 실제 이동 성분(translation) 조건 추가
#      (순수 스케일 변화는 Zoom, 이동+스케일이면 Push-in)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()
original = content

# ─────────────────────────────────────────────────────────────────────
# 1. Zoom: magnitude 1.3 → 1.8, residual 0.09 → 0.10 완화
# ─────────────────────────────────────────────────────────────────────
old_zoom = (
    b"    // Zoom (optical: pure scale, minimal translation, low residual)\r\n"
    b"    if (avgAbsScale > 0.028 && dirConSc > 0.60 && avgScaleGain > 0.07 && avgMagnitude < 1.3 && avgResidual < 0.09) {\r\n"
)
new_zoom = (
    b"    // Zoom (optical: pure scale, minimal translation, low residual)\r\n"
    b"    // Relaxed magnitude 1.3->1.8: handheld zoom has slight translation noise\r\n"
    b"    if (avgAbsScale > 0.028 && dirConSc > 0.60 && avgScaleGain > 0.07 && avgMagnitude < 1.8 && avgResidual < 0.10) {\r\n"
)
assert old_zoom in content, "Zoom detection line not found"
content = content.replace(old_zoom, new_zoom, 1)
print("1. Zoom: magnitude threshold 1.3->1.8, residual 0.09->0.10")

# ─────────────────────────────────────────────────────────────────────
# 2. Push-in: translation 성분 조건 추가
# ─────────────────────────────────────────────────────────────────────
old_pushin = (
    b"    // Push-in / Pull-out (scale + translation combined)\r\n"
    b"    if (avgAbsScale > 0.024 && dirConSc > 0.55 && avgScaleGain > 0.055) {\r\n"
)
new_pushin = (
    b"    // Push-in / Pull-out (scale + translation combined; requires meaningful translation)\r\n"
    b"    // avgMagnitude > 0.55: must have real translation (not just scale noise)\r\n"
    b"    // OR avgAbsScale > 0.040: very large scale alone also qualifies\r\n"
    b"    if (avgAbsScale > 0.024 && dirConSc > 0.55 && avgScaleGain > 0.055 && (avgMagnitude > 0.55 || avgAbsScale > 0.040)) {\r\n"
)
assert old_pushin in content, "Push-in detection line not found"
content = content.replace(old_pushin, new_pushin, 1)
print("2. Push-in: translation requirement added (avgMagnitude > 0.55 || avgAbsScale > 0.040)")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP6-3 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
