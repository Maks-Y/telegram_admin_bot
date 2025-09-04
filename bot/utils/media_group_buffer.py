import asyncio
from collections import defaultdict
from typing import Dict, List, Any

class MediaGroupBuffer:
    """
    Корректная буферизация альбомов (media_group):
    - только ПЕРВОЕ сообщение группы ставит таймер ожидания;
    - остальные сообщения просто накапливаются и ничего не возвращают;
    - спустя окно ожидания возвращается весь пакет одним списком.
    """

    def __init__(self, windup_ms: int = 900):
        self._storage: Dict[str, List[Any]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._pending: set[str] = set()
        self._windup = windup_ms / 1000.0

    async def add_and_collect(self, group_id: str, message):
        # Сохраняем сообщение
        async with self._locks[group_id]:
            self._storage[group_id].append(message)
            is_first = group_id not in self._pending
            if is_first:
                self._pending.add(group_id)

        # Если это НЕ первое сообщение альбома — пока ничего не отдаём
        if not is_first:
            return []

        # Только первое сообщение ждёт добор и возвращает весь пакет
        await asyncio.sleep(self._windup)
        async with self._locks[group_id]:
            pack = self._storage.pop(group_id, [])
            self._pending.discard(group_id)
        return pack
