# Worklog — Abiturend

## 1. Loyiha

- **Aniqlangan loyiha:** Abiturend — abituriyentlar uchun test/mashq platformasi (monorepo).
- **Stack:** Next.js 16.3.5 + React 19 + TypeScript (frontend, `next-intl`); Django 6 + DRF (backend); PostgreSQL 17 (production), SQLite (`DJANGO_USE_SQLITE=1`, test/lokal); Docker Compose + Nginx; GitHub Actions (deploy + verify).
- **Ilova (backend):** `accounts`, `catalog`, `questions`, `practice`, `onboarding`, `gamification`, `premium`, `payments`, `universities`, `telegrambot`, `mcpbridge`, `core`.
- **Maqsad:** butun arxitekturani tekshirish, topilgan muammolarni tuzatish, muhim funksiyalarni testlar va lokal brauzer orqali tasdiqlash.

## 2. Muhim qarorlar va taxminlar

- Ish papkasida avvaldan katta hajmdagi commit qilinmagan o'zgarishlar bor (`git status` da ko'plab modified fayllar, `?? .github/workflows/verify.yml`, `?? backend/practice/migrations/0005_alter_practicesession_status.py`, `?? frontend/lib/navigation.ts`). Ular oldingi ish natijasi deb hisoblandi va **reset/overwrite qilinmadi**.
- Hech qanday `git commit` / `git add` / `git push` bajarilmadi — fayllar tayyorlab qoldirildi.
- `.env*`, kalitlar, tokenlar o'qilmadi va o'zgartirilmadi.
- Bazadirect o'zgartirilmadi; schema o'zgarishlari faqat `makemigrations --check` orqali tekshirildi.
- Supabase/Stitch integratsiyasi loyihada mavjud emas (PostgreShell backend ishlatiladi) — shu sababli tegishli MCP/Stitch vositalari qo'llanmadi.
- Fake/test ma'lumotlari ishga tushirilmadi; barcha tekshiruvlar Django `TestCase` ichida izolyatsiyalangan.

## 3. bajarilgan ish

### 3.1 Baseline tekshiruvlar

| Tekshiruv | Natija |
| --- | --- |
| `manage.py check` (SQLite) | 0 muammo |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| `manage.py test --noinput` (boshlang'ich) | `Ran 267 tests ... OK` |
| `npm run lint` | toza |
| `npx tsc --noEmit` | toza |
| `npm run build` | 63 sahifa + `postbuild` muvaffaqiyatli |

Muhim: testlar **faqat `backend` papkasida** ishga tushadi. Repo ildizidan `manage.py test` 0 ta test topadi (noto'g'ri working directory).

### 3.2 Topilgan va tuzatilgan xato: UTF-8 → CP1251 "mojibake"

Butun repo bo'ylab CP1251 noto'g'ri kod sahifasi orqali yozilgan (juft kodlangan) matn izlandi. Bu xato `json.loads`, ESLint, `tsc` va build uchun **butunlay ko'rinmas** edi — faqat foydalanuvchi ekranida buzilgan matn ko'rinardi. `git HEAD` da ham mavjud edi, ya'ni uzoq muddatli xato.

Tuzatilganlar:

| Fayl | Holat |
| --- | --- |
| `frontend/messages/ru.json` | `weakSkills` bo'limi (27 ta kalit), `nav.weakSkills` (L24), `L456` butunlay mojibake edi → tiklandi |
| `frontend/messages/uz.json` | nuqta (`·`) va uzluksiz chiziq (`—`) noto'g'ri kodlandi; `chegara` so'zidagi kirill `а` lotinga `a` ga tuzatildi |
| `frontend/messages/en.json` | nuqta (`·`) va uzluksiz chiziq (`—`) noto'g'ri kodlandi |
| `backend/telegrambot/services.py` | robot (🤖), grafik (📈), yashil kvadrat (🟩), oq kvadrat (⬜), nuqtali ro'yxat (•) va nuqta (`·`) gliflari noto'g'ri kodlangan edi |

Eslatma: buzilgan ko'rinishdagi misollar bu faylga ataylab yozilmadi — aks holda ularni avtomatik skaner o'zi mojibake deb hisoblardi.

Usul: har bir uzluksiz non-ASCII run `cp1251 -> utf-8` orqali qaytariladi; faqat toza kodlashga aylana oladigan runlar almashtiriladi (haqiqiy o'zbek/rus matni va `—`, `·`, `•`, `«»` bunday aylanmaydi). Har bir almashtirish loglandi, fayllarning zaxira nusxasi olindi, LF line ending va BOM holati saqlanib qoldi.

Qo'shimcha: `backend/telegrambot/services.py` da `weak_skills_text` oldidan PEP8 bo'sh qator qo'shildi.

### 3.3 Regressiya testlari

`backend/core/tests.py` ga `TextEncodingTests` qo'shildi (shu papkada allaqachon repo bo'ylab qo'riqchi testlar bor):

- `test_i18n_messages_are_not_double_encoded` — uchta locale faylida mojibake yo'qligi.
- `test_i18n_messages_have_identical_key_sets` — `uz`/`ru`/`en` kalit to'plamlari bir xil (hozir 523/523/523).
- `test_uz_messages_contain_no_cyrillic_letters` — o'zbek matnida kirill harfi yo'qligi.
- `test_telegram_copy_is_not_double_encoded` — `WELCOME_TEXT`/`HELP_TEXT` toza.
- `test_telegram_welcome_and_help_use_real_typography` — `🤖`, `•`, `—` haqiqiy gliflar saqlangan.

Frontendga i18n test qo'shilmadi: `frontend/package.json` da test runner (vitest/jest) yo'q. CI faqat `manage.py test` ishga tushuradi, shuning uchun qo'riqchi backend testiga joylashtirildi. Backend konteynerida `frontend/` yo'q bo'lgani uchun uch test `skipUnless` bilan himoyalangan.

### 3.4 Hujjat tuzatishlari

- `README.md`: parol tiklash API yo'llari real route'larga moslashtirildi — `POST /api/auth/forgot-password/` va `POST /api/auth/reset-password/` o'rniga `POST /api/auth/password-reset/` va `POST /api/auth/password-reset/confirm/`. (Frontend sahifalari `/forgot-password` va `/reset-password` to'g'ri edi.)
- `README.md` va `ANALIZ.md`: eskirgan test sonlari Django discovery orqali aniq hisoblab yangilandi — 262 → **272** (core 4→10, mcpbridge 20→26, premium 19→23).
- `ANALIZ.md`: i18n parity 520 → **523** va yangi kodlash qo'riqchisi haqidagi izoh qo'shildi.

### 3.5 Rad qilingan gumonlar

- `backend/practice/views.py` dagi `cache_page` decorator: runtime'da tekshirildi — `/api/leaderboard/` `200` va `Cache-Control: max-age=60`. `@method_decorator(cache_page(...))` to'g'ri, xato yo'q.
- Django testlarni repo ildizidan ishga tushirish: 0 test topishi noto'g'ri working directory, loyiha muammosi emas.

## 4. Done

- **Xato:** Rus tilidagi butun `weakSkills` tarjimasi va boshqa 3 fayldagi jami 74 mojibake run'i tuzatildi; Telegram bot matnlari (`🤖`, `•`, `📈`, `🟩`, `⬜`, `·`, `—`) tiklandi.
- **Test:** 5 ta yangi regressiya testi qo'shildi (mojibake, i18n kalit parity, kirill aralashuvi, tipografiya).
- **Hujjat:** `README.md` parol tiklash endpoint'lari va test sonlari, `ANALIZ.md` holat qatori tuzatildi; `worklog.md` yaratildi.

## 5. Verified

| Tekshiruv | Natija |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| `manage.py test --noinput` | **`Ran 272 tests in 222.290s` — `OK`** (267 + 5 yangi) |
| `npm run lint` | toza |
| `npx tsc --noEmit` | toza |
| `npm run build` | 63 sahifa + `prepare-standalone` muvaffaqiyatli |
| Repo bo'ylab mojibake skaneri | `0 mojibake run(s) in 0 file(s)` |
| `uz/ru/en.json` parse + kalit parity | 523/523/523, farq yo'q, LF va BOM saqlangan |

## 6. Remaining

Audit natijasida aniqlangan, ammo **hali tuzatilmagan** masalalar:

1. **Onboarding** — `backend/onboarding/plan.py::weak_subject_ids()` tashlab ketilgan (`status != FINISHED`) sessiya javoblarini ham zaif fan hisobiga oladi; `session__status=FINISHED` filtri yo'q. `weak_skills` va `gamification` bilan mantiqan mos emas.
2. **Weak skills throttling** — `WeakSkillRadarView` va `WeakSkillSubjectView` og'ir agregat query'lar uchun `throttle_scope`siz.
3. **`gamification/services.py::user_stats()`** — streak uchun barcha finished sessiyalar Python'ga yuklanadi; `TruncDate`/distinct agregatga o'tkazish mumkin.
4. **Onboarding N+1** — plan serializerida `_subject_brief`/`_topic_brief` har bir item uchun alohida query.
5. **Payments locale** — `payments.views._status_context()` locale'siz `/premium/payment/{id}/` yasashi sababli `lang` ko'pincha `uz` bo'ladi.
6. **Xavfsizlikni chuqur tekshirish** — `RegisterSerializer` dagi ochiq `role` maydoni orqali `/api/auth/register/` da teacher/admin roliga o'z-o'zidan e'tibor berish mumkin emas; Telegram webhook replay, MCP bearer scope, payment webhook idempotency.
8. **Frontend va infra audit** — route'lar, loading/error/empty holatlar, Docker Compose, Nginx, CI.
9. **Playwright** — lokal serverlar ishga tushirilib auth, onboarding, practice, report, history, mistakes, weak-skills, premium, leaderboard va teacher flowlari brauzerda tekshirilmagan.

## 7. Needs Input

- Haqiqiy Payme/Click gateway credentials yo'q — to'lov oqimining faqat signature va idempotency mantiqi testlarda tekshirilishi mumkin, real to'lovni tasdiqlab bo'lmaydi.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` va `MCP_API_KEY` .env'da; qiymatlariga murojaat qilinmadi, faqat `is_configured()` no-op holati tekshirildi.

## 8. 2026-10-04 — Lokal dev porti (3001) uchun CSRF origin

**Muammo:** `POST /api/auth/login/` va `/api/auth/register/` lokalda 403
— `Origin checking failed - http://localhost:3001 does not match any trusted origins`.

**Sabab:** `3000`-port `8-maktab-crm` loyihasi egallab turgani uchun
abuturend frontend `next dev -p 3001` da ishga tushirildi, esa
`config/settings.py` ning `CSRF_TRUSTED_ORIGINS` defaulti faqat
`localhost:3000` / `localhost:8000` ni o'z ichiga olardi. Next rewrites
orqali o'tganda Django `good_origin` sifatida `Host` ni ko'radi, u esa
orgin bilan mos kelmaydi va faqat ishonchli orginlar ro'yxati qoladi.

**Yechim:** `config/settings.py` — `DEBUG=True` bo'lda default ro'yxatga
`localhost:3001..3009` dev portlari qo'shildi (port band bo'lsa Next.js
o'zi keyingi portga o'tadi). Prod'da `DJANGO_CSRF_TRUSTED_ORIGINS` majburiy
o'rnatilgani uchun bu kengaytirish u erda ishlatilmaydi.

**Tekshiruv:** `http://localhost:3001` orqali CSRF cookie + `X-CSRFToken`
bilan — login noto'g'ri ma'lumot uchun **401**, register bo'sh payload uchun
**400** (ikkalasi ham 403 emas).

## 9. 2026-10-05 — Lokal backend bazasini birlashtirish (SQLite -> PostgreSQL)

**Muammo:** admin panelga dmin paroli o'zgartirilgandan keyin ham login
401/200 (rad etilgan) qaytardi.

**Sabab:** ishlab turgan manage.py runserver **SQLite** (ackend/db.sqlite3)
da ishlagan — u yerda faqat e2e test qoldiqlari (e2efake_*, eyk_user*,
6 ta user, 13 fan) bor va dmin umuman yo'q. Haqiqiy ma'lumot esa
**PostgreSQL**da (biturend: teacher1, student1, admin, 18 fan, 44 savol),
parol ham shu yerga yozilgan edi. Server SQLite'ga DJANGO_USE_SQLITE=1
bilan ishga tushirilgan (User/Machine darajasida emas, faqat o'sha terminalda).

**Amallar:**
1. PostgreSQL'ga backup: pg_dump -U abiturend -d abiturend
   -> ackend/db-backups/abiturend-20261005-025507.sql (106 104 bayt).
2. Kutilmagan 11 ta migratsiya qo'llanildi (onboarding.0001,
   payments.0001-0002, practice.0002-0005, questions.0002).
3. Eski unserver daraxti to'xtatilib, DJANGO_USE_SQLITEsiz qayta ishga
   tushirildi (log: ackend/backend-dev.log).
4. Admin paroli dmin uchun o'rnatildi (faqat shaxsiy hisob uchun).

**Tekshiruv:** /api/subjects/ -> 18 (Postgres), admin login **302** ->
/admin/ 200, API login **200** (id=14), manage.py check toza,
manage.py test --noinput (SQLite) -> **Ran 279 tests ... OK**.

**Eslatma:** lokalda DJANGO_USE_SQLITE=1 qo'ysangiz, ma'lumotlar
db.sqlite3 da (test qoldiqlari) ajralib qoladi — default PostgreSQL.

## 10. 2026-10-07 — Render.com deploy tayyorligi

**Maqsad:** umumiy "Render'ga Django deploy" qo'llanmasini shu loyihaga
moslash (monorepo: `backend/` + `frontend/`, nginx/Docker emas).

**O'zgarishlar:**

| Fayl | O'zgarish |
| --- | --- |
| `backend/requirements.txt` | `gunicorn==23.0.0`, `whitenoise>=6.8,<7`, `dj-database-url>=2.1,<3` qo'shildi (bitta manba — Dockerfile va CI endi alohida o'rnatmaydi) |
| `backend/config/settings.py` | `DATABASE_URL` (dj-database-url, ssl faqat postgres/mysql sxemalarida), WhiteNoise middleware + `STORAGES` (Django 5.1'dan beri `STATICFILES_STORAGE` o'rniga), ALLOWED_HOSTS default'iga `.onrender.com`, CSRF default'iga `https://*.onrender.com` |
| `backend/build.sh` | **yangi** — `python -m pip install` → `collectstatic` → `migrate` → 4 ta idempotent seed |
| `backend/Dockerfile` | alohida `gunicorn` install olib tashlandi (endi requirements.txt da) |
| `.github/workflows/verify.yml` | ortiqcha `pip install gunicorn` olib tashlandi |
| `.gitignore` | `/backend/db-backups/` qo'shildi (PG dump GitHubga push xavfi) |
| `README.md` | "Render.com deploy" bo'limi: baza, Web Service parametrlari, env jadvali, superuser, frontend servisi, cheklovlar |
| `.env.example` | `DATABASE_URL` haqida izoh |

**Qarorlar:**

- **Root Directory = `backend`** — Render shu papkadan build/start bajaradi,
  shuning uchun start command `config.wsgi:application` (loyiha nomi emas).
- **Build Command = `bash build.sh`**, `./build.sh` emas: git Windows'da
  bajarish huquqini yozmaydi, `bash` esa har doim ishlaydi.
- **`STATICFILES_STORAGE` ishlatilmadi** — Django 6.1'da olib tashlangan,
  `STORAGES` ishlatildi.
- **SSL default engine'ga bog'landi** — dastlab `ssl_require=not DEBUG`
  yozilganda SQLite `DATABASE_URL` `sslmode` ni rad etib build/simulyatsiya
  edi; sxema tekshiruvi qo'shildi.
- **Seed'lar build.sh ichida** — README'dagi "CI/CD avtomatik seed qiladi"
  qoidasi Render uchun ham saqlandi (idempotent).
- **CORS kerak emas** — frontend `BACKEND_URL` orqali `/api` ni server
  tomonidan proxy qiladi, ya'ni bir xil origin; CSRF uchun esa wildcard
  `https://*.onrender.com` defaultga qo'shildi.
- **`SECRET_KEY`/`DEBUG` kalitlari loyihada `DJANGO_SECRET_KEY`/`DJANGO_DEBUG`**
  — umumiy qo'llanmadagi nomlar bilan adashtirmaslik uchun README'da aytilgan.
- **media (avatar) disk'i** vaqtinchalik — hujjatda cheklov sifatida yozildi,
  tashqi saqlash qo'shilmadi (kredensial yo'q).

**Tekshiruvlar:**

| Tekshiruv | Natija |
| --- | --- |
| `manage.py check` (SQLite) | 0 muammo |
| `manage.py check` (DATABASE_URL=postgres, DJANGO_DEBUG=False) | 0 muammo; `sslmode=require`, `.onrender.com`, wildcard CSRF tasdiqlandi |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py collectstatic --no-input --clear` | 157 fayl, 453 post-processed (manifest) |
| Whitenoise orqali statik | `/static/admin/css/base.css` va DRF CSS → **200** |
| `manage.py test --noinput` | **Ran 279 tests ... OK** |
| `bash -n build.sh` | sintaksis toza, LF line ending |
| build simulyatsiyasi (yangi `DATABASE_URL=sqlite://...`) | migrate + 4 seed muvaffaqiyatli |
| Linux/CP314 wheel mavjudligi | `psycopg-binary`, `Pillow` manylinux cp314 wheel'lari topildi |
