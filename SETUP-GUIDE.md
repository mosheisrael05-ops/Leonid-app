# 🚀 מדריך התקנה - צעד אחר צעד

## שלב 1: צור חשבון GitHub (אם אין)
1. לך ל: https://github.com
2. לחץ "Sign up"
3. הזן אימייל, סיסמה, שם משתמש
4. אמת את האימייל

## שלב 2: צור Repository חדש
1. לחץ על ➕ למעלה מימין → "New repository"
2. שם: `leonid-app`
3. סמן: ✅ Public
4. ❌ אל תסמן "Add a README"
5. לחץ "Create repository"

## שלב 3: העלה את הקבצים
### אפשרות A - גרור ושחרר (הכי פשוט):
1. בעמוד ה-repo החדש, לחץ "uploading an existing file"
2. גרור את כל הקבצים מתוך תיקיית leonid-app
3. **חשוב!** צריך להעלות גם את תיקייה netlify ובתוכה functions

### אפשרות B - קובץ אחר קובץ:
1. לחץ "Add file" → "Upload files"
2. העלה index.html, netlify.toml, .gitignore, README.md
3. לחץ "Commit changes"
4. לחץ "Add file" → "Create new file"
5. כתוב את הנתיב: `netlify/functions/get-basketball.js`
6. העתק את התוכן של הקובץ ולחץ "Commit"

## שלב 4: חבר ל-Netlify
1. לך ל: https://app.netlify.com
2. היכנס עם חשבון GitHub
3. לחץ "Add new site" → "Import an existing project"
4. בחר "GitHub"
5. חפש ובחר את `leonid-app`
6. הגדרות:
   - Branch: `main`
   - Publish directory: `.`
7. לחץ "Deploy site"

## שלב 5: חבר את הדומיין הקיים
1. בהגדרות האתר ב-Netlify → "Domain management"
2. לחץ "Add custom domain"
3. הוסף: `mellow-arithmetic-14863a.netlify.app`
   (או שנה את שם האתר ב-Settings → "Change site name")

## ✅ מוכן!
מעכשיו כל שינוי ב-GitHub → Netlify מתעדכן אוטומטית!

---

## 📅 עדכון סידור עבודה חודשי (ב-23/24 לכל חודש):
1. פתח את `index.html` ב-GitHub
2. לחץ על ✏️ (העיפרון)
3. חפש: `const workSchedule = {`
4. שנה את התאריכים והשמות לחודש הבא
5. לחץ "Commit changes" (כפתור ירוק)
6. תוך דקה - האתר מתעדכן!
