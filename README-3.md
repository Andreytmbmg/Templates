# VAKIO Base Smart — шаблон MQTT-устройства для Спрут.Хаб (SprutHub)

Готовый шаблон для подключения рекуператора **VAKIO Base Smart** к умному дому **Спрут.Хаб (SprutHub, СХ)** по протоколу **MQTT**. Позволяет управлять приточно-вытяжной вентиляцией из интерфейса СХ, Apple Home (HomeKit) и сценариев автоматизации.

> English: SprutHub MQTT device template for the VAKIO Base Smart recuperator (heat recovery ventilator). Control fan speed, work mode and power from SprutHub and Apple HomeKit.

![Скриншот устройства в Спрут.Хаб](images/screenshot.png)

## Возможности

- Включение и выключение рекуператора
- Регулировка скорости вентилятора
- Выбор режима работы (приток, вытяжка, рекуперация и др.) через список источников, как у телевизора в HomeKit (сервис Television / InputSource, `ActiveIdentifier`)
- Отображение имени режима через `ConfiguredName`
- Корректная работа без retain-топиков
- Совместимость со сценариями СХ (например, управление скоростью по CO₂)

## Требования

- Спрут.Хаб с поддержкой MQTT-шаблонов
- Рекуператор VAKIO Base Smart, подключённый к MQTT-брокеру
- MQTT-брокер (встроенный в СХ или внешний, например Mosquitto)

## Установка

1. Скачайте файл [`VAKIO_Base_Smart.json`](VAKIO_Base_Smart.json) или возьмите его из раздела [Releases](../../releases).
2. В Спрут.Хаб откройте **Настройки → Шаблоны** и импортируйте файл.
3. Добавьте новое MQTT-устройство и выберите шаблон **VAKIO Base Smart**.
4. Укажите базовый топик вашего рекуператора: `<ваш_топик>`.

## MQTT-топики

| Функция | Топик состояния | Топик управления |
|---|---|---|
| Питание | `<topic>/state` | `<topic>/state/set` |
| Скорость | `<topic>/speed` | `<topic>/speed/set` |
| Режим | `<topic>/workmode` | `<topic>/workmode/set` |

*(замените на фактические топики из шаблона)*

## Связанные сценарии

Сценарий автоматического управления качеством воздуха (CO₂, VOC, PM, ночной режим, датчики окон) для двух рекуператоров VAKIO: [Andreytmbmg/logic](https://github.com/Andreytmbmg/logic).

## Обратная связь

Нашли ошибку или есть идея — создавайте [Issue](../../issues). Если шаблон пригодился, поставьте ⭐ — так его проще найдут другие.

---

**Ключевые слова:** VAKIO, Вакио, VAKIO Base Smart, рекуператор, проветриватель, приточно-вытяжная вентиляция, Спрут.Хаб, Спрут Хаб, SprutHub, СХ, MQTT, шаблон устройства, умный дом, HomeKit, recuperator, heat recovery ventilator, smart home, home automation.
