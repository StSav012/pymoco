import time
from array import array
from collections.abc import Collection
from math import nan
from typing import Literal

import usb

from standa_types import (
    EncoderState,
    Mode,
    Parameters,
    State,
)
from utils import (
    first_word,
    first_word_swapped,
    goto_data,
    second_word,
    second_word_swapped,
)

__all__ = ["Standa", "find_serials"]


def get_serial(udev: usb.legacy.DeviceHandle) -> int:
    """Return the serial number of the corresponding usb device."""
    length: int = 512
    # c0 c9 00 00 00 00 10 00
    serial_data: array[int] = udev.controlMsg(
        requestType=0xC0,
        request=0xC9,
        buffer=length,
        value=0x00,
        index=0,
        timeout=1000,
    )
    return int(serial_data)


def find_serials() -> Collection[int]:
    """Return a list containing the serial numbers os the connected Standa controllers."""
    ser: set[int] = set()
    bus: usb.legacy.Bus
    for bus in usb.busses():
        dev: usb.legacy.Device
        for dev in bus.devices:
            if dev.idVendor == 0x10C4 and dev.idProduct == 0x0230:
                udev: usb.legacy.DeviceHandle = dev.open()
                ser.add(get_serial(udev))
    return ser


class Standa:
    """Class used to control the Standa 8SMC1 USB stepper motor controller."""

    def __init__(self, serial: int) -> None:
        self.serial: int = serial
        self.udev: usb.legacy.DeviceHandle | None = None
        # print("Activando Carro S/N=", self.serial)
        bus: usb.legacy.Bus
        for bus in usb.busses():
            dev: usb.legacy.Device
            for dev in bus.devices:
                if dev.idVendor == 0x10C4 and dev.idProduct == 0x0230:
                    udev: usb.legacy.DeviceHandle = dev.open()
                    if serial == get_serial(udev):
                        self.udev = udev
        self.version = int(self.get_version(), 16)

        self.serial = int(self.get_serial())
        self.pos: float = nan  # Current position is unknown

        # Load the default mode
        self.__mode__: Mode = Mode()
        self.set_mode(self.__mode__)

        # Load the default parameters
        self.__parameters__: Parameters = Parameters(dev_ver=self.version)
        self.set_parameters(self.__parameters__)

    def get_status(self, st_type: int) -> array[int]:
        request: int = 0x00
        value: int = 0x0000
        index: int = 0x0000
        length: int = 0x0002

        if st_type not in (usb.RECIP_DEVICE, usb.RECIP_ENDPOINT, usb.RECIP_INTERFACE):
            raise ValueError("Invalid status type", st_type)

        request_type: int = usb.util.CTRL_IN | st_type | usb.TYPE_STANDARD

        return self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=length,
            value=value,
            index=index,
            timeout=1000,
        )

    def set_current_position(self, pos: int) -> bool:
        request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x01
        length: int = 0x0000
        value: int = pos >> 16 & 0xFFFF
        index: int = pos & 0xFFFF
        return length == self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=(),
            value=value,
            index=index,
            timeout=1000,
        )

    def get_version(self) -> str:
        request_type: int = usb.util.CTRL_IN | usb.RECIP_DEVICE | usb.TYPE_STANDARD
        request: int = 0x06
        value: int = 0x0304
        index: int = 0x0409
        length: int = 0x0006
        data: array[int] = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=length,
            value=value,
            index=index,
            timeout=1000,
        )
        s: str = "0x"
        for b in data[2:]:
            s += chr(b)
        return s

    def stop(self) -> bool:
        """Stop the movement."""
        request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x07
        length: int = 0x0000
        value: int = 0x0000
        index: int = 0x0000
        return length == self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=(),
            value=value,
            index=index,
            timeout=1000,
        )

    def get_trailer(self) -> tuple[bool, bool]:
        """Check if the limit switches are pressed."""
        state: State = self.get_state()
        return state.trailer1, state.trailer2

    def get_current_position(self) -> int:
        return self.get_state().cur_pos

    def _fpark(self) -> None:
        """If any of the limit switches is pressed, move slowly the translation stage until they are not."""
        state: State = self.get_state()

        # The trailer close to the motor is pressed
        if state.trailer2:
            while any(self.get_trailer()):
                state = self.get_state()
                self.move(state.cur_pos - 10000, div=8, speed=500)
                self.wait_nt()
            self.stop()
            # ~ self.udev.controlMsg(requestType=0x40, request=0x01,buffer=0,value=0x00, index=0,timeout= 1000)

        # The trailer far from the motor is pressed
        elif state.trailer1:
            while any(self.get_trailer()):
                state = self.get_state()
                self.move(state.cur_pos + 10000, div=8, speed=500)
                self.wait_nt()
            self.stop()

    def park(
        self,
        motor_side: bool = True,
        speed: float = 500,
        div: Literal[1, 2, 4, 8] = 1,
    ) -> None:
        """
        Park the translation stage, and set the current position to 0.

        if motor_side is true, park the translation stage to the motor side, else
        park it to the opposite side.
        """
        # Move away from the trailers
        self._fpark()

        # which side to park
        move = 10000000 if motor_side else -10000000

        self.set_current_position(0)
        # The delays in the wait are needed, because sometimes the run
        # order is not executed immediately
        # TODO: Check for a flush for the USB
        self.wait(0.1)

        self.move(move, div=div, speed=speed)
        self.wait(0.1)  # wait checking for the trailers

        self.move(-move, div=1, speed=128)

        while any(self.get_trailer()):
            pass
        self.stop()
        self.set_current_position(0)
        self.move(0, div=1, speed=64)
        self.wait(0.1)

    def wait(self, timeout: float = 0.1) -> None:
        """Wait time seconds and then until the translation stage stops."""
        if timeout > 0.0:
            time.sleep(timeout)
        while self.get_state().running:
            if any(self.get_trailer()):
                self.stop()
                break

    def wait_nt(self) -> None:
        """Wait until the translation stage stops does not check the trailers."""
        while self.get_state().running:
            pass

    def move(
        self,
        pos: int,
        speed: float = 500,
        div: Literal[1, 2, 4, 8] = 1,
        def_dir: bool = False,
        loft_en: bool = False,
        sl_strt: bool = True,
        w_sync: bool = False,
        sync_out: bool = False,
        force_loft: bool = False,
    ) -> bool:  # L=128,I=0,div=8):#Velocidad 625 , divisor: 8,4,2,1, carro:serial
        """Move to a given position."""
        request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x80
        # length: int = 0x0003

        if pos < 0:
            def_dir = not def_dir
            pos = -pos

        buf = goto_data(
            pos,
            div=div,
            speed=speed,
            def_dir=def_dir,
            loft_en=loft_en,
            sl_strt=sl_strt,
            w_sync=w_sync,
            sync_out=sync_out,
            force_loft=force_loft,
        )

        index: int = first_word(buf)
        value: int = second_word(buf)

        return len(buf) - 4 == self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=buf[4:],
            value=value,
            index=index,
            timeout=1000,
        )

    def set_mode(self, mode: Mode) -> bool:
        if not isinstance(mode, Mode):
            raise TypeError("mode must be an instance of the Mode class")

        request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x81
        length: int = 0x0003
        buf: bytes = mode.to_bytes()

        value: int = first_word_swapped(buf)
        index: int = second_word_swapped(buf)

        data: int = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=buf[4:],
            value=value,
            index=index,
            timeout=1000,
        )
        if data == length:
            self.__mode__ = mode
        return data == length

    def get_state(self) -> State:
        request_type: int = usb.util.CTRL_IN | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x82
        value: int = 0x0000
        index: int = 0x0000
        length: int = 0x000B
        data: array[int] = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=length,
            value=value,
            index=index,
            timeout=1000,
        )
        return State(data, dev_version=self.version)

    def set_parameters(self, para: Parameters) -> bool:
        request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x83
        length: int = 0x0035
        buf: bytes = para.to_bytes()
        value: int = first_word_swapped(buf)
        index: int = second_word(buf)
        data: int = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=buf[4:],
            value=value,
            index=index,
            timeout=1000,
        )
        if data == length:
            self.__parameters__ = para
        return data == length

    def get_encoder_state(self) -> EncoderState:
        request_type: int = usb.util.CTRL_IN | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0x85
        value: int = 0x0000
        index: int = 0x0000
        length: int = 0x0008
        data: array[int] = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=length,
            value=value,
            index=index,
            timeout=1000,
        )
        return EncoderState(data)

    def get_serial(self) -> str:
        request_type: int = usb.util.CTRL_IN | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        request: int = 0xC9
        value: int = 0x0000
        index: int = 0x0000
        length: int = 0x0010
        data: array[int] = self.udev.controlMsg(
            requestType=request_type,
            request=request,
            buffer=length,
            value=value,
            index=index,
            timeout=1000,
        )
        return data.tobytes().decode()

    def set_ss_time(self, start_and_stop_time: tuple[float, float]) -> None:
        """
        Set the start and stop time.

        start_and_stop_time tuple with the start and stop time in ms
        """
        start_time, stop_time = start_and_stop_time
        self.__parameters__.acceleration_time = start_time
        self.__parameters__.deceleration_time = stop_time
        self.set_parameters(self.__parameters__)

    def get_ss_time(self) -> tuple[float, float]:
        """Return the start and stop time."""
        return (
            self.__parameters__.acceleration_time,
            self.__parameters__.deceleration_time,
        )

    # As is not possible to read from the driver board to get the current
    # mode and the current Parameters, all the configuration attributes of the class
    # will be made python properties. This allows us to easily keep synchronized
    # the __mode__, and the __parameters__ buffers with the info
    # recorded on the board

    # Begin definition of properties

    # cur_pos : Indicates the position of the stage in steps
    # This is a wrapper to get_current_position and set_current_position

    cur_pos = property(get_current_position, set_current_position)

    # ss_time: tuple indicating  the start and stop time in millisecond

    ss_time = property(get_ss_time, set_ss_time)

    # End definition of properties

    # Methods above are ready

    # def get_parameters(self):

    def download(self) -> array[int]:
        # request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        # request: int = 0xC8
        # length: int = 0x003D
        # # ~ kern_buf = user_to_kernel ( user_buf, *wLength + 4 );
        # value: int = first_word_swapped(kern_buf)
        # index: int = second_word_swapped(kern_buf)
        raise NotImplementedError("Structures not implemented yet")

    def set_serial(self) -> bool:
        # request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        # request: int = 0xCA
        # length: int = 0x001C
        # # ~ kern_buf = user_to_kernel ( user_buf, *wLength + 4 );
        # value: int = first_word_swapped(kern_buf)
        # index: int = second_word_swapped(kern_buf)
        raise NotImplementedError("Structures not implemented yet")

    def emulate_buttons(self) -> bool:
        # request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        # request: int = 0x0D
        # length: int = 0x0000
        # # ~ kern_buf = user_to_kernel ( user_buf, *wLength + 1 );
        # value: int = first_byte(kern_buf)
        # index: int = 0x0000
        raise NotImplementedError("Structures not implemented yet")

    def save_parameters(self) -> bool:
        # request_type: int = usb.util.CTRL_OUT | usb.RECIP_DEVICE | usb.TYPE_VENDOR
        # request: int = 0x84
        # length: int = 0x0000
        # value: int = 0x0000
        # index: int = 0x0000
        raise NotImplementedError("Structures not implemented yet")
