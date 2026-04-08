# Включение оплаты TBC (tpay)

Сейчас в проекте **`TBC_ENABLED=false`**: карточные платежи через API банка не используются. Работает сценарий **ручного перевода** (IBAN в боте) и подтверждение оплаты админом в Telegram или через `PATCH /admin/requests/{id}`.

## Когда появятся данные от TBC

1. Получите у TBC Bank: **apikey**, **client_id**, **client_secret** (merchant app), согласуйте **callback URL** (HTTPS) для webhook.
2. В `.env` установите:
   - `TBC_ENABLED=true`
   - `TBC_APIKEY=...`
   - `TBC_CLIENT_ID=...`
   - `TBC_CLIENT_SECRET=...`
   - `TBC_RETURN_URL=https://ваш-домен/...` — куда вернётся пользователь после оплаты в браузере
   - `TBC_CALLBACK_URL=https://ваш-домен/payments/webhook` — тот же URL, что зарегистрирован в TBC (должен указывать на ваш FastAPI)
   - опционально `TBC_WEBHOOK_SECRET` — тогда webhook должен передавать подпись в заголовке `x-tbc-signature` (hex HMAC-SHA256 тела)
3. Перезапустите **API** (и бота). Включится:
   - `POST /payments/create` — создание платежа и ссылки на оплату
   - `POST /payments/webhook` — триггер проверки статуса через TBC API (не доверяем телу webhook)
   - фоновая проверка «pending» платежей каждые ~7 минут
4. В боте после заявки пользователь увидит кнопку **«Оплатить картой (TBC)»** вместо текста с IBAN.

## Проверка

- Документация API: `GET /docs` на вашем сервере.
- Health: `GET /health`.

Если снова нужно отключить TBC (тесты без банка): `TBC_ENABLED=false` и перезапуск.
