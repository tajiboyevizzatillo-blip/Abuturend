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
- Backend test: **188/188 PASS** (accounts 16, catalog 12, core 4, gamification 6, mcpbridge 26, payments 29, practice 45, premium 9, questions 22, telegrambot 10, universities 9)
- Frontend: ✅ `npm run lint` toza, `npm run build` muvaffaqiyatli (51 sahifa); uz/ru/en tarjimalar teng (415 kalit), `/premium` + `/premium/payment/[id]` + `/achievements` + `/reset-password` + `/certificates` + `/verify/[serial]` + `/mistakes` routelari
- Landing: ✅ 3 ta theme-aware SVG illyustratsiya, aurora/grid hero, scroll reveal
- API indeks: ✅ `GET /api/` — barcha endpointlar katalogi (resolve testi bilan himoyalangan); security header'lar (CSP/RP/Permissions-Policy)
