#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LG Soundbar probe — разведка локального протокола (TCP 9741).

1) Запрашивает все известные *_INFO блоки и печатает сырой JSON.
2) Режим наблюдения: двигай ползунки в приложении LG — скрипт покажет,
   какие поля изменились (так сопоставим поля с настройками).

Зависимость:  pip3 install pycryptodome
Запуск:       python3 lgsb_probe.py <IP_саундбара>
              python3 lgsb_probe.py <IP_саундбара> --watch 120
"""

import argparse
import json
import socket
import struct
import sys
import time

from Crypto.Cipher import AES

PORT = 9741
KEY = b"T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k"
IV = b"'%^Ur7gy$~t+f)%@"

QUERIES = [
    "PRODUCT_INFO",
    "SPK_LIST_VIEW_INFO",
    "SETTING_VIEW_INFO",
    "EQ_VIEW_INFO",
    "FUNC_VIEW_INFO",
    "PLAY_INFO",
    "C4A_SETTING_INFO",
    "SOUND_SETTING_VIEW_INFO",   # на старых моделях может не существовать
    "SPEAKER_LEVEL_VIEW_INFO",   # пробные, неизвестные просто игнорируются
    "UPDATE_VIEW_INFO",
    "BUILD_INFO_DEV",
    "OPTION_INFO_DEV",
]


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
    return dec.decode("utf-8", errors="replace")


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("соединение закрыто саундбаром")
        buf += chunk
    return buf


def read_packet(sock):
    head = recv_exact(sock, 1)
    if head[0] != 0x10:
        return None
    length = struct.unpack(">I", recv_exact(sock, 4))[0]
    body = recv_exact(sock, length)
    if length % 16:
        return {"_raw_unaligned": body.hex()}
    text = decrypt(body)
    try:
        return json.loads(text)
    except ValueError:
        return {"_undecoded": text}


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, prefix + k + "."))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            out.update(flatten(v, prefix + str(i) + "."))
    else:
        out[prefix[:-1]] = d
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--watch", type=int, default=0,
                    help="секунд наблюдения за изменениями после опроса")
    args = ap.parse_args()

    sock = socket.create_connection((args.host, PORT), timeout=5)
    print("Подключено к %s:%d" % (args.host, PORT))

    for msg in QUERIES:
        sock.sendall(encrypt({"cmd": "get", "msg": msg}))
        time.sleep(0.15)

    state = {}
    dump = {}
    sock.settimeout(3)
    try:
        while True:
            pkt = read_packet(sock)
            if not pkt:
                continue
            name = pkt.get("msg", "?")
            dump[name] = pkt
            state[name] = flatten(pkt.get("data", pkt))
            print("\n=== %s ===" % name)
            print(json.dumps(pkt, ensure_ascii=False, indent=2))
    except socket.timeout:
        pass

    with open("lgsb_dump.json", "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)
    print("\nПолучено блоков: %d → сохранено в lgsb_dump.json" % len(dump))
    if not dump:
        print("Ответов нет: проверь IP / порт, либо прошивка использует другой ключ.")

    if args.watch:
        print("\nНаблюдение %d с — меняй настройки в приложении LG...\n" % args.watch)
        end = time.time() + args.watch
        sock.settimeout(1)
        while time.time() < end:
            try:
                pkt = read_packet(sock)
            except socket.timeout:
                continue
            if not pkt:
                continue
            name = pkt.get("msg", "?")
            new = flatten(pkt.get("data", pkt))
            old = state.get(name, {})
            diff = {k: (old.get(k), v) for k, v in new.items() if old.get(k) != v}
            state[name] = new
            ts = time.strftime("%H:%M:%S")
            if diff:
                for k, (a, b) in diff.items():
                    print("%s  %s.%s: %s → %s" % (ts, name, k, a, b))
            else:
                print("%s  %s (без изменений)" % (ts, name))

    sock.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print("Ошибка:", e)
        sys.exit(1)
