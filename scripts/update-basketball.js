import fs from "fs";
import path from "path";

const API_KEY = process.env.BASKETBALL_API_KEY;
const OUT_PATH = path.join(process.cwd(), "data", "bnei-herzliya.json");

// בני הרצליה: team ID=497, ליגה ישראלית: league=120, עונה=2025-2026
const TEAM_ID = 497;
const LEAGUE_ID = 120;
const SEASON = "2025-2026";

const HEADERS = {
  "x-apisports-key": API_KEY
};

async function apiFetch(endpoint) {
  const url = `https://v1.basketball.api-sports.io/${endpoint}`;
  const res = await fetch(url, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`);
  return await res.json();
}

async function main() {
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });

  // שלוף טבלה
  const standingsData = await apiFetch(`standings?league=${LEAGUE_ID}&season=${SEASON}`);
  let position = null;
  const standings = standingsData?.response?.[0];
  if (standings) {
    for (const group of standings) {
      const team = group.find?.(t => t.team?.id === TEAM_ID);
      if (team) { position = team.position; break; }
    }
  }

  // שלוף משחקים
  const gamesData = await apiFetch(`games?team=${TEAM_ID}&league=${LEAGUE_ID}&season=${SEASON}`);
  const games = gamesData?.response || [];

  const now = new Date();

  const finished = games.filter(g =>
    g.status?.short === "FT" && new Date(g.date) <= now
  ).sort((a, b) => new Date(b.date) - new Date(a.date));

  const upcoming = games.filter(g =>
    g.status?.short === "NS" && new Date(g.date) > now
  ).sort((a, b) => new Date(a.date) - new Date(b.date));

  const last = finished[0] || null;
  const next = upcoming[0] || null;

  // בנה אובייקט תוצאה
  let lastGame = null;
  if (last) {
    const isHome = last.teams?.home?.id === TEAM_ID;
    const myScore = isHome ? last.scores?.home?.total : last.scores?.away?.total;
    const oppScore = isHome ? last.scores?.away?.total : last.scores?.home?.total;
    const opp = isHome ? last.teams?.away?.name : last.teams?.home?.name;
    const won = myScore > oppScore;
    const dateStr = new Date(last.date).toLocaleDateString("he-IL");
    lastGame = {
      date: dateStr,
      opponent: opp,
      myScore,
      oppScore,
      won,
      result: `${won ? "ניצחון" : "הפסד"} ${myScore}:${oppScore} נגד ${opp} (${dateStr})`,
      resultRu: `${won ? "Победа" : "Поражение"} ${myScore}:${oppScore} (${dateStr})`
    };
  }

  let nextGame = null;
  if (next) {
    const isHome = next.teams?.home?.id === TEAM_ID;
    const opp = isHome ? next.teams?.away?.name : next.teams?.home?.name;
    const dateStr = new Date(next.date).toLocaleDateString("he-IL");
    const time = new Date(next.date).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
    nextGame = {
      date: dateStr,
      time,
      opponent: opp,
      isHome,
      text: `נגד ${opp} | ${dateStr} ${time} | ${isHome ? "בית" : "חוץ"}`,
      textRu: `против ${opp} | ${dateStr} ${time}`
    };
  }

  const payload = {
    updatedAt: new Date().toISOString(),
    position,
    lastGame,
    nextGame
  };

  fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2), "utf8");
  console.log("✅ Updated:", JSON.stringify(payload, null, 2));
}

main().catch(e => { console.error("❌ Error:", e.message); process.exit(1); });
