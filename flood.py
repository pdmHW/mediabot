import time
import asyncio

# ── Flood tracking ──
_msg_times = {}      # uid -> [timestamps]
_cb_times = {}       # uid -> [timestamps]
_temp_banned = {}    # uid -> ban_until timestamp

MSG_LIMIT = 5        # max messages
MSG_WINDOW = 3       # per N seconds
CB_LIMIT = 8         # max callbacks
CB_WINDOW = 3        # per N seconds
TEMP_BAN_DURATION = 600  # 10 minutes in seconds
EXTREME_LIMIT = 15   # messages in window before temp ban


def _clean_old(times, window):
    now = time.time()
    return [t for t in times if now - t < window]


def is_temp_banned(uid):
    ban_until = _temp_banned.get(uid, 0)
    if time.time() < ban_until:
        return True, int(ban_until - time.time())
    return False, 0


def check_message_flood(uid):
    """Returns (is_flood, should_ban)"""
    banned, _ = is_temp_banned(uid)
    if banned:
        return True, False

    now = time.time()
    times = _clean_old(_msg_times.get(uid, []), MSG_WINDOW)
    times.append(now)
    _msg_times[uid] = times

    if len(times) >= EXTREME_LIMIT:
        _temp_banned[uid] = now + TEMP_BAN_DURATION
        return True, True

    if len(times) > MSG_LIMIT:
        return True, False

    return False, False


def check_callback_flood(uid):
    """Returns (is_flood, should_ban)"""
    banned, _ = is_temp_banned(uid)
    if banned:
        return True, False

    now = time.time()
    times = _clean_old(_cb_times.get(uid, []), CB_WINDOW)
    times.append(now)
    _cb_times[uid] = times

    if len(times) >= EXTREME_LIMIT:
        _temp_banned[uid] = now + TEMP_BAN_DURATION
        return True, True

    if len(times) > CB_LIMIT:
        return True, False

    return False, False


def get_ban_remaining(uid):
    ban_until = _temp_banned.get(uid, 0)
    remaining = int(ban_until - time.time())
    return max(0, remaining)
