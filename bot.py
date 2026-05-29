import os
import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from googlesearch import search
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

print("=== Загрузка бота ===")
print("Python version:", sys.version)
print("Токен загружен?", bool(os.getenv("BOT_TOKEN")))

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    print("❌ Ошибка: переменная BOT_TOKEN не установлена!")
    sys.exit(1)

SITES = [
    "zanomom.ru",
    "telefon-kod.ru",
    "narodnyy-reyting.ru",
    "otzovik.com",
    "moshennik.net",
    "otzyvru.com",
    "zvonili.com"
]

async def search_site(session, phone: str, site: str):
    query = f'"{phone}" site:{site}'
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, lambda: list(search(query, num_results=1, lang="ru")))
        return (site, results[0] if results else None)
    except Exception as e:
        print(f"Ошибка поиска для {site}: {e}")
        return (site, None)

async def check_kto_zvonil_direct(session, phone: str):
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) >= 10:
        url = f"https://kto-zvonil.ru/number/{digits}/"
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    if soup.find(class_="comment-item") or "отзыв" in text.lower():
                        return ("kto-zvonil.ru (прямая проверка)", url)
        except Exception as e:
            print(f"Ошибка kto-zvonil: {e}")
    return None

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    digits = ''.join(filter(str.isdigit, phone))
    if len(digits) < 10:
        await update.message.reply_text("⚠️ Слишком короткий номер. Введите полный номер с кодом страны.")
        return

    status_msg = await update.message.reply_text(f"🔍 Ищу отзывы о номере {phone}...")
    found = []

    async with aiohttp.ClientSession() as session:
        kto = await check_kto_zvonil_direct(session, phone)
        if kto:
            found.append(kto)
            await status_msg.edit_text(f"✅ kto-zvonil.ru: найдено")
        else:
            await status_msg.edit_text(f"❌ kto-zvonil.ru: ничего не найдено")

        for site in SITES:
            await status_msg.edit_text(f"📡 Проверяю {site}...")
            result = await search_site(session, phone, site)
            if result[1]:
                found.append(result)
                await status_msg.edit_text(f"✅ {site}: найдено")
            else:
                await status_msg.edit_text(f"❌ {site}: ничего не найдено")
            await asyncio.sleep(1)

    if found:
        reply = "📢 **Найдены упоминания:**\n\n"
        for name, url in found:
            reply += f"• **{name}**\n{url}\n\n"
        await status_msg.edit_text(reply)
    else:
        await status_msg.edit_text("✅ На проверенных сайтах ничего не найдено. Возможно, номер чистый.")

def main():
    print("Создаю приложение...")
    app = Application.builder().token(TOKEN).build()
    print("Добавляю обработчик...")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number))
    print("Бот запущен. Жду номер...")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
