const test = require('node:test');
const assert = require('node:assert/strict');
const { createContext, load } = require('./helpers.cjs');

function core() {
  return load(createContext(), 'api.js', 'clip-editor.js').ClipEditorCore;
}

const P = (over = {}) => ({ aspect: 'original', fit: 'crop', resolution: 'original', ...over });

test('outputSize: как на сервере', () => {
  const { outputSize } = core();
  const cases = [
    [[1920, 1080], P(), [1920, 1080]],
    [[1920, 1080], P({ aspect: '9:16' }), [606, 1080]],
    [[1920, 1080], P({ aspect: '9:16', fit: 'blur' }), [1080, 1920]],
    [[1920, 1080], P({ aspect: '9:16', fit: 'pad', resolution: '720' }), [720, 1280]],
    [[720, 1280], P({ aspect: '16:9' }), [720, 404]],
    [[641, 361], P(), [640, 360]],
  ];
  for (const [[w, h], p, expected] of cases) assert.deepEqual([...outputSize(w, h, p)], expected, JSON.stringify(p));
  const [bw, bh] = outputSize(8000, 4000, P());
  assert.ok(Math.max(bw, bh) <= 3840 && bw % 2 === 0 && bh % 2 === 0);
});

test('tokenize: эмодзи отдельно, модификаторы отброшены', () => {
  const { tokenize } = core();
  const tokens = JSON.parse(JSON.stringify(tokenize('Привет 🔥👍🏽 мир❤️').map((t) => [t.text, t.emoji])));
  assert.deepEqual(tokens, [['Привет ', false], ['🔥', true], ['👍', true], [' мир', false], ['❤', true]]);
});

test('wrapLines: перенос по ширине, ручные переносы, длинные слова', () => {
  const { wrapLines, textWidth } = core();
  // кегль 20 => символ 10px; ширина 100px => не более 10 символов в строке
  assert.deepEqual([...wrapLines('один два три четыре', 95, 20)], ['один два', 'три', 'четыре']);
  assert.deepEqual([...wrapLines('один два три четыре', 100, 20)], ['один два', 'три четыре']); // ровно 100px помещается
  assert.deepEqual([...wrapLines('Раз\nДва', 1000, 20)], ['Раз', 'Два']);
  const long = wrapLines('А'.repeat(25), 100, 20);
  assert.ok(long.length === 3 && long.every((l) => textWidth(l, 20) <= 100));
  assert.deepEqual([...wrapLines('  \n ', 100, 20)], []);
});

test('wrapLines: не больше 6 строк и многоточие', () => {
  const { wrapLines, textWidth } = core();
  const lines = wrapLines('слово '.repeat(100), 100, 20);
  assert.equal(lines.length, 6);
  assert.ok(lines[5].endsWith('…') && textWidth(lines[5], 20) <= 100);
});

test('textWidth: эмодзи занимают 1.2 кегля', () => {
  const { textWidth } = core();
  assert.equal(textWidth('🔥', 20), 24);
  assert.equal(textWidth('аб🔥', 20), 44);
});

test('parseSrt: тайминги, многострочные реплики, теги и CRLF', () => {
  const { parseSrt } = core();
  const srt = '1\r\n00:00:01,000 --> 00:00:02,500\r\n<i>Привет</i>\r\nмир\r\n\r\n2\n00:01:00.250 --> 00:01:01,000\nВторая\n\nмусор без таймкода\n';
  const cues = parseSrt(srt);
  assert.equal(cues.length, 2);
  assert.deepEqual({ ...cues[0] }, { start: 1, end: 2.5, text: 'Привет\nмир' });
  assert.equal(cues[1].start, 60.25);
  assert.deepEqual([...parseSrt('совсем не srt')], []);
});
