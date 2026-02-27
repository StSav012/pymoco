import struct
from array import array
from collections.abc import Collection, Iterable
from functools import partial
from math import exp, log

from easystruct import EasyStruct, StructDefItem
from utils import byte, clamp, get_bit, pack_dword, pack_word, word

__all__ = ["State", "Serial", "EncoderState", "Mode", "Parameters"]


class State(EasyStruct):
    def __init__(
        self,
        buf: array | bytes | bytearray | Iterable[int] | None = None,
        dev_version: int = 0x2400,
        **kwargs: int,
    ) -> None:
        if dev_version < 0x2400:

            def write_temperature(t: float) -> int:
                t = clamp(t, 0.0, 100.0)
                t = 10.0 * exp(3950.0 * (1.0 / (t + 273.0) - 1.0 / 298.0))
                return round((5 * t / (10 + t)) * 65536.0 / 3.3)

            def read_temperature(t: int) -> float:
                t *= 3.3 / 65536.0
                t = 10.0 * t / (5.0 - t)
                t = (1.0 / 298.0) + (1.0 / 3950.0) * log(t / 10.0)
                return 1.0 / t - 273.0

        else:

            def write_temperature(t: float) -> int:
                return round((t + 50.0) / 330.0 * 65536.0)

            def read_temperature(t: int) -> float:
                return (t * 3.3 * 100.0 / 65536.0) - 50.0

        def volt(vi: float) -> float:
            v = vi / 65536.0 * 3.3 * 20.0
            if v < 5.0:
                v = 0.0
            return v

        self.s0: int = 0
        self.s1: int = 0
        self.s2: int = 0
        self.cur_pos: int = 0
        self.temp: int = 0
        self.voltage: int = 0

        structdef: Collection[StructDefItem] = [
            StructDefItem("cur_pos", "i", 0x00, lambda x: x * 8, lambda x: x / 8),
            StructDefItem("temp", "H", 0x00, write_temperature, read_temperature),
            StructDefItem("s0", "B", 0x00, None, None),
            StructDefItem("s1", "B", 0x00, None, None),
            StructDefItem("s2", "B", 0x00, None, None),
            StructDefItem("voltage", "H", 0x04, None, volt),
        ]
        super().__init__(structdef, buf, **kwargs)

    @property
    def step_size(self) -> float:
        """Step size is 2^(-M1-2*M2), where M1,M2 = 0,1. May be otherwise, i.e., 1<->2."""
        return 2.0 ** (-get_bit(self.s0, 0) - 2 * get_bit(self.s0, 1))

    @property
    def loft(self) -> bool:
        """Indicate “Loft State”."""
        return get_bit(self.s0, 2)

    @property
    def refined(self) -> bool:
        """If TRUE then full power."""
        return get_bit(self.s0, 3)

    @property
    def direction(self) -> bool:
        """
        Read current direction.

        Relatively!
        """
        return get_bit(self.s0, 4)

    @property
    def on(self) -> bool:
        """If TRUE then Step Motor is ON."""
        return get_bit(self.s0, 5)

    @property
    def full_speed(self) -> bool:
        """
        Indicate whether running full speed.

        Valid in "Slow Start" mode.
        """
        return get_bit(self.s0, 6)

    @property
    def after_reset(self) -> bool:
        """
        Indicate whether the device is just reset.

        TRUE After Device reset, FALSE after "Set Position".
        """
        return get_bit(self.s0, 7)

    @property
    def running(self) -> bool:
        """Indicate whether the step motor is rotating."""
        return get_bit(self.s1, 0)

    @property
    def sync_in(self) -> bool:
        """
        Read logical state directly from input synchronization PIN.

        The pulses are treated as positive.
        """
        return get_bit(self.s1, 1)

    @property
    def sync_out(self) -> bool:
        """
        Read logical state directly from output synchronization PIN.

        The pulses are treated as positive.
        """
        return get_bit(self.s1, 2)

    @property
    def rotary_transducer_pressed(self) -> bool:
        """Indicate current rotary transducer logical press state."""
        return get_bit(self.s1, 3)

    @property
    def rotary_transducer_error(self) -> bool:
        """
        Indicate the rotary transducer error flag.

        Reset by USMC_SetMode function with ResetRT bit being TRUE.
        """
        return get_bit(self.s1, 4)

    @property
    def emergency_reset(self) -> bool:
        """
        Indicate the state of emergency disable button.

        TRUE if the step motor power is off.
        """
        return get_bit(self.s1, 5)

    @property
    def trailer1(self) -> bool:
        """Indicate trailer 1 logical press state."""
        return get_bit(self.s1, 6)

    @property
    def trailer2(self) -> bool:
        """Indicate trailer 2 logical press state."""
        return get_bit(self.s1, 7)

    @property
    def usb_powered(self) -> bool:
        """Return whether the device is USB-powered."""
        return get_bit(self.s2, 0)

    # UNKNOWN   : 6;
    @property
    def working(self) -> bool:
        """
        Return whether the device is functional.

        This bit must be always TRUE (to check functionality).
        """
        return get_bit(self.s2, 7)

    def __repr__(self) -> str:
        props: list[str] = []
        for attr in self.structdef:
            props.append(f"{attr.name}={getattr(self, attr.name)!r}")
        for attr in self.__class__.__dict__:
            if isinstance(getattr(self.__class__, attr), property):
                props.append(f"{attr}={getattr(self, attr)!r}")
        return self.__class__.__name__ + "(" + ", ".join(props) + ")"


class Serial:
    def __init__(self, data: bytes | bytearray | Iterable[int]) -> None:
        st: array[int] = array("B", data)
        self.password = str(st[:16])
        self.serial = str(st[16:])

    def __repr__(self) -> str:
        props: list[str] = []
        for attr in dir(self):
            if not attr.startswith("_"):
                props.append(f"{attr}={getattr(self, attr)!r}")
        return self.__class__.__name__ + "(" + ", ".join(props) + ")"


class EncoderState:
    def __init__(self, data: bytes | bytearray | Iterable[int]) -> None:
        st: array[int] = array("B", data)
        fmt: str = "=II"
        self.e_cur_pos, self.enc_pos = struct.unpack(fmt, st)

    def __repr__(self) -> str:
        props: list[str] = []
        for attr in dir(self):
            if not attr.startswith("_"):
                props.append(f"{attr}={getattr(self, attr)!r}")
        return self.__class__.__name__ + "(" + ", ".join(props) + ")"


class Mode(EasyStruct):
    def __init__(
        self,
        buf: array | bytes | bytearray | Iterable[int] | None = None,
        **kwargs: int,
    ) -> None:
        self.b0: int = 0
        self.b1: int = 0
        self.b2: int = 0
        self.sync_count: int = 0

        structdef: Collection[StructDefItem] = [
            StructDefItem("b0", "B", 0x01, None, None),
            StructDefItem("b1", "B", 0x03, None, None),
            StructDefItem("b2", "B", 0x05, None, None),
            StructDefItem("sync_count", "I", 0x04, pack_dword, pack_dword),
        ]
        super().__init__(structdef, buf, **kwargs)
        for key in kwargs:
            if hasattr(self, key):
                setattr(self, key, kwargs[key])

    def p0bs(self, index: int, value: bool) -> None:
        mask: int = 1 << index
        if value:
            self.b0 |= mask
        else:
            self.b0 &= ~mask

    def p1bs(self, index: int, value: bool) -> None:
        mask: int = 1 << index
        if value:
            self.b1 |= mask
        else:
            self.b1 &= ~mask

    def p2bs(self, index: int, value: bool) -> None:
        mask: int = 1 << index
        if value:
            self.b2 |= mask
        else:
            self.b2 &= ~mask

    buttons_off = property(lambda self: get_bit(self.b0, 0), partial(p0bs, index=0))
    refine_enabled = property(lambda self: get_bit(self.b0, 1), partial(p0bs, index=1))
    reset_power = property(lambda self: get_bit(self.b0, 2), partial(p0bs, index=2))
    emergency_reset = property(lambda self: get_bit(self.b0, 3), partial(p0bs, index=3))
    trailer_1_state = property(lambda self: get_bit(self.b0, 4), partial(p0bs, index=4))
    trailer_2_state = property(lambda self: get_bit(self.b0, 5), partial(p0bs, index=5))
    rotary_transducer_state = property(
        lambda self: get_bit(self.b0, 6), partial(p0bs, index=6)
    )
    trailers_swapped = property(
        lambda self: get_bit(self.b0, 7), partial(p0bs, index=7)
    )

    trailer_1_enabled = property(
        lambda self: get_bit(self.b1, 0), partial(p1bs, index=0)
    )
    trailer_2_enabled = property(
        lambda self: get_bit(self.b1, 1), partial(p1bs, index=1)
    )
    rotary_transducer_enabled = property(
        lambda self: get_bit(self.b1, 2), partial(p1bs, index=2)
    )
    rotary_transducer_stop_on_error = property(
        lambda self: get_bit(self.b1, 3), partial(p1bs, index=3)
    )
    button_1_state = property(lambda self: get_bit(self.b1, 4), partial(p1bs, index=4))
    button_2_state = property(lambda self: get_bit(self.b1, 5), partial(p1bs, index=5))
    buttons_swapped = property(lambda self: get_bit(self.b1, 6), partial(p1bs, index=6))
    reset_rotary_transducer = property(
        lambda self: get_bit(self.b1, 7), partial(p1bs, index=7)
    )

    sync_out_enabled = property(
        lambda self: get_bit(self.b2, 0), partial(p2bs, index=0)
    )
    sync_out_reset = property(lambda self: get_bit(self.b2, 1), partial(p2bs, index=1))
    sync_in_single_move = property(
        lambda self: get_bit(self.b2, 2), partial(p2bs, index=2)
    )
    sync_out_polarity = property(
        lambda self: get_bit(self.b2, 3), partial(p2bs, index=3)
    )
    encoder_enabled = property(lambda self: get_bit(self.b2, 4), partial(p2bs, index=4))
    encoder_counter_inverted = property(
        lambda self: get_bit(self.b2, 5), partial(p2bs, index=5)
    )
    reset_encoder_counter = property(
        lambda self: get_bit(self.b2, 6), partial(p2bs, index=6)
    )
    reset_sm_to_encoder = property(
        lambda self: get_bit(self.b2, 7), partial(p2bs, index=7)
    )

    def __repr__(self) -> str:
        props: list[str] = []
        for attr in self.structdef:
            props.append(f"{attr.name}={getattr(self, attr.name)!r}")
        for attr in self.__class__.__dict__:
            if isinstance(getattr(self.__class__, attr), property):
                props.append(f"{attr}={getattr(self, attr)!r}")
        return self.__class__.__name__ + "(" + ", ".join(props) + ")"


# ~ typedef	struct	_MODE_PACKET	// 7 bytes;
# ~ {
# ~ // Byte 0:
# ~ __u8  PMODE    : 1;	// Turn off buttons (TRUE - buttons disabled).
# ~ __u8  REFINEN  : 1;	// Current reduction regime (TRUE - regime is on).
# ~ __u8  RESETD   : 1;	// Turn power off and make a whole step (TRUE - apply).
# ~ __u8  EMRESET  : 1;	// Quick power off.
# ~ __u8  TR1T     : 1;	// Trailer 1 TRUE state.
# ~ __u8  TR2T     : 1;	// Trailer 2 TRUE state.
# ~ __u8  ROTTRT   : 1;	// Rotary Transducer TRUE state.
# ~ __u8  TRSWAP   : 1;	// If TRUE, Trailers are Swapped (Swapping After Reading Logical State).
# ~ // Byte 1:
# ~ __u8  TR1EN    : 1;	// Trailer 1 Operation Enabled.
# ~ __u8  TR2EN    : 1;	// Trailer 2 Operation Enabled.
# ~ __u8  ROTTREN  : 1;	// Rotary Transducer Operation Enabled.
# ~ __u8  ROTTROP  : 1;	// Rotary Transducer Operation Select (stop on error for TRUE).
# ~ __u8  BUTT1T   : 1;	// Button 1 TRUE state.
# ~ __u8  BUTT2T   : 1;	// Button 2 TRUE state.
# ~ __u8  BUTSWAP  : 1;	// If TRUE, Buttons are Swapped (Swapping After Reading Logical State).
# ~ __u8  RESETRT  : 1;	// Reset Rotary Transducer Check Positions (need 1 full revolution before it can detect error).
# ~ // Byte 2:
# ~ __u8  SNCOUTEN : 1;	// Output Synchronization Enabled.
# ~ __u8  SYNCOUTR : 1;	// Reset output synchronization counter.
# ~ __u8  SYNCINOP : 1;	// Synchronization input mode:
#                               TRUE - Step motor will move one time to the DestPos
#                               FALSE - Step motor will move multiple times by DestPos microsteps as distance.
# ~ __u8  SYNCOPOL : 1;	// Output Synchronization Pin Polarity.
# ~ __u8  ENCODER  : 1;	// Encoder is used on pins {SYNCIN,ROTTR}, disables Synchronization input and Rotary Transducer.
# ~ __u8  INVENC   : 1;	// Invert Encoder Counter Direction.
# ~ __u8  RESBENC  : 1;	// Reset <Encoder Position> and <SM Position in Encoder units> to 0.
# ~ __u8  RESENC   : 1;	// Reset <SM Position in Encoder units> to <Encoder Position>.
# ~ __u16 SYNCCOUNT;	// Number of steps after which synchronization output signal occurs. Appears to be DWORD.
# ~ } MODE_PACKET, * PMODE_PACKET, * LPMODE_PACKET;


class Parameters(EasyStruct):
    def __init__(
        self,
        buf: array | bytes | bytearray | Iterable[int] | None = None,
        dev_ver: int = 0x2400,
        **kwargs: int,
    ) -> None:

        if dev_ver < 0x2407:

            def write_start_pos(_: int) -> int:
                return 0

            def read_start_pos(_: int) -> int:
                return 0
        else:

            def write_start_pos(x: int) -> int:
                return pack_word(x * 8 & 0xFFFFFF00)

            def read_start_pos(x: int) -> int:
                return pack_word(x) // 8

        if dev_ver < 0x2400:

            def write_max_temp(t: float) -> int:
                t = clamp(t, 0.0, 100.0)
                t = 10.0 * exp(3950.0 * (1.0 / (t + 273.0) - 1.0 / 298.0))
                t = (5 * t / (10 + t)) * 65536.0 / 3.3
                return pack_word(word(round(t)))

            def read_max_temp(t: int) -> float:
                t = pack_word(t)
                t *= 3.3 / 65536.0
                t = 10.0 * t / (5.0 - t)
                t = (1.0 / 298.0) + (1.0 / 3950.0) * log(t / 10.0)
                return 1.0 / t - 273.0

        else:

            def write_max_temp(t: float) -> int:
                return pack_word(word(round((t + 50.0) / 330.0 * 65536.0)))

            def read_max_temp(t: int) -> float:
                return (pack_word(t) * 3.3 * 100.0 / 65536.0) - 50.0

        def write_loft_period(x: float) -> int:
            if x == 0.0:
                return 0
            return pack_word(word(65536 - round(125000.0 / clamp(x, 16.0, 5000.0))))

        def read_loft_period(x: int) -> float:
            w: int = pack_word(x)
            if w == 0:
                return 0.0
            return 125000.0 / (65536 - w)

        self.acceleration_time: float = 500.0  # milliseconds
        self.deceleration_time: float = 500.0  # milliseconds
        self.refintimeout: float = 100.0
        self.btimeout1: float = 500.0
        self.btimeout2: float = 500.0
        self.btimeout3: float = 500.0
        self.btimeout4: float = 500.0
        self.btimeoutr: float = 500.0
        self.btimeoutd: float = 500.0
        self.miniperiod: float = 500.0
        self.bto1p: float = 200.0
        self.bto2p: float = 300.0
        self.bto3p: float = 400.0
        self.bto4p: float = 500.0
        self.max_loft: int = 32
        self.start_pos: int = 0
        self.rtdelta: int = 200
        self.rtminerror: int = 15
        self.max_temp: float = 70.0
        self.sine_output: bool = True
        self.loft_period: float = 500.0
        self.encoder_vs_cur_pos: float = 2.5
        self.reserved: bytes = b""

        structdef: Collection[StructDefItem] = [
            StructDefItem(
                "acceleration_time",
                "B",
                self.acceleration_time,
                lambda x: byte(clamp(round(x / 98.0), 1, 15)),
                lambda x: 98.0 * x,
            ),  # AccelT
            StructDefItem(
                "deceleration_time",
                "B",
                self.deceleration_time,
                lambda x: byte(clamp(round(x / 98.0), 1, 15)),
                lambda x: 98.0 * x,
            ),  # DecelT
            StructDefItem(
                "refintimeout",
                "H",
                self.refintimeout,
                lambda x: word(round(clamp(x, 1.0, 9961.0) / 0.152)),
                lambda x: x * 0.152,
            ),  # ptimeout
            StructDefItem(
                "btimeout1",
                "H",
                self.btimeout1,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "btimeout2",
                "H",
                self.btimeout2,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "btimeout3",
                "H",
                self.btimeout3,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "btimeout4",
                "H",
                self.btimeout4,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "btimeoutr",
                "H",
                self.btimeoutr,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "btimeoutd",
                "H",
                self.btimeoutd,
                lambda x: pack_word(word(round(clamp(x, 1.0, 9961.0) / 0.152))),
                lambda x: pack_word(x) * 0.152,
            ),
            StructDefItem(
                "miniperiod",
                "H",
                self.miniperiod,
                lambda x: pack_word(
                    word(65536 - round(125000.0 / clamp(x, 2.0, 625.0)))
                ),
                lambda x: 125000.0 / (65536 - pack_word(x)),
            ),
            StructDefItem(
                "bto1p",
                "H",
                self.bto1p,
                lambda x: pack_word(
                    word(65536 - round(125000.0 / clamp(x, 2.0, 625.0)))
                ),
                lambda x: 125000.0 / (65536 - pack_word(x)),
            ),
            StructDefItem(
                "bto2p",
                "H",
                self.bto2p,
                lambda x: pack_word(
                    word(65536 - round(125000.0 / clamp(x, 2.0, 625.0)))
                ),
                lambda x: 125000.0 / (65536 - pack_word(x)),
            ),
            StructDefItem(
                "bto3p",
                "H",
                self.bto3p,
                lambda x: pack_word(
                    word(65536 - round(125000.0 / clamp(x, 2.0, 625.0)))
                ),
                lambda x: 125000.0 / (65536 - pack_word(x)),
            ),
            StructDefItem(
                "bto4p",
                "H",
                self.bto4p,
                lambda x: pack_word(
                    word(65536 - round(125000.0 / clamp(x, 2.0, 625.0)))
                ),
                lambda x: 125000.0 / (65536 - pack_word(x)),
            ),
            StructDefItem(
                "max_loft",
                "H",
                self.max_loft,
                lambda x: pack_word(word(clamp(x, 1, 1023) * 64)),
                lambda x: pack_word(x) / 64,
            ),
            StructDefItem(
                "start_pos",
                "I",
                self.start_pos,
                write_start_pos,
                read_start_pos,
            ),
            StructDefItem(
                "rtdelta",
                "H",
                self.rtdelta,
                lambda x: pack_word(word(clamp(x, 4, 1023) * 64)),
                lambda x: pack_word(x) / 64,
            ),
            StructDefItem(
                "rtminerror",
                "H",
                self.rtminerror,
                lambda x: pack_word(word(clamp(x, 4, 1023) * 64)),
                lambda x: pack_word(x) / 64,
            ),
            StructDefItem(
                "max_temp",
                "H",
                self.max_temp,
                write_max_temp,
                read_max_temp,
            ),
            StructDefItem(
                "sine_output",
                "B",
                self.sine_output,
                int,
                bool,
            ),
            StructDefItem(
                "loft_period",
                "H",
                self.loft_period,
                write_loft_period,
                read_loft_period,
            ),
            StructDefItem(
                "encoder_vs_cur_pos",
                "B",
                self.encoder_vs_cur_pos,
                lambda x: byte(round(x * 4.0)),
                lambda x: x / 4.0,
            ),  # Encmul
            StructDefItem("reserved", "15s", self.reserved, None, None),
        ]
        super().__init__(structdef, buf, **kwargs)
