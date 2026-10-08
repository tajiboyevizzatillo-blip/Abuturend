# ANALIZ — Abiturend (DTM / Abituriyent platformasi)

## 0-BOSQICH: Loyihani tushunish

- **Maqsad:** O'zbekiston abituriyentlari uchun DTM imtihonlariga tayyorgarlik platformasi — mashq sessiyalari, sinov imtihonlari (umumiy imtihon bilan), sertifikatlar, xatolar daftari, statistika, reyting, premium obuna va to'lovlar.
- **Kimlar foydalanadi:** o'quvchilar (mashq/imtihon/natija), o'qituvchilar (savol banki CRUD), administrator (Django admin), tashqi integratsiyalar (MCP API, Telegram bot).
- **Texnologiyalar:** Next.js 16 (App Router, Turbopack) + React 19 + TypeScript + next-intl (uz/ru/en) — `frontend/`; Django 6 + DRF + session-auth — `backend/` (apps: accounts, catalog, core, questions, practice, premium, payments, gamification, universities, mcpbridge, telegrambot, onboarding).
- **Baza:** PostgreSQL 17 (prod/docker), testda SQLite (`DJANGO_USE_SQLITE=1`).
- **Ishga tushirish:** `docker compose up` (nginx → frontend:3000, backend gunicorn) yoki lokal: `manage.py runserver` + `npm run dev`; deploy — GitHub Actions → VPS (flock bilan seriyalashgan).
- **Holat (2026-10, audit dan keyin):** backend test 272/272, frontend lint+typecheck+build 63 sahifa, i18n 523/523/523 teng (mojibake va kirill aralashuvi tekshiruvi `core.tests.TextEncodingTests` bilan qo'riqlanadi). Muhim funksiyalar: parol tiklash, Payme/Click, umumiy imtihon + sertifikat (`/verify/[serial]`), xatolar daftari (`/mistakes`), onboarding wizard + 7 kunlik reja (`/onboarding`), zaif mavzu radar (`/weak-skills`), sessiyani tashlab ketish (`POST /api/sessions/{id}/abandon/`).

## 1-BOSQICH: Tahlil (topilgan muammolar)

### Xatolar / cheklovlar (tuzatiladigan)
1. **Natijalarni qayta ko'rib bo'lmaydi** — `/sessions/{id}/report/` faqat yakunlagan onda ishlatiladi; tarix va dashboard satrlari bosilmaydi, tahlil yo'qoladi.
2. **Reyting faqat landing top-10** — `LeaderboardView` `[:10]` ga qattiq bog'langan, to'liq reyting sahifasi yo'q.
3. **To'liq tarix yo'q** — dashboardda oxirgi 5 ta sessiya, mock-exams tarixi faqat exam rejimida; mashq sessiyalarini ko'rish va fan bo'yicha filtr imkoniyati yo'q.
4. **Eksport yo'q** — o'z natijalarini CSV/xujjat ko'rinishida yuklab olib bo'lmaydi.
5. **`ReportList` takrorlanadi** — exam-player ichida yashiringan, boshqa joyda (natija sahifasi) ishlatib bo'lmaydi.
6. **Mobil menyu** — header navigatsiyasi `md:flex` bilan yashirin; telefonda menyu boshqaruvi tekshiriladi (stage 4).
7. **`fetchSessionList` sahifalash** — `page_size` yuborilmasa server 20 tagacha qaytaradi (tarix to'ldirilganda jim kesilishi mumkin).

### Xavfsizlik (2026-10 audit'da tekshirildi va tuzatildi)
Audit oldingi xulosasi ("holati yaxshi") to'liq emas edi — quyidagi kamchiliklar
topildi va bartaraf etildi:

- `.env` va barcha `.env.*` variantlari gitignore'da (`.env.example` bundan
  mustasno), `*.pem`/`*.key`/`*.crt` ham ✅
- **SECRET_KEY**: ilgari faqat bitta o'rinbosar qiymat rad etilardi, ammo
  compose boshqasini (`change-me-in-production`) qo'yardi — ya'ni himoya
  ishlashdan to'xtagan edi. Endi barcha o'rinbosar qiymatlar deny-listda,
  uzunlik tekshiriladi, va compose `${VAR:?}` bilan butunlay ishga tushmaydi ✅
- **Rate limiting**: `NUM_PROXIES` yo'q edi, shuning uchun DRF `REMOTE_ADDR`
  (nginx IP) dan foydalanardi — barcha foydalanuvchilar bitta chelada
  (register: butun sayt uchun soatiga 5 marta). Endi `NUM_PROXIES=1` +
  nginx `real_ip` ✅
- **Premium darajasi**: `is_premium()` "biror Subscription qatori bor" degan
  ma'noda edi, `free-trial` esa qator yaratadi — ya'ni to'lov qilmagan
  foydalanuvchi ham PRO imtiyozlarini olardi. Endi daraja (`tier`) tekshiriladi ✅
- **O'qituvchi huquqlari**: `CanManageQuestions` faqat rol darajasida edi;
  boshqa o'qituvchining savolini tahrirlash/o'chirish erkin edi. Endi
  `has_object_permission` qo'shildi ✅
- **Ishonch bayroqlari**: `is_verified`/`is_official` API orqali yozilardi —
  o'qituvchi o'zini "rasmiy" deb belgilay olardi. Endi read-only ✅
- **Open redirect**: `return_path` orqali `/\/evil.com` o'tib ketardi
  (`\` brauzerda `/` ga aylanadi). Endi allow-list ✅
- **Telegram webhook**: kalit bo'ganda `DEBUG` rozi bo'lsa webhook **ochiq**
  qabul qilardi. Endi shartsiz fail-closed ✅
- **CSP**: nginx'dagi `script-src 'self'` Next.js inline skriptlarini bloklagan —
  sahifa chizilardi lekin gidratatsiya ishlamasdi. Endi `unsafe-inline` ✅
- Sessiya/CSRF cookie'lari `DEBUG=False` da `Secure` (ilgari `False`)
- DB ulanishi `CONN_MAX_AGE=60` + health check bilan
- Barcha konteynerlar non-root, healthcheck va log rotation bilan

### Samaradorlik / tozalik
- Leaderboard annotatsiyasi barcha user'lar ustida — endi `cache_page` (60s) va
  `public_read` throttle bilan (u ommaviy, anonim va agregatli eng qimmatli so'rov)
- `/api/stats/summary/` har bir so'rovda barcha sessiyalarni Python'ga olib kelib
  yig'ardi, haftalik faollikni esa har bir javobni tsiklda hisoblar edi; endi
  hammasi SQL agregatida
- Exam-player'ni results sahifasiga import qilsak butun player bundle tushadi → ReportList ajratiladi

### Yetishmayotgan mahsulot qismlari
- Natija tahlili sahifasi, to'liq reyting, to'liq tarix + filtr, CSV eksport, sertifikatni ulashish (copy-link), natija sahifasidan sertifikat CTA.

## 2-BOSQICH: Onboarding wizard (bajarildi)

**Muammo:** yangi o'quvchi ro'yxatdan o'tgach hech narsa yo'q edi — dashboard bo'sh ko'rinardi, o'quvchi nimadan boshlashini bilmasdi, kunlik maqsad yo'q edi. Bu retention uchun eng katta yo'qotish.

**Yechim:** `backend/onboarding` app + `/[locale]/onboarding` sahifasi.

| Qatlam | Nima qilindi |
| ------ | ------------- |
| Model | `OnboardingProfile` (user OneToOne, direction FK null, subjects M2M, exam_date, daily_minutes, level, completed, skipped) + `OnboardingPlan` (profile FK, start_date, `days` JSON, `weak_subject_ids` JSON) |
| API | `GET /api/onboarding/`, `POST /api/onboarding/` (javob + reja, 201), `GET /api/onboarding/plan/` (yo'q bo'lsa 404), `POST /api/onboarding/skip/` |
| Reja qoidasi | `min(7, imtihonga qolgan kun)` kun; kunlik savol = `daqiqa / 2 × daraja (0.8/1.0/1.2)`; daqiqa fanlar orasida og'irlik bilan bo'linadi, xatolar daftaridagi zaif fan **1.6×**; fanlar round-robin, topic aylanadi, ≤3 band/kun va ≤30 savol/band |
| Validatsiya | sanа kelajakda (bugun ham rad), kamida 1 fan, takrorlanish rad, kunlik vaqt 15–480, level choice, faol bo'lmagan fan/direction rad |
| Xavfsizlik | barcha endpoint `IsAuthenticated`, hech qaerda id bo'yicha qidirish yo'q — faqat `request.user`; `select_for_update` bilan qayta yuborishda poyga olib kelmaydi; eski reja `plans.all().delete()` bilan almashtiriladi |
| Redirect | `AuthProvider` `GET /onboarding/` dan `needs_onboarding` oladi; shaxsiy sahifalarda `/onboarding` ga `router.replace` (login/register'da ham aniq). `/profile`, barcha ochiq sahifalar exempt — mehmon katalogdan chiqib keta olmaydi |
| Frontend | 3 qadam + progress bar, qidiruvli yo'nalish ro'yxati, fan chiplari, sana tanlash (min = bugun), daqiqa preset + number input, daraja kartalari; natija ekrani (shaxsiy tavsiya + 7 kunlik kartalar); `lib/onboarding.ts` |
| Dashboard | `TodayPlanCard` — bugungi band, progress bar (bugungi javoblar `weekly_activity` dan), bandga bosilganda `/subjects/{slug}/practice?topic=&count=` |
| Qo'shimcha | `/practice?topic=&count=` qo'llab-quvvatlanadi (ixtiyoriy, eski linklar o'zgarmadi); `/profile` da "Rejani qayta tuzish"; Telegram: bot sozlanganda admin xabari (sozlanmasa no-op) |
| Test | 26 ta test (24 onboarding + 2 telegram): permission (authsiz 403, boshqa profil ko'rinmaydi), validatsiya (sanа, fanlar, daqiqa, level, nofaol fan), reja (uzunlik, taqsimot, qayta yuborish eskirgan rejaning o'rniga), zaif fan ustuvorligi + mastered xato hisobga olinmasligi + boshqa foydalanuvchi xatosi sizib chiqmasligi |

**Tanlangan qarorlar (tushuntirilgan):**
- **AI yo'q** — reja qoidaviy, tushunarli va xatosiz; kiritilgan ma'lumot yetarli emas (kutilgan ball/score yo'q).
- **Yo'nalish ixtiyoriy** — majburlash o'quvchini yo'nalish tanlashga majbur qilardi; fanlar yetarli signal.
- **Ochiq sahifalar exempt** — "majburlama" faqat shaxsiy sahifalarda; aks holda mehmon marketinga chiqib keta olmasdi.
- **Faqat o'quvchilar** — o'qituvchi/admin uchun DTM rejasiga ma'no yo'q.
- **`/profile` exempt** — o'tkazib yuborish va qayta tuzish aynan shu sahifadan boshqariladi.
- **Bajarilish** — kundalik kvota bo'yicha (fan+topic o'rtacha progress). Har bir band alohida hisoblanishi uchun alohida ledger kerak, bu onboarding MVP uchun ortiqcha.

**Keyingi bosqich uchun g'oyalar:** bashorat (yo'nalish + ball → universitet), streak + daily goal, weak-skill radar, 1v1 duel, onboardingdan bepul tarifga CTA (reja premium'da ko'proq savol beradi).

## 3-BOSQICH: Zaif mavzular radari (Weak-skill radar)

**Muammo:** o'quvchi ko'p mashq qilsa ham "qaysi mavzuda kuchsizman?" savoliga
javob topolmardi. `/stats/summary/` faqat eng ko'p xato qilingan 5 mavzuni
(wrong count bo'yicha, foizsiz) ko'rsatardi, bu mavzular ko'p urish qilgan
foydalanuvchilarda "eng zaif" degani bilan mos kelmasdi.

**Yechim:** `backend/practice/weak_skills.py` + `/[locale]/weak-skills` sahifasi.

| Qatlam | Nima qilindi |
| ------ | ------------ |
| Ma'lumot | Alohida `TopicStat` jadvali **yo'q** — `PracticeAnswer` dan agregat bilan (`COUNT`/`SUM(is_correct)`) so'rov paytida hisoblanadi. Sabab: (a) "yangi javob kelganda yangilansin" talabi o'z-o'zidan bajariladi (kashf o'rnidan yangilanish xatosi yo'q), (b) qo'shimcha yozuv/rebuild mantiqi kerak emas. Mavzular ro'yxati faqat o'quvchining **javob bergan** savollaridan chiqadi |
| Mavzu | `Question.topic` allaqachon nullable FK edi — o'zgartirish shart emas. Mavzusiz savollar o'ylab topilgan mavzuga emas, virtual **"Boshqa"** guruhiga (`is_other=true`) tushadi |
| Migratsiya | `questions_0002_question_questions_topic_active` — `Meta.indexes = [(topic, is_active)]`. Zaif-mavzu mashqi `topic_id IN (...) AND is_active AND status` bo'yicha filtrlaydi; FK ga Django o'z indeksini qo'yadi, lekin indeksning **birinchi** ustuni `topic` bo'lganda filtr to'g'ridan-to'g'ri indeksdan foydalanadi |
| Ishonchlilik | `WEAK_SKILL_MIN_ANSWERS` (default 5) dan kam javobli mavzu `enough_data=false` -> zaif **hisoblanmaydi**. Sabab: bitta javobdan "0%" chiqib, foydalanuvchini chalg'itardi |
| Zaif chegarasi | `WEAK_SKILL_THRESHOLD` (default 60): aniqlik < chegara. Chegara bilan **teng** bo'lgan foiz zaif emas |
| Sozlamalar | `WEAK_SKILL_MIN_ANSWERS`, `WEAK_SKILL_THRESHOLD`, `WEAK_SKILL_TOPIC_LIMIT` (5), `WEAK_SKILL_FREE_TOPICS` (3), `WEAK_SKILL_PRACTICE_COUNT` (20) — hammasi `config/settings.py` da env'dan |
| API | `GET /api/weak-skills/` (fanlar radari + zaif mavzular + qoidalar), `GET /api/weak-skills/<fan>/` (fan ichidagi mavzular; PRO uchun 14 kunlik tarix), `POST /api/weak-skills/practice/` (zaif mavzulardan sessiya yaratish) |
| Xavfsizlik | Barcha endpoint `IsAuthenticated`; so'rovda foydalanuvchi id **qabul qilinmaydi** — doim `request.user`. Boshqa hisob ma'lumoti yo'li yo'q. Kunlik bepul sessiya limiti radar yo'lida ham qo'llaniladi (limitni chetlab o'tib bo'lmaydi) |
| Tarif | Free: umumiy fan radari + eng zaif **3** mavzu + fan ichidagi barcha mavzular ko'rinadi, "Mashq qilish" PRO. PRO: barcha mavzular, `hidden_weak_topics` yashirilgan soni, 14 kunlik tarix, zaif mavzular bo'yicha mashq. Chegara/yashirish serverda (`premium.services.is_premium`), frontend faqat ko'rsatadi |
| Sessiya yaratish | `practice/views.py` dan `create_practice_session()` va `session_payload()` modul darajasiga chiqarildi; `/sessions/` va radar **bir xil** kod yo'lini ishlatadi (ikki nusxa sessiya yaratish, kunlik limitni chetlab o'tish oldi bo'lardi). Javob shakli bir xil -> frontend'da `PracticePlayer` ga `startSession` prop'i qo'shildi |
| Frontend | `/[locale]/weak-skills`: radar chart (SVG, qo'lda yozilgan), fan tanlanganda mavzular gorizontal chiziqli diagrammasi, "Eng zaif mavzular" + "Mashq qilish", PRO CTA (`/premium`), bo'sh holat ("Avval bir nechta mashq bajaring"), yuklanish skeleti + xoto holati, dark mode CSS o'zgaruvchilari orqali |
| Chart kutubxonasi | **Qo'shilmadi.** recharts ~90 kB gzipped bo'lib, bitta poligon uchun butun bundle'ga kiradi. Radar — 30 qatorli geometriya; `components/weak-skills/radar-chart.tsx`. Son/foiz har doim matn ko'rinishida chiqadi (rang yagona ko'rsatkich emas) |
| `/mistakes` | "Mavzular bo'yicha ko'rish" havolasi qo'shildi (daftar = savollar, radar = mavzular) |
| Dashboard | `WeakTopicCard` — eng zaif mavzu + foiz + "Mashq qilish" (PRO da), aks holda `/premium` ga |
| Onboarding | `plan.weak_topic_ids()` radardagi xuddi shu qoidadan foydalanadi (min javob + chegara) -> reja va radar "zaif" degani haqida ziddiyatga tushmaydi; kunlik bandlarda zaif mavzular birinchi aylanadi |
| Telegram | `/weak` (va menyudagi tugma) — `TELEGRAM_LINKED_USER` dagi hisobning eng zaif 3 mavzusi. Sozlanmagan/topilmasa **xato bermaydi**, tushuntirish qaytaradi; webhook har doim 200 |
| i18n | `weakSkills` (26 kalit) + `nav.weakSkills` + `mistakes.toRadar` — uz/ru/en uchta faylga ham qo'shildi |
| Test | 19 ta test (`practice/test_weak_skills.py`): aniqlik hisobi, 5-javob qoidasi (4 javob -> zaif emas), "Boshqa" guruhi, javoblanmagan/qoralama savollar hisobga olinmasligi, chegara konfiguratsiyasi va chegara tengligi, foydalanuvchilararo izolyatsiya, 401/403, fan id hamda slug bilan, 404, free limiti yashirish, tarix faqat PRO da, mashq faqat PRO da (402 + sessiya yaratilmasin) |

## 4-BOSQICH: Production audit (2026-10)

Uchta mustaqil audit (backend xavfsizlik, frontend, infratuzilma) o'tkazildi va
topilgan kamchiliklar tuzatildi. To'liq ro'yxat va qarorlar `worklog.md` da.
Eng muhimlari:

**Xavfsizlik**
- `SECRET_KEY` fail-closed himoyasi faqat bitta o'rinbosar qiymatni rad etardi;
  compose boshqasini qo'yardi → deny-list + uzunlik tekshiruvi + `${VAR:?}`
- `NUM_PROXIES` yo'qligi sabab barcha mijoz bitta rate-limit chelada edi
- `is_premium()` "qator bor" degan ma'noda edi → bepul tarif PRO ochib qo'yardi
- `CanManageQuestions` da obyekt darajasidagi ruxsat yo'q edi
- `is_verified`/`is_official` API orqali yozilardi
- `return_path` da `/\/evil.com` open redirect qilib o'tdi
- Telegram webhook `DEBUG` da **ochiq** qabul qilardi
- nginx CSP Next.js inline skriptlarini bloklagan (sahifa o'lim edi)

**Mashhurlik / to'g'rilik**
- Kunlik limit weak-skills yo'lida atomik emas edi (TOCTOU)
- Imtihon davomiyligi mijoz nazoratida (`duration_minutes=240` mumkin edi)
- Reyting ommaviy, anonim va throttlesiz eng qimmatli so'rov edi
- `stats/summary` barcha sessiyalarni Python'da yig'ardi
- Xatolar daftari tashlab ketilgan sessiyalarni hisobga olardi
- Exam'da allaqachon javoblangan savol qayta yuborilardi
- O'qituvchi panelida savol **yaratib bo'lmasdi** (`formOpen` xato hisoblangan)
- `setRetry(fn)` funksiyani state'ga berardi → Retry tugmasi umuman chiqmasdi

**Infratuzilma**
- `certbot` yo'q edi: yangi o'rnatish ishga tushmasdi, 90 kundan keyin
  sertifikat o'zi o'chardi
- `BACKEND_URL` build ARG sifatida berilmagan edi
- `WEAK_SKILL_*` va `TELEGRAM_LINKED_USER` compose'da yo'qotilgan edi
- Migratsiya ikki marta (`CMD` va CI) parallel ishga tushardi
- CI **hech narsani** tekshirmasdi; endi `verify.yml` bor va deploy unga bog'liq
- Barcha konteynerlar root edi; log rotation va memory limit yo'q edi

**Tanlangan qarorlar (tushuntirilgan):**

- **`TopicStat` jadvali emas.** Prompt "jadval yoki so'rov, qaysi tezroq" dedi.
  Agregat so'rovi `practice_answer` -> `practice_session` indekslari ustida ishlaydi
  (va yangi javob kelgach darhol ko'rinadi), jadval esa har bir javob uchun
  qo'shimcha yozuv + "qachon qayta hisoblash?" savoliga olib kelardi.
- **Mavzu ma'lumoti o'ylab topilmadi.** Savollar mavzusiz bo'lsa "Boshqa"
  guruhiga tushadi; o'qituvchi `Topic` yaratib keyin savollarni bog'lashi mumkin.
- **Free tarifda "mashq" faqat PRO.** Sabab: PRO sotish nuqtasi — bepul foydalanuvchi
  ko'radi, PRO'da shu mavzuni mashq qiladi. Yashirilgan mavzular soni (`hidden_weak_weak_topics`)
  CTA uchun aniq signal beradi.
- **Chart kutubxonasi yo'q** (yuqoraga qarang).
- **`/weak` bot buyrug'i** bitta bog'langan hisobni ko'rsatadi: bot chat-id -> foydalanuvchi
  bog'lanishi mavjud emas, yangisini o'ylab topish bu bosqichdan tashqarida.

**Tekshiruv:** backend `python manage.py test` — 234/234 PASS; frontend
`npm run lint` toza, `npx tsc --noEmit` toza, `npm run build` muvaffaqiyatli
(yangi `/[locale]/weak-skills` route'i qo'shildi).
