#!/usr/bin/env python3
"""
gdix51c0-probe — safe read-only probe for the Goodix fingerprint sensor
(ACPI: GDIX51C0) sitting on the SPI bus of the Huawei MateBook 16s (CREFG-XX).

Wire protocol reconstructed from Metrohan/gxfp5130-linux (GPL-2.0),
kernel/proto/gxfp_goodix_proto.c and gxfp_mp_proto.c:

  Goodix frame : [cmd][decl_len:2 LE][payload: decl_len-1][ck]
                 ck = (0xAA - (cmd + len_lo + len_hi + sum(payload))) & 0xFF
  MP frame     : [type<<4][len:2 LE][ck]  where ck = (b0+b1+b2) & 0xFF
                 types: A=0xA, B=0xB, C=0xC
  FW version   : cmd 0xA8, payload [0x01] -> reply cmd 0xA8, ASCII version

This tool only ever sends query commands (firmware version) and reads back.
No writes to sensor flash, no TLS/PSK provisioning — bricking risk: none.

Usage:  python3 probe.py [/dev/spidev1.0] [--speed 1000000]
"""

import argparse
import ctypes
import fcntl
import struct
import sys
import time

# ---------------------------------------------------------------- SPI via ioctl
SPI_IOC_MAGIC = 0x6B  # 'k'


def _IOW(nr: int, size: int) -> int:
    return 0x40000000 | ((size & 0x3FFF) << 16) | (SPI_IOC_MAGIC << 8) | nr


SPI_IOC_WR_MODE = _IOW(1, 1)
SPI_IOC_WR_BITS_PER_WORD = _IOW(3, 1)
SPI_IOC_WR_MAX_SPEED_HZ = _IOW(4, 4)
SPI_IOC_MESSAGE_1 = _IOW(0, 32)

# struct spi_ioc_transfer (64-bit layout, see linux/spi/spidev.h):
# u64 tx_buf, u64 rx_buf, u32 len, u32 speed_hz, u16 delay_usecs,
# u8 bits_per_word, u8 cs_change, u8 tx_nbits, u8 rx_nbits,
# u8 word_delay_usecs, u8 pad
XFER_FMT = "=QQIIHBBBBBB"
XFER_SIZE = struct.calcsize(XFER_FMT)
assert XFER_SIZE == 32, XFER_SIZE


class SpiDev:
    def __init__(self, path: str, speed_hz: int, mode: int = 0, bits: int = 8):
        self.fd = open(path, "r+b", buffering=0)
        self.speed = speed_hz
        fcntl.ioctl(self.fd, SPI_IOC_WR_MODE, struct.pack("=B", mode))
        fcntl.ioctl(self.fd, SPI_IOC_WR_BITS_PER_WORD, struct.pack("=B", bits))
        fcntl.ioctl(self.fd, SPI_IOC_WR_MAX_SPEED_HZ, struct.pack("=I", speed_hz))

    def xfer(self, tx: bytes) -> bytes:
        """One SPI transaction: CS asserted, tx sent, rx captured, CS released."""
        txbuf = ctypes.create_string_buffer(bytes(tx), len(tx))
        rxbuf = ctypes.create_string_buffer(len(tx))
        tr = struct.pack(
            XFER_FMT,
            ctypes.addressof(txbuf),
            ctypes.addressof(rxbuf),
            len(tx),
            self.speed,
            0,      # delay_usecs
            8,      # bits_per_word (0 = driver default; be explicit)
            0,      # cs_change
            0, 0,   # tx_nbits, rx_nbits
            0, 0,   # word_delay_usecs, pad
        )
        fcntl.ioctl(self.fd, SPI_IOC_MESSAGE_1, tr, False)
        return rxbuf.raw

    def close(self):
        self.fd.close()


# ------------------------------------------------------------- protocol frames
def goodix_ck(cmd: int, decl_len: int, payload: bytes) -> int:
    s = cmd + (decl_len & 0xFF) + ((decl_len >> 8) & 0xFF) + sum(payload)
    return (0xAA - s) & 0xFF


def goodix_frame(cmd: int, payload: bytes = b"") -> bytes:
    dl = 1 + len(payload)
    return (
        bytes([cmd, dl & 0xFF, (dl >> 8) & 0xFF])
        + payload
        + bytes([goodix_ck(cmd, dl, payload)])
    )


def mp_frame(mp_type: int, body: bytes) -> bytes:
    h = bytes([mp_type << 4, len(body) & 0xFF, (len(body) >> 8) & 0xFF])
    return h + bytes([(h[0] + h[1] + h[2]) & 0xFF]) + body


def parse_mp(buf: bytes, off: int = 0):
    """Parse MP header at offset; return (type, payload, end) or None."""
    if off + 4 > len(buf):
        return None
    t = buf[off] >> 4
    if t not in (0xA, 0xB, 0xC):
        return None
    ln = buf[off + 1] | (buf[off + 2] << 8)
    if buf[off + 3] != ((buf[off] + buf[off + 1] + buf[off + 2]) & 0xFF):
        return None
    if off + 4 + ln > len(buf):
        return None
    return t, buf[off + 4 : off + 4 + ln], off + 4 + ln


def parse_goodix(buf: bytes):
    """Parse a Goodix frame; return dict or None."""
    if len(buf) < 4:
        return None
    cmd = buf[0]
    dl = buf[1] | (buf[2] << 8)
    if dl < 1:
        return None
    pl = dl - 1
    if 3 + pl + 1 > len(buf):
        return None
    ck = buf[3 + pl]
    ok = goodix_ck(cmd, dl, buf[3 : 3 + pl]) == ck
    return {
        "cmd": cmd,
        "payload": buf[3 : 3 + pl],
        "ck_ok": ok,
    }


# ------------------------------------------------------------------- utilities
def hexdump(data: bytes, width: int = 32, max_lines: int = 8) -> str:
    lines = []
    for i in range(0, min(len(data), width * max_lines), width):
        chunk = data[i : i + width]
        lines.append(
            f"  {i:04x}: " + " ".join(f"{b:02x}" for b in chunk)
        )
    if len(data) > width * max_lines:
        lines.append(f"  ... ({len(data)} bytes total)")
    return "\n".join(lines)


def interesting(data: bytes) -> bool:
    """True if the bus returned anything other than all-zeros / all-FFs."""
    return any(b not in (0x00, 0xFF) for b in data)


def analyze(tag: str, rx: bytes):
    print(f"[{tag}] rx {len(rx)} bytes:")
    print(hexdump(rx))
    if not interesting(rx):
        print("  -> line idle (all 0x00/0xFF)")
        return
    # try MP frame at every offset
    for off in range(0, min(len(rx), 8)):
        mp = parse_mp(rx, off)
        if mp:
            t, body, _end = mp
            print(f"  -> MP frame at +{off}: type {t:#x}, body {len(body)} B")
            g = parse_goodix(body)
            if g:
                print(
                    f"     Goodix: cmd={g['cmd']:#04x} len={len(g['payload'])} "
                    f"ck_ok={g['ck_ok']}"
                )
                printable = bytes(
                    b if 0x20 <= b < 0x7F else 0x2E for b in g["payload"][:64]
                )
                print(f"     payload: {printable.decode('ascii')}")
            return
    print("  -> non-idle data, but no MP/Goodix frame recognized")


# ------------------------------------------------------------------ GPIO CS
# Kernel GPIO v2 uapi (linux/gpio.h). The legacy v1 ioctls are gone on
# modern kernels, so build gpio_v2_line_request by hand:
#   offsets[64] u32 | consumer[32] | config{flags u64, num_attrs u32,
#   pad[5], attrs[10]*24} | num_lines u32 | event_buffer_size u32 |
#   pad[5] | fd s32   == 592 bytes
GPIO_V2_GET_LINE_IOCTL = 0xC250B407        # _IOWR(0xB4, 0x07, 592)
GPIO_V2_LINE_SET_VALUES_IOCTL = 0xC010B40F  # _IOWR(0xB4, 0x0F, 16)
GPIO_V2_LINE_FLAG_OUTPUT = 1 << 3


class GpioLine:
    """One output GPIO line driven through /dev/gpiochipN (v2 uapi)."""

    def __init__(self, chip: str, line: int, initial: int = 1):
        self.fd = open(chip, "r+b", buffering=0)
        offsets = [line] + [0] * 63
        req = struct.pack(
            "=64I 32s Q I 5I 240x I I 5I i",
            *offsets,
            b"gdix51c0-probe",
            GPIO_V2_LINE_FLAG_OUTPUT,
            0,          # num_attrs
            *( [0] * 5 ),  # config padding
            1,          # num_lines
            0,          # event_buffer_size
            *( [0] * 5 ),  # request padding
            -1,         # fd
        )
        assert len(req) == 592, len(req)
        buf = bytearray(req)
        fcntl.ioctl(self.fd, GPIO_V2_GET_LINE_IOCTL, buf, True)
        self.linefd = struct.unpack_from("=i", buf, 588)[0]
        if self.linefd < 0:
            raise OSError("gpio line request failed")
        self.set(initial)

    def set(self, value: int) -> None:
        data = struct.pack("=QQ", value & 1, 1)  # bits, mask (line 0 of set)
        fcntl.ioctl(self.linefd, GPIO_V2_LINE_SET_VALUES_IOCTL, data)

    def close(self) -> None:
        import os

        os.close(self.linefd)
        self.fd.close()


# ------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("device", nargs="?", default="/dev/spidev1.0")
    ap.add_argument("--speed", type=int, default=1_000_000)
    ap.add_argument("--read-len", type=int, default=256)
    ap.add_argument(
        "--gpio-cs",
        type=int,
        default=None,
        help="drive this gpiochip0 line as manual chip-select around transfers "
        "(for pads stuck in GPIO mode, e.g. 15 = GSPI0_CS0B on MateBook 16s)",
    )
    args = ap.parse_args()

    cs = None
    if args.gpio_cs is not None:
        cs = GpioLine("/dev/gpiochip0", args.gpio_cs, initial=1)
        print(f"manual CS on gpiochip0 line {args.gpio_cs}")

    def xfer(tx: bytes) -> bytes:
        if cs is None:
            return spi.xfer(tx)
        cs.set(0)
        try:
            return spi.xfer(tx)
        finally:
            cs.set(1)

    ver = goodix_frame(0xA8, b"\x01")
    ver_mp = mp_frame(0xA, ver)
    print(f"version request (raw Goodix): {ver.hex()}")
    print(f"version request (MP-wrapped) : {ver_mp.hex()}")

    try:
        spi = SpiDev(args.device, args.speed)
    except OSError as e:
        print(f"cannot open {args.device}: {e}", file=sys.stderr)
        return 2
    print(f"opened {args.device}, mode 0, 8 bits, {args.speed} Hz\n")

    # --- probe 1: idle clock-out -------------------------------------------
    analyze("idle-read", xfer(b"\x00" * 64))

    # --- probe 2: raw Goodix frame, write then read (CS toggles) -----------
    xfer(ver)
    time.sleep(0.002)
    analyze("goodix-raw / read", xfer(b"\x00" * args.read_len))

    # --- probe 3: MP-wrapped, write then read ------------------------------
    xfer(ver_mp)
    time.sleep(0.002)
    analyze("mp-wrapped / read", xfer(b"\x00" * args.read_len))

    # --- probe 4: single CS period (full duplex, reply may follow inline) --
    cs.set(0) if cs else None
    combined = spi.xfer(ver_mp + b"\x00" * args.read_len)
    if cs:
        cs.set(1)
    analyze("mp-wrapped combined", combined[len(ver_mp) :])

    spi.close()
    if cs:
        cs.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
