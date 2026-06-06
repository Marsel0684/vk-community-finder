"""
vk_parser.py — поиск сообществ через официальный VK API.
"""

import logging
import httpx
from dataclasses import dataclass
from config import VK_TOKEN, VK_API_URL, VK_API_VERSION, MIN_MEMBERS

logger = logging.getLogger(__name__)


@dataclass
class VKCommunity:
    id: int
    name: str
    screen_name: str        # короткий адрес типа marketingpro
    members_count: int
    description: str
    is_closed: bool         # закрытое сообщество или нет
    community_type: str     # group / page / event

    def vk_link(self) -> str:
        return f"https://vk.com/{self.screen_name}"

    def members_fmt(self) -> str:
        if self.members_count >= 1_000_000:
            return f"{self.members_count / 1_000_000:.1f}M"
        if self.members_count >= 1_000:
            return f"{self.members_count / 1_000:.1f}K"
        return str(self.members_count)

    def type_label(self) -> str:
        labels = {
            "group": "Группа",
            "page":  "Публичная страница",
            "event": "Мероприятие",
        }
        return labels.get(self.community_type, self.community_type)

    def status_emoji(self) -> str:
        return "🔒" if self.is_closed else "🌐"


def _call_vk(method: str, params: dict) -> dict | None:
    """Вызов VK API метода."""
    url = f"{VK_API_URL}/{method}"
    params["access_token"] = VK_TOKEN
    params["v"] = VK_API_VERSION

    try:
        resp = httpx.get(url, params=params, timeout=15)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            logger.error(f"VK API ошибка: [{err['error_code']}] {err['error_msg']}")
            return None

        return data.get("response")

    except Exception as e:
        logger.error(f"VK API запрос упал: {e}")
        return None


def search_communities(
    query: str,
    max_results: int = 30,
    community_type: str = "0",   # 0=все, 1=группы, 2=страницы, 3=мероприятия
    sort: str = "6",             # 0=по умолчанию, 6=по числу подписчиков
    country_id: int = 0,         # 0=все страны, 1=Россия, 2=Украина и т.д.
    city_id: int = 0,
) -> list[VKCommunity]:
    """
    Поиск сообществ ВКонтакте через groups.search.
    Возвращает список отфильтрованных и отсортированных сообществ.
    """
    all_communities: list[VKCommunity] = []
    batch_size = 1000   # максимум за один запрос по VK API

    # Делаем несколько запросов со смещением для большего охвата
    offsets = [0, 1000, 2000]

    for offset in offsets:
        params = {
            "q": query,
            "type": community_type,
            "sort": sort,
            "count": batch_size,
            "offset": offset,
            "fields": "members_count,description,is_closed",
        }

        if country_id:
            params["country_id"] = country_id
        if city_id:
            params["city_id"] = city_id

        response = _call_vk("groups.search", params)
        if not response:
            break

        items = response.get("items", [])
        if not items:
            break

        for item in items:
            members = item.get("members_count", 0)
            if members < MIN_MEMBERS:
                continue

            # Определяем тип: group / page / event
            ctype_raw = item.get("type", "group")
            if isinstance(ctype_raw, int):
                ctype_map = {1: "group", 2: "page", 3: "event"}
                ctype = ctype_map.get(ctype_raw, "group")
            else:
                ctype = ctype_raw

            # Пропускаем закрытые — реклама в них обычно невозможна
            is_closed = bool(item.get("is_closed", 0))

            desc = item.get("description", "") or ""
            desc = desc.replace("<br>", " ").strip()[:250]

            all_communities.append(VKCommunity(
                id=item["id"],
                name=item.get("name", ""),
                screen_name=item.get("screen_name", f"club{item['id']}"),
                members_count=members,
                description=desc,
                is_closed=is_closed,
                community_type=ctype,
            ))

        logger.info(
            f"[VK] '{query}' offset={offset}: "
            f"получено {len(items)}, подходящих {len(all_communities)}"
        )

        # Если вернули меньше batch_size — страниц больше нет
        if len(items) < batch_size:
            break

    # Сортировка по числу участников
    all_communities.sort(key=lambda x: x.members_count, reverse=True)

    # Убираем дубликаты по id
    seen: set[int] = set()
    unique = []
    for c in all_communities:
        if c.id not in seen:
            seen.add(c.id)
            unique.append(c)

    logger.info(
        f"Итого по '{query}': {len(unique)} сообществ "
        f"(фильтр ≥{MIN_MEMBERS} участников)"
    )
    return unique[:max_results]
