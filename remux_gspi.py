#!/usr/bin/env python3
"""
remux_gspi.py — switch GSPI0 CS0B/MOSI pads from GPIO mode to native SPI.

On the MateBook 16s (CREFG) BIOS leaves GSPI0_CS0B (pin 15) and GSPI0_MOSI
(pin 18) in GPIO mode while GSPI0_CLK/MISO (16/17) are already in SPI mode
(mode 2). The Windows driver re-muxes them at runtime; Linux never does, so
the Goodix fingerprint sensor never sees CS/MOSI activity.

Pad register (DW0) address = PCR(0xFD000000) + community(0x6E0000) + 0x0700
+ pin*8. Values are verified against pinctrl debugfs before writing;
originals are printed for a manual revert (--restore).

Usage (root):
    python3 remux_gspi.py           # remux 15 & 18 to mode 2
    python3 remux_gspi.py --restore 0x80800102 0x84000300   # restore originals
"""

import mmap
import sys

PCR_BASE = 0xFD000000
COMMUNITY_OFF = 0x6E0000
PAD_BASE_OFF = 0x0700

# pin -> (name, expected DW0 fingerprint from debugfs, target DW0)
PINS = {
    15: ("GSPI0_CS0B", 0x80800102, None),  # target set below
    16: ("GSPI0_CLK", 0x44000B00, None),
    17: ("GSPI0_MISO", 0x44000B02, None),
    18: ("GSPI0_MOSI", 0x84000300, None),
}
# native-mode template taken from GSPI0_CLK (output pad, mode 2)
TEMPLATE_OUT = 0x44000B00


def dw0_addr(pin: int) -> int:
    return PCR_BASE + COMMUNITY_OFF + PAD_BASE_OFF + pin * 8


def read_dw0(m, pin: int) -> int:
    a = dw0_addr(pin) & ~0xFFF
    off = dw0_addr(pin) & 0xFFF
    return int.from_bytes(m[off : off + 4], "little")


def write_dw0(m, pin: int, val: int) -> None:
    off = dw0_addr(pin) & 0xFFF
    m[off : off + 4] = val.to_bytes(4, "little")


def main() -> int:
    restore = "--restore" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    restore_vals = [int(a, 0) for a in args] if restore else None

    fd = open("/dev/mem", "r+b")
    page = dw0_addr(15) & ~0xFFF
    m = mmap.mmap(fd.fileno(), 0x1000, offset=page)

    print("== проверка отпечатков ==")
    ok = True
    cur = {}
    for pin, (name, expect, _) in PINS.items():
        v = read_dw0(m, pin)
        cur[pin] = v
        match = "OK" if v == expect else f"НЕ СОВПАЛО (жду {expect:#x})"
        print(f"  pin {pin:2d} {name:11s} DW0={v:#010x}  {match}")
        if v != expect:
            ok = False

    if restore:
        vals = {15: restore_vals[0], 18: restore_vals[1]}
        for pin, v in vals.items():
            write_dw0(m, pin, v)
            print(f"  pin {pin}: записано {v:#x}, прочитано {read_dw0(m, pin):#x}")
        return 0

    if not ok:
        print("!! адреса не совпали — НИЧЕГО не записываю (защита от дурака)")
        return 1

    print("\n== переключаю pin 15 (CS) и 18 (MOSI) в native mode 2 ==")
    for pin in (15, 18):
        write_dw0(m, pin, TEMPLATE_OUT)
        now = read_dw0(m, pin)
        if now == cur[pin]:
            print(f"  pin {pin}: ЗАПИСЬ ЗАБЛОКИРОВАНА (pad lock), DW0 не изменился")
        else:
            print(f"  pin {pin}: {cur[pin]:#010x} -> {now:#010x}  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
