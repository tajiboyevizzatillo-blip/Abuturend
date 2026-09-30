# Abiturend — DTM / ABITURIYENT PLATFORM

Abituriyentlar uchun ta'lim, test, imtihon, natija, progress, universitet va yo'nalish
ma'lumotlarini boshqaruvchi zamonaviy platforma.

## Texnologik stack

| Layer     | Texnologiya                          |
| --------- | ------------------------------------ |
| Frontend  | Next.js 16 (App Router, TypeScript)  |
| Backend   | Django 6 + Django REST Framework      |
| Database  | PostgreSQL 17                        |
| Auth      | Session-based cookies (DRF)          |
| i18n      | next-intl (O'zbek / Русский / English)|
| Deploy    | Docker Compose + Nginx               |

## Tuzilma

```text
├── backend/          # Django REST API
│   ├── config/       # settings / urls
│   ├── core/         # tayanch app (health, izoh)
│   ├── premium/      # obuna tariflari + kunlik sessiya limiti
│   ├── gamification/ # XP, daraja va nishonlar (badge)
│   ├── onboarding/    # 3 qadamli wizard + 7 kunlik o'quv reja
│   ├── telegrambot/  # Telegram admin bot (bildirishnomalar + statistika)
│   └── requirements.txt
├── frontend/         # Next.js ilova
│   ├── app/[locale]/ # sahifalar (uz/ru/en)
│   ├── components/   # UI kit va layout
│   ├── i18n/         # routing / request
│   └── messages/     # tarjimalar
├── nginx/nginx.conf  # production reverse-proxy
└── docker-compose.yml
```

## Lokal ishga tushirish

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
# PostgreSQL mavjud bo'lsa: POSTGRES_PASSWORD muhitini o'rnating
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Healthcheck: `GET http://127.0.0.1:8000/api/health/`

Seed data (idempotent, kerak bo'lganda qayta ishga tushiriladi):

```bash
python manage.py seed_catalog       # 13 ta DTM fani
python manage.py seed_universities  # universitetlar va yo'nalishlar
python manage.py seed_premium       # bepul va PRO tariflar
python manage.py seed_badges        # 12 ta yutuq nishoni
```

> `seed_premium` va `seed_badges` **majburiy** — ularsiz `/premium` sahifasi
> bo'sh, nishonlar esa umuman yaratilmaydi. CI/CD deploy avtomatik bajaradi.

### Telegram bot

`.env` da token va chat id ko'rsatilgach ishlaydi:

| Env                        | Tavsif                                  |
| -------------------------- | --------------------------------------- |
| `TELEGRAM_BOT_TOKEN`       | `@BotFather` -> `/newbot` orqali olinadi |
| `TELEGRAM_CHAT_ID`         | Admin chat id (`@userinfobot`)           |
| `TELEGRAM_ALLOWED_CHAT_IDS`| Vergul bilan qo'shimcha chat id'lar      |
| `TELEGRAM_WEBHOOK_SECRET`  | Webhook xavfsizlik kaliti (ixtiyoriy token) |
| `TELEGRAM_WEBHOOK_HOST`    | Domen (masalan `abituriyent.orgtrace.uz`) |

- Yangi foydalanuvchi ro'yxatdan o'tganda **avtomatik xabar**
- O'qituvchi yangi savol qo'shganda **avtomatik xabar** (tekshiruvda)
- `/stats` — kunlik statistika (foydalanuvchilar, savollar, faollik)
- `/trend` — so'nggi 7 kun faolligi
- `/help` — buyruqlar ro'yxati, `/id` — chat ID

Arxitektura: **webhook** asosida — Telegram `/webhooks/telegram/` ga to'g'ridan-to'g'ri
POST yuboradi (polling servisi shart emas). Webhook deploy paytida avtomatik ro'yxatdan
o'tkaziladi:

```bash
cd backend
python manage.py tg_set_webhook --drop          # webhook bekor qilish
python manage.py tg_set_webhook                 # domenni ALLOWED_HOSTS/`TELEGRAM_WEBHOOK_HOST` dan o'qiydi
python manage.py tg_set_webhook --url https://domen/webhooks/telegram/
```

Qo'lda xabar yuborish:

```bash
python manage.py tg_send "Assalomu alaykum!"
python manage.py tg_stats                 # kunlik statistika
python manage.py tg_monitor               # uptime tekshiruvi (nosozlikda xabar)
```

> Har kuni avtomatik statistika uchun: `python manage.py tg_stats` ni cron
> (masalan `0 9 * * *`) ga qo'ying. Monitoring: `*/5 * * * *` da `tg_monitor`.
>
> Lokal sinov uchun polling rejimi hali ham mavjud:
> `python manage.py telegram_poll`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Ochiq: `http://localhost:3000` (avtomatik `/uz` ga yo'naltiriladi).

Production build (`output: "standalone"`):

```bash
npm run build   # next build + static/public ni .next/standalone ichiga ko'chiradi
npm start       # node .next/standalone/server.js
```

> `next start` standalone build bilan mos emas va xato beradi — shuning uchun
> `npm start` to'g'ridan-to'g'ri `server.js` ni ishga tushiradi. Bu Dockerfile
> bilan bir xil bajariladi (`CMD ["node", "server.js"]`).

### 3. Docker (to'liq stack)

```bash
cp .env.example .env   # keyin kerakli qiymatlarni o'zgartiring
docker compose up -d --build
```

`docker compose` `MCP_API_KEY` ni talab qiladi — `.env` da belgilanmagan bo'lsa
stack ishga tushmaydi. Qo'shimchacha, PostgreSQL o'zi `POSTGRES_DB` orqali
yaratiladi; qo'lda o'rnatish uchun `psql -U postgres -f setup_db.sql`.

## Onboarding (3 qadam + 7 kunlik reja)

Yangi o'quvchi ro'yxatdan o'tgach `AuthProvider` bir marta `GET /api/onboarding/`
so'raydi. `needs_onboarding` true bo'lsa, shaxsiy sahifalar (`/dashboard`,
`/subjects`, `/mock-exams`, `/history`, ...) `/[locale]/onboarding` ga
yo'naltiriladi; ochiq sahifalar va `/profile` ochiq qoladi. Wizard'da
**O'tkazib yuborish** (`POST /api/onboarding/skip/`) qaytib kiritmaydi.

| Qadam | Ma'lumot |
| ----- | -------- |
| 1 | Yo'nalish (qidiruv + universitet nomi bo'yicha filter, ixtiyoriy) |
| 2 | Fanlar (kamida bitta) + DTM imtihon sanasi (kelajakda) |
| 3 | Kunlik daqiqa (15–480) + daraja (boshlang'ich / o'rta / yuqori) |

`POST /api/onboarding/` javoblarni saqlaydi va reja quradi (`backend/onboarding/plan.py`):

- reja uzunligi = `min(7, imtihonga qolgan kun)` (sana yo'q bo'lsa 7 kun)
- kunlik savol soni = `daqiqa / 2 × daraja_koeffitsienti` (0.8 / 1.0 / 1.2)
- daqiqa fanlar orasida **og'irliklangan** bo'linadi: xatolar
  daftarida (`/mistakes`) hali yechilmagan xatolar bo'lgan fan 1.6× ulush oladi
- fanlar kunlar bo'ylab round-robin taqsimlanadi, mavzular (topic) aylanadi,
  kuniga ko'pi bilan 3 band va bandga ko'pi bilan 30 savol (API limiti)

Natija ekranida reja kartalari ko'rsatiladi; bandga bosilganda
`/subjects/{slug}/practice?topic=&count=` — aynan rejada yozilgan mavzu va
savol soni ochiladi. Dashboard'da **Bugungi reja** bloki bugungi bandni,
bajarilgan savollar sonini va progress chizig'ini ko'rsatadi. `/profile` dan
`Rejani qayta tuzish` orqali javoblar o'zgartirilib, eski reja almashtiriladi.

Telegram bot sozlanganda (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`) reja
tugagach adminga qisqa xabar boradi; sozlangan bo'lmasa hech narsa yuborilmaydi
va xatoga olib kelmaydi.

## MCP bridge autentifikatsiyasi

MCP HTTP transporti ochiq emas — har bir sorov `Authorization` header talab qiladi:

| Kalit | Ruxsat |
| ----- | ------ |
| `MCP_API_KEY` | Savol qidirish va olish (`include_answers` siz) |
| `MCP_ADMIN_API_KEY` | Hammasi, jumladan `include_answers=true` (javob kaliti) |

```bash
curl -H "Authorization: Bearer $MCP_API_KEY" http://localhost:8001/mcp/
```

- `MCP_API_KEY` bo'lmagan/yoki bo'sh bo'lsa — **barcha** sorovlar 503 bilan
  rad etiladi (fail-closed), MCP xavfsiz tarzda ochiq qolmaydi.
- Noto'g'ri yoki yetishmaydigan token — 401.
- Draft/arxiv/o'chirilgan savollar MCP orqali hech qachon qaytarilmaydi.
- Lokal `stdio` transport ishonchli hisoblanadi va admin darajasida ishlaydi.
- Nginx `/mcp/` location'ida `Authorization` header proxy qilinishi shart.

## Production deploy

Serverda:

```bash
git clone <repo-url> abiturend
cd abiturend
cp .env.example .env
# .env ichida DJANGO_SECRET_KEY, POSTGRES_PASSWORD va domenlarni o'rnating
docker compose up -d --build
```

Nginx `nginx/nginx.conf` reverse-proxy sifatida `frontend:3000` ga yo'naltiradi;
HTTPS Let's Encrypt orqali yoki yuqori qatlamda qo'shiladi.

### Avtomatik deploy (CI/CD)

`.github/workflows/deploy.yml` — `main` branch'ga push bo'lganida avtomatik
deploy'laydi. GitHub repo settings → Secrets and variables → Actions:

| Secret            | Tavsif                                  |
| ----------------- | --------------------------------------- |
| `DEPLOY_HOST`     | Server IP (masalan `189.74.97.158`)     |
| `DEPLOY_USER`     | SSH foydalanuvchi (masalan `root`)      |
| `DEPLOY_PORT`     | SSH port (ixtiyoriy, default `22`)      |
| `DEPLOY_SSH_KEY`  | Serverdagi `~/.ssh/authorized_keys` ga qo'yilgan **private** SSH key |

Oqim avtomatik: pull → build → migrate → collectstatic → webhook o'rnatish.

### Monitoring

`python manage.py tg_monitor` sayt va API uptime'ni tekshiradi; nosozlik
topilsa Telegramga xabar yuboradi. Serverda crontab orqali ishga tushiriladi:

```text
*/5 * * * * root docker exec $(docker ps -qf name=abiturend-backend) python manage.py tg_monitor
```

Kunlik statistika (har kuni 09:00):

```text
0 9 * * * root docker exec $(docker ps -qf name=abiturend-backend) python manage.py tg_stats
```

## Zaif mavzular radari (Weak-skill radar)

Fan va mavzu bo'yicha aniqlikni ko'rsatadi, zaif mavzularni aniqlaydi va ular
bo'yicha bir bosqichda mashq boshlashga imkon beradi (masalan
"Matematika: Funksiyalar — 41%").

| Element | Qanday ishlaydi |
| ------- | ---------------- |
| Sahifa | `/[locale]/weak-skills` (header va mobil menyudan ochiq) |
| Radar | Har bir fan — bitta o'q, qiymati shu fandagi aniqlik (%) |
| Fan kesimi | Fan tanlanganda mavzular bo'yicha gorizontal chiziqli diagramma (foiz + xato soni) |
| Ranglar | 0–40% qizil, 40–70% sariq, 70%+ yashil; foiz matni har doim ko'rinadi |
| Zaiflik qoidasi | Aniqlik `WEAK_SKILL_THRESHOLD` (60%) dan past **va** kamida `WEAK_SKILL_MIN_ANSWERS` (5) ta javob bo'lsa |
| "Boshqa" | Mavzusiz savollar alohida guruhga tushadi (`is_other`) |
| Mashq | "Mashq qilish" -> mavjud mashq tizimi orqali sessiya (jami kunlik limit hisobga olinadi) |
| Tarif | Free: fan radari + eng zaif 3 mavzu; PRO: barcha mavzular, 14 kunlik tarix, zaif mavzular bo'yicha mashq |

API:

| Endpoint | Vazifasi |
| -------- | -------- |
| `GET /api/weak-skills/` | Fanlar radari + eng zaif mavzular + qoidalar |
| `GET /api/weak-skills/<fan>/` | Fan ichidagi mavzular (fan `id` yoki `slug` bo'lishi mumkin); PRO uchun `history` |
| `POST /api/weak-skills/practice/` | Zaif mavzular (`topic_ids`) yoki fan (`subject`) bo'yicha mashq sessiyasi yaratadi (PRO) |

Sozlamalar (ixtiyoriy, `.env`):

```
WEAK_SKILL_MIN_ANSWERS=5      # mavzuni baholash uchun minimal javob
WEAK_SKILL_THRESHOLD=60       # zaif deb hisoblash chegarasi (%)
WEAK_SKILL_TOPIC_LIMIT=5      # "eng zaif" ro'yxat uzunligi
WEAK_SKILL_FREE_TOPICS=3      # bepul tarifda ko'rinadigan zaif mavzular
WEAK_SKILL_PRACTICE_COUNT=20  # zaif mavzulardan olinadigan savollar soni
TELEGRAM_LINKED_USER=         # /weak buyrug'i uchun bog'langan hisob (username yoki id)
```

> Barcha statistika o'quvchining **o'z** javoblaridan agregat bilan hisoblanadi
> (alohida jadval yo'q), shuning uchun yangi javob berilishi bilan darhol
> yangilanadi.

## Status

- PHASE 1 (Foundation): ✅ backend check + migratsiya + health / frontend build + lint + i18n + landing
- PHASE 2 (Authentication): ✅ session-based auth (register/login/logout/me/change-password/csrf), 7 test PASS, protected pages; parolni tiklash: `POST /api/auth/forgot-password/` (token emailga) + `POST /api/auth/reset-password/` (yangi parol, token bir martalik), `/forgot-password` va `/reset-password` sahifalari
- PHASE 3 (Subjects/Topics): ✅ Subject/Topic/Subtopic modellari + API + admin + seed_catalog (13 DTM fani), 7 test PASS, subjects ro'yxati + detail sahifalari
- PHASE 4 (Question bank): ✅ Question/QuestionOption modellari, o'qituvchi CRUD + student browse (javobsiz), difficulty/explanation/source_type, 7 test PASS, teacher/questions panel, 21 umumiy backend test
- PHASE 5 (Practice engine): ✅ `practice` app — practice/exam session, immediate feedback + explanation, finish report; 8 test PASS; PracticePlayer (klaviatura qo'llab-quvvatlash A–D/Enter, streak, score ring)
- PHASE 6 (Analytics): ✅ `GET /api/stats/summary/` — accuracy, streak, weekly activity, subject breakdown, weak topics, recent sessions; `GET /api/sessions/` list; Dashboard real statistika asosida (Eduva uslubi), subjects katalog izlash + premium kartalar, auth split-screen (Figma mos template'laridan qilingan dizayn upgrade)
- PHASE 7 (Universities): ✅ `universities` app — University/Direction modellari + admin + seed_universities + `GET /api/universities/`, `/{slug}/`, `/api/directions/?subject=`; universite katalogi: izlash, fan kesimida filter, ochiluvchi yo'nalishlar (fanlar + davomiylik)
- PHASE 8 (Mock exam): ✅ Sinov imtihoni oqimi — fan/count/vaqt tanlash, taymer (avtomatik yakunlanadi), bepul navigatsiya (`/sessions/{id}/questions/` javob yashirilgan), yakunlanishda score ring + har bir savol bo'yicha tahlil, natijalar tarixi (`/sessions/` exam filter)
- PHASE 8b (Umumiy imtihon + sertifikat): ✅ `subject=null` unified exam — savollar barcha fanlardan round-robin tanlanadi; yakunlangach `POST /api/certificates/` (uslub tanlanadi: `international` — CEFR-uslub toifa A1..C1, `local` — 60%+ muvaffaqiyatli), server `ABT-YYYY-XXXXXX` seriya raqamini chiqaradi; `GET /api/certificates/{serial}/` ochiq tekshiruv (authsiz); `/mock-exams` da "Umumiy imtihon" kartasi, natijada sertifikat tugmalari, `/verify/[serial]` (chop etiladigan hujjat) + `/certificates` (shaxsiy ro'yxat, profile'dan kirish)
- PHASE 8c (Xatolar daftari): ✅ `GET /api/stats/mistakes/` — xato qilingan savollar (wrong count, `is_mastered` keyin to'g'ri javob berganda o'zgaradi, unpublished chiqariladi); `POST /api/sessions/` `question_ids` bilan (mashq rejimi, aniq savollar tartibda, nusxalar/hidden rad etiladi); `/mistakes` sahifasi (ro'yxat + "Mashq qilish" → player xato savollar bilan), header'da "Xatolar" navigatsiyasi
- PHASE 9 (MCP): ✅ `mcpbridge` — Streamable HTTP transport `/mcp/`, 26 test PASS, docker `mcp` servisi + nginx proxy. HTTP transport `Authorization: Bearer` bilan himoyalangan (2 ta daraja: o'qish / admin)
- PHASE 10 (Premium): ✅ `premium` app — `SubscriptionPlan`/`Subscription` + `GET /api/premium/plans|subscription/`, `POST /api/premium/subscribe/`, bepul tarif kuniga 3 sessiya, PRO cheksiz. Limit `POST /api/sessions/` da 402 bilan to'siladi va frontenda Paywall ko'rinishida chiqadi; `/premium` sahifasi (tariflar + joriy holat)
- PHASE 11 (Gamification): ✅ `gamification` app — XP, daraja (200 XP/daftar), 12 ta nishon + `seed_badges`; `GET /api/gamification/badges/`, `POST .../badges/check/`. Sessiya yakunlanganda nishonlar avtomatik beriladi (`new_badges` hisobotda) va `/achievements` sahifasida ko'rsatiladi
- PHASE 12 (Payments): ✅ `payments` app — Payme (Merchant API JSON-RPC `/webhooks/payme/`, Basic auth, tiyin) va Click (Shop API `/webhooks/click/`, Prepare/Complete md5 sign) webhook'lari; `POST /api/payments/checkout/` (kassa havolasi, `return_path`da locale + `{id}` placeholder) + `GET /api/payments/{id}/` (holat polling), obuna avtomatik faollashadi/faqatgina to'ldiriladi, bekor qilinsa tugaydi; `/premium` da tarif uchun Payme/Click tanlash, `/premium/payment/[id]` holat sahifasi; webhook'lar fail-closed (kalit bo'sh = 401/-91), 29 test PASS
- Import/export: ✅ `questions/importexport.py` + `manage.py import_questions` / `export_questions` (CSV, `--create-missing`, `--status` filtri), 6 test PASS
- PHASE 13 (Onboarding): ✅ `onboarding` app — `OnboardingProfile` (yo'nalish, fanlar, imtihon sanasi, kunlik daqiqa, daraja, completed/skipped) + `OnboardingPlan` (7 kunlik JSON reja); 3 qadamli wizard `/onboarding` (qidiruv bilan yo'nalish, fanlar + sana, vaqt + daraja), natija ekrani (shaxsiy tavsiya + reja kartalari), `Bugungi reja` bloki dashboard'da, `/profile` da rejani qayta tuzish; auth gate o'quvchi tugallamagan bo'lsa `/onboarding` ga yo'naltiradi (o'tkazib yuborish bor); qoida asosidagi reja (AI emas): kunlik savol soni = vaqt/2 × daraja, imtihonga qolgan kunlar bilan qisqaradi, xatolar daftaridagi zaif fanlar 1.6× ulush oladi
  - API: `GET /api/onboarding/`, `POST /api/onboarding/` (javob + reja), `GET /api/onboarding/plan/`, `POST /api/onboarding/skip/` (faqat o'z profili, `IsAuthenticated`)
  - Validatsiya: imtihon sanasi kelajakda, kamida 1 fan, kunlik vaqt 15–480 daqiqa
  - Reja bandlari to'g'ridan-to'g'ri mashqni ochadi: `/subjects/{slug}/practice?topic=&count=`
  - Telegram: bot sozlanganda adminga qisqa xabar (sozlanmagan bo'lsa jimgina)
- PHASE 14 (Zaif mavzular radari): ✅ `practice/weak_skills.py` — fan va mavzu bo'yicha aniqlik (aggregat, alohida jadvalsiz), kamida 5 javob qoidasi, 60% zaif chegarasi (env bilan sozlanadi); `GET /api/weak-skills/`, `GET /api/weak-skills/<fan>/`, `POST /api/weak-skills/practice/`; `/[locale]/weak-skills` sahifasi (SVG radar, fan kesimi, zaif mavzular + mashq, PRO CTA), `/mistakes` dan havola, dashboard `WeakTopicCard`, Telegram `/weak`; 19 test PASS
- Backend test: **234/234 PASS** (accounts 16, catalog 12, core 4, gamification 6, mcpbridge 26, onboarding 24, payments 29, practice 64, premium 9, questions 22, telegrambot 10, universities 9)
- Frontend: ✅ `npm run lint` toza, `npm run build` muvaffaqiyatli (63 sahifa); uz/ru/en tarjimalar teng, `/premium` + `/premium/payment/[id]` + `/achievements` + `/reset-password` + `/certificates` + `/verify/[serial]` + `/mistakes` + `/weak-skills` + `/history` + `/leaderboard` + `/results/[id]` + `/onboarding` routelari
- Landing: ✅ 3 ta theme-aware SVG illyustratsiya, aurora/grid hero, scroll reveal
- API indeks: ✅ `GET /api/` — barcha endpointlar katalogi (resolve testi bilan himoyalangan); security header'lar (CSP/RP/Permissions-Policy)
