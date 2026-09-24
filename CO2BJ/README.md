# Монитор качества воздуха Tuya (CO2BJ) для SprutHub через патч Homebridge

Шаблон устройства **Tuya CO2BJ (монитор качества воздуха)** для **SprutHub**, подключаемый через **облачный MQTT-поток Tuya**, который "перехватывается" внутри плагина `tuya-homebridge` небольшим патчем и republish'ится в локальный MQTT-брокер.

Способ актуален, если:
- Устройство подключено через официальный плагин `@homebridge-plugins/homebridge-tuya`
- Подписка Tuya IoT Core (Cloud Development) недоступна/истекла и её нельзя оформить заново, но **облачный push-канал MQTT** (`TuyaOpenMQ`) продолжает получать данные с устройства
- Локальный `local_key` устройства недоступен или получать его через отдельные сторонние инструменты нежелательно

---

## Идея способа

Плагин `homebridge-tuya` внутри себя подключается к облачному MQTT Tuya и получает push-уведомления об изменении статуса устройства (`TuyaOpenMQ._onMessage`). Из-за проблем с подпиской REST API устройство может не появляться как HomeKit-аксессуар, но сам push-канал при этом продолжает работать.

Мы патчим файл плагина так, чтобы при получении каждого сообщения он **дополнительно** публиковал те же данные в локальный MQTT-брокер (тот же, к которому подключён SprutHub) — в топик вида:

```
tuya/{devId}/status
```

SprutHub забирает этот топик обычным MQTT-шаблоном устройства, как любое другое MQTT-устройство.

---

## Требования

- SprutHub
- Homebridge с установленным плагином `@homebridge-plugins/homebridge-tuya` (или аналогичным форком), который получает данные устройства хотя бы через MQTT push-канал (даже при нерабочей REST-подписке)
- Локальный MQTT-брокер, к которому подключены и Homebridge, и SprutHub
- Устройство категории Tuya `co2bj` (монитор качества воздуха), опубликованное через MQTT в виде JSON-массива `status`

---

## Шаг 1. Найти файл плагина

```bash
find / -type d -iname "*tuya*" 2>/dev/null
```

Обычно это:
```
/var/lib/homebridge/node_modules/@homebridge-plugins/homebridge-tuya/
```

Файл с обработчиком входящих сообщений:
```
dist/core/TuyaOpenMQ.js
```

---

## Шаг 2. Пропатчить `TuyaOpenMQ.js`

Патч добавляет:
1. Второе MQTT-подключение к локальному брокеру (создаётся в конструкторе)
2. Кэш последних известных значений по каждому `devId` — устройство Tuya часто шлёт **частичные** обновления (не все параметры разом), поэтому без кэша часть характеристик в SprutHub будет периодически "проваливаться" в 0
3. Publish в локальный брокер полного объединённого набора последних значений при каждом входящем сообщении

Выполните на устройстве с Homebridge (замените адрес брокера на свой):

```bash
python3 << 'PYEOF'
path = "/var/lib/homebridge/node_modules/@homebridge-plugins/homebridge-tuya/dist/core/TuyaOpenMQ.js"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Добавляем локальное MQTT-подключение и кэш в конструктор
old_ctor = "this.log = new Logger_1.PrefixLogger((0, Logger_1.logger)(), TuyaOpenMQ.name, debug);"
new_ctor = old_ctor + """
        this.localClient = mqtt_1.default.connect('mqtt://YOUR_BROKER_IP:PORT');
        this.tuyaStatusCache = {};"""

assert content.count(old_ctor) == 1, "Конструктор не найден или найден несколько раз — правьте вручную"
content = content.replace(old_ctor, new_ctor)

# 2. Заменяем финал _onMessage на merge + publish
old_msg = "this.log.debug('onMessage:\\ntopic = %s\\nprotocol = %s\\nmessage = %s\\nt = %s', topic, protocol, JSON.stringify(message, null, 2), t);"
new_msg = """if (this.localClient) {
            if (!this.tuyaStatusCache[message.devId]) { this.tuyaStatusCache[message.devId] = {}; }
            var _c = this.tuyaStatusCache[message.devId];
            message.status.forEach(function(s) {
                var k = (s.code !== undefined) ? s.code : Object.keys(s).filter(function(kk) { return kk !== 't'; })[0];
                _c[k] = s;
            });
            this.localClient.publish('tuya/' + message.devId + '/status', JSON.stringify(Object.keys(_c).map(function(k) { return _c[k]; })));
        }
        """ + old_msg

assert content.count(old_msg) == 1, "Строка onMessage не найдена или найдена несколько раз — правьте вручную"
content = content.replace(old_msg, new_msg)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Патч применён успешно")
PYEOF
```

**Не забудьте заменить `mqtt://YOUR_BROKER_IP:PORT`** на реальный адрес вашего локального брокера перед запуском.

Перезапустите Homebridge:
```bash
sudo systemctl restart homebridge
```

> ⚠️ Патч применяется к скомпилированному `dist/`, поэтому слетит при обновлении плагина через Homebridge UI. Если автообновления плагинов отключены (рекомендуется) — патч останется рабочим сколько угодно долго. При ручном обновлении плагина патч нужно накатить заново.

---

## Шаг 3. Проверить, что данные идут в брокер

Через MQTT Explorer (или `mosquitto_sub`) подпишитесь на:
```
tuya/#
```

Должны появиться сообщения вида:
```json
tuya/{devId}/status = [
  {"code":"co2_value","value":847,...},
  {"code":"pm25_value","value":10,...},
  {"code":"voc_value","value":392,...},
  {"code":"temp_current","value":26,...},
  {"code":"humidity_value","value":49,...},
  {"code":"ch2o_value","value":42,...},
  {"101":10},
  {"102":7},
  {"113":24}
]
```

---

## Шаг 4. Импортировать шаблон в SprutHub

Каталог → Создать шаблон MQTT → Импортировать → выбрать файл шаблона из этого репозитория.

В шаблоне укажите точный `devId` вашего устройства в `modelIds` и во всех `topicGet` (замените `bf60d78ee3be2683edds5d` на свой).

---

## Поддерживаемые параметры

| Параметр | HomeKit-характеристика | Источник (dp Tuya) |
|---|---|---|
| CO2 | `CarbonDioxideLevel` (+ автоопределение) | `co2_value` |
| Температура | `CurrentTemperature` | `temp_current` |
| Влажность | `CurrentRelativeHumidity` | `humidity_value` |
| PM2.5 | `PM2_5Density` + логика `AirQualityFromPM2_5Density` | `pm25_value` |
| PM10 | `PM10Density` + логика `AirQualityFromPM10Density` | dp `101` |
| VOC (ЛОС) | `VOCDensity` + логика `AirQualityFromVOCDensity` | `voc_value` |
| PM1.0 | `C_PM1_0Density` (кастомная характеристика СХ) + логика | dp `102` |
| Формальдегид (CH2O) | `C_FormaldehydeDensity` (кастомная, мг/м³) + логика | `ch2o_value` (мкг/м³ → делится на 1000) |
| AQI (индекс устройства) | `C_AQIDensity` (кастомная) + логика | dp `113` |

Каждый показатель — отдельный сервис `AirQualitySensor` (кроме CO2/температуры/влажности — у них свои типы сервисов), т.к. в HomeKit словесный вердикт ("Хорошее"/"Отличное") считается один на сервис, а не один на всё устройство.

dp `103` (дубль влажности) намеренно не используется — совпадает с `humidity_value`.

---

## Известные ограничения

- Зависит от того, что облачный MQTT push-канал Tuya (`TuyaOpenMQ`) продолжает работать несмотря на проблемы с REST-подпиской IoT Core — так было на момент написания, но Tuya может это изменить в любой момент
- Патч слетает при обновлении версии плагина `homebridge-tuya` — нужно применять заново
- Названия `logics` для кастомных характеристик (`AirQualityFromC_PM1_0Density`, `AirQualityFromC_FormaldehydeDensity`, `AirQualityFromC_AQIDensity`) подобраны по аналогии со стандартными (`AirQualityFromPM2_5Density` и т.п.) и не задокументированы официально — при необходимости их можно перевыбрать вручную в интерфейсе СпрутХаба (Сервис → Логика)
- Если устройство будет отвязано и привязано заново в приложении Tuya, `devId` может измениться — потребуется обновить топики в шаблоне

---

## Лицензия

MIT — используй, изменяй, делись.
