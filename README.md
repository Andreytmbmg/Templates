# Шаблоны устройств для Спрут.Хаб (SprutHub)

Коллекция MQTT-шаблонов устройств для умного дома **[Sprut Hub](https://spruthub.ru)**. Все шаблоны проверены на реальном оборудовании и используются в работающей системе.

В этом каталоге собраны ссылки на **все шаблоны устройств** из репозиториев автора — как лежащие здесь, так и входящие в комплекты логических и глобальных сценариев.

---

## 📦 Шаблоны в этом репозитории

| Устройство | Подключение | Шаблон | Документация |
|---|---|---|---|
| 🌦 **Shelly / Ecowitt WS90** — метеостанция | Zigbee2MQTT | [Шаблон устройства - mqtt (Shelly) + Ecowitt WS90.json](WS90/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28Shelly%29%20%2B%20Ecowitt%20WS90.json) | [README](WS90/README.MD) |
| 🌫 **Tuya CO2BJ** — монитор качества воздуха | HomeBridge MQTT (через патч `homebridge-tuya`) | [Шаблон устройства - mqtt (Tuya) + CO2BJ.json](CO2BJ/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28Tuya%29%20%2B%20CO2BJ.json) | [README](CO2BJ/README.md) |
| 🔢 **ptvo_counter_2ch** — двухканальный счётчик импульсов (Custom devices DiY) | Zigbee2MQTT | [ptvo_counter_2ch.json](ptvo_counter_2/ptvo_counter_2ch.json) | [README](ptvo_counter_2/README.md) |
| 🧹 **Roborock Saros 10R** — робот-пылесос (сервис «Пылесос») | MQTT (служба `roborock_svc` на python-roborock) | [Шаблон устройства - mqtt (roborock_svc) + Roborock Saros 10R.json](Roborock/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28roborock_svc%29%20%2B%20Roborock%20Saros%2010R.json) | [README](Roborock/README.md) |
| 🔌 **CUKTECH 10 GaN Charger Ultra (AD1204)** — зарядка 4 порта | MQTT (BLE-мост `cuktech-ble-server-lite`) | [Шаблон устройства - mqtt (cuktech-ble-server) + CUKTECH 10 GaN Ultra.json](CUKTECH/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28cuktech-ble-server%29%20%2B%20CUKTECH%2010%20GaN%20Ultra.json) | [README](CUKTECH/README.md) |
| 🔊 **LG S95TR** — саундбар 9.1.5 | MQTT (мост `lgsb_bridge` по локальному протоколу LG) | [Шаблон устройства - mqtt (lgsb_bridge) + LG S95TR.json](LG_S95TR/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28lgsb_bridge%29%20%2B%20LG%20S95TR.json) | [README](LG_S95TR/README.md) |

## 🔗 Шаблоны в репозитории [logic](https://github.com/Andreytmbmg/logic)

Эти шаблоны входят в комплекты с логическими сценариями и лежат рядом с ними.

| Устройство | Подключение | Шаблон | Используется в сценарии |
|---|---|---|---|
| 💨 **VAKIO Base Smart** — рекуператор | MQTT | [Шаблон устройства - MQTT (VAKIO) + Base Smart.json](https://github.com/Andreytmbmg/logic/blob/main/Recuperator/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20MQTT%20%28VAKIO%29%20%2B%20Base%20Smart.json) | [Рекуператор](https://github.com/Andreytmbmg/logic/tree/main/Recuperator) |
| 💨 **VAKIO Base Smart + учёт фильтра** — рекуператор со счётчиками воздуха и ресурсом фильтра F7 | MQTT | [VAKIO_Base_Smart_with_Filter_v6.json](https://github.com/Andreytmbmg/logic/blob/main/Recuperator/filter_f7/VAKIO_Base_Smart_with_Filter_v6.json) | [Фильтр рекуператора](https://github.com/Andreytmbmg/logic/tree/main/Recuperator/filter_f7) |
| ❄️ **Lytko 102** — кондиционер | MQTT | [Шаблон_устройства_-_MQTT_(Lytko)_102_v7.json](https://github.com/Andreytmbmg/logic/blob/main/Conditioner/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD_%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0_-_MQTT_%28Lytko%29_102_v7.json) | [Кондиционер](https://github.com/Andreytmbmg/logic/tree/main/Conditioner) |

> 📘 **Как подключить VAKIO Base Smart к MQTT-брокеру.** Шаблоны VAKIO работают через MQTT, поэтому рекуператор сначала нужно привязать к вашему брокеру. Инструкция есть в официальном репозитории производителя: [vakio-ru/vakio_base_smart](https://github.com/vakio-ru/vakio_base_smart#connect) (раздел «Подключение прибора к брокеру»). Сам репозиторий — интеграция для Home Assistant, но шаг подключения к брокеру общий и для Спрут.Хаб.

---

## Кратко о шаблонах

**Shelly / Ecowitt WS90.** Температура, влажность, давление в мм рт. ст., освещённость, УФ-индекс, скорость, порывы и направление ветра, осадки, датчик дождя, точка росы, ощущаемая температура, ветроохлаждение, Humidex, тренд давления, батарея и статус связи с Zigbee2MQTT. В каталоге также лежат вспомогательные сценарии для средней скорости ветра и среднего УФ-индекса.

**Tuya CO2BJ.** CO₂, температура, влажность, PM1.0, PM2.5, PM10, TVOC, формальдегид и AQI. Каждый показатель качества воздуха вынесен в отдельный сервис, чтобы HomeKit давал оценку по каждому. Данные берутся из облачного push-канала Tuya: небольшой патч плагина `homebridge-tuya` пересылает их в локальный MQTT-брокер.

**ptvo_counter_2ch.** Два импульсных счётчика с возможностью записи начальных показаний (например, для воды в м³), реле L6, уровень и напряжение батареи, качество связи.

**Roborock Saros 10R.** Родной сервис «Пылесос»: состояние, команды старт/пауза/стоп/на базу, режим уборки, мощность, вода, ошибки робота и станции, выбор комнат списком и текущая комната, батарея. Данные даёт небольшая служба на python-roborock, которая работает в локальной сети и публикует их в MQTT; пароль от аккаунта Roborock не хранится.

**CUKTECH 10 GaN Charger Ultra.** Четыре порта (C1, C2, C3, USB-A) как розетки: включение и выключение порта, «используется», мощность, напряжение, ток и протокол зарядки (PD, PPS, QC…). Плюс текущий режим зарядки, «USB-A всегда включён», гашение и блокировка поворота экрана. Данные идут локально по Bluetooth, без облака Xiaomi: мост на Linux-хосте (здесь — ТВ-приставка RK3318) подключается к зарядке и публикует их в MQTT.

**LG S95TR.** Питание, громкость и mute, звуковые режимы как источники ТВ, выбор входа, тон (ВЧ/СЧ/НЧ), уровни сабвуфера и всех динамиков, DRC, Neural:X, ночной режим, автогромкость, AV Sync, Dialog Control, голосовое сопровождение и индикатор. Работает локально, без облака LG: мост на Linux-хосте общается с саундбаром по протоколу приложения LG Sound Bar (TCP 9741) и публикует данные в MQTT.

**VAKIO Base Smart.** Включение, скорость вентилятора и выбор режима работы: приток, приток MAX, рекуперация лето/зима, вытяжка, вытяжка MAX, ночной. Режимы реализованы через сервис Television / InputSource, поэтому в Apple Home выбираются из списка.

**VAKIO Base Smart + учёт фильтра.** Всё то же, плюс счётчики прокачанного воздуха по режимам и индикаторы ресурса фильтра (механика F7, угольный слой, общий износ, срок службы) для сценария Filter Monitor.

**Lytko 102.** Термостат с режимами и скоростью вентилятора, качание жалюзи по положениям, подсветка, зуммер, режимы «Здоровье» и «Сон», блокировка пульта, самоочистка, уличная температура и код ошибки.

---

## Установка шаблона

1. Откройте нужный шаблон по ссылке и скачайте файл (кнопка **Download raw file**).
2. В Спрут.Хаб импортируйте шаблон в разделе шаблонов устройств.
3. Добавьте MQTT-устройство и выберите импортированный шаблон.
4. Для Zigbee2MQTT-устройств включите публикацию атрибутов по отдельным топикам: `advanced.output: "attribute"` или `"attribute_and_json"`.

---

## Другие репозитории

- **[logic](https://github.com/Andreytmbmg/logic)** — логические сценарии: рекуператор по качеству воздуха, учёт фильтра, кондиционер.
- **[global](https://github.com/Andreytmbmg/global)** — глобальные и блочные сценарии: отопление OpenTherm, виртуальные термостаты, погода Yr.no. Шаблонов устройств там нет.

---

## Полезные ссылки

- [vakio-ru/vakio_base_smart](https://github.com/vakio-ru/vakio_base_smart) — официальный репозиторий VAKIO Base Smart: подключение к MQTT-брокеру, интеграция для Home Assistant.
- [Zigbee2MQTT](https://www.zigbee2mqtt.io) — документация по Zigbee2MQTT (для WS90 и ptvo_counter_2ch).

---
Нашли ошибку или хотите предложить шаблон — создавайте [Issue](../../issues). Если шаблон пригодился, поставьте ⭐.

**Ключевые слова:** Спрут.Хаб, Спрут Хаб, SprutHub, СХ, шаблон устройства, MQTT, Zigbee2MQTT, VAKIO, Вакио, Base Smart, рекуператор, Lytko, кондиционер, Shelly WS90, Ecowitt WS90, метеостанция, ptvo_counter_2ch, счётчик импульсов, Tuya, CO2BJ, co2bj, монитор качества воздуха, датчик CO2, PM2.5, формальдегид, homebridge-tuya, CUKTECH, Cuktech 10, AD1204, njcuk.fitting.ad1204, зарядное устройство, GaN, BLE, Bluetooth, LG, S95TR, S90T, саундбар, soundbar, Dolby Atmos, LG Sound Bar, temescal, умный дом, HomeKit, smart home, home automation, device template.
