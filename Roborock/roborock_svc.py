#!/opt/roborock/venv/bin/python
"""roborock_svc — мост Roborock → 3D-дашборд (HTTP :8590) и Sprut.hub (MQTT).

Работает от системного пользователя roborock, ключ входа берётся из
/opt/roborock/.roborock (создан командой `roborock login`). Пароль не хранится.

Настройки: /opt/roborock/roborock_svc.conf (INI). Переменные окружения RR_*
имеют приоритет над файлом — systemd-юнит работает как раньше.
Логи: stdout (journald) + /opt/roborock/roborock_svc.log.
Журнал событий «что, куда и почему поехало»: /opt/roborock/events.log,
HTTP GET /events, retained-топик <base>/event.
"""
import asyncio, configparser, json, logging, logging.handlers, os, signal, time
from collections import deque

from aiohttp import web
import aiomqtt
from roborock.cli import RoborockContext

VERSION = "1.2.1"   # HTTP API: GET/POST /conf, POST /restart

CONF_PATH = os.environ.get("RR_CONF", "/opt/roborock/roborock_svc.conf")

DEFAULTS = {
    "roborock": {"duid": "ВАШ_DUID", "http_port": "8590"},   # duid — узнать: `roborock login`
    "mqtt": {"host": "192.168.1.10", "port": "1883", "topic": "roborock/saros10r"},   # брокер Спрут.Хаб
    "poll": {"status_moving_s": "5", "map_moving_s": "1", "map_idle_s": "600"},
    "start": {"settle_s": "0.5", "select_ttl_s": "120"},
    "log": {"dir": "/opt/roborock", "max_mb": "2", "backups": "3", "events_max": "200"},
}
ENV = {"roborock.duid": "RR_DUID", "roborock.http_port": "RR_HTTP_PORT",
       "mqtt.host": "RR_MQTT_HOST", "mqtt.port": "RR_MQTT_PORT", "mqtt.topic": "RR_TOPIC"}

def load_config():
    """INI-файл + дефолты; переменные окружения RR_* — поверх всего."""
    cp = configparser.ConfigParser()
    cp.read(CONF_PATH)
    cfg = {}
    for sec, opts in DEFAULTS.items():
        for k, d in opts.items():
            key = f"{sec}.{k}"
            v = os.environ.get(ENV[key]) if key in ENV else None
            if v is None and cp.has_option(sec, k):
                v = cp.get(sec, k)
            cfg[key] = v if v is not None else d
    cfg["roborock.http_port"] = int(cfg["roborock.http_port"])
    cfg["mqtt.port"] = int(cfg["mqtt.port"])
    for k in ("poll.status_moving_s", "poll.map_moving_s", "poll.map_idle_s",
              "start.settle_s", "start.select_ttl_s"):
        cfg[k] = float(cfg[k])
    for k in ("log.max_mb", "log.backups", "log.events_max"):
        cfg[k] = int(cfg[k])
    return cfg

CFG = load_config()
DUID = CFG["roborock.duid"]
HTTP_PORT = CFG["roborock.http_port"]
MQTT_HOST = CFG["mqtt.host"]
MQTT_PORT = CFG["mqtt.port"]
BASE = CFG["mqtt.topic"]
PATH_MAX = 4000
LOG_FILE = os.path.join(CFG["log.dir"], "roborock_svc.log")
EVENTS_FILE = os.path.join(CFG["log.dir"], "events.log")

log = logging.getLogger("roborock_svc")
ev_log = logging.getLogger("roborock_svc.events")   # журнал событий в events.log

STATE_RU = {
    1: "Запуск", 2: "Отключён от зарядки", 3: "Ожидание", 5: "Уборка", 6: "Возвращается на базу",
    7: "Ручное управление", 8: "Заряжается", 9: "Ошибка зарядки", 10: "Пауза", 11: "Точечная уборка",
    12: "Ошибка", 13: "Выключается", 14: "Обновление", 15: "Паркуется", 16: "Едет в точку",
    17: "Уборка зоны", 18: "Уборка комнат", 22: "Очистка контейнера", 23: "Мойка тряпок",
    26: "Едет мыть тряпки", 100: "Заряжен",
}
CLEANING = {5, 7, 11, 16, 17, 18, 26}
MOVING = CLEANING | {6, 15}
BUSY = MOVING | {10, 22, 23}
CUSTOM_MOTOR = [{"fan_power": 106, "water_box_mode": 204, "mop_mode": 302}]  # «по настройкам комнат»
JOB = {"task": None, "text": ""}

EVENTS = deque(maxlen=CFG["log.events_max"])   # журнал событий: что, куда и почему поехало

def event(text, source=""):
    """Событие в журнал: память (HTTP /events) + events.log + retained-топик <base>/event."""
    e = {"ts": time.time(), "time": time.strftime("%H:%M:%S"), "text": text, "source": source}
    EVENTS.append(e)
    ev_log.info("%s%s | %s", e["time"], (" (" + source + ")") if source else "", text)
    S["event"] = e["time"] + " " + text + ((" (" + source + ")") if source else "")
    EV.set()

S = {"online": False, "ts": 0, "status": {}, "state": None, "text": "", "cleaning": False,
     "pos": None, "charger": None, "path": [], "room": "", "rooms": {}, "error": None, "boxes": {},
     "event": ""}
# --- Sprut.hub C_VacuumCleaner -------------------------------------------------
# C_CurrentOperationalState: 0 STOPPED 1 RUNNING 2 PAUSED 3 ERROR 64 SEEKING_CHARGER
# 65 CHARGING 66 DOCKED 67 EMPTYING_DUST_BIN 68 CLEANING_MOP 69 FILLING_WATER_TANK 70 UPDATING_MAPS
SH_STATE = {1: 1, 2: 0, 3: 0, 5: 1, 6: 64, 7: 1, 8: 65, 9: 3, 10: 2, 11: 1, 12: 3, 13: 0, 14: 0,
            15: 64, 16: 1, 17: 1, 18: 1, 22: 67, 23: 68, 26: 68, 100: 66}
# ошибки робота Roborock → C_OperationalError (64 нет базы, 65 застрял, 66 нет контейнера,
# 67 контейнер полон, 68 нет воды, 69 нет бака, 72 низкий заряд, 73 не доехать до зоны,
# 74 грязный бак полон, 75 нет грязного бака, 76 колёса, 77 щётки, 78 датчики)
SH_ERR = {1: 78, 2: 65, 3: 65, 4: 78, 5: 77, 6: 77, 7: 76, 8: 65, 9: 66, 12: 72, 13: 64, 15: 78,
          17: 77, 21: 78, 22: 78, 23: 64, 24: 73, 26: 78, 29: 71}
SH_DOCK_ERR = {34: 2, 38: 68, 39: 74, 42: 77, 44: 75, 46: 66, 53: 74}
SH_FAN = {105: 0, 101: 1, 102: 2, 103: 3, 104: 4, 108: 5}
SH_FAN_W = {0: 105, 1: 101, 2: 102, 3: 103, 4: 104, 5: 108}
SH = {"selected": [], "selected_ts": 0.0, "fan": None, "water": None, "mode": None}   # выбор из Sprut.hub до старта

# --- атомарный старт -----------------------------------------------------------
# RUNNING приходит в одном топике, selected_areas/fan/water/mode — в других:
# порядка между топиками MQTT не гарантирует, поэтому стартуем не сразу,
# а через короткое окно, собрав все параметры в одну команду.
START_SETTLE_S = CFG["start.settle_s"]     # окно сборки параметров перед стартом
SELECT_TTL_S = CFG["start.select_ttl_s"]   # выбор комнат живёт N секунд, потом считается «залипшим»
_start_task = None

def schedule_start():
    """Запланировать старт уборки с задержкой-сборкой параметров."""
    global _start_task
    if _start_task and not _start_task.done():
        _start_task.cancel()
    _start_task = asyncio.create_task(_delayed_start())

def cancel_start():
    global _start_task
    if _start_task and not _start_task.done():
        _start_task.cancel()
    _start_task = None

async def _delayed_start():
    try:
        await asyncio.sleep(START_SETTLE_S)
        for c in sh_start():
            await CMDQ.put(c)
    except asyncio.CancelledError:
        pass


def sh_values(o):
    st = S["status"] or {}
    code = S["state"]
    err, derr = st.get("errorCode") or 0, st.get("dockErrorStatus") or 0
    op = SH_STATE.get(code, 0)
    if err or derr:
        op = 3
    e = SH_ERR.get(err, 2) if err else (SH_DOCK_ERR.get(derr, 2) if derr else 0)
    fan = SH_FAN.get(st.get("fanPower"), 2)
    w = st.get("waterBoxMode") or 0
    if w == 200:
        water = 0
    elif 221 <= w <= 250:
        water = 1 if w <= 230 else (2 if w <= 240 else 3)
    else:
        water = {201: 1, 202: 2, 203: 3}.get(w, 2)
    mode = 1 if w == 200 else (2 if st.get("fanPower") == 105 else (0 if st.get("mopMode") in (301, 303) else 3))
    if not S["cleaning"]:   # на базе показываем то, что выбрано для следующей уборки
        fan = SH["fan"] if SH["fan"] is not None else fan
        water = SH["water"] if SH["water"] is not None else water
        mode = SH["mode"] if SH["mode"] is not None else mode
    cur = next((int(k) for k, v in S["rooms"].items() if v and v == S["room"]), 0)
    areas = [{"id": int(k), "name": v, "kind": "room"} for k, v in sorted(S["rooms"].items(), key=lambda x: int(x[0]))]
    return {
        "sh/online": "Online" if o["online"] else "Offline", "sh/active": "1" if o["online"] else "0",
        "sh/op_state": str(op), "sh/error": str(e), "sh/run_mode": "1" if S["cleaning"] else "0",
        "sh/suction": str(fan), "sh/water": str(water), "sh/clean_mode": str(mode),
        "sh/current_area": str(cur), "sh/supported_areas": json.dumps(areas, ensure_ascii=False),
        "sh/selected_areas": json.dumps(SH["selected"]),
    }


def parse_areas(p):
    """«16,17» | «Кухня, Ванная» | [16,17] | [{"id":16}] → список id сегментов."""
    try:
        v = json.loads(p)
    except Exception:
        v = str(p or "").replace(";", ",").split(",")
    if isinstance(v, (int, str)):
        v = [v]
    ids = []
    for x in v or []:
        if isinstance(x, dict):
            x = x.get("id", x.get("areaId", x.get("areaID", x.get("name"))))
        x = str(x).strip()
        if not x:
            continue
        if x.isdigit():
            ids.append(int(x))
        else:
            ids += [int(k) for k, n in S["rooms"].items() if n.lower() == x.lower()]
    return [i for i in dict.fromkeys(ids) if str(i) in S["rooms"]]


def sh_start(source="Sprut.hub"):
    """Команда RUNNING из Sprut.hub: продолжить паузу, иначе убрать выбранные комнаты/всё."""
    fresh = time.time() - SH["selected_ts"] < SELECT_TTL_S
    selected = list(SH["selected"]) if fresh else []
    if not fresh and SH["selected"]:
        log.warning("выбор комнат устарел (> %d с) — игнорируем: %s", SELECT_TTL_S, SH["selected"])
    if S["state"] == 10 and not selected:
        event("Продолжение уборки после паузы", source)
        return [("app_start", None)]
    g = None
    if SH["fan"] is not None or SH["water"] is not None or SH["mode"] is not None:
        st = S["status"] or {}
        mode = SH["mode"] if SH["mode"] is not None else 3
        fan = SH_FAN_W.get(SH["fan"], st.get("fanPower") if st.get("fanPower") in SH_FAN else 102)
        wl = SH["water"] if SH["water"] is not None else 2
        g = {"m": {1: "vac", 2: "mop"}.get(mode, "both"), "f": fan, "w": {0: 1, 1: 5, 2: 15, 3: 25}.get(wl, 15),
             "rt": 301 if mode == 0 else 300, "r": 1}
        if wl == 0 and mode not in (1,):
            g["m"] = "vac"
    segs = selected or [int(k) for k in S["rooms"]]
    names = ", ".join(S["rooms"].get(str(x), str(x)) for x in segs)
    log.info("старт уборки: %s", names)
    if g:
        event(f"Старт уборки: {names} (мощность {SH['fan']}, вода {SH['water']}, режим {SH['mode']})", source)
    else:
        event(f"Старт уборки: {names}", source)
    SH.update(selected=[], selected_ts=0.0, fan=None, water=None, mode=None)   # выбор действует на одну уборку
    if g is None and len(segs) == len(S["rooms"]) and segs:
        return [("app_start", None)]
    start_job([dict(g or {"m": "app"}, segments=segs)])
    return []


EV = asyncio.Event()           # «есть новое» для MQTT
CMDQ: asyncio.Queue = asyncio.Queue()


def _in(r, x, y):
    try:
        return min(r.x0, r.x1) <= x <= max(r.x0, r.x1) and min(r.y0, r.y1) <= y <= max(r.y0, r.y1)
    except Exception:
        return False


def room_at(md, x, y):
    """Имя сегмента Roborock по координатам робота.

    Прямоугольники комнат в разборе карты бывают в миллиметрах робота или в пикселях
    картинки — проверяем оба варианта (пиксели считаем по точкам калибровки карты).
    """
    rooms = getattr(md, "rooms", None) or {}
    if not rooms or x is None or y is None:
        return ""
    cands = [(x, y)]
    try:
        cal = md.calibration() or []
        if len(cal) >= 3:
            (a, b, c) = cal[:3]
            vx0, vy0 = a["vacuum"]["x"], a["vacuum"]["y"]
            mx0, my0 = a["map"]["x"], a["map"]["y"]
            sx = (b["map"]["x"] - mx0) / ((b["vacuum"]["x"] - vx0) or 1)
            sy = (c["map"]["y"] - my0) / ((c["vacuum"]["y"] - vy0) or 1)
            ix, iy = mx0 + (x - vx0) * sx, my0 + (y - vy0) * sy
            cands.append((ix, iy))
            h = getattr(getattr(md, "image", None), "dimensions", None)
            if h is not None and getattr(h, "height", None):
                cands.append((ix, h.height - iy))
    except Exception:
        pass
    for px, py in cands:
        for num, r in rooms.items():
            if _in(r, px, py):
                return S["rooms"].get(str(num)) or (getattr(r, "name", None) or "")
    return ""


def room_boxes(md, pts):
    """Прямоугольники комнат робота в миллиметрах робота: {сегмент: {"name", "box": [x0, y0, x1, y1]}}.

    Разбор карты отдаёт их то в миллиметрах, то в пикселях картинки (ось Y бывает перевёрнута) —
    пробуем все варианты и берём тот, в который попадает больше точек маршрута.
    Нужны дашборду для автоматического совмещения карты пылесоса с планом квартиры.
    """
    rooms = getattr(md, "rooms", None) or {}
    if not rooms:
        return S.get("boxes") or {}
    conv = [lambda x, y: (x, y)]
    try:
        cal = md.calibration() or []
        if len(cal) >= 3:
            (a, b, c) = cal[:3]
            vx0, vy0 = a["vacuum"]["x"], a["vacuum"]["y"]
            mx0, my0 = a["map"]["x"], a["map"]["y"]
            sx = (b["map"]["x"] - mx0) / ((b["vacuum"]["x"] - vx0) or 1) or 1
            sy = (c["map"]["y"] - my0) / ((c["vacuum"]["y"] - vy0) or 1) or 1
            conv.append(lambda x, y: (vx0 + (x - mx0) / sx, vy0 + (y - my0) / sy))
            h = getattr(getattr(md, "image", None), "dimensions", None)
            if h is not None and getattr(h, "height", None):
                hh = h.height
                conv.append(lambda x, y: (vx0 + (x - mx0) / sx, vy0 + ((hh - y) - my0) / sy))
    except Exception:
        pass
    sample = pts[::max(1, len(pts) // 400)]
    for k in ("pos", "charger"):
        if S.get(k) and S[k].get("x") is not None:
            sample.append([S[k]["x"], S[k]["y"]])
    best, score = None, -1
    for f in conv:
        bx = {}
        for num, r in rooms.items():
            try:
                x0, y0 = f(r.x0, r.y0)
                x1, y1 = f(r.x1, r.y1)
            except Exception:
                continue
            bx[str(num)] = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
        sc = sum(1 for p in sample if any(q[0] <= p[0] <= q[2] and q[1] <= p[1] <= q[3] for q in bx.values()))
        if sc > score:
            best, score = bx, sc
    return {k: {"name": S["rooms"].get(k) or "", "box": [round(v) for v in q]} for k, q in (best or {}).items()}


class Robot:
    def __init__(self):
        self.ctx = None
        self.v1 = None

    async def connect(self):
        self.ctx = RoborockContext()
        dm = await self.ctx.get_device_manager()
        dev = await dm.get_device(DUID)
        self.v1 = dev.v1_properties
        if self.v1 is None:
            raise RuntimeError("устройство не поддерживает протокол V1")
        await self.v1.start()
        try:
            await self.v1.rooms.refresh()
            for r in (self.v1.rooms.as_dict().get("rooms") or []):
                S["rooms"][str(r.get("segmentId"))] = r.get("rawName") or r.get("name") or ""
        except Exception as e:
            log.warning("комнаты не получены: %s", e)
        S["online"] = True
        log.info("подключено к %s, комнат: %d", DUID, len(S["rooms"]))
        event(f"Подключено к роботу, комнат: {len(S['rooms'])}")

    async def close(self):
        try:
            if self.ctx:
                await self.ctx.cleanup()
        except Exception:
            pass
        self.ctx = self.v1 = None

    async def status(self):
        st = self.v1.status
        t0 = time.time()
        await st.refresh()
        S["stMs"] = int((time.time() - t0) * 1000)
        d = st.as_dict()
        code = d.get("state")
        S.update(status=d, state=code, text=STATE_RU.get(code, f"Состояние {code}"),
                 cleaning=code in CLEANING, ts=time.time())
        return code

    async def map(self):
        mc = self.v1.map_content
        t0 = time.time()
        await mc.refresh()
        S["mapMs"] = int((time.time() - t0) * 1000)
        S["mapTs"] = time.time()
        md = mc.map_data
        if not md:
            return
        if md.vacuum_position:
            p = md.vacuum_position.as_dict()
            S["pos"] = {"x": p.get("x"), "y": p.get("y"), "a": p.get("a")}
            S["room"] = room_at(md, p.get("x"), p.get("y"))
        if md.charger:
            c = md.charger.as_dict()
            S["charger"] = {"x": c.get("x"), "y": c.get("y"), "a": c.get("a")}
        pts = []
        if md.path:
            for seg in (md.path.as_dict().get("path") or []):
                pts.extend([q["x"], q["y"]] for q in seg)
        S["path"] = pts[-PATH_MAX:]
        try:
            S["boxes"] = room_boxes(md, pts)
        except Exception as e:
            log.warning("комнаты карты: %s", e)
        S["ts"] = time.time()

    async def cmd(self, c):
        name, params = c
        await self.v1.command.send(name, params)


def to_cmd(kind, arg=None):
    kind = (kind or "").strip().lower()
    if kind in ("start", "старт"):
        return ("app_start", None)
    if kind in ("pause", "пауза"):
        return ("app_pause", None)
    if kind in ("stop", "стоп"):
        return ("app_stop", None)
    if kind in ("home", "dock", "домой"):
        return ("app_charge", None)
    if kind in ("locate", "find", "найти"):
        return ("find_me", None)
    if kind in ("resolve_error", "reset_error", "сброс"):
        st = S["status"] or {}
        code = st.get("dockErrorStatus") or st.get("errorCode")
        return ("resolve_error", {"error_code": int(code)}) if code else None
    if kind in ("rooms", "clean_rooms"):
        ids = []
        for part in (arg if isinstance(arg, list) else str(arg or "").replace(";", ",").split(",")):
            part = str(part).strip()
            if not part:
                continue
            if part.isdigit():
                ids.append(int(part))
            else:
                for k, v in S["rooms"].items():
                    if v.lower() == part.lower():
                        ids.append(int(k))
        if ids:
            return ("app_segment_clean", [{"segments": ids, "repeat": 1}])
    return None


async def robot_loop():
    rb = Robot()
    fails = 0
    last_map = 0.0
    last_st = 0.0
    while True:
        try:
            if rb.v1 is None:
                await rb.connect()
                fails = 0
            while not CMDQ.empty():
                c = CMDQ.get_nowait()
                log.info("команда %s", c[0])
                await rb.cmd(c)
                last_map = 0
                last_st = 0
            now = time.monotonic()
            # во время движения карта (позиция и маршрут) читается без пауз, статус — реже
            if not (S["state"] in MOVING and now - last_st < CFG["poll.status_moving_s"]):
                await rb.status()
                last_st = time.monotonic()
            moving = S["state"] in MOVING
            now = time.monotonic()
            if now - last_map > (CFG["poll.map_moving_s"] if moving else CFG["poll.map_idle_s"]):
                await rb.map()
                last_map = time.monotonic()
            S["error"] = None
            EV.set()
            # во время уборки — почти без пауз, на базе — раз в 20 с (или сразу по команде)
            try:
                await asyncio.wait_for(_cmd_wait(), timeout=0.3 if moving else 20)
            except asyncio.TimeoutError:
                pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            fails += 1
            S["error"] = str(e)[:200]
            if fails == 1:
                event("Потеряна связь с роботом: " + S["error"])
            S["online"] = False
            EV.set()
            log.warning("ошибка (%d): %s", fails, e)
            if fails >= 3:
                await rb.close()
            await asyncio.sleep(min(60, 5 * fails))


def motor_params(g):
    """Настройки комнаты из дашборда → параметры set_clean_motor_mode (None = как в приложении)."""
    m = g.get("m") or "app"
    if m == "app":
        return None
    fan = int(g.get("f") or 102)
    water = 220 + max(1, min(30, int(g.get("w") or 15)))
    route = int(g.get("rt") or 300)
    if m == "vac":
        water = 200
    elif m == "mop":
        fan = 105
    return [{"fan_power": fan, "water_box_mode": water, "mop_mode": route}]


async def _wait_state(pred, timeout):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if pred(S["state"]):
            return True
        await asyncio.sleep(1)
    return False


async def run_job(groups):
    """Уборка комнат с разными настройками — по очереди, затем возврат режима «по комнатам»."""
    changed = False
    try:
        for i, g in enumerate(groups):
            segs = [int(x) for x in g.get("segments") or []]
            if not segs:
                continue
            names = ", ".join(S["rooms"].get(str(x), str(x)) for x in segs)
            JOB["text"] = f"{i + 1}/{len(groups)}: {names}"
            mp = motor_params(g)
            if mp:
                await CMDQ.put(("set_clean_motor_mode", mp))
                changed = True
            elif changed:
                await CMDQ.put(("set_clean_motor_mode", CUSTOM_MOTOR))
                changed = False
            await CMDQ.put(("app_segment_clean", [{"segments": segs, "repeat": max(1, min(3, int(g.get("r") or 1)))}]))
            log.info("задание %s: %s %s", JOB["text"], mp or "как в приложении", g.get("r") or 1)
            event(f"Задание {JOB['text']}: {names} — {mp and 'свои настройки' or 'как в приложении'}, проходов {g.get('r') or 1}")
            if i == len(groups) - 1:
                # последняя часть: тоже дожидаемся окончания, чтобы сброс мотор-режима
                # (finally ниже) ушёл в очередь ПОСЛЕ уборки, а не сразу после старта
                await _wait_state(lambda s: s in BUSY, 90)
                await _wait_state(lambda s: s not in BUSY, 4 * 3600)
                break
            # ждём, пока робот начнёт и закончит эту часть
            await _wait_state(lambda s: s in BUSY, 90)
            ok_since = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < 4 * 3600:
                if S["state"] in BUSY:
                    ok_since = None
                else:
                    ok_since = ok_since or time.monotonic()
                    if time.monotonic() - ok_since > 15:
                        break
                await asyncio.sleep(2)
    except asyncio.CancelledError:
        log.info("задание отменено")
        event("Задание отменено")
        raise
    finally:
        if changed:
            await CMDQ.put(("set_clean_motor_mode", CUSTOM_MOTOR))
        JOB["text"] = ""
        JOB["task"] = None


def start_job(groups):
    t = JOB.get("task")
    if t and not t.done():
        t.cancel()
    JOB["task"] = asyncio.create_task(run_job(groups))


def cancel_job():
    t = JOB.get("task")
    if t and not t.done():
        t.cancel()


async def _cmd_wait():
    while CMDQ.empty():
        await asyncio.sleep(0.3)


def snapshot(full=True):
    st = S["status"] or {}
    o = {
        "online": S["online"], "ts": S["ts"], "state": S["state"], "text": S["text"],
        "cleaning": S["cleaning"], "battery": st.get("battery"), "room": S["room"],
        "cleanArea": round((st.get("cleanArea") or 0) / 1e6, 1), "cleanTime": round((st.get("cleanTime") or 0) / 60),
        "errorCode": st.get("errorCode"), "dockError": st.get("dockErrorStatus"),
        "cleanPercent": st.get("cleanPercent"), "pos": S["pos"], "charger": S["charger"],
        "rooms": S["rooms"], "roomBoxes": S["boxes"], "error": S["error"], "job": JOB["text"],
        "event": S["event"],
        "fan": st.get("fanPower"), "water": st.get("waterBoxMode"), "route": st.get("mopMode"),
        # замеры для дашборда: когда и как долго читалась карта/статус робота
        "now": time.time(), "mapTs": S.get("mapTs"), "mapMs": S.get("mapMs"), "stMs": S.get("stMs"),
    }
    if full:
        o["path"] = S["path"]
    return o


CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type", "Cache-Control": "no-store"}


async def h_state(req):
    since = int(req.query.get("from", "0") or 0)
    o = snapshot()
    if since and since <= len(o["path"]):
        o["pathFrom"] = since
        o["path"] = o["path"][since:]
    o["pathLen"] = len(S["path"])
    return web.json_response(o, headers=CORS)


async def h_events(req):
    return web.json_response({"events": list(EVENTS)}, headers=CORS)


async def h_cmd(req):
    try:
        body = await req.json()
    except Exception:
        body = {}
    if body.get("cmd") == "rooms_cfg" and isinstance(body.get("groups"), list):
        names = []
        for g in body["groups"]:
            names.append("+".join(S["rooms"].get(str(x), str(x)) for x in g.get("segments") or []) or "?")
        event("Уборка по группам: " + ", ".join(names), "HTTP")
        start_job(body["groups"])
        return web.json_response({"ok": True}, headers=CORS)
    c = to_cmd(body.get("cmd"), body.get("rooms"))
    if c and c[0] in ("app_charge", "app_stop"):
        cancel_job()
    if not c:
        return web.json_response({"ok": False, "error": "неизвестная команда"}, status=400, headers=CORS)
    event("Команда " + c[0], "HTTP")
    await CMDQ.put(c)
    return web.json_response({"ok": True}, headers=CORS)


async def h_opt(req):
    return web.Response(headers=CORS)


# --- настройки через HTTP (панель HomeBridge) -----------------------------------
# Служба работает от пользователя roborock и владеет CONF_PATH — писать может сама,
# sudo не нужен. Перезапуск: os._exit(0) + Restart=always в systemd-юните.

CONF_META = {   # ключ: (тип, горячее применение без перезапуска)
    "roborock.duid": (str, False),
    "roborock.http_port": (int, False),
    "mqtt.host": (str, False),
    "mqtt.port": (int, False),
    "mqtt.topic": (str, False),
    "poll.status_moving_s": (float, True),
    "poll.map_moving_s": (float, True),
    "poll.map_idle_s": (float, True),
    "start.settle_s": (float, True),
    "start.select_ttl_s": (float, True),
    "log.dir": (str, False),
    "log.max_mb": (int, False),
    "log.backups": (int, False),
    "log.events_max": (int, False),
}

def conf_sections():
    out = {}
    for key, v in CFG.items():
        sec, _, k = key.partition(".")
        out.setdefault(sec, {})[k] = v
    return out

def write_conf():
    cp = configparser.ConfigParser()
    for sec in ("roborock", "mqtt", "poll", "start", "log"):
        cp.add_section(sec)
        for key, v in CFG.items():
            s, _, k = key.partition(".")
            if s == sec:
                cp.set(sec, k, str(v))
    tmp = CONF_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# roborock_svc — файл обслуживается панелью HomeBridge. "
                "Переменные окружения RR_* имеют приоритет.\n")
        cp.write(f)
    os.replace(tmp, CONF_PATH)

async def h_conf(req):
    return web.json_response({"ok": True, "conf": conf_sections()}, headers=CORS)

async def h_conf_save(req):
    try:
        body = await req.json()
    except Exception:
        return web.json_response({"ok": False, "error": "ожидался JSON"}, status=400, headers=CORS)
    hot, restart = [], False
    for sec, opts in (body.get("conf") or {}).items():
        for k, v in (opts or {}).items():
            key = f"{sec}.{k}"
            meta = CONF_META.get(key)
            if not meta:
                continue
            typ, is_hot = meta
            try:
                v = typ(v)
            except Exception:
                return web.json_response({"ok": False, "error": f"некорректное значение: {key}"},
                                         status=400, headers=CORS)
            if CFG.get(key) != v:
                CFG[key] = v
                if is_hot:
                    hot.append(key)
                else:
                    restart = True
    write_conf()
    log.info("настройки сохранены в %s (горячих: %d, нужен перезапуск: %s)",
             CONF_PATH, len(hot), restart)
    event("Настройки службы сохранены" + (", требуется перезапуск" if restart else ""), "HTTP")
    return web.json_response({"ok": True, "applied": hot, "restart_required": restart}, headers=CORS)

async def h_restart(req):
    event("Перезапуск службы (запрос из панели)", "HTTP")
    asyncio.get_running_loop().call_later(0.5, os._exit, 0)   # Restart=always поднимет службу заново
    return web.json_response({"ok": True}, headers=CORS)


async def http_server():
    app = web.Application()
    app.router.add_get("/state", h_state)
    app.router.add_get("/events", h_events)
    app.router.add_get("/conf", h_conf)
    app.router.add_post("/conf", h_conf_save)
    app.router.add_post("/restart", h_restart)
    app.router.add_post("/cmd", h_cmd)
    app.router.add_route("OPTIONS", "/{tail:.*}", h_opt)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", HTTP_PORT).start()
    log.info("HTTP на порту %d", HTTP_PORT)


async def mqtt_loop():
    will = aiomqtt.Will(f"{BASE}/sh/online", "Offline", retain=True)
    while True:
        try:
            async with aiomqtt.Client(MQTT_HOST, MQTT_PORT, identifier="roborock_svc", will=will) as cl:
                log.info("MQTT подключён %s:%d", MQTT_HOST, MQTT_PORT)
                await cl.subscribe(f"{BASE}/set/#")

                async def pub():
                    last = {}
                    full_at = 0.0
                    while True:
                        try:
                            await asyncio.wait_for(EV.wait(), timeout=60)
                        except asyncio.TimeoutError:
                            pass
                        EV.clear()
                        # раз в минуту — все топики заново (если брокер потерял retained, они вернутся)
                        if time.monotonic() - full_at > 60:
                            last = {}
                            full_at = time.monotonic()
                        o = snapshot(full=False)
                        vals = {
                            "online": "true" if o["online"] else "false",
                            "status": o["text"], "state": str(o["state"]),
                            "cleaning": "true" if o["cleaning"] else "false",
                            "battery": str(o["battery"] if o["battery"] is not None else ""),
                            "room": o["room"] or "", "clean_area": str(o["cleanArea"]),
                            "clean_time": str(o["cleanTime"]), "error": str(o["errorCode"] or 0),
                            "dock_error": str(o["dockError"] or 0),
                            "position": json.dumps(o["pos"]) if o["pos"] else "",
                            "event": o.get("event") or "",
                        }
                        vals.update(sh_values(o))
                        for k, v in vals.items():
                            if last.get(k) != v:
                                await cl.publish(f"{BASE}/{k}", v, retain=True)
                                last[k] = v
                        await cl.publish(f"{BASE}/json", json.dumps(o, ensure_ascii=False), retain=True)

                pt = asyncio.create_task(pub())
                EV.set()
                try:
                    async for m in cl.messages:
                        t = str(m.topic)
                        p = m.payload.decode("utf-8", "replace") if isinstance(m.payload, (bytes, bytearray)) else str(m.payload)
                        c = None
                        if t.endswith("/set/target_state"):
                            try:
                                v = int(float(p))
                            except Exception:
                                v = None
                            if v == 1:
                                schedule_start()      # старт через окно сборки — атомарно
                            else:
                                cancel_start()
                                cancel_job()
                                for c2 in {0: [("app_stop", None)], 2: [("app_pause", None)], 3: [("app_charge", None)]}.get(v, []):
                                    event("Команда " + c2[0], "Sprut.hub")
                                    await CMDQ.put(c2)
                        elif t.endswith("/set/rooms_start"):
                            # атомарный старт одним сообщением: {"rooms": "Кухня", "fan": 3, "water": 3, "mode": 3}
                            try:
                                o = json.loads(p)
                            except Exception:
                                o = {"rooms": p}
                            if isinstance(o, str):
                                o = {"rooms": o}
                            SH["selected"] = parse_areas(o.get("rooms"))
                            SH["selected_ts"] = time.time()
                            for k in ("fan", "water", "mode"):
                                if o.get(k) is not None:
                                    try:
                                        SH[k] = int(o[k])
                                    except Exception:
                                        pass
                            for c2 in sh_start("Sprut.hub (rooms_start)"):
                                await CMDQ.put(c2)
                        elif t.endswith("/set/selected_areas"):
                            ids = parse_areas(p)
                            if str(p or "").strip() and not ids:
                                log.warning("комнаты не распознаны: %r (известны: %s)",
                                            p, ", ".join(S["rooms"].values()) or "—")
                            SH["selected"] = ids
                            SH["selected_ts"] = time.time()
                        elif t.endswith(("/set/suction", "/set/water", "/set/clean_mode")):
                            key = {"suction": "fan", "water": "water", "clean_mode": "mode"}[t.rsplit("/", 1)[1]]
                            try:
                                SH[key] = int(float(p))
                            except Exception:
                                pass
                        elif t.endswith("/set/command"):
                            c = to_cmd(p)
                            if c:
                                event("Команда " + c[0], "Sprut.hub")
                        elif t.endswith("/set/clean_rooms"):
                            c = to_cmd("rooms", p)
                            if c:
                                event("Уборка комнат: " + str(p), "Sprut.hub")
                        EV.set()
                        if c and c[0] in ("app_charge", "app_stop"):
                            cancel_job()
                        if c:
                            await CMDQ.put(c)
                finally:
                    pt.cancel()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("MQTT: %s — переподключение через 15 с", e)
            await asyncio.sleep(15)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("roborock").setLevel(logging.WARNING)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=CFG["log.max_mb"] * 1024 * 1024,
                                              backupCount=CFG["log.backups"], encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    efh = logging.handlers.RotatingFileHandler(EVENTS_FILE, maxBytes=CFG["log.max_mb"] * 1024 * 1024,
                                               backupCount=CFG["log.backups"], encoding="utf-8")
    efh.setFormatter(logging.Formatter("%(message)s"))
    ev_log.addHandler(efh)
    ev_log.setLevel(logging.INFO)
    ev_log.propagate = False
    log.info("roborock_svc v%s", VERSION)
    await http_server()
    tasks = [asyncio.create_task(robot_loop()), asyncio.create_task(mqtt_loop())]
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(s, stop.set)
    await stop.wait()
    for t in tasks:
        t.cancel()
    # библиотека Roborock может держать соединения; не ждём 90 с, пока systemd убьёт процесс
    await asyncio.wait(tasks, timeout=5)
    logging.shutdown()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(main())
