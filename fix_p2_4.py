#!/usr/bin/env python3
# P2-4: 양방향 학습 피드백 (Bidirectional Learning)
#
# 핵심 아이디어:
#   현재: 틀린 경우(negative)만 DB에 저장
#   개선: 맞은 경우(positive)도 저장 → 정상 패턴을 강화, kNN 분류 균형 개선
#
# 구현:
#   learnFromBenchmarkComparison에 positive 저장 로직 추가
#   단, positive 과잉 방지: 필드별 positive/negative 비율 2:1 상한
#   addLearningEntry에 type 필드 추가 (positive/negative 식별용)

with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'rb') as f:
    content = f.read()

original = content

# ─────────────────────────────────────────────────────────────────────
# 1. addLearningEntry: type 파라미터 추가 (기본 'negative')
# ─────────────────────────────────────────────────────────────────────
old_add_entry_sig = (
    b"function addLearningEntry(field, label, features, videoName) {\r\n"
    b"  const db = loadLearningDB();"
)
new_add_entry_sig = (
    b"function addLearningEntry(field, label, features, videoName, type = 'negative') {\r\n"
    b"  const db = loadLearningDB();"
)
assert old_add_entry_sig in content, "addLearningEntry signature not found"
content = content.replace(old_add_entry_sig, new_add_entry_sig, 1)
print("1. addLearningEntry: type param added")

# Add type field to the pushed entry
old_push_entry = (
    b"  deduped.push({\r\n"
    b"    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,\r\n"
    b"    ts: Date.now(),\r\n"
    b"    videoName: videoName || '',\r\n"
    b"    field,\r\n"
    b"    label,\r\n"
    b"    features\r\n"
    b"  });"
)
new_push_entry = (
    b"  deduped.push({\r\n"
    b"    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,\r\n"
    b"    ts: Date.now(),\r\n"
    b"    videoName: videoName || '',\r\n"
    b"    field,\r\n"
    b"    label,\r\n"
    b"    type,\r\n"
    b"    features\r\n"
    b"  });"
)
assert old_push_entry in content, "push entry not found"
content = content.replace(old_push_entry, new_push_entry, 1)
print("2. Entry object: type field added")

# ─────────────────────────────────────────────────────────────────────
# 3. learnFromBenchmarkComparison: positive 저장 추가
# ─────────────────────────────────────────────────────────────────────
old_learn_loop = (
    b"  for (const row of rows) {\r\n"
    b"    if (!row.detectedScene) continue;\r\n"
    b"    const features = row.detectedScene.camera?._features;\r\n"
    b"    if (!features) continue;\r\n"
    b"    for (const f of LEARNABLE) {\r\n"
    b"      if (row[f.rowKey] === false) {\r\n"
    b"        const correctLabel = row.benchmarkScene[f.benchKey];\r\n"
    b"        if (!correctLabel) continue;\r\n"
    b"        addLearningEntry(f.camKey, correctLabel, features, videoFile?.name);\r\n"
    b"        learned++;\r\n"
    b"      }\r\n"
    b"    }\r\n"
    b"  }"
)
new_learn_loop = (
    b"  // Count existing negatives per field for positive throttle\r\n"
    b"  const existingDB = loadLearningDB();\r\n"
    b"  const negCount = {};\r\n"
    b"  for (const e of existingDB.entries) {\r\n"
    b"    if (e.type !== 'positive') negCount[e.field] = (negCount[e.field] || 0) + 1;\r\n"
    b"  }\r\n"
    b"  const posCount = {};\r\n"
    b"  for (const e of existingDB.entries) {\r\n"
    b"    if (e.type === 'positive') posCount[e.field] = (posCount[e.field] || 0) + 1;\r\n"
    b"  }\r\n"
    b"\r\n"
    b"  for (const row of rows) {\r\n"
    b"    if (!row.detectedScene) continue;\r\n"
    b"    const features = row.detectedScene.camera?._features;\r\n"
    b"    if (!features) continue;\r\n"
    b"    for (const f of LEARNABLE) {\r\n"
    b"      if (row[f.rowKey] === false) {\r\n"
    b"        // Negative: save the correct label\r\n"
    b"        const correctLabel = row.benchmarkScene[f.benchKey];\r\n"
    b"        if (!correctLabel) continue;\r\n"
    b"        addLearningEntry(f.camKey, correctLabel, features, videoFile?.name, 'negative');\r\n"
    b"        negCount[f.camKey] = (negCount[f.camKey] || 0) + 1;\r\n"
    b"        learned++;\r\n"
    b"      } else if (row[f.rowKey] === true) {\r\n"
    b"        // Positive: save what we detected correctly, but throttle\r\n"
    b"        // Limit: positives per field <= 2x negatives (min 3 negatives required)\r\n"
    b"        const negN = negCount[f.camKey] || 0;\r\n"
    b"        const posN = posCount[f.camKey] || 0;\r\n"
    b"        if (negN < 3) continue;  // need baseline negatives first\r\n"
    b"        if (posN >= negN * 2) continue;  // positives capped at 2x negatives\r\n"
    b"        const detectedLabel = row.detectedScene.camera?.[f.camKey];\r\n"
    b"        if (!detectedLabel) continue;\r\n"
    b"        // Only save if detected label matches benchmark (sanity check)\r\n"
    b"        const benchLabel = row.benchmarkScene[f.benchKey];\r\n"
    b"        if (detectedLabel !== benchLabel) continue;\r\n"
    b"        addLearningEntry(f.camKey, detectedLabel, features, videoFile?.name, 'positive');\r\n"
    b"        posCount[f.camKey] = (posCount[f.camKey] || 0) + 1;\r\n"
    b"        learned++;\r\n"
    b"      }\r\n"
    b"    }\r\n"
    b"  }"
)
assert old_learn_loop in content, "learn loop not found"
content = content.replace(old_learn_loop, new_learn_loop, 1)
print("3. learnFromBenchmarkComparison: positive examples added with 2x throttle")

# ─────────────────────────────────────────────────────────────────────
# 4. getLearningDBStats: positive/negative 분리 통계 추가
# ─────────────────────────────────────────────────────────────────────
old_stats = (
    b"function getLearningDBStats() {\r\n"
    b"  const db = loadLearningDB();\r\n"
    b"  const byField = {};\r\n"
    b"  for (const e of db.entries) byField[e.field] = (byField[e.field] || 0) + 1;\r\n"
    b"  return { total: db.entries.length, byField };\r\n"
    b"}"
)
new_stats = (
    b"function getLearningDBStats() {\r\n"
    b"  const db = loadLearningDB();\r\n"
    b"  const byField = {};\r\n"
    b"  let positives = 0, negatives = 0;\r\n"
    b"  for (const e of db.entries) {\r\n"
    b"    byField[e.field] = (byField[e.field] || 0) + 1;\r\n"
    b"    if (e.type === 'positive') positives++; else negatives++;\r\n"
    b"  }\r\n"
    b"  return { total: db.entries.length, byField, positives, negatives };\r\n"
    b"}"
)
assert old_stats in content, "getLearningDBStats not found"
content = content.replace(old_stats, new_stats, 1)
print("4. getLearningDBStats: positive/negative split added")

if content != original:
    with open('D:/MakingApps/Apps/Cinematography/storyboard.html', 'wb') as f:
        f.write(content)
    print(f"\nP2-4 done. {len(content)} bytes (+{len(content)-len(original)})")
else:
    print("No changes!")
