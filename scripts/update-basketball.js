// Fetch Bnei Herzliya's league table position from api-sports.io and merge it into
// data/bnei-herzliya.json as "standing". Games come from data/bhbasket-games.json
// (scripts/fetch_bhbasket.py), so this script touches only the "standing" key.
// On any failure or empty response the previous "standing" is kept; null is never written.
const fs = require("fs");
const path = require("path");

const API_KEY = process.env.APISPORTS_KEY;
const OUT_PATH = path.join(process.cwd(), "data", "bnei-herzliya.json");

const TEAM_ID = 1566;
const LEAGUE_ID = 51;

// Season runs Aug-Jul, e.g. October 2026 -> "2026-2027". Override with SEASON env if needed.
function currentSeason() {
  const now = new Date();
  const start = now.getUTCMonth() >= 7 ? now.getUTCFullYear() : now.getUTCFullYear() - 1;
  return `${start}-${start + 1}`;
}
const SEASON = process.env.SEASON || currentSeason();

async function fetchStanding() {
  const url = `https://v1.basketball.api-sports.io/standings?league=${LEAGUE_ID}&season=${SEASON}`;
  const res = await fetch(url, { headers: { "x-apisports-key": API_KEY } });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data = await res.json();
  const errors = data?.errors;
  if (errors && (Array.isArray(errors) ? errors.length : Object.keys(errors).length)) {
    throw new Error(`API errors: ${JSON.stringify(errors)}`);
  }

  // response is a list of groups (stages); each group is a list of team rows.
  const groups = (data?.response || []).filter(Array.isArray);
  const group = groups.find(g => g.some(r => r?.team?.id === TEAM_ID));
  if (!group) return null;
  const row = group.find(r => r?.team?.id === TEAM_ID);

  const position = Number(row.position);
  const total = group.length;
  const wins = Number(row.games?.win?.total);
  const losses = Number(row.games?.lose?.total);
  if (![position, wins, losses].every(Number.isFinite) || position < 1 || total < 1) return null;
  return { position, total, wins, losses, updated: new Date().toISOString() };
}

async function main() {
  let existing = {};
  try {
    existing = JSON.parse(fs.readFileSync(OUT_PATH, "utf8"));
  } catch (_) {}

  if (!API_KEY) {
    console.log("APISPORTS_KEY not set — keeping previous standing");
    return;
  }

  let standing = null;
  try {
    console.log(`Fetching standings: league=${LEAGUE_ID} season=${SEASON} team=${TEAM_ID}`);
    standing = await fetchStanding();
  } catch (e) {
    console.log(`Standings fetch failed: ${e.message} — keeping previous standing`);
    return;
  }
  if (!standing) {
    console.log("No standings data for the team — keeping previous standing");
    return;
  }

  const payload = { ...existing, standing };
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2) + "\n", "utf8");
  console.log("Saved standing:", JSON.stringify(standing));
}

main().catch(e => { console.error("Fatal:", e.message); process.exit(0); });
