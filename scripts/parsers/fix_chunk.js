const fs = require('fs');

const srcPath = process.env.HOME + '/.claude/projects/d--CS-computer-programming-Workspace-RollingWord/818c310e-c3c6-4bca-a14c-f47593e56422/tool-results/toolu_01Wc9dZRHzaztR3GAcxN3xyS.json';
const outPath = 'chunk1.json';

const raw = JSON.parse(fs.readFileSync(srcPath, 'utf-8'));
const text = raw[0].text;

const start = text.indexOf('[');
const end = text.lastIndexOf(']');
let jsonStr = text.substring(start, end + 1);

// 尝试直接解析
let data;
try {
  data = JSON.parse(jsonStr);
  console.log('直接解析成功，条数:', data.length);
} catch (e) {
  console.log('直接解析失败，使用逐对象提取...');
  console.log('错误位置:', e.message);

  // 逐对象提取：找到每个 { "word": ... } 块
  data = [];
  let depth = 0;
  let objStart = -1;

  for (let i = 0; i < jsonStr.length; i++) {
    let ch = jsonStr[i];
    if (ch === '{' && depth === 0) {
      objStart = i;
      depth = 1;
    } else if (ch === '{') {
      depth++;
    } else if (ch === '}') {
      depth--;
      if (depth === 0 && objStart >= 0) {
        let objStr = jsonStr.substring(objStart, i + 1);
        try {
          let obj = JSON.parse(objStr);
          if (obj.word) {
            data.push(obj);
          }
        } catch (e2) {
          // 尝试修复：替换未转义的内部引号
          try {
            // 修复策略：找到每个字段值，修复里面的引号
            let fixed = objStr.replace(/"([^"]*?)"\s*:\s*"([\s\S]*?)"\s*([,}])/g, function(match, key, val, end) {
              let safeVal = val.replace(/"/g, '\\"');
              return '"' + key + '": "' + safeVal + '"' + end;
            });
            let obj = JSON.parse(fixed);
            if (obj.word) data.push(obj);
          } catch (e3) {
            // 最后手段：手动提取word字段
            let wm = objStr.match(/"word"\s*:\s*"([^"]+)"/);
            if (wm) {
              let fallback = { word: wm[1], definition_cn: '', definition_en: '', cognates: '', synonyms_antonyms: '', sentences: '', notes: '' };

              let fields = ['definition_cn', 'definition_en', 'cognates', 'synonyms_antonyms', 'sentences', 'notes'];
              for (let f of fields) {
                let fm = objStr.match(new RegExp('"' + f + '"\\s*:\\s*"([^"]*(?:\\\\.[^"]*)*)"'));
                if (fm) fallback[f] = fm[1].replace(/\\"/g, '"');
              }
              data.push(fallback);
            }
          }
        }
      }
    }
  }
  console.log('逐对象提取完成，条数:', data.length);
}

const outStr = JSON.stringify(data, null, 2) + '\n';
fs.writeFileSync(outPath, outStr.replace(/\r\n/g, '\n'), 'utf-8');
console.log('已写入', outPath);

// 显示前3条
for (let i = 0; i < Math.min(3, data.length); i++) {
  console.log('\n---', data[i].word, '---');
  console.log('  释义:', data[i].definition_cn);
  console.log('  同源:', data[i].cognates || '(无)');
}
