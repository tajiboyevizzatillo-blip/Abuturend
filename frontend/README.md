# Abiturend — frontend

Next.js 16 (App Router) + React 19 + TypeScript, Tailwind CSS v4, next-intl.
Bu backendga (`/api`) so'rov yubuvchi SPA emas, balki o'z server-side render'ini
qiladigan ilova: sahifalar `app/[locale]/` ostida, `next-intl` orqali
uz/ru/en tilida xizmat qiladi.

## Buyruqlar

| Buyruq | Vazifasi |
| ------ | ------- |
| `npm run dev` | Lokal ishlab chiqish serveri (`http://localhost:3000` → `/uz`) |
| `npm run lint` | ESLint (flat config, `eslint-config-next`) |
| `npx tsc --noEmit` | Tur tekshiruvi (`tsconfig.json` da `strict: true`) |
| `npm run build` | Ishlab chiqarish uchun build + `postbuild` da standalone'ga tayyorlash |
| `npm start` | `node .next/standalone/server.js` — **`next start` emas**, chunki `output: "standalone"` |

Backend lokal da ishlayotgan bo'lishi kerak (masalan `docker compose up backend`),
aks holda `/api` so'rovlari `ECONNREFUSED` oladi.

## Muhit o'zgaruvchilari

| O'zgaruvchi | Qayerda | Izoh |
| ----------- | ------- | ----- |
| `NEXT_PUBLIC_API_URL` | `lib/api.ts` | Brauzer ishlatadigan API manzili. Docker'da `/api` (same-origin, nginx yo'naltiradi) |
| `BACKEND_URL` | `next.config.ts` | **Build vaqtida** o'qiladi: rewrite `.next/routes-manifest.json` ichiga yoziladi. Runtime'da almashtirib bo'lmaydi |

## Tuzilma

- `app/[locale]/` — 22 ta sahifa, har biri uchta tilda
- `components/` — `ui/` (qo'lda yozilgan shadcn-uslubidagi primitivlar), `layout/`, `auth/`, `providers/`, va feature bo'yicha papkalar (`practice/`, `exam/`, `dashboard/`, ...)
- `lib/` — `api.ts` (fetch + CSRF + `ApiError`) va har bir soha uchun alohida typed mijoz
- `i18n/` — next-intl sozlamalari; `proxy.ts` — til muvofiqligi middleware'i
- `messages/{uz,ru,en}.json` — tarjimalar (uchalasida ham kalitlar teng)

## Muhim xususiyatlar

- `next.config.ts` da `skipTrailingSlashRedirect: true`: Next aks holda `POST` so'rovi
  uchun 308 qilib, Django'ning `APPEND_SLASH` redirect'ini buzadi.
- Autentifikatsiya — Django session cookie (`credentials: "include"`), token
  brauzerda saqlanmaydi.
- `output: "standalone"` uchun `messages/` va `i18n/` runner stage'ga ko'chiriladi,
  chunki `i18n/request.ts` JSON'ni runtime'da import qiladi.