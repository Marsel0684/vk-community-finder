"""
handlers.py — команды Telegram-бота.
"""

import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.utils.markdown import hbold, hlink
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from vk_parser import search_communities, VKCommunity
from config import MAX_RESULTS, ALLOWED_USERS, MIN_MEMBERS

router = Router()
logger = logging.getLogger(__name__)


class SearchState(StatesGroup):
    waiting_query = State()


def _check_access(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


# ── Форматирование ────────────────────────────────────────

def _format_community(c: VKCommunity, index: int) -> str:
    lines = [f"{index}. {hbold(c.name)}"]
    lines.append(
        f"{c.status_emoji()} {c.type_label()}  |  "
        f"👥 {c.members_fmt()} участников"
    )
    if c.description:
        desc = c.description[:130]
        if len(c.description) > 130:
            desc += "…"
        lines.append(f"📝 {desc}")
    lines.append(f"🔗 {hlink('Открыть сообщество', c.vk_link())}")
    return "\n".join(lines)


def _format_results(communities: list[VKCommunity], query: str) -> list[str]:
    if not communities:
        return [
            f"😔 По запросу <b>{query}</b> сообществ не найдено.\n\n"
            f"Фильтр: от {MIN_MEMBERS:,} участников · открытые.\n"
            "Попробуй другое ключевое слово."
        ]

    messages = []
    header = (
        f"🔍 ВКонтакте · <b>{query}</b>: {len(communities)} сообществ\n"
        f"Фильтр: от {MIN_MEMBERS:,} участников · сортировка по размеру\n"
        + "─" * 32
    )
    messages.append(header)

    chunk = []
    for i, c in enumerate(communities, 1):
        chunk.append(_format_community(c, i))
        if len(chunk) == 5:
            messages.append("\n\n".join(chunk))
            chunk = []
    if chunk:
        messages.append("\n\n".join(chunk))

    return messages


# ── Клавиатура фильтров ───────────────────────────────────

def _filter_keyboard(query: str) -> InlineKeyboardMarkup:
    """Кнопки для фильтрации по типу сообщества."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Все", callback_data=f"type:0:{query}"),
            InlineKeyboardButton(text="👥 Группы", callback_data=f"type:1:{query}"),
            InlineKeyboardButton(text="📰 Страницы", callback_data=f"type:2:{query}"),
        ]
    ])


# ── Хэндлеры ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    if not _check_access(message.from_user.id):
        return
    await message.answer(
        "👋 <b>VK Community Finder</b>\n"
        "Поиск сообществ ВКонтакте для рекламных размещений\n\n"
        "<b>Как использовать:</b>\n"
        "Напиши ключевое слово или используй /search\n\n"
        "<b>Примеры:</b>\n"
        "/search маркетинг\n"
        "/search фитнес Москва\n"
        "/search таджвид\n"
        "/search мамы дети\n\n"
        f"Показывает до {MAX_RESULTS} сообществ · от {MIN_MEMBERS:,} участников\n"
        "🌐 только открытые · сортировка по размеру"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not _check_access(message.from_user.id):
        return
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "/search [запрос] — поиск сообществ\n"
        "/help — эта справка\n\n"
        "<b>Примеры запросов:</b>\n"
        "• маркетинг\n"
        "• таргетинг реклама\n"
        "• фитнес похудение\n"
        "• мамы дети воспитание\n"
        "• бизнес предпринимательство\n"
        "• кулинария рецепты\n"
        "• ислам таджвид\n\n"
        "После результатов появятся кнопки фильтра:\n"
        "📋 Все · 👥 Группы · 📰 Страницы"
    )


@router.message(Command("search"))
async def cmd_search(message: Message):
    if not _check_access(message.from_user.id):
        return
    query = message.text.removeprefix("/search").strip()
    if not query:
        await message.answer("❓ Укажи запрос. Пример: /search маркетинг")
        return
    await _do_search(message, query)


@router.message(F.text & ~F.text.startswith("/"))
async def msg_search(message: Message):
    if not _check_access(message.from_user.id):
        return
    query = message.text.strip()
    if len(query) < 2:
        return
    await _do_search(message, query)


@router.callback_query(F.data.startswith("type:"))
async def filter_by_type(callback: CallbackQuery):
    """Фильтр по типу сообщества через кнопки."""
    _, ctype, query = callback.data.split(":", 2)
    await callback.answer("Фильтрую...")
    await _do_search(callback.message, query, community_type=ctype)


# ── Логика поиска ─────────────────────────────────────────

async def _do_search(
    message: Message,
    query: str,
    community_type: str = "0",
):
    wait_msg = await message.answer(
        f"🔍 Ищу сообщества ВКонтакте по запросу <b>{query}</b>..."
    )

    try:
        loop = asyncio.get_event_loop()
        communities = await loop.run_in_executor(
            None,
            lambda: search_communities(
                query=query,
                max_results=MAX_RESULTS,
                community_type=community_type,
            )
        )

        await wait_msg.delete()

        # Отправляем результаты
        parts = _format_results(communities, query)
        for i, text in enumerate(parts):
            # К последнему сообщению добавляем кнопки фильтра
            if i == len(parts) - 1 and communities:
                await message.answer(
                    text,
                    disable_web_page_preview=True,
                    reply_markup=_filter_keyboard(query),
                )
            else:
                await message.answer(text, disable_web_page_preview=True)
            await asyncio.sleep(0.3)

    except Exception as e:
        logger.error(f"Ошибка поиска '{query}': {e}")
        await wait_msg.edit_text("❌ Ошибка при поиске. Попробуй снова.")
