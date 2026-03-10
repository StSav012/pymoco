from collections.abc import Iterable, Sequence
from struct import pack, unpack
from typing import Literal


def get_bit(num: int, bit: int = 0) -> bool:
    b: int = 0x01 << bit
    return (num & b) == b


def tobyte(lb: Iterable[bool]) -> int:
    res = 0
    for n, b in enumerate(lb):
        res += b << n
    return res


def byte2bits(b: int) -> Sequence[int]:
    return [get_bit(b, n) for n in range(8)]


def clamp[T](val: T, minv: T, maxv: T) -> T:
    if minv <= val <= maxv:
        return val
    raise ValueError(f"Value should be within {minv} and {maxv}")


# define		BYTE_I(i)				(*(((__u8 * )pPacketData)+i))


def first_byte(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return buf[0]


def second_byte(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return buf[1]


def third_byte(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return buf[2]


def fourth_byte(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return buf[3]


def first_word(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return unpack("H", buf[0:2])[0]


def second_word(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return unpack("H", buf[2:4])[0]


def first_word_swapped(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return (first_byte(buf) << 8) | second_byte(buf)


def second_word_swapped(buf: int | Sequence[int]) -> int:
    if isinstance(buf, int):
        buf = buf.to_bytes(4)
    return (third_byte(buf) << 8) | fourth_byte(buf)


# define		REST_DATA(pPacketData)			((void *)(((__u16 * )pPacketData)+2))


def byte(b: int) -> int:
    return b & 0xFF


def word(w: int) -> int:
    return w & 0xFFFF


def hibyte(w: int) -> int:
    return (w & 0xFF00) >> 8


def lobyte(w: int) -> int:
    return w & 0x00FF


def hiword(dw: int) -> int:
    return (dw & 0xFFFF0000) >> 16


def loword(dw: int) -> int:
    return dw & 0x0000FFFF


def pack_word(w: int) -> int:
    return hibyte(w) | (lobyte(w) << 8)


def pack_dword(w: int) -> int:
    return (
        hibyte(hiword(w))
        | (lobyte(hiword(w)) << 8)
        | (hibyte(loword(w)) << 16)
        | (lobyte(loword(w)) << 24)
    )


def goto_data(
    dest_pos: int,
    speed: float = 500,
    div: Literal[1, 2, 4, 8] = 1,
    def_dir: bool = False,
    loft_en: bool = False,
    sl_strt: bool = False,
    w_sync: bool = False,
    sync_out: bool = False,
    force_loft: bool = False,
) -> bytes:
    if not (16.0 <= speed <= 5000.0):
        raise ValueError("Invalid speed")
    timer_period: int = pack_word(65536 - round(1e6 / speed))
    m: tuple[bool, bool] = {
        1: (False, False),
        2: (True, False),
        4: (False, True),
        8: (True, True),
    }[div]

    return pack(
        "iHB",
        dest_pos * 8,
        timer_period,
        tobyte([*m, def_dir, loft_en, sl_strt, w_sync, sync_out, force_loft]),
    )


# ~
# ~ typedef	struct	_GO_TO_PACKET	// 7 bytes;
# ~ {
# ~ __u32 DestPos;		// Destination Position.
# ~ __u16  TimerPeriod;	// Period between steps is 12*(65536-[TimerPeriod])/[SysClk] in seconds, where SysClk = 24MHz.
# ~ // Byte 7:
# ~ __u8  M1        : 1;	// | Step size is 2^(-M1-2*M2), where M1,M2 = 0,1. May be otherwise 1<->2.
# ~ __u8  M2        : 1;	// |
# ~ __u8  DEFDIR    : 1;	// Default direction. For "Anti Loft" operation.
# ~ __u8  LOFTEN    : 1;	// Enable automatic "Anti Loft" operation.
# ~ __u8  SLSTRT    : 1;	// Slow Start(and Stop) mode.
# ~ __u8  WSYNCIN   : 1;	// Wait for input synchronization signal to start.
# ~ __u8  SYNCOUTR  : 1;	// Reset output synchronization counter.
# ~ __u8  FORCELOFT : 1;	// Force driver automatic "Anti Loft" mechanism to reset "Loft State".
# ~ } GO_TO_PACKET, * PGO_TO_PACKET, * LPGO_TO_PACKET;
# ~
# ~


# ~ typedef	struct	_DOWNLOAD_PACKET	// 65 bytes;
# ~ {
# ~ __u8 Page;		// Page number ( 0 - 119 ). 0 - first, 119 - last.
# ~ __u8 Data [64];		// Data.
# ~ } DOWNLOAD_PACKET, * PDOWNLOAD_PACKET, * LPDOWNLOAD_PACKET;
# ~
# ~
# ~ typedef	struct	_SERIAL_PACKET	// 32 bytes;
# ~ {
# ~ __u8 Password     [16];
# ~ __u8 SerialNumber [16];
# ~ } SERIAL_PACKET, * PSERIAL_PACKET, * LPSERIAL_PACKET;
