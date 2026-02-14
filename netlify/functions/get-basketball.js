// Netlify Function - מביאה נתונים על בני הרצליה (FINAL + SMART)
// עם תמיכה במשחקי גביע (hardcode חכם) + זיהוי אוטומטי
// Cache חכם - מתעדכן אוטומטית כל 48 שעות

const https = require('https');

// משתנה גלובלי לשמירת cache (נשמר בזיכרון)
let cachedData = null;
let lastUpdate = null;

// פונקציה למשיכת HTML מאתר
function fetchHTML(url) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

// פונקציה לבדיקה אם יש משחק גביע קרוב
function checkUpcomingCupGame() {
  const today = new Date();
  
  // ===== משחקי גביע עתידיים - עדכן כאן! =====
  const cupGames = [
    {
      opponent: 'הפועל העמק',
      date: '16.02.26',
      description: 'חצי גמר גביע המדינה',
      until: new Date('2026-02-17') // יום אחרי המשחק
    }
    // הוסף משחקי גביע עתידיים כאן בפורמט הזה:
    // {
    //   opponent: 'שם היריב',
    //   date: 'DD.MM.YY',
    //   description: 'גמר גביע / רבע גמר גביע / וכו',
    //   until: new Date('YYYY-MM-DD') // יום אחרי המשחק
    // }
  ];
  
  // בודק אם יש משחק גביע רלוונטי
  for (const game of cupGames) {
    if (today < game.until) {
      return {
        opponent: `${game.opponent} (${game.date})`,
        date: game.date,
        isCup: true,
        description: game.description
      };
    }
  }
  
  return null;
}

// פונקציה לחילוץ נתונים מה-HTML
function parseBasketballData(teamHTML, tableHTML) {
  const data = {
    position: 'טוען...',
    lastGame: { result: 'טוען...', date: '' },
    nextGame: { opponent: 'טוען...', date: '' },
    lastUpdated: new Date().toISOString()
  };

  // ===== בדיקה: האם יש משחק גביע קרוב? =====
  const cupGame = checkUpcomingCupGame();
  if (cupGame) {
    data.nextGame = {
      opponent: `${cupGame.opponent} - ${cupGame.description}`,
      date: cupGame.date
    };
    console.log('🏆 משחק גביע קרוב זוהה:', cupGame);
  }

  // חילוץ מיקום בטבלה
  const tableRows = tableHTML.match(/<tr[^>]*>[\s\S]*?<\/tr>/gi) || [];
  for (let i = 0; i < tableRows.length; i++) {
    if (tableRows[i].includes('בני') && tableRows[i].includes('הרצליה')) {
      const posMatch = tableRows[i].match(/>(\d+)</);
      if (posMatch) {
        data.position = posMatch[1];
        break;
      }
    }
  }

  // חילוץ משחקים - רק אם לא מצאנו משחק גביע
  if (!cupGame) {
    const gameTable = teamHTML.match(/משחקים ותוצאות אחרונות[\s\S]*?<\/table>/i);
    
    if (gameTable) {
      const rows = gameTable[0].match(/<tr[^>]*>[\s\S]*?<\/tr>/gi) || [];
      
      let foundNext = false;

      for (const row of rows) {
        if (!row.includes('הרצליה')) continue;

        const dateMatch = row.match(/(\d{2}\.\d{2}\.\d{2})/);
        const scoreMatch = row.match(/(\d+)-(\d+)/);
        
        // משחק עתידי (יש תאריך, אין תוצאה)
        if (dateMatch && !scoreMatch && !foundNext) {
          const teams = row.match(/>(הפועל|מכבי|עירוני|בני|אליצור)\s+([^<]+)</g) || [];
          
          for (const team of teams) {
            const cleanTeam = team.replace(/>/g, '').trim();
            if (cleanTeam !== 'בני הרצליה' && !cleanTeam.includes('הרצליה')) {
              data.nextGame = {
                opponent: cleanTeam,
                date: dateMatch[1]
              };
              foundNext = true;
              break;
            }
          }
        }
      }
    }
  }

  // חילוץ תוצאה אחרונה
  const gameTable = teamHTML.match(/משחקים ותוצאות אחרונות[\s\S]*?<\/table>/i);
  
  if (gameTable) {
    const rows = gameTable[0].match(/<tr[^>]*>[\s\S]*?<\/tr>/gi) || [];
    
    for (const row of rows) {
      if (!row.includes('הרצליה')) continue;

      const dateMatch = row.match(/(\d{2}\.\d{2}\.\d{2})/);
      const scoreMatch = row.match(/(\d+)-(\d+)/);
      
      // משחק שהסתיים (יש תוצאה)
      if (scoreMatch && dateMatch) {
        data.lastGame = {
          result: scoreMatch[0],
          date: dateMatch[1]
        };
        break;
      }
    }
  }

  return data;
}

// הפונקציה הראשית
exports.handler = async function(event, context) {
  try {
    // בדיקה אם יש cache ולא עברו 48 שעות
    const now = Date.now();
    const CACHE_DURATION = 48 * 60 * 60 * 1000; // 48 שעות במילישניות

    if (cachedData && lastUpdate && (now - lastUpdate) < CACHE_DURATION) {
      console.log('🏀 משתמש בנתונים שמורים (cache)');
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({
          ...cachedData,
          cached: true,
          cacheAge: Math.floor((now - lastUpdate) / 1000 / 60) + ' דקות'
        })
      };
    }

    // אין cache או שפג תוקפו - מושכים נתונים חדשים
    console.log('🏀 מושך נתונים חדשים מ-Sport5...');
    
    const [teamHTML, tableHTML] = await Promise.all([
      fetchHTML('https://www.sport5.co.il/team.aspx?FolderID=2594'),
      fetchHTML('https://www.sport5.co.il/liga.aspx?FolderID=273')
    ]);
    
    const data = parseBasketballData(teamHTML, tableHTML);
    
    // שמירה ב-cache
    cachedData = data;
    lastUpdate = now;
    
    console.log('✅ נתונים חדשים נשמרו בהצלחה:', data);
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        ...data,
        cached: false
      })
    };
    
  } catch (error) {
    console.error('❌ שגיאה:', error);
    
    // אם יש cache ישן, נחזיר אותו גם אם יש שגיאה
    if (cachedData) {
      return {
        statusCode: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Access-Control-Allow-Origin': '*'
        },
        body: JSON.stringify({
          ...cachedData,
          cached: true,
          error: 'משתמש בנתונים ישנים בגלל שגיאה'
        })
      };
    }
    
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify({
        error: error.message,
        position: '...',
        lastGame: { result: 'שגיאה', date: '' },
        nextGame: { opponent: 'שגיאה', date: '' }
      })
    };
  }
};
