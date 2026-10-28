#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LG Soundbar (S95TR / S90T) <-> MQTT bridge для SprutHub.

Протокол: TCP 9741, AES-CBC JSON (как в temescal).
Состояние публикуется retained в <base>/<name>, команды — в <base>/<name>/set.
Уровни публикуются в dB, как в приложении LG (ВЧ -6..6, саб -15..6 и т.д.).

Зависимости:  pip3 install pycryptodome paho-mqtt
Запуск:
  python3 lgsb_bridge.py --host <IP_саундбара> --mqtt <IP_брокера> \
      [--mqtt-port <порт_брокера, по умолчанию 1883>] \
      [--user <логин> --password <пароль>] [--base lgsb/s95tr]
"""

import argparse
import json
import logging
import socket
import struct
import threading
import time

from Crypto.Cipher import AES
import paho.mqtt.client as mqtt

PORT = 9741
KEY = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
IV = b"'%^Ur7gy$~t+f)%@"
POLL_SEC = 300         # страховочный опрос саундбара (изменения он присылает сам)
REPUBLISH_SEC = 60     # повторная публикация состояния для СХ
RECONNECT_SEC = 10

SPK = "SPK_LIST_VIEW_INFO"
SET = "SETTING_VIEW_INFO"
EQ = "EQ_VIEW_INFO"
FUNC = "FUNC_VIEW_INFO"

# Уровни: имя -> (msg, поле, минимум). dB = raw + минимум.
LEVELS = {
    "treble":    (EQ,  "i_treble",          -6),
    "middle":    (EQ,  "i_middle",          -6),
    "bass":      (EQ,  "i_bass",            -6),
    "woofer":    (SET, "i_woofer_level",   -15),
    "center":    (SET, "i_center_level",    -6),
    "top":       (SET, "i_top_level",       -6),
    "side":      (SET, "i_side_level",      -6),
    "rear":      (SET, "i_rear_level",      -6),
    "rear_top":  (SET, "i_rear_top_level",  -6),
    "rear_side": (SET, "i_rear_side_level", -6),
    "dialog":    (SET, "i_dialog_level",     0),
}
LEVEL_MAX = {"dialog": 6}  # у остальных максимум +6

INTS = {
    "volume":     (SPK,  "i_vol"),
    "input":      (FUNC, "i_curr_func"),
    "sound_mode": (EQ,   "i_curr_eq"),
    "av_sync":    (SET,  "i_av_sync"),
    "backlight":  (SET,  "i_back_light"),   # светодиодный индикатор/дисплей
}

BOOLS = {
    "power":          (SPK, "b_powerstatus"),
    "mute":           (SPK, "b_mute"),
    "drc":            (SET, "b_drc"),
    "neuralx":        (SET, "b_neuralx"),
    "auto_vol":       (SET, "b_auto_vol"),
    "night":          (SET, "b_night_time"),
    "rear_on":        (SET, "b_rear"),
    "auto_power":     (SET, "b_auto_power"),
    "voice":          (SET, "b_voice_feedback"),  # голосовое сопровождение
    "dialog_enabled": (SET, "b_enable_dialog"),   # только чтение
}
READ_ONLY = {"dialog_enabled"}

STRINGS = {
    "audio_source": "s_audio_source",
    "model":        "s_model_name",
}

INPUT_NAMES = {
    20: "HDMI eARC", 15: "Оптика", 4: "Оптика", 6: "HDMI", 0: "Wi-Fi",
    1: "Bluetooth", 19: "USB", 18: "USB",
}
# Коды 0-22 — по temescal; 23-26 появились в моделях 2024 года.
# Порядок как в ai_eq_list (= порядок в приложении).
MODE_NAMES = {
    19: "AI Sound Pro", 0: "Стандарт", 7: "Кино", 26: "Чёткий голос",
    21: "Спорт", 6: "Музыка", 22: "Игра", 14: "Bass Blast",
    5: "Пользовательский", 15: "Dolby Atmos", 23: "Синхронизация с телевизором",
    24: "IMAX DTS", 25: "IMAX DTS:X", 20: "Чёткий голос",
}
OPTICAL_CODE = 15     # в ai_func_list S95TR оптика = 15 (на SN-серии 4)
AV_SYNC_STEP_MS = 10   # i_av_sync в шагах по 10 мс (0..300 мс)

# Обратная карта: поле устройства -> (имя, тип)
FIELD_MAP = {}
for n, (_, f, _m) in LEVELS.items():
    FIELD_MAP[f] = (n, "level")
for n, (_, f) in INTS.items():
    FIELD_MAP[f] = (n, "int")
for n, (_, f) in BOOLS.items():
    FIELD_MAP[f] = (n, "bool")
for n, f in STRINGS.items():
    FIELD_MAP[f] = (n, "str")

log = logging.getLogger("lgsb")


def encrypt(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    enc = AES.new(KEY, AES.MODE_CBC, IV).encrypt(raw)
    return b"\x10" + struct.pack(">I", len(enc)) + enc


def decrypt(data):
    dec = AES.new(KEY, AES.MODE_CBC, IV).decrypt(data)
    pad = dec[-1]
    if 1 <= pad <= 16:
        dec = dec[:-pad]
    return json.loads(dec.decode("utf-8"))


class Bridge:
    def __init__(self, a):
        self.a = a
        self.base = a.base.rstrip("/")
        self.sock = None
        self.lock = threading.Lock()
        self.cache = {}

        try:
            self.mq = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="lgsb-bridge")
        except AttributeError:  # paho-mqtt 1.x
            self.mq = mqtt.Client(client_id="lgsb-bridge")
        if a.user:
            self.mq.username_pw_set(a.user, a.password)
        self.mq.will_set(self.base + "/available", "offline", retain=True)
        self.mq.on_connect = self.on_connect
        self.mq.on_message = self.on_message

    # ---------- MQTT ----------
    def on_connect(self, client, userdata, flags, rc, *args):
        log.info("MQTT подключён")
        client.subscribe(self.base + "/+/set")
        if self.sock:
            client.publish(self.base + "/available", "online", retain=True)
        for k, v in self.cache.items():
            client.publish(self.base + "/" + k, v, retain=True)

    def pub(self, name, value):
        value = str(value)
        if self.cache.get(name) == value:
            return
        self.cache[name] = value
        self.mq.publish(self.base + "/" + name, value, retain=True)
        log.debug("%s = %s", name, value)

    def on_message(self, client, userdata, msg):
        if msg.retain:
            return  # старые retained-команды не исполняем
        name = msg.topic[len(self.base) + 1:-4]
        payload = msg.payload.decode("utf-8", "replace").strip()
        try:
            self.handle_set(name, payload)
        except Exception as e:
            log.warning("set %s=%s: %s", name, payload, e)

    def handle_set(self, name, p):
        if name in LEVELS:
            msg, field, mn = LEVELS[name]
            mx = LEVEL_MAX.get(name, 6)
            db = max(mn, min(mx, int(round(float(p)))))
            self.send_set(msg, {field: db - mn})
        elif name == "av_sync":
            ms = max(0, min(300, int(round(float(p)))))
            self.send_set(SET, {"i_av_sync": int(round(ms / float(AV_SYNC_STEP_MS)))})
        elif name in INTS:
            msg, field = INTS[name]
            v = int(round(float(p)))
            if name == "input" and v in (4, 15):
                v = OPTICAL_CODE   # оптика: код из ai_func_list этой модели
            if name == "volume":
                v = max(0, min(100, v))
            self.send_set(msg, {field: v})
        elif name in BOOLS and name not in READ_ONLY:
            msg, field = BOOLS[name]
            v = p.lower() in ("on", "true", "1")
            if name == "power":
                # так же делает интеграция LG Soundbar в Home Assistant
                self.send_set(SPK, {"b_powerkey": v})
            elif name == "night":
                # прошивка отдаёт b_night_time, temescal пишет b_night_mode
                self.send_set(SET, {"b_night_time": v, "b_night_mode": v})
            else:
                self.send_set(msg, {field: v})
        else:
            log.warning("неизвестная команда: %s", name)

    # ---------- Soundbar ----------
    def send(self, obj):
        with self.lock:
            if not self.sock:
                raise ConnectionError("нет связи с саундбаром")
            self.sock.sendall(encrypt(obj))

    def send_set(self, msg, data):
        log.info("SET %s %s", msg, data)
        self.send({"cmd": "set", "msg": msg, "data": data})
        time.sleep(0.2)
        self.send({"cmd": "get", "msg": msg})

    def request_all(self):
        for m in (SPK, SET, EQ, FUNC, "PRODUCT_INFO", "UPDATE_VIEW_INFO"):
            self.send({"cmd": "get", "msg": m})
            time.sleep(0.1)

    def recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("саундбар закрыл соединение")
            buf += chunk
        return buf

    def process(self, pkt):
        data = pkt.get("data")
        if not isinstance(data, dict):
            return
        ver = data.get("o_system_ver")
        if isinstance(ver, dict) and ver.get("s_main"):
            self.pub("firmware", "%s / %s" % (ver.get("s_main"), ver.get("s_micom", "-")))
        for field, val in data.items():
            if field not in FIELD_MAP:
                continue
            name, kind = FIELD_MAP[field]
            if kind == "level":
                self.pub(name, int(val) + LEVELS[name][2])
            elif kind == "bool":
                self.pub(name, "on" if val else "off")
            elif kind == "int" and name == "av_sync":
                self.pub(name, int(val) * AV_SYNC_STEP_MS)
            elif kind == "int":
                self.pub(name, int(val))
                if name == "input":
                    self.pub("input_name", INPUT_NAMES.get(val, "Вход %s" % val))
                elif name == "sound_mode":
                    self.pub("sound_mode_name", MODE_NAMES.get(val, "Режим %s" % val))
            else:
                self.pub(name, val)

    def poller(self):
        last_poll = time.time()
        while True:
            time.sleep(REPUBLISH_SEC)
            if time.time() - last_poll >= POLL_SEC:
                last_poll = time.time()
                try:
                    for m in (SPK, SET, EQ, FUNC):
                        self.send({"cmd": "get", "msg": m})
                        time.sleep(0.1)
                except Exception:
                    pass  # переподключением займётся основной цикл
            for k, v in list(self.cache.items()):
                self.mq.publish(self.base + "/" + k, v, retain=True)

    def run(self):
        self.mq.connect_async(self.a.mqtt, self.a.mqtt_port, 60)
        self.mq.loop_start()
        threading.Thread(target=self.poller, daemon=True).start()

        while True:
            try:
                s = socket.create_connection((self.a.host, PORT), timeout=10)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                s.settimeout(POLL_SEC * 3)
                with self.lock:
                    self.sock = s
                log.info("Саундбар %s подключён", self.a.host)
                self.mq.publish(self.base + "/available", "online", retain=True)
                self.request_all()
                while True:
                    head = self.recv_exact(1)
                    if head[0] != 0x10:
                        continue
                    ln = struct.unpack(">I", self.recv_exact(4))[0]
                    body = self.recv_exact(ln)
                    if ln % 16:
                        continue
                    try:
                        self.process(decrypt(body))
                    except ValueError as e:
                        log.debug("плохой пакет: %s", e)
            except Exception as e:
                log.warning("Связь с саундбаром: %s", e)
            with self.lock:
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                self.sock = None
            self.mq.publish(self.base + "/available", "offline", retain=True)
            time.sleep(RECONNECT_SEC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="IP саундбара")
    ap.add_argument("--mqtt", default="127.0.0.1")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--base", default="lgsb/s95tr")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.debug else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    Bridge(a).run()


if __name__ == "__main__":
    main()
