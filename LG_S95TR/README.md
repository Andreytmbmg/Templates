# Саундбар LG S95TR для SprutHub через локальный протокол → MQTT

Шаблон устройства **LG S95TR** (9.1.5, 2024) для **SprutHub**. Работает **локально**, без облака LG ThinQ. Небольшой мост `lgsb_bridge.py` подключается к саундбару по его сетевому протоколу (TCP 9741, тот же, что использует приложение LG Sound Bar) и публикует состояние в MQTT-брокер SprutHub.

В шаблон выведены почти все настройки из приложения LG: тон, уровни всех динамиков, DRC, Neural:X, ночной режим, AV Sync, индикатор и т. д.

Скорее всего, подойдёт и для других Wi-Fi-саундбаров LG (S90TY, S95QR, SC9S…), но проверено только на S95TR.

---

## Что умеет шаблон

| Сервис | Что делает |
|---|---|
| Саундбар (`Television`) | питание, выбор звукового режима как источника: AI Sound Pro, Стандарт, Кино, Чёткий голос, Спорт, Музыка, Игра, Bass Blast, Пользовательский, Dolby Atmos, Синхронизация с телевизором, IMAX DTS, IMAX DTS:X |
| Громкость (`Speaker`) | громкость 0–100, mute |
| Вход HDMI eARC / HDMI / Оптика / Bluetooth / Wi-Fi / USB | `Switch`: включение выбирает вход |
| DRC, Neural:X, Автоуровень громкости, Ночной режим, Объёмный звук, Автовключение, Голосовое сопровождение | `Switch` |
| ВЧ / СЧ / НЧ | −6…+6 dB |
| Сабвуфер | −15…+6 dB |
| Центр, Верхние, Боковые, Задние, Задние верхние, Задние боковые | −6…+6 dB |
| Dialog Control | 0…6 (только при DTS:X) |
| AV Sync | 0…300 мс, шаг 10 |
| Вход / Источник звука / Режим звука | текстовое состояние (`DOLBY AUDIO`, `HDMI eARC`…) |
| Опции | светодиодный индикатор (Авто яркость / Авто выкл. / Всегда вкл.), связь моста, модель, прошивка |

Все значения синхронизируются в обе стороны: изменения в приложении LG сразу видны в SprutHub, и наоборот.

---

## Требования

- SprutHub с MQTT-брокером (в примере `192.168.31.147:44444`)
- Linux-хост в той же сети, что и саундбар (здесь ТВ-приставка RK3318 на Armbian, Debian bullseye), Python 3.9+
- Саундбар подключён к Wi-Fi через приложение LG Sound Bar
- Фиксированный IP саундбара (закрепите его в DHCP роутера)

---

## Шаг 1. Найти IP саундбара

Ни приложение LG, ни роутер (часто) IP не показывают. Проще всего найти его через mDNS, на Mac:

```bash
dns-sd -B _googlecast._tcp
# → LG-S90T-Soundbar-xxxxxxxx   (S95TR представляется как S90T — это нормально)
dns-sd -L "LG-S90T-Soundbar-xxxxxxxx" _googlecast._tcp
# → can be reached at XXXXXXXX-....local.:8009
ping -c 2 XXXXXXXX-....local
```

---

## Шаг 2. Проверка протокола (необязательно)

`lgsb_probe.py` подключается к саундбару, печатает все блоки настроек и в режиме `--watch` показывает, какие поля меняются, когда вы двигаете ползунки в приложении. Пригодится для других моделей.

```bash
python3 -m venv lgsb && source lgsb/bin/activate
pip install pycryptodome
python lgsb_probe.py <IP_саундбара> --watch 120
```

---

## Шаг 3. Установка моста

```bash
sudo mkdir -p /opt/lgsb && sudo chown $USER /opt/lgsb
cd /opt/lgsb
# положите сюда lgsb_bridge.py
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install pycryptodome paho-mqtt
```

> В bullseye `apt install python3-pip` может падать с 404 (пакеты убраны из `bullseye-security`). Системный pip не нужен — venv приносит свой.

Пробный запуск:

```bash
venv/bin/python lgsb_bridge.py --host <IP_саундбара> --mqtt 192.168.31.147 --mqtt-port 44444 --debug
```

Должны появиться `MQTT подключён`, `Саундбар … подключён` и поток значений (`volume = 5`, `woofer = 6`…). Если брокер требует авторизацию — добавьте `--user` и `--password`.

---

## Шаг 4. Служба systemd

Поправьте IP в `lgsb.service` и установите:

```bash
sudo cp lgsb.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lgsb
sudo journalctl -u lgsb -n 20 --no-pager
```

> Не запускайте мост вручную, пока работает служба: у обоих экземпляров один MQTT client_id, и брокер будет выкидывать их по очереди (в логе бесконечное `MQTT подключён`). Для отладки: `sudo systemctl stop lgsb`.

---

## Шаг 5. Шаблон в SprutHub

1. Импортируйте `Шаблон устройства - mqtt (lgsb_bridge) + LG S95TR.json` в каталог шаблонов контроллера MQTT.
2. Добавьте устройство вручную с ID **`lgsb/s95tr`** (автопоиск его не находит).
3. Значения подтянутся в течение минуты.

---

## MQTT-топики

Префикс `lgsb/s95tr` (меняется параметром `--base`). Состояние — `lgsb/s95tr/<имя>`, команды — `lgsb/s95tr/<имя>/set`.

| Имя | Значение | Поле протокола |
|---|---|---|
| `power`, `mute` | `on` / `off` | `b_powerstatus` (команда `b_powerkey`), `b_mute` |
| `volume` | 0–100 | `i_vol` |
| `input` / `input_name` | код / название входа | `i_curr_func` |
| `sound_mode` / `sound_mode_name` | код / название режима | `i_curr_eq` |
| `treble`, `middle`, `bass` | dB | `i_treble`, `i_middle`, `i_bass` |
| `woofer` | dB | `i_woofer_level` |
| `center`, `top`, `side`, `rear`, `rear_top`, `rear_side` | dB | `i_*_level` |
| `dialog` | 0–6 | `i_dialog_level` |
| `av_sync` | мс | `i_av_sync` (×10) |
| `drc`, `neuralx`, `auto_vol`, `night`, `rear_on`, `auto_power`, `voice` | `on` / `off` | `b_drc`, `b_neuralx`, `b_auto_vol`, `b_night_time`, `b_rear`, `b_auto_power`, `b_voice_feedback` |
| `backlight` | 0 авто яркость, 1 авто выкл., 2 всегда вкл. | `i_back_light` |
| `audio_source`, `model`, `firmware`, `dialog_enabled`, `available` | только чтение | |

Уровни протокол передаёт со смещением (`raw = dB − min`), мост пересчитывает их в dB, как в приложении.

**Коды входов S95TR:** 20 HDMI eARC, 6 HDMI, 15 Оптика, 1 Bluetooth, 0 Wi-Fi, 19 USB.

**Коды режимов:** 19 AI Sound Pro, 0 Стандарт, 7 Кино, 26 Чёткий голос, 21 Спорт, 6 Музыка, 22 Игра, 14 Bass Blast, 5 Пользовательский, 15 Dolby Atmos, 23 Синхронизация с телевизором, 24 IMAX DTS, 25 IMAX DTS:X.

---

## Особенности

- **Повторная публикация.** Брокер SprutHub не хранит retained для этих топиков, поэтому мост раз в минуту переотправляет всё состояние (`REPUBLISH_SEC`). Изменения саундбар присылает сам, его опрос — раз в 5 минут для страховки (`POLL_SEC`).
- **Старые команды игнорируются.** Retained-сообщения в `…/set` мост не исполняет, чтобы при перезапуске не перетереть настройки из приложения.
- **HDMI eARC** может не переключаться командой: саундбар выбирает его сам, когда телевизор шлёт звук по CEC.
- **Ночной режим** мост отправляет сразу в два поля (`b_night_time` и `b_night_mode`), т. к. модели разных лет используют разные.

---

## Благодарности

- [google/python-temescal](https://github.com/google/python-temescal) — разбор протокола LG Sound Bar (TCP 9741, AES-CBC JSON)
- Интеграция [LG Soundbars](https://www.home-assistant.io/integrations/lg_soundbar/) для Home Assistant
