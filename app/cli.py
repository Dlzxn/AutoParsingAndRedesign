"""Служебные команды.

    python -m app.cli migrate                      — применить миграции БД
    python -m app.cli create-admin EMAIL PASSWORD  — создать администратора (или выдать права существующему)
    python -m app.cli import-legacy DIR            — перенести данные старой версии (clips_history.json,
                                                     tarifs.json, platforms.json) и захешировать пароли
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.auth import service as auth_service
from app.config import get_settings
from app.core.security import hash_password, is_password_hash
from app.db.base import dispose_engine, init_engine, session_factory
from app.db.migrate import upgrade_to_head
from app.db.models import ClipHistory, Platform, Tariff, User
from app.db.seed import seed_defaults
from app.media.fetch import platform_for_url

LEGACY_PLATFORM_KEYS = {"yt": "yt", "vk": "vk", "coub": "coub", "reddit": "reddit", "imgur": "imgur", "tumblr": "tumblr"}


async def _init() -> None:
    engine = init_engine(get_settings().resolved_database_url)
    await upgrade_to_head(engine)
    async with session_factory()() as db:
        await seed_defaults(db)


async def cmd_migrate(_: argparse.Namespace) -> None:
    await _init()
    print("Миграции применены")


async def cmd_create_admin(args: argparse.Namespace) -> None:
    await _init()
    async with session_factory()() as db:
        email = auth_service.normalize_identity(args.email)
        user = await db.scalar(select(User).where(User.email == email).order_by(User.id).limit(1))
        if user:
            user.is_admin = True
            await auth_service.set_password(db, user, args.password)
            print(f"Пользователь {email} (id={user.id}) теперь администратор, пароль обновлён")
        else:
            user = await auth_service.create_user(db, email, args.password, is_admin=True)
            print(f"Создан администратор {email} (id={user.id})")


async def cmd_import_legacy(args: argparse.Namespace) -> None:
    await _init()
    root = Path(args.directory)
    async with session_factory()() as db:
        # 1. Пароли открытым текстом -> хеши
        users = (await db.scalars(select(User))).all()
        hashed = 0
        for user in users:
            if user.password and not is_password_hash(user.password):
                user.password = await asyncio.to_thread(hash_password, user.password)
                hashed += 1
        await db.commit()
        print(f"Паролей захешировано: {hashed}")

        # 2. История клипов
        history_file = root / "clips_history.json"
        if history_file.exists():
            data = json.loads(history_file.read_text(encoding="utf-8"))
            user_ids = set((await db.scalars(select(User.id))).all())
            existing = set((await db.execute(select(ClipHistory.user_id, ClipHistory.url))).all())
            added = skipped = 0
            for raw_id, urls in data.items():
                try:
                    user_id = int(raw_id)
                except ValueError:
                    skipped += len(urls)
                    continue
                if user_id not in user_ids:
                    skipped += len(urls)
                    continue
                for url in dict.fromkeys(urls):  # убираем дубли, сохраняя порядок
                    if not isinstance(url, str) or len(url) > 2048 or (user_id, url) in existing:
                        continue
                    db.add(ClipHistory(user_id=user_id, url=url, platform=platform_for_url(url)))
                    existing.add((user_id, url))
                    added += 1
            await db.commit()
            print(f"История клипов: добавлено {added}, пропущено (нет пользователя) {skipped}")

        # 3. Тарифы
        tariffs_file = root / "tarifs.json"
        if tariffs_file.exists():
            data = json.loads(tariffs_file.read_text(encoding="utf-8"))
            for key, values in data.items():
                tariff = await db.get(Tariff, key)
                if tariff is None:
                    continue
                tariff.price = int(values.get("price") or 0)
                tariff.token_in_day = values.get("token_in_day")
                tariff.sale = str(values.get("sale")).lower() == "true"
                tariff.new_price = int(values.get("new_price") or 0)
            await db.commit()
            print("Тарифы перенесены")

        # 4. Статусы платформ
        platforms_file = root / "platforms.json"
        if platforms_file.exists():
            data = json.loads(platforms_file.read_text(encoding="utf-8"))
            for key, values in data.items():
                platform = await db.get(Platform, LEGACY_PLATFORM_KEYS.get(key, key))
                if platform is not None:
                    platform.enabled = values.get("status") == "on"
            await db.commit()
            print("Статусы платформ перенесены")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    p = sub.add_parser("create-admin")
    p.add_argument("email")
    p.add_argument("password")
    p.set_defaults(func=cmd_create_admin)
    p = sub.add_parser("import-legacy")
    p.add_argument("directory", help="каталог с clips_history.json, tarifs.json, platforms.json")
    p.set_defaults(func=cmd_import_legacy)
    args = parser.parse_args(argv)

    async def run() -> None:
        try:
            await args.func(args)
        except auth_service.AuthError as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        finally:
            await dispose_engine()

    asyncio.run(run())


if __name__ == "__main__":
    main()
