#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const BENCHMARK_OPTIONS = {
  transitions: [
    '',
    'cut', 'match-cut', 'action-cut', 'jump-cut', 'smash-cut', 'cross-cut', 'graphic-cut', 'flash',
    'dissolve', 'match-dissolve', 'fade', 'fade-white', 'defocus',
    'wipe', 'iris', 'whip-pan', 'zoom',
    'l-cut', 'j-cut'
  ],
  shotSizes: ['', 'ECU', 'BCU', 'CU', 'MCU', 'MS', 'Cowboy', 'MLS', 'FS', 'LS', 'ELS', 'Establishing', 'INSERT'],
  framings: ['', 'Single', 'Two-shot', 'Three-shot', 'OTS', 'POV', 'Crowd', 'Empty'],
  movements: ['', 'Static', 'Pan', 'Whip-pan', 'Tilt', 'Push-in', 'Pull-out', 'Tracking', 'Trucking', 'Arc', 'Crane', 'Pedestal', 'Handheld', 'Steadicam', 'Zoom-in', 'Zoom-out', 'Dolly-zoom', 'Rack-focus', 'Drone'],
  lensTypes: ['', 'Ultra-wide(<16mm)', 'Wide(16-35mm)', 'Normal(35-60mm)', 'Telephoto(60-135mm)', 'Super-telephoto(>135mm)', 'Macro'],
  angles: ['', 'Overhead', 'High', 'Eye-level', 'Shoulder-level', 'Low', 'Worms-eye', 'Dutch', 'Aerial'],
  dofs: ['', 'Deep', 'Moderate', 'Shallow', 'Very-shallow'],
  lightingTypes: ['', 'Natural', 'Artificial', 'Mixed', 'Practical'],
  lightingConditions: ['', 'High-key', 'Low-key', 'Silhouette', 'Chiaroscuro', 'Flat', 'Rembrandt'],
  compositions: ['', 'Rule-of-thirds', 'Center-framed', 'Symmetrical', 'Leading-lines', 'Frame-within-frame', 'Negative-space', 'Golden-ratio']
};

const FIELD_MAP = [
  { metric: 'transition', key: 'transition', canon: canonicalTransition },
  { metric: 'shot', key: 'shotSize', canon: canonicalShotSize },
  { metric: 'framing', key: 'framing', canon: canonicalFraming },
  { metric: 'movement', key: 'movement', canon: canonicalMovement },
  { metric: 'lens', key: 'lensType', canon: canonicalLensType },
  { metric: 'angle', key: 'angle', canon: canonicalAngle },
  { metric: 'dof', key: 'dof', canon: canonicalDOF },
  { metric: 'lightingType', key: 'lightingType', canon: canonicalLightingType },
  { metric: 'lightingCondition', key: 'lightingCondition', canon: canonicalLightingCondition },
  { metric: 'composition', key: 'composition', canon: canonicalComposition }
];

const RECOGNITION_METRICS = [
  'shot',
  'framing',
  'movement',
  'lens',
  'angle',
  'dof',
  'lightingType',
  'lightingCondition',
  'composition'
];

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || (!args.project && !args.detected && !args.benchmark)) {
    printUsage();
    process.exit(args.help ? 0 : 1);
  }

  const projectPayload = args.project ? readJson(args.project) : null;
  const benchmarkPayload = args.benchmark ? readJson(args.benchmark) : projectPayload?.benchmark_json || null;
  const detectedPayload = args.detected ? readJson(args.detected) : projectPayload?.scenes_json || projectPayload || null;

  if (!benchmarkPayload) {
    fail('Benchmark data not found. Pass --benchmark <file> or a project JSON containing benchmark_json.');
  }
  if (!detectedPayload) {
    fail('Detected scene data not found. Pass --detected <file> or a project JSON containing scenes_json.');
  }

  const benchmarkData = normalizeBenchmarkData(benchmarkPayload);
  const detectedScenes = normalizeDetectedScenes(detectedPayload);

  if (!benchmarkData.scenes.length) fail('Benchmark scenes are empty.');
  if (!detectedScenes.length) fail('Detected scenes are empty.');

  const result = compareScenes(benchmarkData, detectedScenes);

  if (args.json) {
    process.stdout.write(JSON.stringify(result, null, 2));
    process.stdout.write('\n');
    return;
  }

  printReport(result, args.limit);
}

function parseArgs(argv) {
  const out = { limit: 10 };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--project') out.project = argv[++i];
    else if (arg === '--benchmark') out.benchmark = argv[++i];
    else if (arg === '--detected') out.detected = argv[++i];
    else if (arg === '--limit') out.limit = Math.max(1, parseInt(argv[++i], 10) || 10);
    else if (arg === '--json') out.json = true;
    else if (arg === '--help' || arg === '-h') out.help = true;
    else fail(`Unknown argument: ${arg}`);
  }
  return out;
}

function printUsage() {
  process.stdout.write(
    [
      'Usage:',
      '  node scripts/evaluate-benchmark.js --project exported-project.json',
      '  node scripts/evaluate-benchmark.js --benchmark benchmark.json --detected detected-scenes.json',
      '',
      'Accepted inputs:',
      '  --project   JSON containing scenes_json and benchmark_json',
      '  --benchmark StoryFrame benchmark JSON or a compatible scenes wrapper',
      '  --detected  StoryFrame scenes JSON, scenes_json array, or compatible wrapper',
      '',
      'Options:',
      '  --json      Print machine-readable JSON',
      '  --limit N   Number of mismatch rows to show in text mode',
      ''
    ].join('\n')
  );
}

function readJson(filePath) {
  const fullPath = path.resolve(filePath);
  try {
    return JSON.parse(fs.readFileSync(fullPath, 'utf8'));
  } catch (error) {
    fail(`Failed to read JSON: ${fullPath}\n${error.message}`);
  }
}

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function parseTimecodeInput(value) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const text = String(value ?? '').trim();
  if (!text) return null;
  if (/^\d+(\.\d+)?$/.test(text)) return parseFloat(text);

  const parts = text.split(':').map(part => part.trim());
  if (parts.length < 2 || parts.length > 4 || parts.some(part => part === '' || Number.isNaN(Number(part)))) {
    return null;
  }

  const nums = parts.map(Number);
  if (parts.length === 4) {
    const [h, m, s, f] = nums;
    return h * 3600 + m * 60 + s + f / 30;
  }
  if (parts.length === 3) {
    const [h, m, s] = nums;
    return h * 3600 + m * 60 + s;
  }
  const [m, s] = nums;
  return m * 60 + s;
}

function matchOption(value, options) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const found = options.find(option => option.toLowerCase() === raw.toLowerCase());
  return found || raw;
}

function canonicalTransition(value) {
  const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return '';
  if (raw.includes('match') && raw.includes('dissolve')) return 'match-dissolve';
  if (raw.includes('graphic')) return 'graphic-cut';
  if (raw.includes('match') && raw.includes('cut')) return 'match-cut';
  if (raw.includes('jump')) return 'jump-cut';
  if (raw.includes('smash')) return 'smash-cut';
  if (raw.includes('action cut') || raw.includes('cut on action') || raw === 'action') return 'action-cut';
  if (raw.includes('cross') || raw.includes('parallel') || raw.includes('intercut')) return 'cross-cut';
  if (raw.includes('flash') && !raw.includes('back') && !raw.includes('forward')) return 'flash';
  if (raw.includes('whip') || raw.includes('swish') || raw.includes('swipe pan')) return 'whip-pan';
  if (raw.includes('zoom')) return 'zoom';
  if (raw.includes('iris')) return 'iris';
  if (raw.includes('wipe') || (raw.includes('push') && raw.includes('transition'))) return 'wipe';
  if (raw.includes('dissolve') || raw.includes('crossfade') || raw.includes('cross fade')) return 'dissolve';
  if (raw.includes('defocus') || raw.includes('blur tran')) return 'defocus';
  if (raw.includes('fade') && (raw.includes('white') || raw.includes('bright'))) return 'fade-white';
  if (raw.includes('fade')) return 'fade';
  if (raw.includes('l-cut') || raw === 'l cut' || raw.includes('audio advance')) return 'l-cut';
  if (raw.includes('j-cut') || raw === 'j cut' || raw.includes('audio delay')) return 'j-cut';
  return 'cut';
}

function canonicalShotSize(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase();
  const aliasMap = {
    ews: 'ELS',
    ws: 'LS',
    'wide shot': 'LS',
    'long shot': 'LS',
    'extreme long shot': 'ELS',
    'establishing shot': 'Establishing',
    'extreme close-up': 'ECU',
    'big close-up': 'BCU',
    'close-up': 'CU',
    'medium close-up': 'MCU',
    'medium shot': 'MS',
    'american shot': 'Cowboy',
    'cowboy shot': 'Cowboy',
    'medium long shot': 'MLS',
    'full shot': 'FS',
    'full figure': 'FS'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.shotSizes);
}

function canonicalFraming(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase();
  const aliasMap = {
    'over-the-shoulder': 'OTS',
    'over the shoulder': 'OTS',
    pov: 'POV',
    'point of view': 'POV',
    crowd: 'Crowd',
    empty: 'Empty',
    single: 'Single'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.framings);
}

function canonicalMovement(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase();
  const aliasMap = {
    static: 'Static',
    'slight move': 'Static',
    'dolly/tracking': 'Tracking',
    tracking: 'Tracking',
    trucking: 'Trucking',
    truck: 'Trucking',
    arc: 'Arc',
    pedestal: 'Pedestal',
    crane: 'Crane',
    handheld: 'Handheld',
    steadicam: 'Steadicam',
    gimbal: 'Steadicam',
    pan: 'Pan',
    tilt: 'Tilt',
    'push in': 'Push-in',
    'pull out': 'Pull-out',
    'zoom in': 'Zoom-in',
    'zoom out': 'Zoom-out',
    'dolly zoom': 'Dolly-zoom',
    'whip pan': 'Whip-pan'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.movements);
}

function canonicalLensType(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  if ((key.includes('ultra') || key.includes('super wide')) && key.includes('wide')) return 'Ultra-wide(<16mm)';
  if (key.includes('super') && key.includes('tele')) return 'Super-telephoto(>135mm)';
  if (key === 'wide' || key.includes('wide angle') || key.includes('wide-angle')) return 'Wide(16-35mm)';
  if (key === 'normal' || key === 'standard' || key.includes('standard lens')) return 'Normal(35-60mm)';
  if (key === 'tele' || key === 'telephoto' || key.includes('portrait lens')) return 'Telephoto(60-135mm)';
  if (key.includes('macro') || key.includes('close focus')) return 'Macro';
  return matchOption(raw, BENCHMARK_OPTIONS.lensTypes);
}

function canonicalAngle(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  const aliasMap = {
    overhead: 'Overhead',
    'birds-eye': 'Overhead',
    "bird's-eye": 'Overhead',
    'birds eye': 'Overhead',
    "bird's eye": 'Overhead',
    high: 'High',
    'high angle': 'High',
    'eye level': 'Eye-level',
    eyelevel: 'Eye-level',
    'shoulder level': 'Shoulder-level',
    low: 'Low',
    'low angle': 'Low',
    'worms eye': 'Worms-eye',
    "worm's eye": 'Worms-eye',
    dutch: 'Dutch',
    'dutch angle': 'Dutch',
    aerial: 'Aerial',
    drone: 'Aerial'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.angles);
}

function canonicalDOF(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  const aliasMap = {
    deep: 'Deep',
    'deep focus': 'Deep',
    moderate: 'Moderate',
    medium: 'Moderate',
    'medium dof': 'Moderate',
    shallow: 'Shallow',
    'shallow focus': 'Shallow',
    'very shallow': 'Very-shallow',
    'very-shallow': 'Very-shallow',
    'extremely shallow': 'Very-shallow'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.dofs);
}

function canonicalLightingType(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  const aliasMap = {
    natural: 'Natural',
    daylight: 'Natural',
    sunlight: 'Natural',
    practical: 'Practical',
    'practical light': 'Practical',
    artificial: 'Artificial',
    studio: 'Artificial',
    mixed: 'Mixed',
    'mixed lighting': 'Mixed'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.lightingTypes);
}

function canonicalLightingCondition(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  const aliasMap = {
    flat: 'Flat',
    silhouette: 'Silhouette',
    'high key': 'High-key',
    'high-key': 'High-key',
    'low key': 'Low-key',
    'low-key': 'Low-key',
    chiaroscuro: 'Chiaroscuro',
    rembrandt: 'Rembrandt'
  };
  if (aliasMap[key]) return aliasMap[key];
  return matchOption(raw, BENCHMARK_OPTIONS.lightingConditions);
}

function canonicalComposition(value) {
  const raw = String(value ?? '').trim();
  if (!raw) return '';
  const key = raw.toLowerCase().replace(/\s+/g, ' ');
  if (key.includes('golden')) return 'Golden-ratio';
  if (key.includes('frame within')) return 'Frame-within-frame';
  if (key.includes('negative')) return 'Negative-space';
  if (key.includes('leading')) return 'Leading-lines';
  if (key.includes('symmet')) return 'Symmetrical';
  if (key.includes('center')) return 'Center-framed';
  if (key.includes('third')) return 'Rule-of-thirds';
  return matchOption(raw, BENCHMARK_OPTIONS.compositions);
}

function normalizeBenchmarkScene(scene, index, durationHint = 0) {
  const startRaw = scene?.startTime ?? scene?.start ?? 0;
  const startTime = coerceTime(startRaw, 0, durationHint);
  const endRaw = scene?.endTime ?? scene?.end ?? startTime;
  const endTime = Math.max(coerceTime(endRaw, startTime, durationHint), startTime);
  return {
    id: scene?.id || `bench-${index + 1}`,
    index: index + 1,
    startTime,
    endTime,
    transition: canonicalTransition(scene?.transition),
    shotSize: canonicalShotSize(scene?.shotSize ?? scene?.shot_size ?? scene?.camera?.shotSize),
    framing: canonicalFraming(scene?.framing ?? scene?.camera?.framing),
    movement: canonicalMovement(scene?.movement ?? scene?.camera_movement ?? scene?.camera?.movement),
    lensType: canonicalLensType(scene?.lensType ?? scene?.lens_type ?? scene?.camera?.lensType),
    angle: canonicalAngle(scene?.angle ?? scene?.camera_angle ?? scene?.camera?.angle),
    dof: canonicalDOF(scene?.dof ?? scene?.depth_of_field ?? scene?.camera?.dof),
    lightingType: canonicalLightingType(scene?.lightingType ?? scene?.lighting_type ?? scene?.camera?.lightingType),
    lightingCondition: canonicalLightingCondition(scene?.lightingCondition ?? scene?.lighting_condition ?? scene?.camera?.lightingCondition),
    composition: canonicalComposition(scene?.composition ?? scene?.composition_tag ?? scene?.camera?.composition),
    notes: String(scene?.notes ?? scene?.note ?? '')
  };
}

function normalizeDetectedScene(scene, index) {
  const startRaw = scene?.startTime ?? scene?.start ?? 0;
  const endFallback = Number.isFinite(startRaw) ? startRaw : parseTimecodeInput(startRaw) ?? 0;
  const endRaw = scene?.endTime ?? scene?.end ?? endFallback;
  return {
    id: scene?.id || `det-${index + 1}`,
    index: Number(scene?.index) || index + 1,
    startTime: coerceTime(startRaw, 0),
    endTime: Math.max(coerceTime(endRaw, endFallback), coerceTime(startRaw, 0)),
    transition: canonicalTransition(scene?.transition),
    camera: {
      shotSize: canonicalShotSize(scene?.camera?.shotSize ?? scene?.shotSize ?? scene?.shot_size),
      framing: canonicalFraming(scene?.camera?.framing ?? scene?.framing),
      movement: canonicalMovement(scene?.camera?.movement ?? scene?.movement ?? scene?.camera_movement),
      lensType: canonicalLensType(scene?.camera?.lensType ?? scene?.lensType ?? scene?.lens_type),
      angle: canonicalAngle(scene?.camera?.angle ?? scene?.angle ?? scene?.camera_angle),
      dof: canonicalDOF(scene?.camera?.dof ?? scene?.dof ?? scene?.depth_of_field),
      lightingType: canonicalLightingType(scene?.camera?.lightingType ?? scene?.lightingType ?? scene?.lighting_type),
      lightingCondition: canonicalLightingCondition(scene?.camera?.lightingCondition ?? scene?.lightingCondition ?? scene?.lighting_condition),
      composition: canonicalComposition(scene?.camera?.composition ?? scene?.composition ?? scene?.composition_tag)
    }
  };
}

function coerceTime(value, fallback = 0, maxDuration = 0) {
  const parsed = parseTimecodeInput(value);
  if (parsed === null || !Number.isFinite(parsed)) return fallback;
  const upper = maxDuration > 0 ? Math.max(maxDuration, parsed, fallback) : Math.max(parsed, fallback, 0);
  return clamp(parsed, 0, upper);
}

function normalizeBenchmarkData(payload) {
  const source = payload?.benchmark_json || payload;
  const scenesInput = Array.isArray(source?.scenes)
    ? source.scenes
    : Array.isArray(source)
      ? source
      : [];
  const durationHint = Number(source?.video?.duration) || 0;
  return {
    version: Number(source?.version) || 1,
    video: {
      name: String(source?.video?.name || ''),
      duration: durationHint
    },
    scoring: {
      boundaryToleranceSec: Math.max(0.05, Number(source?.scoring?.boundaryToleranceSec) || 0.35)
    },
    scenes: scenesInput.map((scene, index) => normalizeBenchmarkScene(scene, index, durationHint))
  };
}

function normalizeDetectedScenes(payload) {
  const source = payload?.scenes_json || payload?.scenes || payload;
  const scenes = Array.isArray(source) ? source : [];
  return scenes.map((scene, index) => normalizeDetectedScene(scene, index));
}

function findBestDetectedSceneMatch(targetScene, detectedScenes, usedIndices) {
  let best = null;

  detectedScenes.forEach((scene, detectedIndex) => {
    if (usedIndices.has(detectedIndex)) return;

    const overlap = Math.max(0, Math.min(targetScene.endTime, scene.endTime) - Math.max(targetScene.startTime, scene.startTime));
    const benchDuration = Math.max(targetScene.endTime - targetScene.startTime, 0.01);
    const detectedDuration = Math.max(scene.endTime - scene.startTime, 0.01);
    const overlapRatio = overlap / Math.max(benchDuration, detectedDuration);
    const startError = Math.abs(scene.startTime - targetScene.startTime);
    const endError = Math.abs(scene.endTime - targetScene.endTime);
    const score = overlapRatio * 5 - (startError + endError) * 0.65 - (overlap <= 0 ? 0.45 : 0);

    if (!best || score > best.score) {
      best = { scene, detectedIndex, score, overlapRatio, startError, endError };
    }
  });

  if (best) return best;

  detectedScenes.forEach((scene, detectedIndex) => {
    const startError = Math.abs(scene.startTime - targetScene.startTime);
    const endError = Math.abs(scene.endTime - targetScene.endTime);
    const score = -startError - endError;
    if (!best || score > best.score) {
      best = { scene, detectedIndex, score, overlapRatio: 0, startError, endError };
    }
  });

  return best;
}

function compareScenes(benchmarkData, detectedScenes) {
  const tolerance = benchmarkData.scoring.boundaryToleranceSec;
  const usedIndices = new Set();
  const metrics = {
    boundary: { hits: 0, total: 0 },
    transition: { hits: 0, total: 0 },
    shot: { hits: 0, total: 0 },
    framing: { hits: 0, total: 0 },
    movement: { hits: 0, total: 0 },
    lens: { hits: 0, total: 0 },
    angle: { hits: 0, total: 0 },
    dof: { hits: 0, total: 0 },
    lightingType: { hits: 0, total: 0 },
    lightingCondition: { hits: 0, total: 0 },
    composition: { hits: 0, total: 0 }
  };
  const confusions = Object.fromEntries(FIELD_MAP.map(field => [field.metric, {}]));

  const rows = benchmarkData.scenes.map((benchmarkScene, rowIndex) => {
    const match = findBestDetectedSceneMatch(benchmarkScene, detectedScenes, usedIndices);
    const detectedScene = match?.scene || null;
    if (match?.detectedIndex !== undefined) usedIndices.add(match.detectedIndex);

    const startError = detectedScene ? Math.abs(detectedScene.startTime - benchmarkScene.startTime) : null;
    const endError = detectedScene ? Math.abs(detectedScene.endTime - benchmarkScene.endTime) : null;
    metrics.boundary.total++;
    const boundaryHit = !!detectedScene && startError <= tolerance && endError <= tolerance;
    if (boundaryHit) metrics.boundary.hits++;

    const fieldResults = {};
    for (const field of FIELD_MAP) {
      const expected = benchmarkScene[field.key];
      const actual = field.key === 'transition' ? detectedScene?.transition : detectedScene?.camera?.[field.key];
      const expectedNorm = field.canon(expected);
      const actualNorm = field.canon(actual);
      if (!expectedNorm) {
        fieldResults[field.metric] = null;
        continue;
      }
      metrics[field.metric].total++;
      const hit = actualNorm === expectedNorm;
      if (hit) metrics[field.metric].hits++;
      fieldResults[field.metric] = hit;
      if (!hit) {
        const confusionKey = `${expectedNorm} -> ${actualNorm || '(blank)'}`;
        confusions[field.metric][confusionKey] = (confusions[field.metric][confusionKey] || 0) + 1;
      }
    }

    const checks = [boundaryHit, ...Object.values(fieldResults).filter(value => value !== null)];
    const hits = checks.filter(Boolean).length;
    const misses = checks.length - hits;
    const warnThreshold = Math.max(2, Math.floor(checks.length / 3));
    const status = !detectedScene ? 'bad' : misses === 0 ? 'ok' : misses <= warnThreshold ? 'warn' : 'bad';

    return {
      rowIndex,
      benchmarkScene,
      detectedScene,
      overlapRatio: match?.overlapRatio ?? 0,
      startError,
      endError,
      boundaryHit,
      ...fieldResults,
      status
    };
  });

  const appMetrics = Object.values(metrics).filter(metric => metric.total > 0);
  const overall = appMetrics.length
    ? appMetrics.reduce((sum, metric) => sum + metric.hits / metric.total, 0) / appMetrics.length
    : 0;

  const recognitionMetrics = RECOGNITION_METRICS
    .map(name => metrics[name])
    .filter(metric => metric.total > 0);
  const recognitionOverall = recognitionMetrics.length
    ? recognitionMetrics.reduce((sum, metric) => sum + metric.hits / metric.total, 0) / recognitionMetrics.length
    : 0;

  return {
    generatedAt: new Date().toISOString(),
    benchmarkSceneCount: benchmarkData.scenes.length,
    detectedSceneCount: detectedScenes.length,
    tolerance,
    overall,
    recognitionOverall,
    sceneCountDiff: detectedScenes.length - benchmarkData.scenes.length,
    metrics: Object.fromEntries(
      Object.entries(metrics).map(([name, metric]) => [name, {
        ...metric,
        accuracy: metric.total ? metric.hits / metric.total : null
      }])
    ),
    confusions: Object.fromEntries(
      Object.entries(confusions).map(([name, map]) => [
        name,
        Object.entries(map)
          .sort((a, b) => b[1] - a[1])
          .map(([pair, count]) => ({ pair, count }))
      ])
    ),
    unmatchedDetected: detectedScenes.filter((_, index) => !usedIndices.has(index)).map(scene => ({
      index: scene.index,
      startTime: scene.startTime,
      endTime: scene.endTime
    })),
    rows
  };
}

function printReport(result, limit = 10) {
  const lines = [];
  lines.push('StoryFrame Benchmark Evaluation');
  lines.push(`Generated: ${result.generatedAt}`);
  lines.push(`Benchmark scenes: ${result.benchmarkSceneCount}`);
  lines.push(`Detected scenes: ${result.detectedSceneCount}`);
  lines.push(`Boundary tolerance: ${result.tolerance.toFixed(2)}s`);
  lines.push(`App overall: ${percent(result.overall)}`);
  lines.push(`Recognition-only overall: ${percent(result.recognitionOverall)}`);
  lines.push('');
  lines.push('Per-field accuracy');

  for (const [name, metric] of Object.entries(result.metrics)) {
    if (!metric.total) continue;
    lines.push(`- ${name}: ${percent(metric.accuracy)} (${metric.hits}/${metric.total})`);
  }

  const mismatches = result.rows
    .filter(row => row.status !== 'ok')
    .sort((a, b) => scoreRow(b) - scoreRow(a))
    .slice(0, limit);

  if (mismatches.length) {
    lines.push('');
    lines.push(`Top mismatches (${mismatches.length})`);
    for (const row of mismatches) {
      const parts = [];
      for (const field of FIELD_MAP) {
        const expected = row.benchmarkScene[field.key];
        if (!expected) continue;
        const actual = field.key === 'transition' ? row.detectedScene?.transition : row.detectedScene?.camera?.[field.key];
        if (field.canon(expected) !== field.canon(actual)) {
          parts.push(`${field.metric}: ${expected} -> ${actual || '(blank)'}`);
        }
      }
      const boundary = row.startError === null
        ? 'no matched scene'
        : `start ${row.startError.toFixed(2)}s, end ${row.endError.toFixed(2)}s`;
      lines.push(`- bench S${row.benchmarkScene.index} vs det ${row.detectedScene ? `S${row.detectedScene.index}` : 'none'} | ${boundary}`);
      if (parts.length) lines.push(`  ${parts.join(' | ')}`);
    }
  }

  const hotFields = Object.entries(result.confusions)
    .map(([name, items]) => ({ name, item: items[0] }))
    .filter(entry => entry.item)
    .sort((a, b) => b.item.count - a.item.count)
    .slice(0, 5);

  if (hotFields.length) {
    lines.push('');
    lines.push('Most common confusions');
    for (const entry of hotFields) {
      lines.push(`- ${entry.name}: ${entry.item.pair} (${entry.item.count})`);
    }
  }

  if (result.unmatchedDetected.length) {
    lines.push('');
    lines.push(`Unmatched detected scenes: ${result.unmatchedDetected.length}`);
  }

  process.stdout.write(lines.join('\n'));
  process.stdout.write('\n');
}

function percent(value) {
  return `${Math.round((value || 0) * 100)}%`;
}

function scoreRow(row) {
  let misses = row.boundaryHit ? 0 : 1;
  for (const field of FIELD_MAP) {
    if (row[field.metric] === false) misses++;
  }
  return misses;
}

main();
