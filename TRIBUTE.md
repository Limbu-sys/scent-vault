# Tribute — настройка оплаты Scent Vault

## 1. API-ключ (уже есть)

Ключ прописан в `.env` (локально) или в переменных Amvera — **не публикуйте его в git**.

## 2. Создайте товар для оплаты

1. Откройте [@Tribute](https://t.me/tribute) → панель автора
2. Создайте **Custom product** (товар с доставкой) или **Digital product** с произвольной суммой
3. Название: «Оплата заказа Scent Vault»
4. Скопируйте ссылку на товар (формат `https://t.me/tribute/app?startapp=...`)
5. Вставьте в `TRIBUTE_SHOP_URL` (локально `.env`, на Amvera — переменные окружения)

## 3. Webhook (обязательно для авто-статуса «Оплачен»)

1. Панель Tribute → **⋮** → **Settings** → **API Keys**
2. Поле **Webhook URL**:

```
https://ВАШ-ДОМЕН.amvera.io/webhook/tribute
```

3. Сохраните. Tribute шлёт POST с заголовком `trbt-signature` (HMAC-SHA256 тела запроса, ключ = API key).

### Локальная отладка webhook

Используйте [ngrok](https://ngrok.com/) или аналог:

```bash
ngrok http 8782
# Webhook URL: https://xxxx.ngrok-free.app/webhook/tribute
```

## 4. Привязка заказа к оплате

Покупатель при оплате в Tribute **обязательно** указывает в комментарии:

```
#A1B2C3D4
```

(номер заказа из приложения, с решёткой)

Сервер распознаёт события: `new_digital_product`, `new_order`, `donation_paid` и др.

## 5. Проверка

После деплоя:

```bash
curl -X POST https://ваш-домен.amvera.io/webhook/tribute \
  -H "Content-Type: application/json" \
  -H "trbt-signature: ..." \
  -d '{"name":"new_digital_product","payload":{"comment":"#TEST1234"}}'
```

Без валидной подписи ответ `401` — это нормально.

## 6. Чеки (самозанятый)

После оплаты сформируйте чек в приложении **«Мой налог»** на сумму заказа (ФИО покупателя из Telegram / адрес доставки).
