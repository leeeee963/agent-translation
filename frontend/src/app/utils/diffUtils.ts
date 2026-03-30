// ── Token-level diff engine (multilingual) ─────────────────────────

export type DiffOp = { type: 'equal' | 'delete' | 'insert'; text: string };

/** Tokenize text into word-level segments using Intl.Segmenter (handles all languages). */
function tokenize(text: string): string[] {
  const segmenter = new Intl.Segmenter(undefined, { granularity: 'word' });
  return [...segmenter.segment(text)].map(s => s.segment);
}

/** LCS-based token-level diff between two strings. */
export function tokenDiff(before: string, after: string): DiffOp[] {
  const beforeTokens = tokenize(before);
  const afterTokens = tokenize(after);
  const m = beforeTokens.length;
  const n = afterTokens.length;

  // Build LCS length table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = beforeTokens[i - 1] === afterTokens[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }

  // Backtrack to build diff ops
  const ops: DiffOp[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && beforeTokens[i - 1] === afterTokens[j - 1]) {
      ops.push({ type: 'equal', text: beforeTokens[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.push({ type: 'insert', text: afterTokens[j - 1] });
      j--;
    } else {
      ops.push({ type: 'delete', text: beforeTokens[i - 1] });
      i--;
    }
  }
  ops.reverse();

  // Merge consecutive ops of the same type
  const merged: DiffOp[] = [];
  for (const op of ops) {
    if (merged.length > 0 && merged[merged.length - 1].type === op.type) {
      merged[merged.length - 1].text += op.text;
    } else {
      merged.push({ ...op });
    }
  }
  return merged;
}
