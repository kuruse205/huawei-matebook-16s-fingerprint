# Huawei MateBook 16s (CREFG) — сканер отпечатков Goodix GDIX51C0 под Linux

Исследование, как найти и «разбудить» встроенный сканер отпечатков (кнопка
питания, чип Goodix, ACPI ID `GDIX51C0`) на Huawei MateBook 16s под Arch
Linux. Репозиторий — полный разбор: где сенсор прячется, как его увидеть,
как поднять ему питание, и на каком стене упёрлись в конец.

## TL;DR — статус

| Что | Статус |
|---|---|
| Сенсор объявлен в ACPI (`Device (SPBA)`, `_HID GDIX51C0`) | ✅ да |
| Гейт включения в BIOS (`HFTE`) уже открыт | ✅ да |
| Устройство энумерируется ядром: `/sys/bus/spi/devices/spi-GDIX51C0:00` | ✅ да |
| Драйвера под Linux | ❌ нет ни mainline, ни сторонних |
| Питание/ресет через GPIO | ⚠️ найдены линии (321/140), подняты вручную |
| Разговор по SPI | ❌ блокер: пады CS/MOSI не замуксованы в SPI-режим и залочены BIOS'ом; сенсор на них не отвечает |

**Итог:** сенсор под Linux на этой машине пока не работает. Всё, что ниже —
карта территории для тех, кто доделает (включая будущее меня).

## Ключевые находки (декодировано из DSDT)

Сканер сидит **на SPI, а не на USB** — поэтому в `lsusb` его не видно
никогда. Он объявлен в DSDT как `Device (SPBA)` под `_SB.PC00.SPI0`
(Intel LPSS SPI, PCI `00:1e.2`, в Linux это `spi1`), 10 МГц, mode 0.

Пины GPIO кодируются в DSDT как `0x0900_0000 | (группа << 16) | линия`;
таблица `GPCL` (см. `acpi_GPCL_gpio_table.dsl`) даёт базу каждой группы в
глобальной нумерации gpiochip0 (INTC1055, 360 линий):

| Назначение | Код из DSDT | Группа | Линия | Глобальный GPIO |
|---|---|---|---|---|
| IRQ сенсора (`GpioInt`, он же поднимается `_INI`) | `0x090E0001` | 14 | 1 | **321** |
| Ресет/выход (`GpioIo`) | `0x0907000C` | 7 | 12 | **140** |
| CS шины SPI (`GSPI0_CS0B`) | — | 0 | 15 | **15** |
| CLK шины SPI (`GSPI0_CLK`) | — | 0 | 16 | **16** |
| MISO шины SPI (`GSPI0_MISO`) | — | 0 | 17 | **17** |
| MOSI шины SPI (`GSPI0_MOSI`) | — | 0 | 18 | **18** |

`_STA` устройства возвращает «присутствует», только если байт `HFTE`
(OperationRegion `OGNS` в SystemMemory) ненулевой — на этой машине он уже
включён, ничего в BIOS менять не нужно.

Протокол (из [Metrohan/gxfp5130-linux](https://github.com/Metrohan/gxfp5130-linux),
у них MateBook D16 с сенсором за EC-eSPI-мэйлбоксом):

```
Goodix-кадр:  [cmd][len:2 LE][payload len-1 байт][ck]
              ck = (0xAA - (cmd + len_lo + len_hi + Σpayload)) & 0xFF
MP-кадр:      [тип<<4][len:2 LE][ck]  ck = (b0+b1+b2) & 0xFF, типы A/B/C
Версия FW:    cmd 0xA8, payload [0x01] -> ответ cmd 0xA8 с ASCII-версией
```

## Полная история исследования (можно повторить пошагово)

### 1. Убедиться, что сенсор есть в системе

```bash
ls /sys/bus/spi/devices/          # spi-GDIX51C0:00 — вот он
cat /sys/bus/spi/devices/spi-GDIX51C0:00/uevent   # MODALIAS=acpi:GDIX51C0:...
readlink /sys/bus/spi/devices/spi-GDIX51C0:00/driver  # пусто — драйвера нет
```

### 2. Дать пользователям доступ к SPI-шине

```bash
sudo modprobe spidev
echo spidev | sudo tee /sys/bus/spi/devices/spi-GDIX51C0:00/driver_override
echo spi-GDIX51C0:00 | sudo tee /sys/bus/spi/drivers/spidev/bind
sudo chmod 666 /dev/spidev1.0
```

Теперь шина сенсора доступна из userspace как `/dev/spidev1.0`.

### 3. Поднять питание и снять ресет (реплика ACPI `_INI`)

```bash
sudo pacman -S libgpiod
sudo gpioset -c gpiochip0 321=1     # линия, которую _INI дёргает первой
sleep 0.01
sudo gpioset -c gpiochip0 140=1     # вторая линия из _INI
sudo gpioget -c gpiochip0 321 140   # обе должны быть active
```

После этого сенсор запитан (в `_INI` BIOS делает ровно эти два вызова
`SHPO(pin, 1)`, но по факту после загрузки линии стоят в нуле).

### 4. Прогнать зонд

```bash
sudo python3 probe.py /dev/spidev1.0 --speed 1000000
sudo python3 probe.py /dev/spidev1.0 --speed 10000000
# вариант с ручным chip-select (пин CS застрял в GPIO-режиме):
sudo python3 probe.py /dev/spidev1.0 --gpio-cs 15
```

Зонд отправляет только read-only запросы (версия прошивки) и печатает
hexdump ответа с разбором MP/Goodix-кадров. **На этом этапе ответа нет —
см. ниже, почему.**

### 5. Диагностика пинов SPI (та самая стена)

```bash
sudo cat /sys/kernel/debug/pinctrl/INTC1055:00/pins | grep GSPI
```

Ожидаемое (и наблюдаемое) на CREFG:

```
pin 15 (GSPI0_CS0B) GPIO 0x80800102 [LOCKED full, ACPI]
pin 16 (GSPI0_CLK)  mode 2 [LOCKED full, ACPI]
pin 17 (GSPI0_MISO) mode 2 [LOCKED full, ACPI]
pin 18 (GSPI0_MOSI) GPIO 0x84000300 [LOCKED full]
```

CLK/MISO уже в SPI-режиме, а **CS и MOSI остались в GPIO-режиме, и все
четыре пада залочены** (`PADCFGLOCK`) — перепрограммировать их нельзя ни
через pinctrl, ни через `/dev/mem` (на Arch `CONFIG_IO_STRICT_DEVMEM=y`).
Мы пробовали: ручной GPIO-CS (проход 4) + родной CLK/MISO — сенсор MISO
не драйвит вообще. Похоже, физически сенсор подключён не к этим падам
(общий BIOS для разных SKU), либо нужен ещё один «включатель», которого
нет в ACPI.

`remux_gspi.py` — попытка перемуксовать пады 15/18 напрямую через MMIO
(PCR 0xFD000000 + 0x6E0000 + 0x0700 + пин*8). На стоковом Arch-ядре не
работает (`Operation not permitted`), оставлен для ядер без STRICT_DEVMEM
и для документации адресов.

## Что дальше (для продолжающих)

1. **Ядро без STRICT_DEVMEM / своя сборка**: прогнать `remux_gspi.py` —
   если пады перейдут в mode 2, зонд может оживить шину (CS/MOSI
   аппаратно залочены — возможно, запись молча игнорируется даже там;
   тогда не судьба).
2. **Снять дамп с Windows-стороны**: на живом Windows-драйвере Goodix
   посмотреть, какие пады он муксует и куда реально идут CS/MISO
   (например, через ReTimer/мультиплексор). Это ответит на вопрос
   «врёт ли DSDT про SPI0».
3. **Реверс EC-протокола**: на старших MateBook (D16 2024) сенсор висит
   за EC (eSPI-мэйлбокс, MMIO-окно в `_CRS`). На 16s такого окна в ACPI
   нет, EC — классический порт-ный PNP0C09 (порты 62/66). Если сенсор
   физически сидит на EC — путь один: реверсить протокол Huawei EC.
4. Если заведётся — база для драйвера уже есть: транспорт из
   [gxfp5130-linux](https://github.com/Metrohan/gxfp5130-linux)
   (DKMS-модуль + libfprint-форк с SIGFM + PAM), у них хороший roadmap.

## Безопасность и откат

- `probe.py` шлёт только запросы чтения; записей во флеш сенсора нет,
  брикнуть нечем.
- `driver_override`, привязка spidev и значения GPIO живут до
  перезагрузки: **одна перезагрузка полностью откатывает всё**.
- На этой машине **нельзя включать deep-сон** (`mem_sleep=deep`):
  S3-сон на прошивке CREFG намертво вешает ноут (проверено, спасает
  только долгое удержание кнопки питания). Только s2idle (дефолт).

## Файлы

- `probe.py` — зонд SPI (чистый Python 3, без зависимостей; ioctl к
  spidev + GPIO v2 uapi для ручного CS)
- `remux_gspi.py` — перемуксовка падов GSPI0 через /dev/mem (для ядер
  без STRICT_DEVMEM), с проверкой «отпечатков» перед записью
- `acpi_SPBA_device.dsl` — узел сенсора из DSDT (SPBA/GDIX51C0)
- `acpi_GPCL_gpio_table.dsl` — таблица GPIO-групп/баз из DSDT

## Благодарности и лицензия

Протокол и структура кадров — из проекта
[Metrohan/gxfp5130-linux](https://github.com/Metrohan/gxfp5130-linux)
(GPL-2.0, форк Void755). Код здесь — GPL-2.0.
