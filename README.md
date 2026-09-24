# Шаблоны устройств для Спрут.Хаб (SprutHub)

Коллекция MQTT-шаблонов устройств для умного дома **[Sprut Hub](https://spruthub.ru)**. Все шаблоны проверены на реальном оборудовании и используются в работающей системе.

В этом каталоге собраны ссылки на **все шаблоны устройств** из репозиториев автора — как лежащие здесь, так и входящие в комплекты логических и глобальных сценариев.

---

## 📦 Шаблоны в этом репозитории

| Устройство | Подключение | Шаблон | Документация |
|---|---|---|---|
| 🌦 **Shelly / Ecowitt WS90** — метеостанция | Zigbee2MQTT | [Шаблон устройства - mqtt (Shelly) + Ecowitt WS90.json](WS90/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28Shelly%29%20%2B%20Ecowitt%20WS90.json) | [README](WS90/README.MD) |
| 🌫 **Tuya CO2BJ** — монитор качества воздуха | HOMEBRIDGE MQTT (через патч `homebridge-tuya`) | [Шаблон устройства - mqtt (Tuya) + CO2BJ.json](CO2BJ/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20mqtt%20%28Tuya%29%20%2B%20CO2BJ.json) | [README](CO2BJ/README.md) |
| 🔢 **ptvo_counter_2ch** — двухканальный счётчик импульсов (Custom devices DiY) | Zigbee2MQTT | [ptvo_counter_2ch.json](ptvo_counter_2/ptvo_counter_2ch.json) | [README](ptvo_counter_2/README.md) |

## 🔗 Шаблоны в репозитории [logic](https://github.com/Andreytmbmg/logic)

Эти шаблоны входят в комплекты с логическими сценариями и лежат рядом с ними.

| Устройство | Подключение | Шаблон | Используется в сценарии |
|---|---|---|---|
| 💨 **VAKIO Base Smart** — рекуператор | MQTT | [Шаблон устройства - MQTT (VAKIO) + Base Smart.json](https://github.com/Andreytmbmg/logic/blob/main/Recuperator/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0%20-%20MQTT%20%28VAKIO%29%20%2B%20Base%20Smart.json) | [Рекуператор](https://github.com/Andreytmbmg/logic/tree/main/Recuperator) |
| 💨 **VAKIO Base Smart + учёт фильтра** — рекуператор со счётчиками воздуха и ресурсом фильтра F7 | MQTT | [VAKIO_Base_Smart_with_Filter_v6.json](https://github.com/Andreytmbmg/logic/blob/main/Recuperator/filter_f7/VAKIO_Base_Smart_with_Filter_v6.json) | [Фильтр рекуператора](https://github.com/Andreytmbmg/logic/tree/main/Recuperator/filter_f7) |
| ❄️ **Lytko 102** — кондиционер | MQTT | [Шаблон_устройства_-_MQTT_(Lytko)_102_v7.json](https://github.com/Andreytmbmg/logic/blob/main/Conditioner/%D0%A8%D0%B0%D0%B1%D0%BB%D0%BE%D0%BD_%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B8%CC%86%D1%81%D1%82%D0%B2%D0%B0_-_MQTT_%28Lytko%29_102_v7.json) | [Кондиционер](https://github.com/Andreytmbmg/logic/tree/main/Conditioner) |

---

## Кратко о шаблонах

**Shelly / Ecowitt WS90.** Температура, влажность, давление в мм рт. ст., освещённость, УФ-индекс, скорость, порывы и направление ветра, осадки, датчик дождя, точка росы, ощущаемая температура, ветроохлаждение, Humidex, тренд давления, батарея и статус связи с Zigbee2MQTT. В каталоге также лежат вспомогательные сценарии для средней скорости ветра и среднего УФ-индекса.

**Tuya CO2BJ.** CO₂, температура, влажность, PM1.0, PM2.5, PM10, TVOC, формальдегид и AQI. Каждый показатель качества воздуха вынесен в отдельный сервис, чтобы HomeKit давал оценку по каждому. Данные берутся из облачного push-канала Tuya: небольшой патч плагина `homebridge-tuya` пересылает их в локальный MQTT-брокер.

**ptvo_counter_2ch.** Два импульсных счётчика с возможностью записи начальных показаний (например, для воды в м³), реле L6, уровень и напряжение батареи, качество связи.

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

Нашли ошибку или хотите предложить шаблон — создавайте [Issue](../../issues). Если шаблон пригодился, поставьте ⭐.

**Ключевые слова:** Спрут.Хаб, Спрут Хаб, SprutHub, СХ, шаблон устройства, MQTT, Zigbee2MQTT, VAKIO, Вакио, Base Smart, рекуператор, Lytko, кондиционер, Shelly WS90, Ecowitt WS90, метеостанция, ptvo_counter_2ch, счётчик импульсов, Tuya, CO2BJ, co2bj, монитор качества воздуха, датчик CO2, PM2.5, формальдегид, homebridge-tuya, умный дом, HomeKit, smart home, home automation, device template.
