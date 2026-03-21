#!/usr/bin/env python3
# P3-4: detectContentMode CG vs 2D 서브타입 구분
#
# 핵심 아이디어:
#   CG 애니메이션(픽사, 3D 게임)은 실제 카메라 물리학 시뮬레이션 → 렌즈/DOF 가드 불필요
#   2D 셀 애니메이션(지브리, TV애니)은 광학 효과 없음 → 기존 가드 유지
#
# 서브타입 판별:
#   satEntropy < 2.5 AND colorCount < 150 → 'cel' (2D 극소 팔레트)
#   그 외 animation → 'cg' (3D, 팔레트 크지만 여전히 live-action보다 제한적)
#
# 결과 활용:
#   isCGAnim: true → lens/DOF/angle 가드 해제 (CG는 광학 물리학 시뮬)
#   isCelAnim: true → 기존 모든 가드 적용
#
# 구현:
#   1. detectContentMode: subtype + isCGAnim 필드 추가
#   2. 모든 animation guard에서 cel 체크 조건 추가 (contentMode.isCelAnim)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. detectContentMode 반환값에 subtype/isCGAnim/isCelAnim 추가
# ─────────────────────────────────────────────────────────────────────
old_detect_return = (
    b"  const raw = satEntropyScore * 0.55 + colorQuantScore * 0.45;\r\n"
    b"  const isAnimation = raw > 0.45;\r\n"
    b"  return {\r\n"
    b"    score: raw,\r\n"
    b"    isAnimation,\r\n"
    b"    confidence: Math.min(Math.abs(raw - 0.45) * 2.2, 1.0),\r\n"
    b"    detail: `satEntropy=${satEntropy.toFixed(2)} colorCount=${colorSet.size} animScore=${raw.toFixed(2)}`\r\n"
    b"  };\r\n"
    b"}"
)
new_detect_return = (
    b"  const raw = satEntropyScore * 0.55 + colorQuantScore * 0.45;\r\n"
    b"  const isAnimation = raw > 0.45;\r\n"
    b"\r\n"
    b"  // P3-4: Subtype detection - CG animation vs 2D/cel animation\r\n"
    b"  // CG animation (Pixar/game-style) simulates real camera physics -> less need for guards\r\n"
    b"  // 2D/cel animation (hand-drawn) has no optical physics -> apply all guards\r\n"
    b"  // Cel indicators: very low entropy + very small palette\r\n"
    b"  const isCelAnim  = isAnimation && satEntropy < 2.8 && colorSet.size < 200;\r\n"
    b"  const isCGAnim   = isAnimation && !isCelAnim;  // higher color variety -> likely 3D/CG\r\n"
    b"  const subtype = !isAnimation ? 'live' : isCelAnim ? 'cel' : 'cg';\r\n"
    b"\r\n"
    b"  return {\r\n"
    b"    score: raw,\r\n"
    b"    isAnimation,\r\n"
    b"    isCelAnim,  // true: 2D/cel - no optical physics, apply all animation guards\r\n"
    b"    isCGAnim,   // true: CG - has virtual camera physics, guards partially relaxed\r\n"
    b"    subtype,    // 'live' | 'cel' | 'cg'\r\n"
    b"    confidence: Math.min(Math.abs(raw - 0.45) * 2.2, 1.0),\r\n"
    b"    detail: `satEntropy=${satEntropy.toFixed(2)} colorCount=${colorSet.size} animScore=${raw.toFixed(2)} subtype=${subtype}`\r\n"
    b"  };\r\n"
    b"}"
)
assert old_detect_return in content, "detectContentMode return not found"
content = content.replace(old_detect_return, new_detect_return, 1)
print("1. detectContentMode: subtype/isCGAnim/isCelAnim added")

# ─────────────────────────────────────────────────────────────────────
# 2. estimateLens 애니메이션 가드: CG에서는 기본값 반환 안 함
#    (CG는 real virtual camera DOF 가짐)
# ─────────────────────────────────────────────────────────────────────
old_lens_anim_guard = (
    b"  // Only apply optical analysis when: content is live-action, OR animator explicitly rendered DOF.\r\n"
    b"  if (contentMode && contentMode.isAnimation && contentMode.confidence > 0.40) {\r\n"
)
new_lens_anim_guard = (
    b"  // Only apply optical analysis when: live-action, CG (virtual camera), OR cel with explicit DOF.\r\n"
    b"  // CG animation uses a virtual camera with real physics - lens estimation is valid for CG.\r\n"
    b"  if (contentMode && contentMode.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40) {\r\n"
)
assert old_lens_anim_guard in content, "lens anim guard not found"
content = content.replace(old_lens_anim_guard, new_lens_anim_guard, 1)
print("2. estimateLens: guard restricted to cel animation only")

# ─────────────────────────────────────────────────────────────────────
# 3. estimateAngle animConfCap: CG에서는 cap 적용 안 함
# ─────────────────────────────────────────────────────────────────────
old_conf_cap = (
    b"  const animConfCap = (contentMode && contentMode.isAnimation && contentMode.confidence > 0.40) ? 0.68 : 1.0;\r\n"
)
new_conf_cap = (
    b"  // animConfCap: only apply to cel (2D) animation; CG has real virtual camera angles\r\n"
    b"  const animConfCap = (contentMode && contentMode.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40) ? 0.68 : 1.0;\r\n"
)
assert old_conf_cap in content, "animConfCap not found"
content = content.replace(old_conf_cap, new_conf_cap, 1)
print("3. animConfCap: restricted to cel animation")

# ─────────────────────────────────────────────────────────────────────
# 4. estimateAngle isAnimScene: CG에서는 eff 신호 비활성화 안 함
# ─────────────────────────────────────────────────────────────────────
old_isanim_scene = (
    b"  const isAnimScene = contentMode && contentMode.isAnimation && contentMode.confidence > 0.40;\r\n"
)
new_isanim_scene = (
    b"  // isAnimScene: only cel (2D) animation has unreliable sky/ground/foreshortening signals.\r\n"
    b"  // CG animation uses simulated real-world lighting and perspective, so signals remain valid.\r\n"
    b"  const isAnimScene = contentMode && contentMode.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40;\r\n"
)
assert old_isanim_scene in content, "isAnimScene not found"
content = content.replace(old_isanim_scene, new_isanim_scene, 1)
print("4. isAnimScene: restricted to cel animation")

# ─────────────────────────────────────────────────────────────────────
# 5. estimateDOF isAnimDOF: CG에서는 DOF 가드 적용 안 함
# ─────────────────────────────────────────────────────────────────────
old_isanim_dof = (
    b"  const isAnimDOF = contentMode && contentMode.isAnimation && contentMode.confidence > 0.40;\r\n"
)
new_isanim_dof = (
    b"  // isAnimDOF: only for cel animation. CG animation renders real DOF from virtual cameras.\r\n"
    b"  const isAnimDOF = contentMode && contentMode.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40;\r\n"
)
assert old_isanim_dof in content, "isAnimDOF not found"
content = content.replace(old_isanim_dof, new_isanim_dof, 1)
print("5. isAnimDOF: restricted to cel animation")

# ─────────────────────────────────────────────────────────────────────
# 6. estimateLighting isAnimLighting: CG에서는 lighting 가드 적용 안 함
# ─────────────────────────────────────────────────────────────────────
old_isanim_lighting = (
    b"  const isAnimLighting = contentMode && contentMode.isAnimation && contentMode.confidence > 0.40;\r\n"
)
new_isanim_lighting = (
    b"  // isAnimLighting: only cel (2D) animation has rim light and gradient issues.\r\n"
    b"  // CG animation renders realistic lighting from virtual light sources.\r\n"
    b"  const isAnimLighting = contentMode && contentMode.isAnimation && contentMode.isCelAnim && contentMode.confidence > 0.40;\r\n"
)
assert old_isanim_lighting in content, "isAnimLighting not found"
content = content.replace(old_isanim_lighting, new_isanim_lighting, 1)
print("6. isAnimLighting: restricted to cel animation")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP3-4 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
