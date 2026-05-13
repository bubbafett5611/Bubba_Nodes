import { performance } from "node:perf_hooks";
import { buildSearchIndex, findMatchesFromIndex } from "../web/comfyui/autocomplete/search.js";
import { getSearchQueryVariations } from "../web/comfyui/autocomplete/utils.js";

function makeWord(i) {
  const tag = `tag_${i}`;
  const aliasA = `alias_${i}`;
  const aliasB = i % 7 === 0 ? `character_${i}` : `style_${i}`;
  return {
    text: tag,
    source: "danbooru",
    count: Math.max(0, 1_000_000 - i * 3),
    aliases: [aliasA, aliasB],
  };
}

function makeDataset(size) {
  const words = [];
  for (let i = 0; i < size; i += 1) {
    words.push(makeWord(i));
  }
  words.push({ text: "masterpiece", source: "custom", count: 250_000, aliases: ["best_quality"] });
  words.push({ text: "dramatic lighting", source: "custom", count: 170_000, aliases: ["cinematic_light"] });
  words.push({ text: "1girl", source: "custom", count: 900_000, aliases: ["solo_female"] });
  return words;
}

function rankAndTrim(matches, limit) {
  return matches
    .sort((a, b) => {
      const aCount = typeof a.count === "number" ? a.count : -1;
      const bCount = typeof b.count === "number" ? b.count : -1;
      if (bCount !== aCount) return bCount - aCount;
      const aScore = Number.isFinite(a.matchScore) ? a.matchScore : 0;
      const bScore = Number.isFinite(b.matchScore) ? b.matchScore : 0;
      if (bScore !== aScore) return bScore - aScore;
      return a.text.localeCompare(b.text);
    })
    .slice(0, limit);
}

function timeMs(fn) {
  const start = performance.now();
  const result = fn();
  const elapsed = performance.now() - start;
  return { result, elapsed };
}

const DATASET_SIZE = Number.parseInt(process.env.BUBBA_BENCH_TAGS || "75000", 10);
const SUGGESTION_LIMIT = Number.parseInt(process.env.BUBBA_BENCH_LIMIT || "20", 10);
const QUERIES = [
  "tag_1",
  "tag_120",
  "character_",
  "dramatic",
  "best q",
  "solo",
  "tag_70000",
  "cinematic",
];

const words = makeDataset(DATASET_SIZE);

const build = timeMs(() => buildSearchIndex(words));
const index = build.result;

// Warmup once to reduce first-call noise.
for (const query of QUERIES) {
  const queryVariations = getSearchQueryVariations(query);
  const matches = findMatchesFromIndex(index, queryVariations);
  rankAndTrim(matches, SUGGESTION_LIMIT);
}

const rows = [];
let totalMatchMs = 0;
let totalRankMs = 0;
for (const query of QUERIES) {
  const queryVariations = getSearchQueryVariations(query);
  const matchTiming = timeMs(() => findMatchesFromIndex(index, queryVariations));
  const rankTiming = timeMs(() => rankAndTrim(matchTiming.result, SUGGESTION_LIMIT));

  totalMatchMs += matchTiming.elapsed;
  totalRankMs += rankTiming.elapsed;
  rows.push({
    query,
    candidates: matchTiming.result.length,
    top: rankTiming.result.length,
    matchMs: matchTiming.elapsed,
    rankMs: rankTiming.elapsed,
    totalMs: matchTiming.elapsed + rankTiming.elapsed,
  });
}

const avgMs = rows.reduce((acc, row) => acc + row.totalMs, 0) / rows.length;
const maxMs = rows.reduce((acc, row) => Math.max(acc, row.totalMs), 0);

console.log("Autocomplete Benchmark");
console.log(`dataset_size=${DATASET_SIZE} queries=${QUERIES.length} limit=${SUGGESTION_LIMIT}`);
console.log(`build_index_ms=${build.elapsed.toFixed(3)}`);
console.log(`avg_query_ms=${avgMs.toFixed(3)} max_query_ms=${maxMs.toFixed(3)} avg_match_ms=${(totalMatchMs / rows.length).toFixed(3)} avg_rank_ms=${(totalRankMs / rows.length).toFixed(3)}`);
console.log("\nPer-query breakdown:");
for (const row of rows) {
  console.log(
    `${row.query.padEnd(14)} candidates=${String(row.candidates).padStart(6)} top=${String(row.top).padStart(3)} match_ms=${row.matchMs.toFixed(3).padStart(8)} rank_ms=${row.rankMs.toFixed(3).padStart(8)} total_ms=${row.totalMs.toFixed(3).padStart(8)}`,
  );
}
