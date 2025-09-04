from datetime import datetime, timedelta
import pytz

MOSCOW_TZ = "Europe/Moscow"

def parse_user_dt(s: str, tz: str | None = None) -> datetime:
    """
    Парсит строку даты/времени и возвращает aware datetime в заданном TZ.
    Поддерживаемые форматы:
      1) 'YYYY-MM-DD HH:MM'         -> ISO
      2) 'DD.MM.YYYY HH:MM'         -> RU формат
      3) 'HH:MM'                    -> время сегодня в TZ (если прошло — завтра)
    Если tz не задан, используем Europe/Moscow.
    """
    s = (s or "").strip()
    zone = pytz.timezone(tz or MOSCOW_TZ)
    now = datetime.now(zone)

    # 3) Только время 'HH:MM'
    try:
        t = datetime.strptime(s, "%H:%M").time()
        dt = zone.localize(datetime(now.year, now.month, now.day, t.hour, t.minute))
        if dt <= now:  # если уже прошло — переносим на завтра
            dt = dt + timedelta(days=1)
        return dt
    except ValueError:
        pass

    # 2) RU 'DD.MM.YYYY HH:MM'
    try:
        naive = datetime.strptime(s, "%d.%m.%Y %H:%M")
        return zone.localize(naive)
    except ValueError:
        pass

    # 1) ISO 'YYYY-MM-DD HH:MM'
    naive = datetime.strptime(s, "%Y-%m-%d %H:%M")  # бросит ValueError, если не подходит
    return zone.localize(naive)
