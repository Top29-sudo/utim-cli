const fs = require('fs');
const path = 'src/components/PowershellUI/TerminalWidgets.jsx';
let c = fs.readFileSync(path, 'utf8');

// Mojibake replacements (UTF-8 misread as Latin-1)
const replacements = {
  '\u00e2\u20ac\u00a2': '\u2022', // â€¢ -> •
  '\u00e2\u0153\u201c': '\u2713', // âœ“ -> ✓
  '\u00c2\u00b7': '\u00b7',       // Â· -> ·
  '\u00e2\u20ac\u201d': '\u2014', // â€” -> —
  '\u00e2\u20ac\u0153': '\u201c', // â€œ -> “
  '\u00e2\u20ac\u2122': '\u2019', // â€™ -> ’
  '\u00e2\u20ac\u02dc': '\u2018', // â€˜ -> ‘
  '\u00e2\u20ac\u201c': '\u2013', // â€“ -> –
  '\u00e2\u20ac\u00a6': '\u2026', // â€¦ -> …
  '\u00e2\u20ac\u00b0': '\u2030', // â€° -> ‰
  '\u00e2\u2039\u203a': '\u00ab', // â‹š -> «
  '\u00e2\u2030\u00a0': '\u2020', // â€  -> †
  '\u00e2\u20ac\u00b9': '\u2039', // â€¹ -> ‹
  '\u00e2\u20ac\u00ba': '\u203a', // â€º -> ›
  '\u00e2\u20ac\u00a1': '\u2021', // â€¡ -> ‡
  '\u00e2\u20ac\u00a4': '\u20ac', // â‚¬ -> €
  '\u00c2\u00a0': '\u00a0',       // Â  -> nbsp
  '\u00c3\u00a9': '\u00e9',       // Ã© -> é
  '\u00c3\u00a8': '\u00e8',       // Ã¨ -> è
  '\u00c3\u00aa': '\u00ea',       // Ãª -> ê
  '\u00c3\u00a7': '\u00e7',       // Ã§ -> ç
  '\u00c3\u00a0': '\u00e0',       // Ã  -> à
  '\u00c3\u00a2': '\u00e2',       // Ã¢ -> â
  '\u00c3\u00a4': '\u00e4',       // Ã¤ -> ä
  '\u00c3\u00a1': '\u00e1',       // Ã¡ -> á
  '\u00c3\u00a3': '\u00e3',       // Ã£ -> ã
  '\u00c3\u00a5': '\u00e5',       // Ã¥ -> å
  '\u00c3\u00b6': '\u00f6',       // Ã¶ -> ö
  '\u00c3\u00bc': '\u00fc',       // Ã¼ -> ü
  '\u00c3\u00b3': '\u00f3',       // Ã³ -> ó
  '\u00c3\u00b1': '\u00f1',       // Ã± -> ñ
  '\u00c3\u00b4': '\u00f4',       // Ã´ -> ô
  '\u00c3\u00a6': '\u00e6',       // Ã¦ -> æ
  '\u00c3\u00b8': '\u00f8',       // Ã¸ -> ø
  '\u00c3\u00a9\u00a2': '\u00e9\u00a2',
};

let count = 0;
for (const [from, to] of Object.entries(replacements)) {
  if (from === to) continue;
  const re = new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
  const matches = c.match(re);
  if (matches) {
    count += matches.length;
    c = c.replace(re, to);
  }
}

// Also handle the specific known mojibake sequences from the file
// "âœ“ COPIED" -> "✓ COPIED"
c = c.replace(/âœ“/g, '✓');
// "â€¢" -> "•"
c = c.replace(/â€¢/g, '•');
// "Â·" -> "·"
c = c.replace(/Â·/g, '·');
// "â€”" -> "—"
c = c.replace(/â€”/g, '—');
// "â€œ" -> "“"
c = c.replace(/â€œ/g, '“');
// "â€™" -> "’"
c = c.replace(/â€™/g, '’');
// "â€˜" -> "‘"
c = c.replace(/â€˜/g, '‘');
// "â€“" -> "–"
c = c.replace(/â€“/g, '–');
// "â€¦" -> "…"
c = c.replace(/â€¦/g, '…');
// "â€°" -> "‰"
c = c.replace(/â€°[^ ]?/g, '‰');

fs.writeFileSync(path, c, 'utf8');
console.log('Replacements done. Total mojibake sequences replaced:', count);
