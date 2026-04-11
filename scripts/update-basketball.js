 import fs from "fs";
import path from "path";

const API_KEY = process.env.APISPORTS_KEY; // ✅ תוקן
const OUT_PATH = path.join(process.cwd(), "data", "bnei-herzliya.json");

const TEAM_ID = 1566;
const LEAGUE_ID = 51;
const SEASON = "2025-2026";

const HEADERS = { "x-apisports-key": API_KEY };

async function apiFetch(endpoint) {
  const url = `https://v1.basketball.api-sports.io/${endpoint}`;
  const res = await fetch(url, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`);
  return await res.json();
}

// --- Fallback: סריקת אתרי ספורט ---
async function scrapeNextGameFromNews() {
  const sources = [
    {
      name: "bhbasket",
      url: "https://bhbasket.co.il",
      // מחפש טקסט בסגנון "המשחק הבא"
    },
    {
      name: "ynet",
      url: "https://www.ynet.co.il/sport/basketball",
    },
    {
      name: "maariv",
      url: "https://www.maariv.co.il/sport/basketball",
    },
    {
      name: "israelhayom",
      url: "https://www.israelhayom.co.il/sport",
    },
  ];

  const searchTerms = [
    "בני הרצליה",
    "הרצליה"
  ];

  for (const source of sources) {
    try {
      console.log(`🔍 מנסה לסרוק: ${source.name}`);
      const res = await fetch(source.url, {
        headers: {
          "User-Agent": "Mozilla/5.0 (compatible; LeonidApp/1.0)",
          "Accept": "text/html",
        },
        signal: AbortSignal.timeout(8000),
      });

      if (!res.ok) {
        console.log(`  ⚠️ ${source.name} החזיר ${res.status}`);
        continue;
      }

      const html = await res.text();

      // חיפוש תאריך עתידי בפורמטים שכיחים ליד שם הקבוצה
      // פורמטים: DD/MM, DD.MM, DD/MM/YY, DD.MM.YY
      const datePattern = /(\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?)/g;

      // מצא חלונות טקסט שמכילים "הרצליה" + תאריך
      const herzliyaBlocks = [];
      for (const term of searchTerms) {
        const idx = html.indexOf(term);
        if (idx === -1) continue;
        // לקחת 500 תווים לפני ואחרי
        const block = html.substring(Math.max(0, idx - 200), idx + 300);
        herzliyaBlocks.push(block);
      }

      if (herzliyaBlocks.length === 0) {
        console.log(`  ℹ️ ${source.name} - לא נמצאה הרצליה`);
        continue;
      }

      // חיפוש תאריך עתידי בבלוקים
      const now = new Date();
      const currentYear = now.getFullYear();

      for (const block of herzliyaBlocks) {
        const matches = [...block.matchAll(/(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?/g)];
        for (const m of matches) {
          let day = parseInt(m[1]);
          let month = parseInt(m[2]) - 1;
          let year = m[3] ? (m[3].length === 2 ? 2000 + parseInt(m[3]) : parseInt(m[3])) : currentYear;
          const candidateDate = new Date(year, month, day);
          if (candidateDate > now) {
            // מצאנו תאריך עתידי!
            // חפש שם יריב בבלוק
            const opponent = extractOpponent(block);
            const dateStr = `${String(day).padStart(2,'0')}.${String(month+1).padStart(2,'0')}.${String(year).slice(-2)}`;
            console.log(`  ✅ ${source.name}: נמצא משחק ב-${dateStr} נגד ${opponent}`);
            return { dateStr, opponent, source: source.name };
          }
        }
      }

      console.log(`  ℹ️ ${source.name} - לא נמצא תאריך עתידי`);
    } catch (e) {
      console.log(`  ❌ ${source.name} שגיאה: ${e.message}`);
    }
  }

  return null;
}

function extractOpponent(block) {
  // רשימת קבוצות ליגת winner סל
  const teams = [
    "מכבי תל אביב", "הפועל תל אביב", "הפועל ירושלים", "הפועל חולון",
    "מכבי ראשון לציון", "הפועל באר שבע", "מכבי רעננה", "הפועל גליל עליון",
    "הפועל העמק", "מכבי עירוני רמת גן", "עירוני קרית אתא", "עירוני נס ציונה",
    "אליצור נתניה", "הפועל אילת"
  ];
  for (const team of teams) {
    if (block.includes(team)) return team;
  }
  return "יריב לא ידוע";
}

function teamNameRu(hebrewName) {
  const map = {
    "מכבי תל אביב": "Маккаби Тель-Авив",
    "הפועל תל אביב": "Апоэль Тель-Авив",
    "הפועל ירושלים": "Апоэль Иерусалим",
    "הפועל חולון": "Апоэль Холон",
    "מכבי ראשון לציון": "Маккаби Ришон ле-Цион",
    "הפועל באר שבע": "Апоэль Беэр-Шева",
    "מכבי רעננה": "Маккаби Раанана",
    "הפועל גליל עליון": "Апоэль Галиль Эльон",
    "הפועל העמק": "Апоэль ха-Эмек",
    "מכבי עירוני רמת גן": "Маккаби Рамат-Ган",
    "עירוני קרית אתא": "Ирони Кирьят-Ата",
    "עירוני נס ציונה": "Ирони Нес-Циона",
    "אליצור נתניה": "Элицур Нетания",
    "הפועל אילת": "Апоэль Эйлат",
  };
  return map[hebrewName] || hebrewName;
}

async function main() {
  fs.mkdirSync(path.dirname(OUT_PATH), { recursive: true });

  // טען JSON קיים (לשמור נתונים אם ה-API ריק)
  let existing = {};
  try {
    existing = JSON.parse(fs.readFileSync(OUT_PATH, "utf8"));
  } catch (_) {}

  let position = existing.position || null;
  let lastGame = existing.lastGame || null;
  let nextGame = existing.nextGame || null;

  // --- API ---
  if (API_KEY) {
    try {
      console.log("📡 שולח לAPI-Sports...");

      const standingsData = await apiFetch(`standings?league=${LEAGUE_ID}&season=${SEASON}`);
      const standings = standingsData?.response?.[0];
      if (standings) {
        for (const group of standings) {
          const team = group.find?.(t => t.team?.id === TEAM_ID);
          if (team) { position = team.position; break; }
        }
      }
      console.log(`  מיקום: ${position}`);

      const gamesData = await apiFetch(`games?team=${TEAM_ID}&league=${LEAGUE_ID}&season=${SEASON}`);
      const games = gamesData?.response || [];
      const now = new Date();

      const finished = games
        .filter(g => g.status?.short === "FT" && new Date(g.date) <= now)
        .sort((a, b) => new Date(b.date) - new Date(a.date));

      const upcoming = games
        .filter(g => g.status?.short === "NS" && new Date(g.date) > now)
        .sort((a, b) => new Date(a.date) - new Date(b.date));

      const last = finished[0] || null;
      const next = upcoming[0] || null;

      if (last) {
        const isHome = last.teams?.home?.id === TEAM_ID;
        const myScore = isHome ? last.scores?.home?.total : last.scores?.away?.total;
        const oppScore = isHome ? last.scores?.away?.total : last.scores?.home?.total;
        const opp = isHome ? last.teams?.away?.name : last.teams?.home?.name;
        const won = myScore > oppScore;
        const dateStr = new Date(last.date).toLocaleDateString("he-IL");
        lastGame = {
          date: dateStr, opponent: opp, myScore, oppScore, won,
          result: `${won ? "ניצחון" : "הפסד"} ${myScore}:${oppScore} נגד ${opp} (${dateStr})`,
          resultRu: `${won ? "Победа" : "Поражение"} ${myScore}:${oppScore} (${dateStr})`
        };
        console.log(`  משחק אחרון: ${lastGame.result}`);
      }

      if (next) {
        const isHome = next.teams?.home?.id === TEAM_ID;
        const opp = isHome ? next.teams?.away?.name : next.teams?.home?.name;
        const dateStr = new Date(next.date).toLocaleDateString("he-IL");
        const time = new Date(next.date).toLocaleTimeString("he-IL", { hour: "2-digit", minute: "2-digit" });
        nextGame = {
          date: dateStr, time, opponent: opp, isHome,
          text: `נגד ${opp} | ${dateStr} ${time} | ${isHome ? "בית" : "חוץ"}`,
          textRu: `против ${opp} | ${dateStr} ${time}`
        };
        console.log(`  משחק הבא: ${nextGame.text}`);
      } else {
        console.log("  ⚠️ API לא החזיר משחק הבא — עובר לסריקת אתרים");
      }

    } catch (e) {
      console.log(`⚠️ API נכשל: ${e.message} — עובר לסריקת אתרים`);
    }
  } else {
    console.log("⚠️ אין API key — עובר ישירות לסריקת אתרים");
  }

  // --- Fallback: סריקת אתרי ספורט אם אין משחק הבא ---
  if (!nextGame) {
    console.log("🗞️ מנסה לסרוק אתרי ספורט...");
    const scraped = await scrapeNextGameFromNews();
    if (scraped) {
      const oppRu = teamNameRu(scraped.opponent);
      nextGame = {
        date: scraped.dateStr,
        opponent: scraped.opponent,
        source: scraped.source,
        text: `נגד ${scraped.opponent} (${scraped.dateStr})`,
        textRu: `против ${oppRu} (${scraped.dateStr})`
      };
      console.log(`✅ נמצא ממקור ${scraped.source}: ${nextGame.text}`);
    } else {
      console.log("❌ לא נמצא משחק הבא בשום מקור");
    }
  }

  const payload = {
    updatedAt: new Date().toISOString(),
    position,
    lastGame,
    nextGame
  };

  fs.writeFileSync(OUT_PATH, JSON.stringify(payload, null, 2), "utf8");
  console.log("✅ נשמר:", OUT_PATH);
  console.log(JSON.stringify(payload, null, 2));
}

main().catch(e => { console.error("❌ שגיאה קריטית:", e.message); process.exit(1); });
