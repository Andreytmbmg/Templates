# Зарядка CUKTECH 10 GaN Charger Ultra (AD1204) для SprutHub через BLE → MQTT

Шаблон устройства **CUKTECH 10 GaN Charger Ultra** (`njcuk.fitting.ad1204`) для **SprutHub**. Данные идут **локально по Bluetooth LE**, без облака Xiaomi. Мост [cuktech-ble-server-lite](https://github.com/yanjing19989/cuktech-ble-server-lite) подключается к зарядке и публикует её состояние в MQTT-брокер SprutHub.

Способ актуален, если:
- зарядка добавлена в SprutHub через контроллер Xiaomi, но данных нет: `gattPollingSupported: false`, «No accessories have been created from the template»;
- даже через BLE-шлюз Xiaomi `get_properties` не отвечает;
- рядом с зарядкой есть Linux-машина с Bluetooth (здесь это ТВ-приставка RK3318 на Armbian).

Официальная поддержка в SprutHub: [sprut/Hub#4697](https://github.com/sprut/Hub/issues/4697).

---

## Что умеет шаблон

| Сервис | Характеристики |
|---|---|
| Порт C1 / C2 / C3 / USB-A (`Outlet`) | вкл/выкл порта, «используется», мощность (Вт), напряжение (В), ток (А), протокол (PD/PPS/QC/…) |
| Режим зарядки | текущий режим: AI / Apple / Single / Balance |
| USB-A всегда включён | `Switch` |
| Гасить экран без нагрузки | `Switch` |
| Блокировка поворота экрана | `Switch` |
| Информация | `C_Online`: мост подключён и авторизован |

---

## Требования

- SprutHub с MQTT-брокером: нужны его IP-адрес и порт (смотрите в настройках MQTT-контроллера SprutHub)
- Linux-хост с Bluetooth LE в радиусе действия зарядки
- MiOT **TOKEN** зарядки: 24 hex-символа. Нужен именно TOKEN, BLE KEY не подходит
- Пока работает мост, приложение Mi Home не должно держать BLE-подключение к зарядке: она принимает только одного клиента

---

## Шаг 1. Bluetooth на RK3318 (Armbian)

На приставках с модулем **AP6330 (BCM4330)** Bluetooth есть, но по умолчанию выключен.

```bash
# проверить модуль и наличие прошивки
ls /lib/firmware/brcm/ | grep -i 4330          # нужен BCM4330B1.hcd

# включить оверлей (Wi-Fi + BT на uart0)
sudo cp /boot/armbianEnv.txt /boot/armbianEnv.txt.bak
echo "overlays=rk3318-box-wlan-ap6330" | sudo tee -a /boot/armbianEnv.txt
sudo reboot        # если программная перезагрузка зависнет, перезагрузите по питанию
```

После загрузки:

```bash
dmesg | grep -i bluetooth     # hci0: BCM4330B1 ... Patch
```

BlueZ. На Debian bullseye пакеты из `bullseye-security` удалены, поэтому ставим из основного репозитория:

```bash
sudo apt install -y bluez/bullseye libasound2/bullseye libasound2-data/bullseye
sudo btmgmt -i hci0 power on
sudo timeout 20 bluetoothctl scan on | grep -i <MAC зарядки>
```

> Сообщение `Using default device address (43:30:b1:00:00:00)` на работу не влияет. Сменить адрес через `btmgmt public-addr` нельзя (`Rejected`), но сканирование и подключение работают.

---

## Шаг 2. Установка моста

Мосту нужен Python ≥ 3.10, а в bullseye только 3.9. Поэтому ставим отдельный Python через `uv`: системный Python и Homebridge это не затрагивает.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env

sudo mkdir -p /opt/cuktech && sudo chown $USER /opt/cuktech
git clone https://github.com/yanjing19989/cuktech-ble-server-lite /opt/cuktech/server
cd /opt/cuktech/server
uv venv --python 3.12 .venv
uv pip install --python .venv -e .
```

---

## Шаг 3. Токен зарядки

```bash
cd /opt/cuktech
git clone https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor extractor
cd extractor
uv run --python 3.12 --with-requirements requirements.txt token_extractor.py
```

Войдите в аккаунт: удобнее по QR-коду (`q`). Выберите сервер, на котором зарядка в Mi Home (обычно `cn`). Из блока `CUKTECH 10 GaN Charger Ultra` возьмите поле **TOKEN**.

---

## Шаг 4. Конфиг

```bash
sudo mkdir -p /etc/cuktech
sudo tee /etc/cuktech/config.yaml >/dev/null <<'EOF'
ble:
  mac: "<MAC зарядки>"       # формат AA:BB:CC:DD:EE:FF, есть в выводе token_extractor
  token: "<TOKEN>"           # 24 hex-символа из поля TOKEN (не BLE KEY)
mqtt:
  host: "<IP MQTT-брокера>"  # только IP, без порта, например "192.168.1.10"
  port: <порт брокера>       # число без кавычек, например 1883
  username: ""               # логин брокера, если нет — оставить ""
  password: ""               # пароль брокера, если нет — оставить ""
  topic_prefix: "cuktech/charger"
  keepalive: 60
server:
  host: "0.0.0.0"
  port: 8199
  reconnect_base: 1.0
  reconnect_max: 300.0
  command_timeout: 10.0
  protocol_refresh_interval: 600.0
  port_verify_interval: 15.0
  port_stale_timeout: 45.0
  log_level: "INFO"
EOF
sudo chmod 600 /etc/cuktech/config.yaml
sudo chown $USER /etc/cuktech/config.yaml
```

Проверка вручную:

```bash
cd /opt/cuktech/server
CUKTECH_CONFIG_PATH=/etc/cuktech/config.yaml .venv/bin/cuktech-server
```

В брокере должны появиться топики `cuktech/charger/...`.

---

## Шаг 5. Служба systemd

Скопируйте [`cuktech-ble.service`](cuktech-ble.service) в `/etc/systemd/system/` и замените в нём:

- `<пользователь>` — пользователь, под которым запускаете мост (тот, кто владеет `/opt/cuktech`; проверить: `whoami`);
- `<MAC зарядки>` — MAC вашей зарядки в двух строках `bluetoothctl disconnect`.

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cuktech-ble
sudo journalctl -u cuktech-ble -f
```

> **Важно.** Если процесс моста остановить без закрытия соединения, BlueZ может продолжать держать BLE-подключение. Зарядка тогда перестаёт рекламировать себя, а мост пишет `Device with address ... was not found`. Строки `ExecStartPre` / `ExecStopPost` в службе обрывают такое подключение. Вручную: `sudo bluetoothctl disconnect <MAC>`.

---

## Шаг 6. Шаблон в SprutHub

1. Импортируйте `Шаблон устройства - mqtt (cuktech-ble-server) + CUKTECH 10 GaN Ultra.json` в каталог шаблонов контроллера MQTT.
2. Добавьте устройство с ID **`cuktech/charger`**.

---

## MQTT-топики моста

| Топик | Направление | Содержимое |
|---|---|---|
| `cuktech/charger/port/c1` … `/c3`, `/a` | ← | `{"active":true,"voltage":9.0,"current":2.1,"power":18.9,"protocol":"PD","raw_protocol":7}` |
| `cuktech/charger/settings` | ← | `{"5":1,"15":1,"16":15,...}`: piid → значение |
| `cuktech/charger/status` | ← | `{"connected":true,"authenticated":true,...}` (Last Will) |
| `cuktech/charger/port` | → | `{"port":"c1","action":"on"}` |
| `cuktech/charger/set` | → | `{"piid":5,"value":3}` |

Основные piid (siid 2):

| piid | Назначение |
|---|---|
| 5 | Режим: 1 AI, 2 Apple, 3 Single, 4 Balance |
| 15 | USB-A всегда включён |
| 16 | Битовая маска портов: bit0 C1, bit1 C2, bit2 C3, bit3 A (1 = включён) |
| 19 | Гасить экран без нагрузки |
| 20 | Блокировка поворота экрана |

Режим можно сменить из сценария SprutHub, отправив `{"piid":5,"value":N}` в `cuktech/charger/set`.

---

## Благодарности

- [kairui1108/cuktech-ble-ha-integration](https://github.com/kairui1108/cuktech-ble-ha-integration): исходный разбор протокола и интеграция для Home Assistant
- [yanjing19989/cuktech-ble-server-lite](https://github.com/yanjing19989/cuktech-ble-server-lite): BLE → MQTT мост
- [PiotrMachowski/Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor)
