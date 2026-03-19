/**
 * StoryFrame Build Script
 * Vercel 빌드 시 환경변수를 HTML에 주입하고 dist/index.html 생성
 *
 * 필요한 환경변수:
 *   SUPABASE_URL        — Supabase 프로젝트 URL (https://xxxx.supabase.co)
 *   SUPABASE_ANON_KEY   — Supabase anon/public key
 */

const fs = require('fs');
const path = require('path');

const SUPABASE_URL = process.env.SUPABASE_URL || '';
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || '';

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.warn('[build] SUPABASE_URL / SUPABASE_ANON_KEY 환경변수가 없습니다. 클라우드 기능이 비활성화됩니다.');
}

const src = path.join(__dirname, 'storyboard.html');
let html = fs.readFileSync(src, 'utf8');

html = html.replace(/REPLACE_SUPABASE_URL/g, SUPABASE_URL);
html = html.replace(/REPLACE_SUPABASE_ANON_KEY/g, SUPABASE_ANON_KEY);

const distDir = path.join(__dirname, 'dist');
if (!fs.existsSync(distDir)) fs.mkdirSync(distDir);

fs.writeFileSync(path.join(distDir, 'index.html'), html, 'utf8');
console.log('[build] dist/index.html 생성 완료');
