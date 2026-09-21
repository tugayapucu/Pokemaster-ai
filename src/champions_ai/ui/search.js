// Forgiving search over names, for the board's inputs.
//
// A player mistypes under a clock, and the typed language refuses anything it
// cannot resolve exactly -- on purpose, because a silently wrong match looks
// healthy afterwards. This sits in front of it: it suggests, the player picks,
// and what is sent is the exact id. So a typo costs a glance, never a wrong
// Pokemon.
//
// Tiers, best first, so a near-exact match always beats a guess:
//   0 exact  1 starts with  2 a word starts with  3 contains
//   4 letters in order, skipping some  5+ one or two typos
//
// Shared by the page and by the Node test, hence the module shim at the end.
(function (root) {
  "use strict";

  function norm(text) {
    return String(text).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function distance(a, b) {
    // Edits between two strings, where swapping two neighbouring letters is one
    // typo, not two (optimal string alignment). Plain Levenshtein counted
    // `slyveon` as two edits from its target and refused it in a short name --
    // and a swapped pair is the commonest typo there is.
    const rows = [Array.from({ length: b.length + 1 }, (_, j) => j)];
    for (let i = 1; i <= a.length; i += 1) {
      const row = [i];
      for (let j = 1; j <= b.length; j += 1) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        row[j] = Math.min(rows[i - 1][j] + 1, row[j - 1] + 1, rows[i - 1][j - 1] + cost);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
          row[j] = Math.min(row[j], rows[i - 2][j - 2] + 1);
        }
      }
      rows.push(row);
    }
    return rows[a.length][b.length];
  }

  function gaps(query, target) {
    // Letters of `query` found in order in `target`; the count of skipped
    // letters, or -1 when they are not all there.
    let at = 0;
    let skipped = 0;
    for (const letter of query) {
      const found = target.indexOf(letter, at);
      if (found < 0) return -1;
      skipped += found - at;
      at = found + 1;
    }
    return skipped;
  }

  function score(query, entry) {
    const q = norm(query);
    if (!q) return Infinity;
    const full = norm(entry.name);
    const id = norm(entry.id || entry.name);
    if (full === q || id === q) return 0;
    if (full.startsWith(q) || id.startsWith(q)) return 1 + (full.length - q.length) / 1000;
    const words = String(entry.name).toLowerCase().split(/[\s\-]+/).map(norm);
    if (words.some((word) => word.startsWith(q))) return 2;
    if (full.includes(q) || id.includes(q)) return 3;
    if (q.length >= 3) {
      const skipped = gaps(q, full);
      if (skipped >= 0 && skipped <= full.length) return 4 + skipped / 100;
    }
    if (q.length >= 4) {
      // Against the whole name, and against its first letters, so a typo in a
      // half-typed name still finds it.
      const d = Math.min(distance(q, full), distance(q, full.slice(0, q.length)));
      if (d <= Math.max(1, Math.floor(q.length / 4))) return 5 + d;
    }
    return Infinity;
  }

  function rank(query, entries, limit = 8) {
    return entries
      .map((entry) => ({ entry, s: score(query, entry) }))
      .filter((pair) => pair.s !== Infinity)
      .sort((a, b) => a.s - b.s || a.entry.name.length - b.entry.name.length
                      || a.entry.name.localeCompare(b.entry.name))
      .slice(0, limit)
      .map((pair) => pair.entry);
  }

  const api = { norm, distance, rank, score };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Search = api;
})(this);
