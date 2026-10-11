# Реверс виндового драйвера gfspi — рабочие заметки

Цель: узнать, как Windows общается со сканером (ACPI `GDIX51C0`), и
перенести это под Linux. Статус: драйвер добыт и распакован, первичный
триаж сделан, статанализ `gfspi.dll` — следующий шаг.

## Артефакты (не в git — копирайт Goodix/Huawei)

Локально: `_vendor/gfspi/` (добавлен в `.gitignore`)

- `gfspi.dll` (5.1 МБ) — **весь драйвер**, UMDF usermode (не ядро!)
- `gfspi.inf.txt` — INF (конвертирован из UTF-16)
- `gfspi_strings_utf16.txt` / `gfspi_strings_ascii.txt` — дампы строк
- `EngineAdapter.dll`, `AlgoChicago.dll`, `AlgoMilan.dll`,
  `SessionService.exe`, `GoodixEventLog.dll` — движок WinBio и алгоритмы
- `install.cmd` — скрипт установки (devcon по `ACPI\GDIX51*`)

Источник: consumer.huawei.com, страница MateBook 16s → Driver Download →
Fingerprint: `HUAWEI_MateBook_16s_FingerPrint_1.1.142.8` (zip → NSIS →
NSIS → файлы). DriverVer 04/22/2022.

## Что уже известно из триажа

1. INF матчит **`ACPI\GDIX51C0`** — наш сенсор; комментарий Goodix:
   «REE SPI **ST32/HC32**» (MCU сенсора — STM32 или HC32).
   Родственные ID (закомментированы в INF): `GXFP5197` «Volta ST MCU»,
   `GXFP51A0` «Wright HC MCU» — то же семейство **GXFP5xxx**, что у
   MateBook D16 (`GXFP5130`), для которого есть готовый Linux-стек
   [gxfp5130-linux](https://github.com/Metrohan/gxfp5130-linux).
2. Драйвер — **UMDF 2.15 usermode, `AllowDirectHardwareAccess`**: всю
   логику реверсим в одном usermode PE-файле.
3. Транспорт: **SPB (Windows Simple Peripheral Bus = SPI)** + GPIO.
   Строки: `gpio-io count: %d, spi count: %d, interrupt count: %d`,
   `spb failed 0x%x`, `Open Reset GPIO`, `Open write-done GPIO`,
   `Open read-done GPIO`, `Hard-reset MCU via GPIO`,
   `not support hard reset for EC projects` (значит, есть EC-варианты
   проекта и прямой-SPI варианты — наш, судя по _CRS, прямой).
4. Безопасность сенсора: **TLS-PSK на mbedtls** (статически слинкован),
   тот же PSK-флоу, что у D16 (generate/seal psk, psk cache) —
   подтверждение совместимости семейства.
5. Прошивка: строки `Begin to update firmware ...slice length %d, %d
   frames`, CRC8-проверки OTP (`Chicago*_OTP_CRC_Check`) —
   прошивка/конфиг заливается хостом или проверяется при старте.
6. Семейства сенсоров в коде: **Chicago** (ChicagoHU, ChicagoT),
   **Milan** (MilanG, MilanL), **Volta**, **Wright**, dummy.
7. `ChangeSpiSpeedSwitch` — драйвер меняет частоту SPI на лету
   (типично: медленно для boot-ROM, быстро после).

## Linux-блокер (нужно понять из драйвера!)

На Linux пады GSPI0: CLK(16)/MISO(17) в native mode 2, **CS0B(15)/MOSI(18)
залочены в GPIO-режиме** (PADCFGLOCK full, проверено — режим не
переключается). Получается, стандартный pxa2xx-spi не может слать байты.
Windows с теми же локами работает ⇒ либо Serial IO-драйвер Windows
использует другие пады/другой механизм CS, либо BIOS по-другому
инициализирует пады под Windows (ACPI-_DSM?), либо драйвер CS делает
GPIO-тогглом сам. **Это ключевой вопрос к gfspi.dll.**

## Задания для Ghidra/IDA (gfspi.dll, x86-64 PE)

Ключевые строки-якоря (искать xref'ы):

1. **Открытие устройства/ресурсов**: `"gpio-io count"` → функция парсинга
   _CRS/ресурсов WDF; что открывается: WDF SPB target? IoTarget на GUID?
   Скорость/режим SPI при открытии; логика `ChangeSpiSpeedSwitch`
   (значения частот).
2. **CS**: как притапливается chip-select — нативный SPB (SpiSerialBus
   device selection) или GPIO-тоггл вокруг трансферов? Если GPIO — какой
   пин из ресурсов.
3. **Проволочный формат**: функции рядом с `"spb failed"`, `"cont cmd
   0x%x 0x%x"`, `"!!!!bad package (checkSum not match)"` — как строится
   пакет (заголовок/магия/длина/CRC8?), полный ли аналог MP+Goodix-кадра
   из gxfp5130-linux (`[cmd][len:2][payload][ck=0xAA-Σ]` в
   `[0xA0][len:2][ck]`) или отличается для прямой SPI-шины.
4. **Boot-последовательность**: xref `"Hard-reset MCU via GPIO"` —
   тайминги ресета, первые команды, ожидаемые ответы, нужен ли
   sync-паттерн до TLS; что читается по IRQ (`interrupt count`).
5. **PSK/TLS**: соответствует ли D16-флоу (provision-psk.sh) — можно ли
   переиспользовать их userspace как есть.
6. Опционально: `EngineAdapter.dll` — где лежит PSK на Windows (DPAPI?),
   пригодится для миграции ключа (не критично — Windows нет).

## Связка с D16-стеком

Если формат кадра совпадёт (ожидаемо), план порта:

1. Транспорт: маленький kernel-модуль ИЛИ spidev (если победим мукс) —
   обмен кадрами.
2. Верх: userspace из gxfp5130-linux (TLS-PSK, capture) + libfprint-форк
   (SIGFM) + fprintd/PAM.

## Журнал находок

- 2026-10-12: драйвер скачан с сайта Huawei, распакован (zip→NSIS→NSIS),
  INF/строки задамплены, этот файл создан.
- 2026-10-12 (глубокая ночь): **Ghidra-автокопание** (headless 75с,
  проект `~/Tools/ghidra_projects/gxfp`, скрипт MineStringXrefs.java →
  `_vendor/ghidra_export/gfspi_mined.txt`). Главные результаты:
  1. Утёкли пути исходников Goodix: `f:\git\huawei_win\winfpcode\
     milan_watt\milanspi\{common\peripheral.c, private.c,
     milanfusb\device.c, milanfusb\usbhal.c}` — проект «milan_watt».
     Файл usbhal.c — наследие USB-версии, внутри уже SPI.
  2. **Транспорт = IOCTL_SPB_EXECUTE_SEQUENCE (0x41808)** в
     `SpbPeripheralExecuteSequence` (peripheral.c): WdfRequestCreate →
     WdfMemoryCreatePreallocated → WdfIoTargetFormatRequestForIoctl →
     атомарная последовательность write+read с нативным CS от SPB.
     Для Linux это эквивалент full-duplex-трансфера одним опусканием CS.
  3. **Проект-типы** (глоб. DAT_1804e12ec): 0x12 и 1 = SPI-проекты
     (наш 16s = 0x12: требует ≥1 GpioIo (reset) + GpioInt + SpiSerialBus;
     SPI открывается по connection-ID 0x12019f через FUN_1800119bc);
     0xc = мейлбокс с read-done/write-done GPIO (это D16!); 1,2 = EC;
     9/0xb/0xd/0xe/0x11 = ресет через ACPI **_DSM** (хелпер с
     '_DSM'-GUID); 4 = KB soft reset.
  4. **HardResetMcu (peripheral.c, 0x6b0-0x755)** для 0x12: WDF-GPIO
     запись `true` → Sleep(cfg+0x438) → инверсия → запись → Sleep
     (cfg+0x43c) → «Done». Полярность вероятно active-low (в _CRS
     GpioIo), т.е. физически: ресет-низ → пауза → ресет-высок.
  5. **ФОРМАТ КАДРА ПОДТВЕРЖДЁН БАЙТ-В-БАЙТ С D16** —
     `CheckPackageHead` (private.c:69-79) = `gxfp_check_mp_head`:
     тип в старшем нибле ∈ {0xA,0xB,0xC}, `ck = b0+b1+b2`, `len<0x6C00`.
  6. `SpiSendDataToDevice` (usbhal.c:0xd40+), конструирует кадр
     `calloc(payload+8)`:
     `[4B префикс (FUN_180015f44)] [flags = тип<<4 | ack<<1 (|1 если
     без ожидания)] [len_lo][len_hi] [payload] [ck]`,
     где `decl_len = payload+1`, ck при параметре-ack=1 считается
     функцией с семенем **0xAA** (FUN_1800638a0), иначе константа
     **0x88**. payload = Goodix-кадр `[cmd][data...]`.
- Осталось добить (задания для GUI-сессии): FUN_180015f44 (магия 4B
  префикса — вероятно sync-заголовок шины), FUN_1800638a0 (формула ck
  — 0xAA−Σ по всему кадру?), FUN_1800119bc (открытие SPB: установка
  частоты/режима), где применяется ChangeSpiSpeedSwitch (значения),
  логика чтения ответа после EXECUTE_SEQUENCE (сколько байт читается
  первым заходом), и главная загадка — мукс пинов CS/MOSI на Linux
  (в Windows SPB-контроллер как-то их получает; искать _DSM у
  контроллера SPI0 в DSDT или ресурсы "GPIO override").
