# Чайник Polaris PWK 1841CGLD (IQ Home) для SprutHub через MQTT

Шаблон устройства **Polaris PWK 1841CGLD Wi-Fi IQ Home** для **SprutHub**. Чайник работает **локально**, без облака Polaris: в новых прошивках в приложении Polaris IQ Home есть пункт «Настройки MQTT», и чайник сам подключается к вашему брокеру.

Топики и значения сверены с работающим чайником (прошивка Wi-Fi 1.13, MCU 20.10.4) и с интеграцией [samoswall/polaris-mqtt](https://github.com/samoswall/polaris-mqtt) для Home Assistant.

---

## Что умеет шаблон

| Сервис | Характеристики |
|---|---|
| Кипячение (`Switch`) | вкл/выкл кипячения |
| Нагрев (`Thermostat`) | текущая температура воды, целевая температура 30–100 °C, вкл/выкл разогрева |
| Режим работы (`Television` / `InputSource`) | Кипячение, Разогрев, Разогрев с удержанием, IQ Кипячение; в названии виден текущий режим или «Выключен» |
| Ночник (`Lightbulb`) | вкл/выкл |
| Подсветка, Звук, Блокировка кнопок (`Switch`) | настройки |
| Чайник на базе (`ContactSensor`) | стоит ли чайник на базе + текст ошибки (мало воды, снят с базы, ошибка термодатчика…) |
| Опции | прошивка Wi-Fi и MCU, RSSI, имя Wi-Fi-сети |

---

## Важно: встроенный брокер SprutHub не подходит

Чайник отправляет `SUBSCRIBE` сразу после `CONNECT`, не дожидаясь `CONNACK`. Встроенный брокер SprutHub такое соединение рвёт, в логе каждые 10 секунд:

```
SUBSCRIBE received on already closed connection, CId=null ...
CONNACK send failed, cleanup session and close the connection
```

Поэтому чайник подключается к отдельному **Mosquitto**, а SprutHub читает его вторым MQTT-контроллером.

```
Чайник ──MQTT──▶ Mosquitto (Linux-хост, :1883) ◀──MQTT── SprutHub (контроллер MQTT №2)
```

---

## Шаг 1. Mosquitto на Linux-хосте

Здесь это ТВ-приставка RK3318 на Armbian, подойдёт любой Linux в локальной сети.

```bash
sudo apt install mosquitto mosquitto-clients
```

В `/etc/mosquitto/mosquitto.conf` должны быть строки:

```
allow_anonymous true
listener 1883
```

> Если они уже есть в основном конфиге, не дублируйте их в `conf.d/`: второй `listener 1883` даст `Address already in use`, и Mosquitto не запустится.

```bash
sudo systemctl restart mosquitto
sudo ss -tlnp | grep 1883     # 0.0.0.0:1883 ... mosquitto
hostname -I                   # IP хоста для следующих шагов
```

## Шаг 2. Чайник → Mosquitto

В приложении **Polaris IQ Home**: чайник → ⚙️ → **Настройки MQTT**.

- Соединение: **вкл**
- Адрес сервера: IP Linux-хоста, без `mqtt://` и без порта
- Порт: `1883`, SSL: **выкл**
- Пользователь и пароль: пусто
- **Сохранить**

Если пункта «Настройки MQTT» нет, прошивка старая: запросите новую в поддержке Polaris через приложение.

> Приложение передаёт настройки через облако Polaris. Если облако «лежит» (баннер «Временные неполадки»), настройки не применятся: после сохранения поля снова окажутся пустыми.

Проверка:

```bash
sudo tail -f /var/log/mosquitto/mosquitto.log
# New client connected from 192.168.x.x as 685377a1xxxx (p2, c1, k20)

mosquitto_sub -h localhost -t 'polaris/#' -v -W 15
```

Чайник публикует топики `polaris/<MAC>/state/...` и принимает команды в `polaris/<MAC>/control/...`.

## Шаг 3. SprutHub

1. Скачайте [шаблон](Шаблон%20устройства%20-%20MQTT%20(Polaris)%20+%20PWK-1841CGLD.json) и положите его в `Templates/MQTT/Custom`, затем **Настройки → Основные → Расширенные → Перезагрузить шаблоны**.
2. Создайте или включите второй MQTT-контроллер и укажите брокер `<IP хоста>:1883`. Первый контроллер остаётся на встроенном брокере.
3. Запустите **Поиск устройств** на этом контроллере.

---

## Топики

| Топик (`polaris/<MAC>/…`) | Значения |
|---|---|
| `state/mode` → `control/mode` | `0` выкл, `1` кипячение, `3` разогрев, `4` разогрев с удержанием, `5` IQ кипячение |
| `state/temperature` → `control/temperature` | целевая температура; `0`, когда чайник выключен |
| `state/sensor/temperature` | текущая температура воды, `28.00` |
| `state/night` → `control/night` | состояние `0`/`1`, команда `true`/`false` |
| `state/backlight`, `state/sound`, `state/child_lock` → `control/…` | `true`/`false` |
| `state/error/empty_base` | `false`: чайник на базе |
| `state/error/code` | `00` нет, `01` мало воды, `02` снят с базы, `03`/`04` термодатчик, `05` блокировка, `06`/`07` смените воду |
| `state/firmware`, `state/mcu_firmware`, `state/diag/rssi`, `state/last_wifi` | информация |

## Другие модели

Шаблон находит устройство по топику `state/night`, поэтому подхватит и другие чайники Polaris с ночником; топики у них те же. Чайники без ночника по этому `modelIds` не найдутся. Список моделей и их функций есть в [samoswall/polaris-mqtt](https://github.com/samoswall/polaris-mqtt).
