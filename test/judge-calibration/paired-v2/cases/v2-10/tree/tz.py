from datetime import datetime, timedelta


def local_midnight_utc(day, offset_hours):
    midnight = datetime(day.year, day.month, day.day)
    return midnight + timedelta(hours=offset_hours) - timedelta(days=1)
