"""
Запустите этот скрипт ОДИН РАЗ для каждого бота чтобы создать сессию.
После успешного входа сессия сохранится в папку sessions/ и
при следующем запуске main.py код больше не потребуется.

Использование:
    python create_session.py
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telethon import TelegramClient
from db.database import init_db, get_all_bots, get_bot


async def create_session(bot_cfg: dict):
    base_dir     = os.path.dirname(os.path.abspath(__file__))
    sessions_dir = os.path.join(base_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    session_file = os.path.join(sessions_dir, f"bot_{bot_cfg['id']}")

    # Если старая сессия существует — удаляем, она могла быть на тестовом DC
    old_session = session_file + ".session"
    if os.path.exists(old_session):
        os.remove(old_session)
        print(f"  🗑  Старая сессия удалена, создаём новую...")

    print(f"\n  Подключение к Telegram для бота «{bot_cfg['name']}»...")
    print(f"  Телефон: {bot_cfg['phone']}")

    client = TelegramClient(
        session_file,
        int(bot_cfg["api_id"]),
        bot_cfg["api_hash"],
    )

    try:
        await client.start(phone=bot_cfg["phone"])
        me = await client.get_me()
        print(f"  ✅ Успешно! Вошли как: {me.first_name} (id={me.id})")

        # Явно сохраняем сессию на диск
        await client.disconnect()

        size = os.path.getsize(session_file + ".session")
        print(f"  💾 Файл сессии: {session_file}.session ({size} байт)")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        try:
            await client.disconnect()
        except Exception:
            pass
        return False


def main():
    init_db()
    bots = get_all_bots()

    if not bots:
        print("❌ Боты не найдены в базе данных.")
        print("   Сначала добавьте бота через главное приложение (python main.py),")
        print("   затем запустите этот скрипт.")
        input("\nНажмите Enter для выхода...")
        return

    print("=" * 55)
    print("  Selene — Создание Telegram-сессий для юзерботов")
    print("=" * 55)

    # Поддержка запуска из GUI: python create_session.py --bot-id 1
    bot_id_arg = None
    if "--bot-id" in sys.argv:
        try:
            bot_id_arg = int(sys.argv[sys.argv.index("--bot-id") + 1])
        except (IndexError, ValueError):
            pass

    if bot_id_arg is not None:
        chosen = [b for b in bots if b["id"] == bot_id_arg]
        if not chosen:
            print(f"❌ Бот с id={bot_id_arg} не найден.")
            input("\nНажмите Enter для выхода...")
            return
    elif len(bots) == 1:
        chosen = [bots[0]]
        print(f"\nНайден 1 бот: {bots[0]['emoji']} {bots[0]['name']}")
    else:
        print("\nДоступные боты:")
        for i, b in enumerate(bots, 1):
            has_session = os.path.exists(
                os.path.join(os.path.dirname(__file__), "sessions", f"bot_{b['id']}.session")
            )
            status = "✅" if has_session else "❌ нет сессии"
            print(f"  {i}. {b['emoji']} {b['name']} — {status}")

        print("\nВведите номера ботов через запятую (или Enter для всех): ", end="")
        raw = input().strip()
        if not raw:
            chosen = bots
        else:
            try:
                indices = [int(x.strip()) - 1 for x in raw.split(",")]
                chosen  = [bots[i] for i in indices if 0 <= i < len(bots)]
            except (ValueError, IndexError):
                print("❌ Неверный ввод.")
                input("\nНажмите Enter для выхода...")
                return

    for bot in chosen:
        print(f"\n{'─' * 45}")
        print(f"  Бот: {bot['emoji']} {bot['name']}")
        asyncio.run(create_session(bot))

    print(f"\n{'=' * 55}")
    print("  Готово! Теперь запустите python main.py")
    print("=" * 55)
    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
