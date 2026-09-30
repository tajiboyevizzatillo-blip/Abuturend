# ANALIZ — Abiturend (DTM / Abituriyent platformasi)

## 0-BOSQICH: Loyihani tushunish

- **Maqsad:** O'zbekiston abituriyentlari uchun DTM imtihonlariga tayyorgarlik platformasi — mashq sessiyalari, sinov imtihonlari (umumiy imtihon bilan), sertifikatlar, xatolar daftari, statistika, reyting, premium obuna va to'lovlar.
- **Kimlar foydalanadi:** o'quvchilar (mashq/imtihon/natija), o'qituvchilar (savol banki CRUD), administrator (Django admin), tashqi integratsiyalar (MCP API, Telegram bot).
- **Texnologiyalar:** Next.js 16 (App Router, Turbopack) + React 19 + TypeScript + next-intl (uz/ru/en) — `frontend/`; Django 6 + DRF + session-auth — `backend/` (apps: accounts, catalog, core, questions, practice, premium, payments, gamification, universities, mcpbridge, telegrambot).
- **Baza:** PostgreSQL 17 (prod/docker), testda SQLite (`DJANGO_USE_SQLITE=1`).
- **Ishga tushirish:** `docker compose up` (nginx → frontend:3000, backend gunicorn) yoki lokal: `manage.py runserver` + `npm run dev`; deploy — GitHub Actions → VPS (flock bilan seriyalashgan).
- **Holat (2026-09):** backend test 188/188, frontend lint+build 51 sahifa, i18n 415/415/415 teng. Muhim funksiyalar: parol tiklash, Payme/Click, umumiy imtihon + sertifikat (`/verify/[serial]`), xatolar daftari (`/mistakes`).

## 1-BOSQICH: Tahlil (topilgan muammolar)

### Xatolar / cheklovlar (tuzatiladigan)
1. **Natijalarni qayta ko'rib bo'lmaydi** — `/sessions/{id}/report/` faqat yakunlagan onda ishlatiladi; tarix va dashboard satrlari bosilmaydi, tahlil yo'qoladi.
2. **Reyting faqat landing top-10** — `LeaderboardView` `[:10]` ga qattiq bog'langan, to'liq reyting sahifasi yo'q.
3. **To'liq tarix yo'q** — dashboardda oxirgi 5 ta sessiya, mock-exams tarixi faqat exam rejimida; mashq sessiyalarini ko'rish va fan bo'yicha filtr imkoniyati yo'q.
4. **Eksport yo'q** — o'z natijalarini CSV/xujjat ko'rinishida yuklab olib bo'lmaydi.
5. **`ReportList` takrorlanadi** — exam-player ichida yashiringan, boshqa joyda (natija sahifasi) ishlatib bo'lmaydi.
6. **Mobil menyu** — header navigatsiyasi `md:flex` bilan yashirin; telefonda menyu boshqaruvi tekshiriladi (stage 4).
7. **`fetchSessionList` sahifalash** — `page_size` yuborilmasa server 20 tagacha qaytaradi (tarix to'ldirilganda jim kesilishi mumkin).

### Xavfsizlik (holati yaxshi — tekshirildi)
- `.env` gitignore'da, faqat `.env.example` (kalitlar bo'sh) track qilinadi ✅
- Throttling: auth 20/min, register 5/hour, password 10/hour, answers 120/min, checkout 20/min ✅
- DEBUG real server jarayonlarda o'chirilgan, SECRET_KEY fail-closed ✅
- Session-auth: boshqaning sessiyasi/hisoboti ko'rinmaydi (queryset filtri), sertifikat ochiq tekshiruvi faqat seriya bo'yicha ✅
- Payme/Click webhook'lari fail-closed (kalit bo'sh = 401) ✅
- Kodda maxfiy kalit/`print`/`console.log`/TODO topilmadi ✅

### Samaradorlik / tozalik
- Leaderboard annotatsiyasi barcha user'lar ustida (baza o'sganda `[:10]` bilan cheklangan — limit parametri bilan saqlanadi)
- Exam-player'ni results sahifasiga import qilsak butun player bundle tushadi → ReportList ajratiladi

### Yetishmayotgan mahsulot qismlari
- Natija tahlili sahifasi, to'liq reyting, to'liq tarix + filtr, CSV eksport, sertifikatni ulashish (copy-link), natija sahifasidan sertifikat CTA.
