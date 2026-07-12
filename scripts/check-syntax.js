#!/usr/bin/env node
// storyboard.html 내 <script> 블록 JS 구문 검사

const fs = require('fs');
const path = require('path');

const target = path.join(__dirname, '..', 'storyboard.html');

if (!fs.existsSync(target)) {
  process.exit(0);
}

const html = fs.readFileSync(target, 'utf8');
const blocks = html.match(/<script\b[^>]*>([\s\S]*?)<\/script>/gi) || [];

let errors = 0;
blocks.forEach((block, i) => {
  const code = block.replace(/<\/?script[^>]*>/gi, '');
  if (!code.trim()) return;
  try {
    new Function(code);
  } catch (err) {
    console.error(`[오류] 블록 ${i + 1}: ${err.message}`);
    errors++;
  }
});

if (errors > 0) {
  console.error(`JS 구문 오류 ${errors}개 발견`);
  process.exit(1);
} else {
  console.log(`JS 구문 OK (${blocks.length}개 블록 검사)`);
}
