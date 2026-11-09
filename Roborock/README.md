# Roborock Saros 10R шаблон для SprutHub через MQTT

> **Авторы:** разработка службы `roborock_svc` (v1.1–v1.2: атомарный старт, настройки из INI, журнал событий) и панели **HomeBridge** `homebridge-roborock-panel` — при участии **Kimi (Moonshot AI)**. Идеи, сценарии и тестирование — **Andrey (Andreytmbmg)**.

Шаблон устройства **Roborock Saros 10R** для **SprutHub** на родном сервисе **«Пылесос» (C_VacuumCleaner)**.

Своей интеграции Roborock в SprutHub нет, поэтому данные берёт небольшая служба `roborock_svc.py` на базе библиотеки [python-roborock](https://github.com/Python-roborock/python-roborock). Она работает на любой Linux-машине в локальной сети (например, на приставке с Homebridge), читает состояние робота и карту и публикует всё в MQTT-брокер. Команды из SprutHub служба отправляет роботу.

Пароль от аккаунта Roborock на машине не хранится: один раз выполняется вход по коду из письма, дальше служба использует сохранённый ключ.

---

## Возможности

| Характеристика SprutHub | Что показывает / делает |
|---|---|
| Состояние | Уборка, пауза, едет на базу, заряжается, на базе, очистка контейнера, мойка тряпок, ошибка |
| Команда | Старт, пауза, стоп, на базу. «Старт» после паузы продолжает уборку |
| Режим работы | Ожидание / Уборка |
| Режим уборки | Сухая, влажная, сухая и влажная, глубокая |
| Мощность всасывания | Выкл, тихая, сбалансированная, турбо, макс, макс+ |
| Подача воды | Выкл, низкая, средняя, высокая |
| Код ошибки | Ошибки робота и станции переведены в список SprutHub: застрял, нет воды, бак грязной воды полон, щётки заблокированы и т.д. |
| Доступные / выбранные зоны | Комнаты с карты Roborock списком, выбор нескольких комнат |
| Текущая зона | Комната, где сейчас робот |
| Батарея | Заряд, низкий заряд, зарядка |
| Дополнительно | Статус текстом, комната, убранная площадь, время уборки, коды ошибок робота и станции |
| Событие | Журнал «что, куда и почему поехало»: последний старт с комнатами и источником (Sprut.hub/HTTP), команды, потеря связи |

**Как работает старт.** «Старт» собирает выбранные зоны, мощность, воду и режим в одну команду (окно сборки 0,5 с) — порядок MQTT-топиков не важен, робот убирает именно то, что выбрано. Если в «Выбранных зонах» отмечены комнаты — убирает только их, иначе запускается обычная уборка всей квартиры. Выбор комнат живёт 2 минуты: если старт не пришёл, он сбрасывается и робот не уедет «в прошлую комнату». Мощность, вода и режим действуют на одну уборку, после неё робот возвращается к настройкам комнат из приложения Roborock. Есть и атомарный вариант одним сообщением: топик `set/rooms_start` с `{"rooms":"Кухня","fan":3,"water":3,"mode":3}`.

---

## Требования

- SprutHub
- MQTT-брокер
- Linux-машина в той же сети, Python 3.11+
- Робот Roborock, добавленный в приложение Roborock (проверено на Saros 10R, `roborock.vacuum.a144`; другие модели с протоколом V1 тоже должны работать)
- Желательно отдельный аккаунт Roborock, которому робот расшарен из основного

---

## Установка службы

```bash
# пользователь и окружение
sudo useradd --system --home /opt/roborock --shell /usr/sbin/nologin roborock
sudo mkdir -p /opt/roborock && sudo chown roborock:roborock /opt/roborock
sudo -u roborock python3 -m venv /opt/roborock/venv
sudo -u roborock /opt/roborock/venv/bin/pip install "python-roborock[cli]" aiomqtt aiohttp

# вход (код придёт на почту), затем узнать DUID робота
sudo -u roborock -H /opt/roborock/venv/bin/roborock login --email you@example.com
sudo -u roborock -H /opt/roborock/venv/bin/roborock list-devices

# служба
sudo install -o roborock -g roborock -m 755 roborock_svc.py /opt/roborock/roborock_svc.py
sudo install -o roborock -g roborock -m 644 roborock_svc.conf /opt/roborock/roborock_svc.conf
sudo cp roborock-svc.service /etc/systemd/system/
sudo nano /opt/roborock/roborock_svc.conf   # duid, mqtt host/port/topic
sudo systemctl daemon-reload && sudo systemctl enable --now roborock-svc
sudo journalctl -u roborock-svc -f
```

В юните службы стоят ограничения (низкий приоритет, 25% CPU, 150 МБ памяти), чтобы она не мешала другим программам на машине.

## Установка шаблона

1. Скопируйте файл `Шаблон устройства - mqtt (roborock_svc) + Roborock Saros 10R.json`.
2. Импортируйте его в SprutHub:
   ```
   Настройки → Шаблоны устройств → MQTT → Импорт
   ```
3. Устройство найдётся по топикам `roborock/saros10r/...`.

---

## MQTT-топики

Служба публикует с флагом retain и раз в минуту повторяет все топики.

| Топик | Значение |
|---|---|
| `roborock/saros10r/sh/op_state` | Состояние для C_CurrentOperationalState |
| `roborock/saros10r/sh/error` | Ошибка для C_OperationalError |
| `roborock/saros10r/sh/suction`, `sh/water`, `sh/clean_mode` | Мощность, вода, режим |
| `roborock/saros10r/sh/supported_areas` | `[{"id":1,"name":"Кухня","kind":"room"},…]` |
| `roborock/saros10r/sh/selected_areas` | `[1,4]` |
| `roborock/saros10r/sh/current_area` | id комнаты |
| `roborock/saros10r/sh/online`, `sh/active` | `Online`/`Offline`, `1`/`0` |
| `roborock/saros10r/event` | Последнее событие: старт с комнатами и источником, команда, потеря связи (retained) |
| `roborock/saros10r/battery`, `status`, `room`, `state`, `error`, `dock_error`, `clean_area`, `clean_time` | Исходные значения |
| `roborock/saros10r/json` | Всё состояние одним JSON |

Команды:

| Топик | Значение |
|---|---|
| `roborock/saros10r/set/target_state` | `0` стоп, `1` старт, `2` пауза, `3` на базу |
| `roborock/saros10r/set/selected_areas` | `[1,4]`, `1,4` или `Кухня, Ванная` |
| `roborock/saros10r/set/suction`, `set/water`, `set/clean_mode` | Значения из списков SprutHub |
| `roborock/saros10r/set/command` | `start`, `pause`, `stop`, `home`, `locate`, `resolve_error` |
| `roborock/saros10r/set/rooms_start` | `{"rooms":"Кухня","fan":3,"water":3,"mode":3}` — атомарный старт одним сообщением |

Кроме MQTT служба отдаёт по HTTP (порт 8590): `/state` — состояние, карту и маршрут (для 3D-плана квартиры), `/cmd` — команды, `/events` — журнал событий, `/conf` (GET/POST) — настройки, `POST /restart` — самоперезапуск. Для SprutHub это не обязательно, но на этот же API опирается панель плагина `homebridge-roborock-panel`.

---

## Ограничения

- Камера робота недоступна: python-roborock её не поддерживает.
- Прогресс и оставшееся время в SprutHub не заполняются: робот их не отдаёт.
- Код режима «сначала сухая, потом влажная» у Roborock пока не выяснен. В SprutHub под этим пунктом сейчас работает «сухая и влажная одновременно».

---

## Авторы

Шаблон и служба: [Andreytmbmg](https://github.com/Andreytmbmg).

Доработка службы v1.1–v1.2 (атомарный старт уборки, настройки в INI, журнал событий, HTTP API `/conf` и `/restart`) и панель HomeBridge `homebridge-roborock-panel` — при участии **Kimi (Moonshot AI)**.
