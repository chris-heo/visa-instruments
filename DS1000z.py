import math
import os
import pyvisa
from enum import Enum, Flag, auto

class _Scpihelper():
    def __init__(self, scope, message_prefix: str = ""):
        self.scope = scope
        self.resource = scope.resource
        self.message_prefix = message_prefix
    
    def _write(self, message: str) -> int:
        return self.resource.write("%s%s" % (self.message_prefix, message))
    
    def _read(self, strip: bool = True) -> str:
        answer = self.resource.read()
        if strip is True:
            answer = answer.strip()
        return answer

    def _query(self, message: str, strip: bool = True) -> str:
        answer = self.resource.query("%s%s" % (self.message_prefix, message))
        if strip is True:
            answer = answer.strip()
        return answer
    
    def _write_bool(self, message: str, value: bool):
        self.resource.write("%s%s %u" % (self.message_prefix, message, (1 if value else 0)))

    def _query_bool(self, message: str) -> bool:
        answer = self.resource.query("%s%s" % (self.message_prefix, message)).strip().upper()
        if answer in ("1", "ON"):
            return True
        elif answer in ("0", "OFF"):
            return False
        else:
            raise Exception("unexpected answer '%s'" % (answer))

    def _query_number(self, message: str):
        answer = self.resource.query("%s%s" % (self.message_prefix, message)).strip().upper()
        if answer == "9.91E37":
            return math.nan
        elif answer == "9.9E37":
            return math.inf
        elif answer == "-9.9E37":
            return -math.inf
        elif answer == "MEASURE ERROR!":
            raise Exception("Measure error")
        
        return answer

    def _write_int(self, message: str, value : int):
        self.resource.write("%s%s %u" % (self.message_prefix, message, value))

    def _query_int(self, message: str) -> int:
        answer = self._query_number(message)
        if isinstance(answer, str):
            return int(answer)
        else:
            return answer

    def _write_float(self, message: str, value: float):
        self.resource.write("%s%s %.4e" % (self.message_prefix, message, value))

    def _query_float(self, message: str) -> float:
        answer = self._query_number(message)
        if isinstance(answer, str):
            return float(answer)
        else:
            return answer

class _Channels():
    def __init__(self, scope) -> None:
        self.scope = scope

        self._items = [_Channel(scope, i) for i in range(1, 5)]

    def __getitem__(self, i):
        assert i >= 1 and i <= 4
        return self._items[i - 1]

class _Decoders():
    def __init__(self, scope) -> None:
        self.scope = scope

        self._items = [
            _Decoder(scope, 1),
            _Decoder(scope, 2),
        ]
    
    def __getitem__(self, i):
        assert i >= 1 and i <= 2
        return self._items[i - 1]

class DS1000z(_Scpihelper):
    def __init__(self, resource):
        self.resource = resource
        super().__init__(self)

        self.channel = _Channels(self)
        self.acquire = _Acquire(self)
        self.calibrate = _Calibrate(self)
        self.cursor = _Cursor(self)
        self.decoder = _Decoders(self)
        self.display = _Display(self)
        self.math = _Math(self)
        self.measure = _Measure(self)
        self.reference = _References(self)
        self.system = _System(self)
        self.timebase = _Timebase(self)
        self.trigger = _Trigger(self)
        self.waveform = _Waveform(self)

    def autoscale(self):
        """Enable the waveform auto setting function. 
        
        The oscilloscope will automatically adjust the vertical scale, 
        horizontal timebase, and trigger mode according to the input signal to 
        realize optimum waveform display. 
        This command is equivalent to pressing the AUTO key on the front panel.
        """
        self._write(":AUT")
    
    def clear(self):
        """Clear all the waveforms on the screen. 
        
        If the oscilloscope is in the RUN state, waveform will still be displayed.
        This command is equivalent to pressing the CLEAR key on the front panel.
        """
        self._write(":CLE")
    
    def run(self):
        """Starts the oscilloscope acquisition
        This commands are equivalent to pressing the RUN/STOP key on the front panel.
        """
        self._write(":RUN")

    def stop(self):
        """Stops the oscilloscope acquisition
        This commands are equivalent to pressing the RUN/STOP key on the front panel.
        """
        self._write(":STOP")

    def singleshot(self):
        """Set the oscilloscope to the single trigger mode.
        This command is equivalent to any of the following two operations: 
        pressing the SINGLE key on the front panel and sending the 
        :TRIGger:SWEep SINGle command.
        """
        self._write(":SING")
    
    def force_trigger(self):
        """Generate a trigger signal forcefully.
        This command is only applicable to the normal and single trigger modes
        (see the :TRIGger:SWEep command) and is equivalent to pressing the FORCE
        key in the trigger control area on the front panel."""
        self._write(":TFOR")

    def clear_events_errors(self):
        """Clear all the event registers and clear the error queue."""
        self._write("*CLS")

    @property
    def events_status(self) -> int:
        """Set or query the enable register for the standard event status register set."""
        return self._query_int("*ESE?")

    @events_status.setter
    def events_status(self, value: int):
        assert True
        self._write("*ESE %u" % (value))
    
    @property
    def events_query_clear(self) -> int:
        """Query and clear the event register for the standard event status register."""
        return self._query_int("*ESR?")

    @property
    def id(self) -> str:
        """Query the ID string of the instrument."""
        return self._query("*IDN?")

    @property
    def operation_finished(self) -> bool:
        """The command is used to query whether the current operation is finished. """
        return self._query_bool("*OPC?")
    
    def set_operation_finished(self):
        """The command is used to set the Operation Complete bit (bit 0) in the standard 
        event status register to 1 after the current operation is finished."""
        self._write("*OPC")

    def reset(self):
        """Restore the instrument to the default state."""
        self._write("*RST")

    @property
    def status_byte(self) -> int:
        """Set or query the enable register for the status byte register set."""
        return self._query_int("*SRE?")

    @status_byte.setter
    def status_byte(self, value: int):
        assert value >= 0 and value <= 255
        self._write("*SRE %u" % (value))

    @property
    def status_events(self) -> int:
        """Query the event register for the status byte register. 
        The value of the status byte register is set to 0 after this command is executed."""
        return self._query_int("*STB?")
    
    def selftest(self) -> int:
        """Perform a self-test and then return the seilf-test results."""
        return self._query_int("*TST?")

    def wait(self):
        """Wait for the operation to finish."""
        self._write("*WAI")

class AcquireMode(Enum):
    Normal = "NORM"
    Average = "AVER"
    Peak = "PEAK"
    HighResolution = "HRES"

class _Acquire(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":ACQ")

    @property
    def averages(self) -> int:
        """Set or query the number of averages under the average acquisition mode.
        The value must be a power of 2 between 2 and 1024"""
        return self._query_int(":AVER?")

    @averages.setter
    def averages(self, value: int):
        assert value in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)
        self._write(":AVER %u" % (value))

    @property
    def memory_depth(self) -> int:
        """Set or query the memory depth of the oscilloscope 
        (namely the number of waveform points that can be stored in a single trigger sample). 
        The default unit is pts (points)."""
        return self._query_int(":MDEP?")

    @memory_depth.setter
    def memory_depth(self, value: int):
        #FIXME: support Auto, restrict to values
        self._write(":MDEP %u" % (value))

    @property
    def type(self) -> AcquireMode:
        """Set or query the acquisition mode of the oscilloscope."""
        return AcquireMode(self._query(":TYPE?"))

    @type.setter
    def type(self, value: AcquireMode):
        self._write(":TYPE %s" % (value.value))

    @property
    def sampling_rate(self) -> int:
        """Query the current sample rate. The default unit is Sa/s."""
        return self._query_int(":RAT?")

class _Calibrate(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CAL")

    def start(self):
        """The oscilloscope starts to execute self-calibration."""
        self._write(":STAR")

    def quit(self):
        """Exit the self-calibration at any time."""
        self._write(":QUIT")

class BandwidthLimit(Enum):
    Off = "OFF"
    Limit_20M = "20M"

class Coupling(Enum):
    AC = "AC"
    DC = "DC"
    GND = "GND"

class VerticalUnit(Enum):
    Voltage = "VOLT"
    Watt = "WATT"
    Ampere = "AMP"
    Unknown = "UNKN"

class _Channel(_Scpihelper):
    def __init__(self, scope: DS1000z, channel: int):
        assert channel > 0 and channel < 5
        super().__init__(scope, ":CHAN%u" % (channel))
        self.channel = channel

    @property
    def bandwidth_limit(self) -> BandwidthLimit:
        """Set or query the bandwidth limit parameter of the specified channel."""
        return BandwidthLimit(self._query(":BWL?"))
    
    @bandwidth_limit.setter
    def bandwidth_limit(self, value: BandwidthLimit):
        self._write(":BWL %s" % (value.value))
    
    @property
    def coupling(self) -> Coupling:
        """Set or query the coupling mode of the specified channel."""
        return Coupling(self._query(":COUP?"))

    @coupling.setter
    def coupling(self, value: Coupling):
        self._write(":COUP %s" % (value.value))
    
    @property
    def display(self) -> bool:
        """Enable or disable the specified channel or query the status 
        of the specified channel."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

    @property
    def invert(self) -> bool:
        """Enable or disable the waveform invert of the specified channel or 
        query the status of the waveform invert of the specified channel."""
        return self._query_bool(":INV?")
    
    @invert.setter
    def invert(self, value: bool):
        self._write_bool(":INV", value)

    @property
    def offset(self) -> float:
        """Set or query the vertical offset of the specified channel. 
        The default unit is V.
        
        probe ratio  1X & vertical scale >= 0.5 V/div:  -100 V ...  +100 V
        probe ratio  1X & vertical scale  < 0.5 V/div:    -2 V ...    +2 V
        probe ratio 10X & vertical scale >= 5   V/div: -1000 V ... +1000 V
        probe ratio 10X & vertical scale  < 5   V/div:   -20 V ...   +20 V
        """
        return self._query_float(":OFFS?")

    @offset.setter
    def offset(self, value: float):
        assert value >= -1000 and value <= 1000
        self._write_float(":OFFS", value)

    @property
    def range(self) -> float:
        """Set or query the vertical range of the specified channel. 
        The default unit is V."""
        return self._query_float(":RANG?")

    @range.setter
    def range(self, value: float):
        assert value >= 8e-3 and value >= 800
        self._write_float(":RANG", value)

    @property
    def delay_calibration(self) -> float:
        """Set or query the delay calibration time of the specified channel 
        to calibrate the zero offset of the corresponding channel. 
        The default unit is s."""
        return self._query_float(":TCAL?")
    
    @delay_calibration.setter
    def delay_calibration(self, value: float):
        assert value > 100e-12
        self._write_float(":TCAL", value)
    
    @property
    def scale(self) -> float:
        """Set or query the vertical scale of the specified channel.
        The default unit is V.
        if vernier function is disabled, the scale is in 1-2-5 step"""
        return self._query_float(":SCAL?")

    @scale.setter
    def scale(self, value: float):
        assert value >= 1e-3 and value <= 100
        self._write_float(":SCAL", value)

    @property
    def probe(self) -> float:
        """Set or query the probe ratio of the specified channel.
        must be in discrete steps"""
        return self._query_float(":PROB?")

    @probe.setter
    def probe(self, value: float):
        assert value in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
            1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
        self._write_float(":PROB", value)

    @property
    def vertical_unit(self) -> VerticalUnit:
        """Set or query the amplitude display unit of the specified channel."""
        return VerticalUnit(self._query(":UNIT?"))

    @vertical_unit.setter
    def vertical_unit(self, value: VerticalUnit):
        self._write(":UNIT %s" % (value.value))

    @property
    def vernier(self) -> bool:
        """Enable or disable the fine adjustment of the vertical scale 
        of the specified channel, or query the fine adjustment status 
        of the vertical scale of the specified channel."""
        return self._query_bool(":VERN?")
    
    @vernier.setter
    def vernier(self, value: bool):
        self._write_bool(":VERN", value)

class CursorMode(Enum):
    Off = "OFF"
    Manual = "MAN"
    Track = "TRAC"
    Auto = "AUTO"
    XY = "XY"

class _Cursor(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CURS")

        self.manual = _CursorManual(scope)
        self.track = _CursorTrack(scope)
        self.auto = _CursorAuto(scope)
        self.xy = _CursorXY(scope)

    @property
    def mode(self) -> CursorMode:
        """Set or query the cursor measurement mode."""
        return CursorMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: CursorMode):
        self._write(":MODE %s" % (value.value))

class CursorManualType(Enum):
    X = "X"
    Y = "Y"

class CursorManualSource(Enum):
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"
    LogicAnalyzer = "LA"

class CursorManualHorizontalUnit(Enum):
    Second = "S"
    Hertz = "HZ"
    Degree = "DEG"
    Percent = "PER"

class CursorManualVerticalUnit(Enum):
    Percent = "PER"
    Source = "SOUR"

class _CursorManual(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CURS:MAN")

    @property
    def type(self) -> CursorManualType:
        """Set or query the cursor type in manual cursor measurement mode."""
        return CursorManualType(self._query(":TYPE?"))

    @type.setter
    def type(self, value: CursorManualType):
        self._write(":TYPE %s" % (value.value))

    @property
    def source(self) -> CursorManualSource:
        """Set or query the channel source of the manual cursor measurement mode."""
        return CursorManualSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: CursorManualSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def horizontal_unit(self) -> CursorManualHorizontalUnit:
        """Set or query the horizontal unit in the manual cursor measurement mode."""
        return CursorManualHorizontalUnit(self._query(":TUN?"))

    @horizontal_unit.setter
    def horizontal_unit(self, value: CursorManualHorizontalUnit):
        self._write(":TUN %s" % (value.value))

    @property
    def vertical_unit(self) -> CursorManualVerticalUnit:
        """Set or query the vertical unit in the manual cursor measurement mode."""
        return CursorManualVerticalUnit(self._query(":VUN?"))

    @vertical_unit.setter
    def vertical_unit(self, value: CursorManualVerticalUnit):
        self._write(":VUN %s" % (value.value))

    @property
    def ax(self) -> int:
        """Set or query the horizontal position of cursor A 
        in the manual cursor measurement mode."""
        return self._query_int(":AX?")

    @ax.setter
    def ax(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":AX %u" % (value))

    @property
    def bx(self) -> int:
        """Set or query the horizontal position of cursor B 
        in the manual cursor measurement mode."""
        return self._query_int(":BX?")

    @bx.setter
    def bx(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":BX %u" % (value))

    @property
    def ay(self) -> int:
        """Set or query the vertical position of cursor A 
        in the manual cursor measurement mode."""
        return self._query_int(":AY?")

    @ay.setter
    def ay(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":AY %u" % (value))

    @property
    def by(self) -> int:
        """Set or query the vertical position of cursor B 
        in the manual cursor measurement mode."""
        return self._query_int(":BY?")

    @by.setter
    def by(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":BY %u" % (value))

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in the manual cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in the manual cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in the manual cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in the manual cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":BYV?")

    @property
    def x_delta(self) -> float:
        """Query the difference between the X values of cursor A and cursor B (BX-AX)
        in the manual cursor measurement mode. 
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":XDEL?")

    @property
    def x_delta_inverse(self) -> float:
        """Query the reciprocal of the absolute value of the difference 
        between the X values of cursor A and cursor B (1/|dX|) 
        in the manual cursor measurement mode. The unit depends on the 
        horizontal unit currently selected."""
        return self._query_float(":IXDEL?")

    @property
    def y_delta(self) -> float:
        """Query the difference between the Y values of cursor A and cursor B (BY-AY)
        in the manual cursor measurement mode. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":YDEL?")


class CursorTrackSource(Enum):
    Off = "OFF"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"

class _CursorTrack(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CURS:TRAC")

    @property
    def source1(self) -> CursorTrackSource:
        """Set or query the channel source of cursor A in the track cursor measurement mode."""
        return CursorTrackSource(self._query(":SOUR1?"))

    @source1.setter
    def source1(self, value: CursorTrackSource):
        self._write(":SOUR1 %s" % (value.value))
    
    @property
    def source2(self) -> CursorTrackSource:
        """Set or query the channel source of cursor B in the track cursor measurement mode."""
        return CursorTrackSource(self._query(":SOUR2?"))

    @source2.setter
    def source2(self, value: CursorTrackSource):
        self._write(":SOUR2 %s" % (value.value))

    @property
    def ax(self) -> int:
        """Set or query the horizontal position of cursor A 
        in the track cursor measurement mode."""
        return self._query_int(":AX?")

    @ax.setter
    def ax(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":AX %u" % (value))

    @property
    def bx(self) -> int:
        """Set or query the horizontal position of cursor B 
        in the track cursor measurement mode."""
        return self._query_int(":BX?")

    @bx.setter
    def bx(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":BX %u" % (value))

    @property
    def ay(self) -> int:
        """Set or query the vertical position of cursor A 
        in the track cursor measurement mode."""
        return self._query_int(":AY?")

    @ay.setter
    def ay(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":AY %u" % (value))

    @property
    def by(self) -> int:
        """Set or query the vertical position of cursor B 
        in the track cursor measurement mode."""
        return self._query_int(":BY?")

    @by.setter
    def by(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":BY %u" % (value))

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in the track cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in the track cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in the track cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in the track cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":BYV?")

    @property
    def x_delta(self) -> float:
        """Query the difference between the X values of cursor A and cursor B (BX-AX)
        in the track cursor measurement mode. 
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":XDEL?")

    @property
    def x_delta_inverse(self) -> float:
        """Query the reciprocal of the absolute value of the difference 
        between the X values of cursor A and cursor B (1/|dX|) 
        in the track cursor measurement mode. The unit depends on the 
        horizontal unit currently selected."""
        return self._query_float(":IXDEL?")

    @property
    def y_delta(self) -> float:
        """Query the difference between the Y values of cursor A and cursor B (BY-AY)
        in the track cursor measurement mode. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":YDEL?")

class CursorItem(Enum):
    Off = "OFF"
    Item1 = "ITEM1"
    Item2 = "ITEM2"
    Item3 = "ITEM3"
    Item4 = "ITEM4"

class _CursorAuto(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CURS:AUTO")
    
    @property
    def item(self) -> CursorItem:
        """Select the parameters to be measured by the auto cursor 
        from the five parameters enabled last or query the parameters currently measured by the auto cursor."""
        return CursorItem(self._query(":ITEM?"))

    @item.setter
    def item(self, value: CursorItem):
        self._write(":ITEM %s" % (value.value))

    @property
    def ax(self) -> int:
        """Query the horizontal position of cursor A in auto cursor measurement."""
        return self._query_int(":AX?")

    @property
    def bx(self) -> int:
        """Query the horizontal position of cursor B in auto cursor measurement."""
        return self._query_int(":BX?")

    @property
    def ay(self) -> int:
        """Query the vertical position of cursor A in auto cursor measurement."""
        return self._query_int(":AY?")

    @property
    def by(self) -> int:
        """Query the vertical position of cursor B in auto cursor measurement."""
        return self._query_int(":BY?")

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in auto cursor measurement.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in auto cursor measurement. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in auto cursor measurement.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in auto cursor measurement. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":BYV?")

class _CursorXY(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":CURS:XY")

    @property
    def ax(self) -> int:
        """Query the horizontal position of cursor A in auto cursor measurement."""
        return self._query_int(":AX?")

    @ax.setter
    def ax(self, value: int):
        #assert value >= 5 and value <= 394
        self._write(":AX %u" % (value))

    @property
    def bx(self) -> int:
        """Query the horizontal position of cursor B in auto cursor measurement."""
        return self._query_int(":BX?")

    @bx.setter
    def bx(self, value: int):
        #assert value >= 5 and value <= 394
        self._write(":BX %u" % (value))

    @property
    def ay(self) -> int:
        """Query the vertical position of cursor A in auto cursor measurement."""
        return self._query_int(":AY?")

    @ay.setter
    def ay(self, value: int):
        #assert value >= 5 and value <= 394
        self._write(":AY %u" % (value))

    @property
    def by(self) -> int:
        """Query the vertical position of cursor B in auto cursor measurement."""
        return self._query_int(":BY?")

    @by.setter
    def by(self, value: int):
        #assert value >= 5 and value <= 394
        self._write(":BY %u" % (value))

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in XY cursor measurement.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in XY cursor measurement. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in XY cursor measurement.
        The unit depends on the horizontal unit currently selected."""
        return self._query_float(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in XY cursor measurement. 
        The unit depends on the vertical unit currently selected."""
        return self._query_float(":BYV?")

class DecoderMode(Enum):
    Parallel = "PAR"
    UART = "UART"
    SPI = "SPI"
    IIC = "IIC"

class DecoderFormat(Enum):
    Hexadecimal = "HEX"
    ASCII = "ASC"
    Decimal = "DEC"
    Binary = "BIN"
    Line = "LINE"

class _Decoder(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        self.index = index
        super().__init__(scope, ":DEC%u" % (index))

        self.threshold = _DecoderThreshold(scope, self.index)
        self.config = _DecoderConfig(scope, index)

        self.uart = _DecoderUart(scope, index)
        self.iic = _DecoderIic(scope, index)
        self.spi = _DecoderSpi(scope, index)
        self.parallel = _DecoderParallel(scope, index)

        self.event_table = _EventTable(scope, index)

    @property
    def mode(self) -> DecoderMode:
        """Set or query the decoder type."""
        return DecoderMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: DecoderMode):
        self._write(":MODE %s" % (value.value))

    @property
    def display(self) -> bool:
        """Turn on or off the decoder or query the status of the decoder."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

    @property
    def format(self) -> DecoderFormat:
        """Set or query the bus display format."""
        return DecoderFormat(self._query(":FORM?"))

    @format.setter
    def format(self, value: DecoderFormat):
        self._write(":FORM %s" % (value.value))

    @property
    def position(self) -> int:
        """Set or query the vertical position of the bus on the screen."""
        return self._query_int(":POS?")

    @position.setter
    def position(self, value: int):
        assert value >= 50 and value <= 350
        self._write_int(":POS", value)
    
class _DecoderThreshold(_Scpihelper):
    """Set or query the threshold level of the specified analog channel."""

    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:THRE" % (index))

    def __getitem__(self, key):
        #FIXME: is it better to have the index 1...4 or 0...3?
        assert key >= 1 and key <= 4
        self._query_float(":CHAN%u?" % (key))

    def __setitem__(self, key, value):
        assert key >= 1 and key <= 4
        self._write_float(":CHAN%u" % (key), value)
    
    @property
    def auto(self) -> bool:
        """Turn on or off the auto threshold function of the analog channels, 
        or query the status of the auto threshold function of the analog channels."""
        return self._query_bool(":AUTO?")
    
    @auto.setter
    def auto(self, value: bool):
        self._write_bool(":AUTO", value)

class _DecoderConfig(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:CONF" % (index))

    @property
    def label(self) -> bool:
        """Turn on or off the label display function, or query the status of the label display function."""
        return self._query_bool(":LAB?")
    
    @label.setter
    def label(self, value: bool):
        self._write_bool(":LAB", value)

    @property
    def line(self) -> bool:
        """Turn on or off the bus display function, or query the status of the bus display function."""
        return self._query_bool(":LINE?")
    
    @line.setter
    def line(self, value: bool):
        self._write_bool(":LINE", value)

    @property
    def format(self) -> bool:
        """Turn on or off the format display function, or query the status of the format display function."""
        return self._query_bool(":FORM?")
    
    @format.setter
    def format(self, value: bool):
        self._write_bool(":FORM", value)

    @property
    def endian(self) -> bool:
        """Turn on or off the endian display function in serial bus decoding, or query the status of the endian 
        display function in serial bus decoding."""
        return self._query_bool(":END?")
    
    @endian.setter
    def endian(self, value: bool):
        self._write_bool(":END", value)

    @property
    def width(self) -> bool:
        """Turn on or off the width display function, or query the status of the width display function."""
        return self._query_bool(":WID?")
    
    @width.setter
    def width(self, value: bool):
        self._write_bool(":WID", value)

    @property
    def sample_rate(self) -> bool:
        """Query the current digital sample rate."""
        return self._query_bool(":SRAT?")


class DecoderUartSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Off = "OFF"

class DecoderUartPolarity(Enum):
    Negative = "NEG"
    Positive = "POS"

class DecoderUartEndian(Enum):
    LSB = "LSB"
    MSB = "MSB"

class DecoderUartStopbits(Enum):
    One = "1"
    OnePointFive = "1.5"
    Two = "2"

class DecoderUartParity(Enum):
    No = "NONE"
    Even = "EVEN"
    Odd = "OFF"

class _DecoderUart(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:UART" % (index))

    @property
    def tx(self) -> DecoderUartSource:
        """Set or query the TX channel source of RS232 decoding."""
        return DecoderUartSource(self._query(":TX?"))

    @tx.setter
    def tx(self, value: DecoderUartSource):
        self._write(":TX %s" % (value.value))

    @property
    def rx(self) -> DecoderUartSource:
        """Set or query the RX channel source of RS232 decoding."""
        return DecoderUartSource(self._query(":RX?"))

    @rx.setter
    def rx(self, value: DecoderUartSource):
        self._write(":RX %s" % (value.value))

    @property
    def polarity(self) -> DecoderUartPolarity:
        """Set or query the polarity of RS232 decoding.
        Negative polarity high level = 0, low level = 1 (use this for RS232)
        Positive polarity high level = 1, low level = 0 (use this for TTL)"""
        return DecoderUartPolarity(self._query(":POL?"))

    @polarity.setter
    def polarity(self, value: DecoderUartPolarity):
        self._write(":POL %s" % (value.value))

    @property
    def endian(self) -> DecoderUartEndian:
        """Set or query the endian of RS232 decoding."""
        return DecoderUartEndian(self._query(":END?"))

    @endian.setter
    def endian(self, value: DecoderUartEndian):
        self._write(":END %s" % (value.value))

    @property
    def baudrate(self) -> int:
        """Set or query the baud rate of UART decoding. The default unit is bps (bits per second)."""
        return self._query_int(":BAUD?")

    @baudrate.setter
    def baudrate(self, value: int):
        assert value >= 110 and value <= 20e6
        self._write_int(":BAUD", value)

    @property
    def width(self) -> int:
        """Set or query the width of each frame of data in UART decoding."""
        return self._query_int(":WIDT?")

    @width.setter
    def width(self, value: int):
        assert value >= 5 and value <= 8
        self._write_int(":WIDT", value)

    @property
    def stopbits(self) -> DecoderUartStopbits:
        """Set or query the stop bit after each frame of data in RS232 decoding."""
        return DecoderUartStopbits(self._query(":STOP?"))

    @stopbits.setter
    def stopbits(self, value: DecoderUartStopbits):
        self._write(":STOP %s" % (value.value))

    @property
    def parity(self) -> DecoderUartParity:
        """Set or query the even-odd check mode of the data transmission in UART decoding."""
        return DecoderUartParity(self._query(":PAR?"))

    @parity.setter
    def parity(self, value: DecoderUartParity):
        self._write(":PAR %s" % (value.value))

class DecoderIicSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class DecoderIicAddress(Enum):
    Normal = "NORM"
    ReadWrite = "RW"

class _DecoderIic(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:UART" % (index))

    @property
    def clk(self) -> DecoderIicSource:
        """Set or query the signal source of the clock channel in I2C decoding."""
        return DecoderIicSource(self._query(":CLK?"))

    @clk.setter
    def clk(self, value: DecoderIicSource):
        self._write(":CLK %s" % (value.value))

    @property
    def data(self) -> DecoderIicSource:
        """Set or query the signal source of the data channel in I2C decoding."""
        return DecoderIicSource(self._query(":DATA?"))

    @data.setter
    def data(self, value: DecoderIicSource):
        self._write(":DATA %s" % (value.value))

    @property
    def address(self) -> DecoderIicAddress:
        """Set or query the address mode of I2C decoding."""
        return DecoderIicAddress(self._query(":ADDR?"))

    @address.setter
    def address(self, value: DecoderIicAddress):
        self._write(":ADDR %s" % (value.value))

class DecoderSpiSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Off = "OFF"

class DecoderSpiCspolarity(Enum):
    ActiveLow = "NCS"
    ActiveHigh = "CS"

class DecoderSpiFramesync(Enum):
    Chipselect = "CS"
    Timeout = "TIM"

class DecoderSpiPolarity(Enum):
    Negative = "NEG"
    Positive = "POS"

class DecoderSpiClockedge(Enum):
    Rise = "RISE"
    Fall = "FALL"

class DecoderSpiEndian(Enum):
    LSB = "LSB"
    MSB = "MSB"

class _DecoderSpi(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:SPI" % (index))

    @property
    def clk(self) -> DecoderSpiSource:
        """Set or query the signal source of the clock channel in SPI decoding."""
        return DecoderSpiSource(self._query(":CLK?"))

    @clk.setter
    def clk(self, value: DecoderSpiSource):
        assert value != DecoderSpiSource.Off
        self._write(":CLK %s" % (value.value))

    @property
    def miso(self) -> DecoderSpiSource:
        """Set or query the MISO channel source in SPI decoding."""
        return DecoderSpiSource(self._query(":MISO?"))

    @miso.setter
    def miso(self, value: DecoderSpiSource):
        self._write(":MISO %s" % (value.value))

    @property
    def mosi(self) -> DecoderSpiSource:
        """Set or query the MOSI channel source in SPI decoding."""
        return DecoderSpiSource(self._query(":MOSI?"))

    @mosi.setter
    def mosi(self, value: DecoderSpiSource):
        self._write(":MOSI %s" % (value.value))

    @property
    def cs(self) -> DecoderSpiSource:
        """Set or query the CS channel source in SPI decoding."""
        return DecoderSpiSource(self._query(":CS?"))

    @cs.setter
    def cs(self, value: DecoderSpiSource):
        assert value != DecoderSpiSource.Off
        self._write(":CS %s" % (value.value))

    @property
    def cs_polarity(self) -> DecoderSpiCspolarity:
        """Set or query the CS polarity in SPI decoding."""
        return DecoderSpiCspolarity(self._query(":SEL?"))

    @cs_polarity.setter
    def cs_polarity(self, value: DecoderSpiCspolarity):
        self._write(":SEL %s" % (value.value))

    @property
    def frame_sync(self) -> DecoderSpiFramesync:
        """Set or query the frame synchronization mode of SPI decoding."""
        return DecoderSpiFramesync(self._query(":MODE?"))

    @frame_sync.setter
    def frame_sync(self, value: DecoderSpiFramesync):
        self._write(":MODE %s" % (value.value))

    @property
    def timeout(self) -> float:
        """Set or query the timeout time in the timeout mode of SPI decoding. 
        The default unit is s."""
        return self._query_float(":TIM?")

    @timeout.setter
    def timeout(self, value: float):
        assert value > 0
        self._write_float(":TIM", value)

    @property
    def polarity(self) -> DecoderSpiPolarity:
        """Set or query the polarity of the SDA data line in SPI decoding."""
        return DecoderSpiPolarity(self._query(":POL?"))

    @polarity.setter
    def polarity(self, value: DecoderSpiPolarity):
        self._write(":POL %s" % (value.value))

    @property
    def clock_edge(self) -> DecoderSpiClockedge:
        """Set or query the clock type when the instrument samples the data line in SPI decoding."""
        return DecoderSpiClockedge(self._query(":EDGE?"))

    @clock_edge.setter
    def clock_edge(self, value: DecoderSpiClockedge):
        self._write(":EDGE %s" % (value.value))

    @property
    def endian(self) -> DecoderSpiEndian:
        """Set or query the endian of the SPI decoding data."""
        return DecoderSpiEndian(self._query(":END?"))

    @endian.setter
    def endian(self, value: DecoderSpiEndian):
        self._write(":END %s" % (value.value))

    @property
    def width(self) -> int:
        """Set or query the number of bits of each frame of data in SPI decoding."""
        return self._query_int(":WIDT?")

    @width.setter
    def width(self, value: int):
        assert value >= 8 and value <= 32
        self._write_int(":WIDT", value)

class DecoderParallelSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class DecoderParallelEdge(Enum):
    Rise = "RISE"
    Fall = "FALL"
    Both = "BOTH"

class DecoderParallelPolarity(Enum):
    Negative = "NEG"
    Positive = "POS"

class _DecoderSpiBitsource(_Scpihelper):
    """Set ro query the channel source of the data bit."""

    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:PAR" % (index))

    def __getitem__(self, key):
        assert key >= 0 and key <= 15
        self._write_int(":BITX", key)
        return DecoderParallelSource(self._query(":SOUR?"))

    def __setitem__(self, key, value: DecoderParallelSource):
        assert key >= 0 and key <= 15
        self._write_int(":BITX", key)
        self._write(":SOUR %s" % (value.value))

class _DecoderParallel(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        super().__init__(scope, ":DEC%u:PAR" % (index))

        self.bits = _DecoderSpiBitsource(scope, index)

    @property
    def clock(self) -> Enum:
        """Set or query the CLK channel source of parallel decoding."""
        return Enum(self._query(":CLK?"))

    @clock.setter
    def clock(self, value: Enum):
        self._write(":CLK %s" % (value.value))

    @property
    def edge(self) -> DecoderParallelEdge:
        """Set or query the edge type of the clock channel when the instrument samples the data channel in parallel decoding."""
        return DecoderParallelEdge(self._query(":EDGE?"))

    @edge.setter
    def edge(self, value: DecoderParallelEdge):
        self._write(":EDGE %s" % (value.value))

    @property
    def width(self) -> int:
        """Set or query the data width (namely the number of bits of each frame of data) of the parallel bus."""
        return self._query_int(":WIDT?")

    @width.setter
    def width(self, value: int):
        assert value >= 1 and value <= 16
        self._write_int(":WIDT", value)

    @property
    def prop_enum(self) -> DecoderParallelPolarity:
        """Set or query the data polarity of parallel decoding"""
        return DecoderParallelPolarity(self._query(":POL?"))

    @prop_enum.setter
    def prop_enum(self, value: DecoderParallelPolarity):
        self._write(":POL %s" % (value.value))

    @property
    def noise_reject(self) -> bool:
        """Turn on or off the noise rejection function of parallel decoding, 
        or query the status of the noise rejection function of parallel decoding."""
        return self._query_bool(":NREJ?")
    
    @noise_reject.setter
    def noise_reject(self, value: bool):
        self._write_bool(":NREJ", value)

    @property
    def noise_reject_time(self) -> float:
        """Set or query the noise rejection time of parallel decoding. The default unit is s."""
        return self._query_float(":NRT?")

    @noise_reject_time.setter
    def noise_reject_time(self, value: float):
        assert value >= 0 and value <= 100e-3
        self._write_float(":NRT", value)

    @property
    def clock_compensation(self) -> float:
        """Set or query the clock compensation time of parallel decoding. The default unit is s."""
        return self._query_float(":CCOM?")

    @clock_compensation.setter
    def clock_compensation(self, value: float):
        assert value >= -100e-3 and value <= 100e-3
        self._write_float(":CCOM", value)

    @property
    def plot(self) -> bool:
        """Turn on or off the curve function of parallel decoding, or query the status of the curve function of parallel decoding."""
        return self._query_bool(":PLOT?")
    
    @plot.setter
    def plot(self, value: bool):
        self._write_bool(":PLOT", value)

class DisplayType(Enum):
    Vectors = "VECT"
    Dots = "DOTS"

class DisplayPersistence(Enum):
    Minimum = "MIN"
    Time_100ms = "0.1"
    Time_200ms = "0.2"
    Time_500ms = "0.5"
    Time_1s = "1"
    Time_5s = "5"
    Time_10s = "10"
    Infinite = "INF"

class DisplayGrid(Enum):
    Full = "FULL"
    Half = "GALF"
    Off = "NONE"

class DisplayDataFormat(Enum):
    BMP24 = "BMP24"
    BMP8 = "BMP8"
    PNG = "PNG"
    JPEG = "JPEG"
    TIFF = "TIFF"

class _Display(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":DISP")

    def clear(self):
        """Clear all the waveforms on the screen."""
        self._write(":CLE")

    def save_screenshot(self, filename: str = None, color: bool = True, 
        invert: bool = False, format: DisplayDataFormat = DisplayDataFormat.PNG):
        """Read the data stream of the image currently displayed on the screen 
        and set the color, invert display, and format of the image acquired.

        Args:
            filename (str, optional): if provided, the image data is saved to the destination. Defaults to None.
            color (bool, optional): color of the image, True for color, False denotes intensity graded color. Defaults to True.
            invert (bool, optional): inverts the image. Defaults to False.
            format (DisplayDataFormat, optional): file format of the. Defaults to DisplayDataFormat.PNG.

        Returns:
            b'': bytestring of the image data
        """
        cmd = "%s:DATA? %u,%u,%s" % (
            self.message_prefix,
            1 if color else 0,
            1 if invert else 0,
            format.value
        )

        data = bytearray(self.resource.query_binary_values(cmd, "B"))

        if filename:
            try:
                os.remove(filename)
            except OSError:
                pass
            with open(filename, 'wb') as fs:
                fs.write(data)

        return data

    @property
    def type(self) -> DisplayType:
        """Set or query the display mode of the waveform on the screen."""
        return DisplayType(self._query(":TYPE?"))

    @type.setter
    def type(self, value: DisplayType):
        self._write(":TYPE %s" % (value.value))

    @property
    def persistence(self) -> DisplayPersistence:
        """Set or query the persistence time."""
        return DisplayPersistence(self._query(":GRAD?"))

    @persistence.setter
    def persistence(self, value: DisplayPersistence):
        self._write(":GRAD %s" % (value.value))

    @property
    def waveform_brightness(self) -> int:
        """Set or query the waveform brightness."""
        return self._query_int(":WBR?")

    @waveform_brightness.setter
    def waveform_brightness(self, value: int):
        assert value >= 0 and value <= 100
        self._write(":WBR %u" % (value))

    @property
    def grid(self) -> DisplayGrid:
        """ Set or query the grid type of screen display."""
        return DisplayGrid(self._query(":GRID?"))

    @grid.setter
    def grid(self, value: DisplayGrid):
        self._write(":GRID %s" % (value.value))

    @property
    def grid_brightness(self) -> int:
        """Set or query the grid type of screen display."""
        return self._query_int(":GBR?")

    @grid_brightness.setter
    def grid_brightness(self, value: int):
        assert value >= 0 and value <= 100
        self._write(":GBR %u" % (value))

class EventTableFormat(Enum):
    Hexadecimal = "HEX"
    ASCII = "ASC"
    Decimal = "DEC"

class EventTableView(Enum):
    Package = "PACK"
    Detail = "DET"
    Payload = "PAYL"

class EventTableColumn(Enum):
    Data = "DATA"
    TX = "TX"
    RX = "RX"
    MISO = "MISO"
    MOSI = "MOSI"

class EventTableSort(Enum):
    Ascending = "ASC"
    Descending = "DESC"

class _EventTable(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index in (1, 2)
        self.index = index
        super().__init__(scope, ":ETAB%u" % (index))

    @property
    def display(self) -> bool:
        """Turn on or off the decoding event table, or query the status of the decoding event table."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

    @property
    def format(self) -> EventTableFormat:
        """Set or query the data display format of the event table."""
        return EventTableFormat(self._query(":FORM?"))

    @format.setter
    def format(self, value: EventTableFormat):
        self._write(":FORM %s" % (value.value))

    @property
    def view(self) -> EventTableView:
        """Set or query the display mode of the event table."""
        return EventTableView(self._query(":VIEW?"))

    @view.setter
    def view(self, value: EventTableView):
        self._write(":VIEW %s" % (value.value))

    @property
    def column(self) -> EventTableColumn:
        """Set or query the current column of the event table."""
        return EventTableColumn(self._query(":COL?"))

    @column.setter
    def column(self, value: EventTableColumn):
        self._write(":COL %s" % (value.value))

    @property
    def row(self) -> int:
        """Set or query the current row of the event table."""
        return self._query_int(":ROW?")

    @row.setter
    def row(self, value: int):
        assert True
        self._write_int(":ROW", value)

    @property
    def sort(self) -> EventTableSort:
        """Set or query the display type of the decoding results in the event table."""
        return EventTableSort(self._query(":SORT?"))

    @sort.setter
    def sort(self, value: EventTableSort):
        self._write(":SORT %s" % (value.value))

    @property
    def data(self) -> str:
        tmp = self._query(":DATA?", True)
        if len(tmp) < 2:
            return ""
        if tmp[0] != "#":
            raise Exception("No TMC header found")
        hlen = int(tmp[1])

        return tmp[hlen+2:]

#TODO: Function
#TODO: Digital Channels
#TODO: LAN

class MathOperator(Enum):
    Add = "ADD"
    Subtract = "SUBT"
    Multiply = "MULT"
    Division = "DIV"
    And = "AND"
    Or = "OR"
    Xor = "XOR"
    Not = "NOT"
    FFT = "FFT"
    Integrate = "INTG"
    Differentiate = "DIFF"
    Sqrt = "SQRT"
    Log = "LOG"
    Ln = "LN"
    Exp = "EXP"
    Absolute = "ABS"
    Filter = "FILT"

class MathAlgebraicSource(Enum):
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    FX = "FX"

class MathLogicSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    FX = "FX"

class _Math(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MATH")

        self.fft = _MathFFT(scope)
        self.filter = _MathFilter(scope)
        self.option = _MathOption(scope)
    
    @property
    def display(self) -> bool:
        """Enable or disable the math operation function or query the math operation status."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

    @property
    def operator(self) -> MathOperator:
        """Set or query the operator of the math operation."""
        return MathOperator(self._query(":OPER?"))

    @operator.setter
    def operator(self, value: MathOperator):
        self._write(":OPER %s" % (value.value))

    @property
    def source1(self) -> MathAlgebraicSource:
        """Set or query the source or source A of algebraic operation/functional operation/the outer layer operation of compound operation."""
        return MathAlgebraicSource(self._query(":SOUR1?"))

    @source1.setter
    def source1(self, value: MathAlgebraicSource):
        self._write(":SOUR1 %s" % (value.value))

    @property
    def source2(self) -> MathAlgebraicSource:
        """Set or query the source or source B of algebraic operation/functional operation/the outer layer operation of compound operation."""
        return MathAlgebraicSource(self._query(":SOUR2?"))

    @source2.setter
    def source2(self, value: MathAlgebraicSource):
        self._write(":SOUR2 %s" % (value.value))

    @property
    def logic_source1(self) -> MathLogicSource:
        """Set or query source A of logic operation."""
        return MathLogicSource(self._query(":LSOU1?"))

    @logic_source1.setter
    def logic_source1(self, value: MathLogicSource):
        self._write(":LSOU1 %s" % (value.value))

    @property
    def logic_source2(self) -> MathLogicSource:
        """Set or query source B of logic operation."""
        return MathLogicSource(self._query(":LSOU2?"))

    @logic_source2.setter
    def logic_source2(self, value: MathLogicSource):
        self._write(":LSOU2 %s" % (value.value))

    @property
    def scale(self) -> float:
        """Set or query the vertical scale of the operation result. Must be in 1-2-5 steps
        The unit depends on the operator currently selected and the unit of the source."""
        return self._query_float(":SCAL?")

    @scale.setter
    def scale(self, value: float):
        assert value >= 1e-12 and value >= 5e12
        self._write_float(":SCAL", value)
    
    @property
    def offset(self) -> float:
        """et or query the vertical offset of the operation result. 
        The unit depends on the operator currently selected and the unit of the source.
        
        Related to the vertical scale of the operation result 
        Range: (-1000 x MathVerticalScale) to (1000 x MathVerticalScale) 
        Step: MathVerticalScale/50"""
        return self._query_float(":OFFS?")

    @offset.setter
    def offset(self, value: float):
        self._write_float(":OFFS", value)

    @property
    def invert(self) -> bool:
        """Enable or disable the inverted display mode of the operation result, 
        or query the inverted display mode status of the operation result."""
        return self._query_bool(":INV?")
    
    @invert.setter
    def invert(self, value: bool):
        self._write_bool(":INV", value)

    def reset(self):
        """Sending this command, the instrument adjusts the vertical scale of the operation result to the
        most proper value according to the current operator and the horizontal timebase of the source."""
        self._write(":RES")

class MathFFTSource(Enum):
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class MathFFTWindow(Enum):
    Rectangle = "RECT"
    Blackman = "BLAC"
    Hanning = "HANN"
    Hamming = "HAMM"
    Flattop = "FLAT"
    Triangle = "TRI"

class MathFFTUnit(Enum):
    Vrms = "VRMS"
    Decibel = "DB"

class MathFFTMode(Enum):
    Trace = "TRAC"
    Memory = "MEM"

class _MathFFT(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MATH:FFT")
    
    @property
    def source(self) -> MathFFTSource:
        """Set or query the source of FFT operation/filter."""
        return MathFFTSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: MathFFTSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def window(self) -> MathFFTWindow:
        """Set or query the window function of the FFT operation."""
        return MathFFTWindow(self._query(":WIND?"))

    @window.setter
    def window(self, value: MathFFTWindow):
        self._write(":WIND %s" % (value.value))

    @property
    def prop_bool(self) -> bool:
        """Enable or disable the half-screen display mode of the FFT operation, or query the status 
        of the half display mode of the FFT operation."""
        return self._query_bool(":SPL?")
    
    @prop_bool.setter
    def prop_bool(self, value: bool):
        self._write_bool(":SPL", value)

    @property
    def unit(self) -> MathFFTUnit:
        """Set or query the vertical unit of the FFT operation result."""
        return MathFFTUnit(self._query(":UNIT?"))

    @unit.setter
    def unit(self, value: MathFFTUnit):
        self._write(":UNIT %s" % (value.value))

    @property
    def horizontal_scale(self) -> float:
        """Set or query the horizontal scale of the FFT operation result. The default unit is Hz.
        Can be set to 1/1000, 1/400, 1/200, 1/100, 1/40, or 1/20 of the FFT sample rate."""
        return self._query_float(":HSC?")

    @horizontal_scale.setter
    def horizontal_scale(self, value: float):
        assert value > 0
        self._write_float(":HSC", value)

    @property
    def center_frequency(self) -> float:
        """Set or query the center frequency of the FFT operation result, namely the frequency 
        relative to the horizontal center of the screen.
        The default unit is Hz."""
        return self._query_float(":HCEN?")

    @center_frequency.setter
    def center_frequency(self, value: float):
        assert value > 0
        self._write_float(":HCEN", value)
    
    @property
    def mode(self) -> MathFFTMode:
        """Set or query the FFT mode."""
        return MathFFTMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: MathFFTMode):
        self._write(":MODE %s" % (value.value))

class MathFilterType(Enum):
    Lowpass = "LPAS"
    Highpass = "HPAS"
    Bandpass = "BPAS"
    Bandstop = "BSTOP"

class _MathFilter(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MATH:FILT")

    @property
    def type(self) -> MathFilterType:
        """Set or query the filter type."""
        return MathFilterType(self._query(":TYPE?"))

    @type.setter
    def type(self, value: MathFilterType):
        self._write(":TYPE %s" % (value.value))

    @property
    def cutoff_frequency1(self) -> float:
        """Set or query the cutoff frequency (ωc1) of the low pass/high pass filter or cutoff 
        frequency 1 (ωc1) of the band pass/band stop filter. The default unit is Hz."""
        return self._query_float(":W1?")

    @cutoff_frequency1.setter
    def cutoff_frequency1(self, value: float):
        assert value > 0
        self._write_float(":W1", value)

    @property
    def cutoff_frequency2(self) -> float:
        """Set or query the cutoff frequency (ωc2) of the low pass/high pass filter or cutoff 
        frequency 2 (ωc2) of the band pass/band stop filter. The default unit is Hz."""
        return self._query_float(":W2?")

    @cutoff_frequency2.setter
    def cutoff_frequency2(self, value: float):
        assert value > 0
        self._write_float(":W2", value)

class _MathOption(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MATH:OPT")

        self.fx = _MathOptionFX(scope)

    @property
    def start(self) -> int:
        """Set or query the start point of the waveform math operation."""
        return self._query_int(":STAR?")

    @start.setter
    def start(self, value: int):
        assert value >= 0 and value < 1200
        self._write_int(":STAR", value)

    @property
    def end(self) -> int:
        """Set or query the end point of the waveform math operation."""
        return self._query_int(":END?")

    @end.setter
    def end(self, value: int):
        assert value >= 1 and value <= 1200
        self._write_int(":END", value)

    @property
    def invert(self) -> bool:
        """Enable or disable the inverted display mode of the operation result, 
        or query the inverted display mode status of the operation result."""
        return self._query_bool(":INV?")
    
    @invert.setter
    def invert(self, value: bool):
        self._write_bool(":INV", value)

    @property
    def sensitivity(self) -> float:
        """Set or query the sensitivity of the logic operation. The default unit is div 
        (namely the current vertical scale)."""
        return self._query_float(":SENS?")

    @sensitivity.setter
    def sensitivity(self, value: float):
        assert value >= 0 and value <= 0.96
        self._write_float(":SENS", value)

    @property
    def distance(self) -> int:
        """Set or query the smoothing window width of differential operation (diff)."""
        return self._query_int(":DIS?")

    @distance.setter
    def distance(self, value: int):
        assert value >= 3 and value >= 201
        self._write_int(":DIS", value)

    @property
    def autoscale(self) -> bool:
        """Enable or disable the auto scale setting of the operation result 
        or query the status of the auto scale setting."""
        return self._query_bool(":ASC?")
    
    @autoscale.setter
    def autoscale(self, value: bool):
        self._write_bool(":ASC", value)

    @property
    def threshold1(self) -> float:
        """Set or query the threshold level of source A in logic operations. The default unit is V.
        Range: ((-4 x VerticalScale - VerticalOffset) to 4 x VerticalScale - VerticalOffset) """
        return self._query_float(":THR1?")

    @threshold1.setter
    def threshold1(self, value: float):
        assert True
        self._write_float(":THR1", value)

    @property
    def threshold2(self) -> float:
        """Set or query the threshold level of source B in logic operations. The default unit is V.
        Range: ((-4 x VerticalScale - VerticalOffset) to 4 x VerticalScale - VerticalOffset) """
        return self._query_float(":THR2?")

    @threshold2.setter
    def threshold2(self, value: float):
        assert True
        self._write_float(":THR2", value)

class MathOptionFXSource(Enum):
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class MathOptionFXOperator(Enum):
    Add = "ADD"
    Subtract = "SUBT"
    Multiply = "MULT"
    Division = "DIV"

class _MathOptionFX(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MATH:OPT:FX")

    @property
    def source1(self) -> MathOptionFXSource:
        """Set or query source A of the inner layer operation of compound operation."""
        return MathOptionFXSource(self._query(":SOUR1?"))

    @source1.setter
    def source1(self, value: MathOptionFXSource):
        self._write(":SOUR1 %s" % (value.value))

    @property
    def source2(self) -> MathOptionFXSource:
        """Set or query source B of the inner layer operation of compound operation."""
        return MathOptionFXSource(self._query(":SOUR2?"))

    @source2.setter
    def source2(self, value: MathOptionFXSource):
        self._write(":SOUR2 %s" % (value.value))

    @property
    def operator(self) -> MathOptionFXOperator:
        """Set or query the operator of the inner layer operation of compound operation."""
        return MathOptionFXOperator(self._query(":OPER?"))

    @operator.setter
    def operator(self, value: MathOptionFXOperator):
        self._write(":OPER %s" % (value.value))


#TODO: Mask - Not available on DS1054z

class MeasureSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"

class MeasureCounterSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Off = "OFF"

class MeasureStatisticMode(Enum):
    Difference = "DIFF"
    Extremum = "EXTR"

class MeasureItem(Enum):
    Vmax = "VMAX"
    Vmin = "VMIN"
    Vpp = "VPP"
    Vtop = "VTOP"
    Vbase = "VBAS"
    Vamplitude = "VAMP"
    Vaverage = "VAVG"
    Vrms = "VRMS"
    Overshoot = "OVER"
    Preshoot = "PRES"
    Area = "MAR"
    PeriodArea = "MPAR"
    Period = "PER"
    Frequency = "FREQ"
    Risetime = "RTIM"
    Falltime = "FTIM"
    PositivePulseWidth = "PWID"
    NegativePulseWidth = "NWID"
    PositiveDutyCylce = "PDUT"
    NegativeDutyCylce = "NDUT"
    RisingEdgeDelay = "RDEL"
    FallingEdgeDelay = "FDEL"
    RisingEdgePhase = "RPH"
    FallingEdgePhase = "FPH"
    TimeMaximum = "TVMAX"
    TimeMinimum = "TVMIN"
    PositiveSlewRate = "PSLEW"
    NegativeSlewRate = "NSLEW"
    Vupper = "VUP"
    Vmid = "VMID"
    Vlower = "VLOW"
    Variance = "VARI"
    PeriodVrms = "PVRMS"
    PositivePulses = "PPUL"
    NegativePulses = "NPUL"
    PositiveEdges = "PEDG"
    NegativeEdges = "NEDG"

class MeasureStatisticType(Enum):
    Maximum = "MAX"
    Minimum = "MIN"
    Current = "CURR"
    Average = "AVER"
    Deviation = "DEV"

class MeasureAllmeasureSource(Flag):
    Channel1 = auto()
    Channel2 = auto()
    Channel3 = auto()
    Channel4 = auto()
    Math = auto()

    @classmethod
    def from_string(cls, s: str):
        tmp = cls(0)
        #FIXME: is there any better way to do this?
        a = s.upper().split(",")
        vals = {
            "CHAN1" : cls.Channel1,
            "CHAN2" : cls.Channel2,
            "CHAN3" : cls.Channel3,
            "CHAN4" : cls.Channel4,
            "MATH" : cls.Math
            }
        for val in vals:
            if val in a:
                tmp |= vals[val]
        return tmp

    def to_string(self):
        vals = {
            "CHAN1" : self.Channel1,
            "CHAN2" : self.Channel2,
            "CHAN3" : self.Channel3,
            "CHAN4" : self.Channel4,
            "MATH" : self.Math
            }
        tmp = []
        for val in vals:
            if vals[val] in self:
                tmp.append(val)
        return ",".join(tmp)

class _Measure(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MEAS")

        self.setup = _MeasureSetup(scope)
        self.statistics = _MeasureStatistics(scope)

    @property
    def source(self) -> MeasureSource:
        """Set or query the source of the current measurement parameter."""
        return MeasureSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: MeasureSource):
        self._write(":SOUR %s" % (value.value))
    
    @property
    def counter_source(self) -> MeasureCounterSource:
        """Set or query the source of the frequency counter, or disable the frequency counter."""
        return MeasureCounterSource(self._query(":COUN:SOUR?"))

    @counter_source.setter
    def counter_source(self, value: MeasureCounterSource):
        self._write(":COUN:SOUR %s" % (value.value))

    @property
    def counter_value(self) -> float:
        """Query the measurement result of the frequency counter. The default unit is Hz."""
        return self._query_float(":COUN:VAL?")
    
    def clear(self, item):
        """Clear one or all of the last five measurement items enabled.
        1 to 5 or True for all"""
        assert item in (1, 2, 3, 4, 5, True)
        if item is True:
            self._write(":CLE ALL")
        else:
            self._write(":CLE ITEM%u" % (item))

    def recover(self, item):
        """Recover the measurement item which has been cleared.
        1 to 5 or True for all"""
        assert item in (1, 2, 3, 4, 5, True)
        if item is True:
            self._write(":REC ALL")
        else:
            self._write(":REC ITEM%u" % (item))

    @property
    def all_display(self) -> bool:
        """Enable or disable the all measurement function, 
        or query the status of the all measurement function."""
        return self._query_bool(":ADIS?")
    
    @all_display.setter
    def all_display(self, value: bool):
        self._write_bool(":ADIS", value)

    @property
    def allmeasure_source(self) -> MeasureAllmeasureSource:
        """Set or query the source(s) of the all measurement function."""
        ans = self._query(":AMS?")
        return MeasureAllmeasureSource.from_string(ans)

    @allmeasure_source.setter
    def allmeasure_source(self, value: MeasureAllmeasureSource):
        self._write(":AMS %s" % (value.to_string()))

    def item_add(self, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Measure any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        assert item in (MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase) and source1 is not None

        message = ":ITEM %s" % (item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        self._write(message)

    def item_read(self, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Query the measurement result of any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        dualsource_measurements = (
            MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase)
        assert item not in dualsource_measurements or (item in dualsource_measurements and source2 is not None)

        message = ":ITEM? %s" % (item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        return self._query_float(message)

class MeasureSetupSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class _MeasureSetup(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MEAS:SET")

    @property
    def max(self) -> int:
        """Set or query the upper limit of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._query_int(":MAX?")

    @max.setter
    def max(self, value: int = 90):
        assert value >= 7 and value <= 95
        self._write(":MAX %u" % (value))

    @property
    def mid(self) -> int:
        """Set or query the middle point of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._query_int(":MID?")

    @mid.setter
    def mid(self, value: int = 50):
        assert value >= 6 and value <= 94
        self._write(":MID %u" % (value))

    @property
    def min(self) -> int:
        """Set or query the middle point of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._query_int(":MIN?")

    @min.setter
    def min(self, value: int = 10):
        assert value >= 5 and value <= 93
        self._write(":MIN %u" % (value))

    @property
    def phase_source_a(self) -> MeasureSetupSource:
        """Set or query source A of Phase (rising) 1→2 and Phase (falling) 1→2 measurements."""
        return MeasureSetupSource(self._query(":PSA?"))

    @phase_source_a.setter
    def phase_source_a(self, value: MeasureSetupSource):
        self._write(":PSA %s" % (value.value))

    @property
    def phase_source_b(self) -> MeasureSetupSource:
        """Set or query source B of Phase (rising) 1→2 and Phase (falling) 1→2 measurements."""
        return MeasureSetupSource(self._query(":PSB?"))

    @phase_source_b.setter
    def phase_source_b(self, value: MeasureSetupSource):
        self._write(":PSB %s" % (value.value))

    @property
    def delay_source_a(self) -> MeasureSetupSource:
        """Set or query source A of Delay (rising) 1→2 and Delay (falling) 1→2 measurements."""
        return MeasureSetupSource(self._query(":DSA?"))

    @delay_source_a.setter
    def delay_source_a(self, value: MeasureSetupSource):
        self._write(":DSA %s" % (value.value))

    @property
    def delay_source_b(self) -> MeasureSetupSource:
        """Set or query source B of Delay (rising) 1→2 and Delay (falling) 1→2 measurements."""
        return MeasureSetupSource(self._query(":DSB?"))

    @delay_source_b.setter
    def delay_source_b(self, value: MeasureSetupSource):
        self._write(":DSB %s" % (value.value))

class _MeasureStatistics(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":MEAS:STAT")

    @property
    def display(self) -> bool:
        """Enable or disable the statistic function, or query the status of the statistic function."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

    @property
    def mode(self) -> MeasureStatisticMode:
        """Set or query the statistic mode."""
        return MeasureStatisticMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: MeasureStatisticMode = MeasureStatisticMode.Extremum):
        self._write(":MODE %s" % (value.value))

    def reset(self):
        self._write(":RES")

    def item_add(self, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Enable the statistic function of any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        assert item in (MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase) and source1 is not None

        message = ":ITEM %s" % (item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        self._write(message)

    def reset(self):
        """Clear the history data and make statistic again."""
        self._write(":RES")

    def item_read(self, type: MeasureStatisticType, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Query the statistic function of any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        assert item in (MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase) and source2 is not None

        message = ":ITEM? %s,%s" % (type.value, item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        return self._query_float(message)

class ReferenceSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"

class _References(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":REF")

        self._items = [_Reference(scope, i) for i in range(1, 11)]

    def __getitem__(self, i):
        assert i >= 1 and i <= 10
        return self._items[i - 1]

    @property
    def display(self) -> bool:
        """Enable or disable the REF function, or query the status of the REF function."""
        return self._query_bool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write_bool(":DISP", value)

class ReferenceColor(Enum):
    Gray = "GRAY"
    Green = "GREE"
    Lightblue = "LBL"
    Magenta = "MAG"
    Orange = "ORAN"

class _Reference(_Scpihelper):
    def __init__(self, scope: DS1000z, index: int):
        assert index >= 1 and index <= 10
        self.index = index
        super().__init__(scope, ":REF%u" % (index))

    @property
    def enable(self) -> bool:
        """Enable or disable the specified reference channel, or query the status of the specified reference channel."""
        return self._query_bool(":ENAB?")
    
    @enable.setter
    def enable(self, value: bool):
        self._write_bool(":ENAB", value)

    @property
    def source(self) -> ReferenceSource:
        """Set or query the source of the current reference channel."""
        return ReferenceSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: ReferenceSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def vertical_scale(self) -> float:
        """Set or query the vertical scale of the specified reference channel. 
        The unit is the same as the unit of the source."""
        return self._query_float(":VSC?")

    @vertical_scale.setter
    def vertical_scale(self, value: float):
        assert value >= 1e-3 and value <= 100
        self._write_float(":VSC", value)

    @property
    def vertical_offset(self) -> float:
        """Set or query the vertical offset of the specified reference channel. 
        The unit is the same as the unit of the source.
        Range: (-10 x RefVerticalScale) to (10 x RefVerticalScale)"""
        return self._query_float(":VOFF?")

    @vertical_offset.setter
    def vertical_offset(self, value: float):
        self._write_float(":VOFF", value)

    def reset(self):
        """Reset the vertical scale and vertical offset of the specified reference channel to their default values."""
        self._write(":RES")
    
    def save(self):
        """Store the waveform of the current reference channel to the internal memory as reference waveform."""
        self._write(":SAV")

    @property
    def color(self) -> ReferenceColor:
        """Set or query the display color of the current reference channel."""
        return ReferenceColor(self._query(":COL?"))

    @color.setter
    def color(self, value: ReferenceColor):
        self._write(":COL %s" % (value.value))

#TODO: Source
#TODO: Storage

class SystemLanguage(Enum):
    SimplifiedChinese = "SCH"
    TraditionalChinese = "TCH"
    English = "ENGL"
    Portuguese = "PORT"
    German = "GERM"
    Polish = "POL"
    Korean = "KOR"
    Japanese = "JAPA"
    French = "FREN"
    Russian = "RUSS"

class SystemPoweronsettings(Enum):
    Last = "LAT"
    Default = "DEF"

class _System(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":SYST")

    @property
    def autoscale_enable(self) -> bool:
        """Enable or disable the AUTO key on the front panel, or query the status of the AUTO key."""
        return self._query_bool(":AUT?")
    
    @autoscale_enable.setter
    def autoscale_enable(self, value: bool):
        self._write_bool(":AUT", value)

    @property
    def beeper_enable(self) -> bool:
        """Enable or disable the beeper, or query the status of the beeper."""
        return self._query_bool(":BEEP?")
    
    @beeper_enable.setter
    def beeper_enable(self, value: bool):
        self._write_bool(":BEEP", value)

    @property
    def error(self) -> str:
        """Query and delete the last system error message."""
        return self._query(":ERR?")

    @property
    def error_next(self) -> str:
        """Query and delete the next last system error message."""
        return self._query(":ERR:NEXT?")

    @property
    def horizontal_grid(self) -> int:
        """Query the number of grids in the horizontal direction of the instrument screen."""
        return self._query_int(":GAM?")

    @property
    def language(self) -> SystemLanguage:
        """Set or query the system language."""
        return SystemLanguage(self._query(":LANG?"))

    @language.setter
    def language(self, value: SystemLanguage):
        self._write(":LANG %s" % (value.value))

    @property
    def lock(self) -> bool:
        """Enable or disable the keyboard lock function, or query the status of the keyboard lock function."""
        return self._query_bool(":LOCK?")
    
    @lock.setter
    def lock(self, value: bool):
        self._write_bool(":LOCK", value)

    @property
    def power_on_settings(self) -> SystemPoweronsettings:
        """Set or query the system configuration to be recalled when the oscilloscope is powered on again after power-off."""
        return SystemPoweronsettings(self._query(":PON?"))

    @power_on_settings.setter
    def power_on_settings(self, value: SystemPoweronsettings):
        self._write(":PON %s" % (value.value))

    def option_install(self, option: str):
        """Install a option.

        Args:
            option (str): license code for the option
        """
        assert len(option) == 28
        self._write("OPT:INST %s" % (option))

    def options_uninstall(self, confirm: bool = False):
        """Unionstall the options installed.

        Args:
            confirm (bool, optional): confirm that you want to do this. Defaults to False.
        """
        assert confirm is True
        self._write("OPT:UNINST")

    @property
    def analog_channsels(self) -> int:
        """Query the number of analog channels of the instrument.
        This always returns 4"""
        return self._query_int(":RAM?")

    @property
    def setup(self) -> bytearray:
        """Import the setting parameters of the oscilloscope to restore the oscilloscope to the specified setting."""
        return bytearray(self.resource.query_binary_values("%s:SET?" % (self.message_prefix), "B"))

    @setup.setter
    def setup(self, value: bytearray):
        #FIXME: this doesn't work
        raise Exception("this does not compute")
        self._write(":SET #9%9u%s" % (len(value), value))

#TODO: Trace

class TimebaseMode(Enum):
    Main = "MAIN"
    XY = "XY"
    Roll = "ROLL"

class _Timebase(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":TIM")

    @property
    def delay_enable(self) -> bool:
        """Enable or disable the delayed sweep, or query the status of the delayed sweep."""
        return self._query_bool(":DEL:ENAB?")
    
    @delay_enable.setter
    def delay_enable(self, value: bool):
        self._write_bool(":DEL:ENAB", value)

    @property
    def delay_offset(self) -> float:
        """Set or query the delayed timebase offset. The default unit is s."""
        return self._query_float(":DEL:OFFS?")

    @delay_offset.setter
    def delay_offset(self, value: float):
        assert True
        self._write_float(":DEL:OFFS", value)

    @property
    def delay_scale(self) -> float:
        """Set or query the delayed timebase scale. The default unit is s/div."""
        return self._query_float(":DEL:SCAL?")

    @delay_scale.setter
    def delay_scale(self, value: float):
        assert True
        self._write_float(":DEL:SCAL", value)

    @property
    def offset(self) -> float:
        """Set or query the main timebase offset. The default unit is s."""
        return self._query_float(":OFFS?")

    @offset.setter
    def offset(self, value: float):
        assert True
        self._write_float(":OFFS", value)

    @property
    def scale(self) -> float:
        """Set or query the main timebase scale. The default unit is s/div."""
        return self._query_float(":SCAL?")

    @scale.setter
    def scale(self, value: float):
        assert True
        self._write_float(":SCAL", value)

    @property
    def mode(self) -> TimebaseMode:
        """Set or query the mode of the horizontal timebase."""
        return TimebaseMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: TimebaseMode):
        self._write(":MODE %s" % (value.value))

class TriggerMode(Enum):
    Edge = "EDGE"
    Pulse = "PULS"
    Runt = "RUNT"
    Window = "WIND"
    NthEdge = "NEDG"
    Slope = "SLOP"
    Video = "VID"
    Pattern = "PATT"
    Delay = "DEL"
    Timeout = "TIM"
    Duration = "DUR"
    SetupHold = "SHOL"
    RS232 = "RS232"
    I2C = "IIC"
    SPI = "SPI"

class TriggerCoupling(Enum):
    AC = "AC"
    DC = "DC"
    LFReject = "LFR"
    HFReject = "HFR"

class TriggerStatus(Enum):
    Triggered = "TD"
    Waiting = "WAIT"
    Run = "RUN"
    Auto = "AUTO"
    Stop = "STOP"

class TriggerSweep(Enum):
    Auto = "AUTO"
    Normal = "NORM"
    SingleShot = "SING"

class _Trigger(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":TRIG")

        self.edge = _TriggerEdge(scope)
        self.pulse = _TriggerPulse(scope)

    @property
    def mode(self) -> TriggerMode:
        """Select or query the trigger type."""
        return TriggerMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: TriggerMode):
        self._write(":MODE %s" % (value.value))

    @property
    def coupling(self) -> TriggerCoupling:
        """Select or query the trigger coupling type."""
        return TriggerCoupling(self._query(":COUP?"))

    @coupling.setter
    def coupling(self, value: TriggerCoupling):
        self._write(":COUP %s" % (value.value))

    @property
    def status(self) -> TriggerStatus:
        """Query the current trigger status."""
        return TriggerStatus(self._query(":STAT?"))

    @property
    def sweep(self) -> TriggerSweep:
        """Set or query the trigger mode."""
        return TriggerSweep(self._query(":SWE?"))

    @sweep.setter
    def sweep(self, value: TriggerSweep):
        self._write(":SWE %s" % (value.value))


    @property
    def holdoff(self) -> float:
        """Set or query the trigger holdoff time. The default unit is s."""
        return self._query_float(":HOLD?")

    @holdoff.setter
    def holdoff(self, value: float):
        assert value >= 16e-9 and value <= 10
        self._write_float(":HOLD", value)

    @property
    def noise_rejection(self) -> bool:
        """Enable or disable noise rejection, or query the status of noise rejection."""
        return self._query_bool(":NREJ?")
    
    @noise_rejection.setter
    def prop_bool(self, value: bool):
        self._write_bool(":NREJ", value)

    @property
    def position(self) -> int:
        """Query the position in the internal memory that corresponds to the waveform trigger position.
        -2 denotes that the instrument is not triggered and there is no trigger position.
        -1 denotes the instrument is triggered outside the internal memory; namely, at this point,
           users cannot set the instrument to read the data in the internal memory starting 
           from the trigger position.
        An integer that is greater than 0 denotes that the return value is the position in the internal
        memory that corresponds to the trigger position."""
        return self._query_int(":POS?")

class TriggerEdgeSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    AC = "AC"

class TriggerEdgeSlope(Enum):
    Rise = "POS"
    Fall = "NEG"
    Both = "RFAL"

class _TriggerEdge(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":TRIG:EDG")

    @property
    def source(self) -> TriggerEdgeSource:
        """Set or query the trigger source in edge trigger."""
        return TriggerEdgeSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: TriggerEdgeSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def slope(self) -> TriggerEdgeSlope:
        """Set or query the edge type in edge trigger."""
        return TriggerEdgeSlope(self._query(":SLOP?"))

    @slope.setter
    def slope(self, value: TriggerEdgeSlope):
        self._write(":SLOP %s" % (value.value))

    @property
    def level(self) -> float:
        """Set or query the trigger level in edge trigger. 
        The unit is the same as the current amplitude unit of the signal source selected.
        Range is ((-5 x VerticalScale - OFFSet) to 5 x VerticalScale - OFFSet"""
        return self._query_float(":LEV?")

    @level.setter
    def level(self, value: float):
        assert True
        self._write_float(":LEV", value)


class TriggerPulseSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"

class TriggerPulseWhen(Enum):
    PositiveGreater = "PGR"
    PositiveLess = "PLES"
    PositivePulseWindow = "PGL"

    NegativeGreater = "NGR"
    NegativeLess = "NLES"
    NegativePulseWindow = "NGL"

class _TriggerPulse(_Scpihelper):
    def __init__(self, scope: DS1000z):
        super().__init__(scope, ":TRIG:PULS")
    
    @property
    def source(self) -> TriggerPulseSource:
        """Set or query the channel of which the waveform data will be read."""
        return TriggerPulseSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: TriggerPulseSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def when(self) -> TriggerPulseWhen:
        """Set or query the trigger condition in pulse width trigger."""
        return TriggerPulseWhen(self._query(":WHEN?"))

    @when.setter
    def when(self, value: TriggerPulseWhen):
        self._write(":WHEN %s" % (value.value))

    @property
    def width(self) -> float:
        """Set or query the pulse width in pulse width trigger. The default unit is s."""
        return self._query_float(":WIDT?")

    @width.setter
    def width(self, value: float):
        assert value >= 8e-9 and value <= 10
        self._write_float(":WIDT", value)

    @property
    def upper_width(self) -> float:
        """Set or query the upper pulse width in pulse width trigger. The default unit is s."""
        return self._query_float(":UWID?")

    @upper_width.setter
    def upper_width(self, value: float):
        assert value >= 16e-9 and value <= 10
        self._write_float(":UWID", value)

    @property
    def lower_width(self) -> float:
        """Set or query the lower pulse width in pulse width trigger. The default unit is s."""
        return self._query_float(":WIDT?")

    @lower_width.setter
    def lower_width(self, value: float):
        assert value >= 8e-9 and value <= 9.99
        self._write_float(":WIDT", value)

    @property
    def level(self) -> float:
        """Set or query the trigger level in pulse width trigger. 
        The unit is the same as the current amplitude unit.
        Range is ((-5 x VerticalScale - OFFSet) to 5 x VerticalScale - OFFSet"""
        return self._query_float(":LEV?")

    @level.setter
    def level(self, value: float):
        assert True
        self._write_float(":LEV", value)

#TODO: :TRIGger:SLOPe
#TODO: :TRIGger:VIDeo
#TODO: :TRIGger:PATTern
#TODO: :TRIGger:DURATion
#TODO: :TRIGger:TIMeout
#TODO: :TRIGger:RUNT
#TODO: :TRIGger:WINDows
#TODO: :TRIGger:DELay 
#TODO: :TRIGger:SHOLd 
#TODO: :TRIGger:NEDGe 
#TODO: :TRIGger:RS232 
#TODO: :TRIGger:IIC 
#TODO: :TRIGger:SPI 

class WaveformSource(Enum):
    Digital0 = "D0"
    Digital1 = "D1"
    Digital2 = "D2"
    Digital3 = "D3"
    Digital4 = "D4"
    Digital5 = "D5"
    Digital6 = "D6"
    Digital7 = "D7"
    Digital8 = "D8"
    Digital9 = "D9"
    Digital10 = "D10"
    Digital11 = "D11"
    Digital12 = "D12"
    Digital13 = "D13"
    Digital14 = "D14"
    Digital15 = "D15"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"

class WaveformMode(Enum):
    """
    Normal: read the waveform data displayed on the screen
    Maximum: read the waveform data displayed on the screen when the instrument is in 
        the run state and the waveform data in the internal memory in the stop state
    Raw: read the waveform data in the internal memory. Note that the waveform data 
        in the internal memory can only be read when the oscilloscope is in the stop
        state and the oscilloscope cannot be operated during the reading process
    """
    Normal = "NORM"
    Maximum = "MAX" 
    Raw = "RAW"

class WaveformFormat(Enum):
    Word = "WORD"
    Byte = "BYTE"
    ASCII = "ASC"

class WaveformPreamble():
    def __init__(self, preambledata):
        assert len(preambledata) == 10
        self.format = None
        if preambledata[0] == "0":
            self.format = WaveformFormat.Byte
        elif preambledata[0] == "1":
            self.format = WaveformFormat.Word
        elif preambledata[0] == "2":
            self.format = WaveformFormat.ASCII

        self.type = None
        if preambledata[1] == "0":
            self.type = WaveformMode.Normal
        elif preambledata[1] == "1":
            self.type = WaveformMode.Maximum
        elif preambledata[1] == "2":
            self.type = WaveformMode.Raw

        self.points = int(preambledata[2])
        self.count = int(preambledata[3])
        self.xincrement = float(preambledata[4])
        self.xorigin = float(preambledata[5])
        self.xreference = float(preambledata[6])
        self.yincrement = float(preambledata[7])
        self.yorigin = float(preambledata[8])
        self.yreference = float(preambledata[9])


class _Waveform(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope, ":WAV")

    @property
    def source(self) -> WaveformSource:
        """Set or query the channel of which the waveform data will be read."""
        return WaveformSource(self._query(":SOUR?"))

    @source.setter
    def source(self, value: WaveformSource):
        self._write(":SOUR %s" % (value.value))

    @property
    def mode(self) -> WaveformMode:
        """Set or query the reading mode used by :WAVeform:DATA?."""
        return WaveformMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: WaveformMode):
        self._write(":MODE %s" % (value.value))

    @property
    def format(self) -> WaveformFormat:
        """Set or query the return format of the waveform data."""
        return WaveformFormat(self._query(":FORM?"))

    @format.setter
    def format(self, value: WaveformFormat):
        self._write(":FORM %s" % (value.value))

    @property
    def x_increment(self) -> float:
        """Query the time difference between two neighboring points 
        of the specified channel source in the X direction.
        
        In the NORMal mode, XINCrement = TimeScale/100. 
        In the RAW mode, XINCrement = 1/SampleRate. 
        In MAX mode, XINCrement = TimeScale/100 when the instrument is in running 
        status; XINCrement = 1/SampleRate when the instrument is in stop status.

        When the channel source is one from CHANnel1 to CHANnel4 or from D0 to D15, the unit is s. 
        When the channel source is MATH and the operation type is FFT, the unit is Hz."""
        return self._query_float(":XINC?")

    @property
    def x_origin(self) -> float:
        """Query the start time of the waveform data of the channel source 
        currently selected in the X direction.
        
        In NORMal mode, the query returns the start time of the waveform data displayed on the screen. 
        In RAW mode, the query returns the start time of the waveform data in the internal memory. 
        In MAX mode, the query returns the start time of the waveform data displayed on the 
        screen when the instrument is in running status; the query returns the start time of 
        the waveform data in the internal memory when the instrument is in stop status.

        When the channel source is one from CHANnel1 to CHANnel4 or from D0 to D15, the unit is s. 
        When the channel source is MATH and the operation type is FFT, the unit is Hz."""
        return self._query_float(":XOR?")

    @property
    def x_reference_time(self) -> float:
        """Query the reference time of the specified channel source in the X direction."""
        return self._query_float(":XREF?")

    @property
    def y_increment(self) -> float:
        """Query the waveform increment of the specified channel source in the Y direction. 
        The unit is the same as the current amplitude unit.
        
        In NORMal mode, YINCrement = VerticalScale/25. 
        In RAW mode, YINCrement is related to the Verticalscale of the internal waveform and the 
        Verticalscale currently selected. 
        In MAX mode, YINCrement = VerticalScale/25 when the instrument is in running status; 
        YINCrement is related to the Verticalscale of the internal waveform and the Verticalscale 
        currently selected when the instrument is in stop status.
        """
        return self._query_float(":YINC?")

    @property
    def y_origin(self) -> float:
        """Query the vertical offset relative to the vertical reference position 
        of the specified channel source in the Y direction.
        
        In NORMal mode, YORigin = VerticalOffset/YINCrement. 
        In RAW mode, YORigin is related to the Verticalscale of the internal waveform and the 
        Verticalscale currently selected. 
        In MAX mode, YORigin = VerticalOffset/YINCrement when the instrument is in running 
        status; YORigin is related to the Verticalscale of the internal waveform and the 
        Verticalscale currently selected when the instrument is in stop status."""
        return self._query_float(":YOR?")

    @property
    def y_reference(self) -> int:
        """Query the vertical reference position of the specified channel source in the Y direction."""
        return self._query_int(":YREF?")

    @property
    def start(self) -> int:
        """Set or query the start point of waveform data reading."""
        return self._query_int(":STAR?")

    @start.setter
    def start(self, value: int):
        assert value >= 1
        self._write(":STAR %u" % (value))

    @property
    def stop(self) -> int:
        """Set or query the stop point of waveform data reading."""
        return self._query_int(":STOP?")

    @stop.setter
    def stop(self, value: int):
        assert value >= 1
        self._write(":STOP %u" % (value))

    @property
    def preamble(self) -> str:
        """Query and return all the waveform parameters."""
        tmp = self._query(":PRE?").split(",")
        return WaveformPreamble(tmp)
    
    def get_data(self, 
        source: WaveformSource = None, 
        mode: WaveformMode = WaveformMode.Normal, 
        start: int = 1, stop: int = math.inf):
        """Read the waveform data.

        Args:
            source (WaveformSource, optional): Channel for the waveform data to be read. Defaults to None (which is the currently selected channel).
            mode (WaveformMode, optional): see WaveformMode. Defaults to WaveformMode.Normal.
            start (int, optional): start point of the data. Defaults to 1.
            stop (int, optional): end point of the data. Defaults to math.inf.

        Raises:
            Exception: _description_

        Returns:
            _type_: _description_
        """
        assert start >= 1 or start < 0
        assert stop >= start

        self.scope.stop()
        if source is not None:
            self.source = source
        
        self.mode = mode
        self.format = WaveformFormat.Byte

        info = self.preamble

        if info.format != WaveformFormat.Byte:
            raise Exception("Currently only WaveformFormat.Byte is supported")

        # allow pythonic negative start points
        if start < 0:
            start = info.points + start
        
        if start < 1:
            start = 1

        if info.points < stop:
            stop = info.points

        #print("start: %u" % start)
        #print("stop: %u" % stop)
        
        point_cnt = stop - start + 1

        block_size = 250000 # maximum number of waveform points for each read
        
        block_cnt = int(math.ceil(point_cnt / block_size))
        offset = start
        data_raw = []

        for i in range(0, block_cnt):
            #print("reading from: %u" % offset)
            self.start = offset
            offset += block_size - 1
            
            if offset > stop:
                offset = stop
            #print("reading to: %u" % offset)
            self.stop = offset
            offset += 1

            chunk = self.resource.query_binary_values("%s:DATA?" % (self.message_prefix), "B")
            data_raw.extend(chunk)

        return WaveformData(source, info, start, stop, data_raw)

class WaveformData():
    def __init__(self, source: WaveformSource, preamble: WaveformPreamble, start: int, stop: int, data_raw: list):
        self.preamble = preamble
        self.start = start
        self.stop = stop
        self.source = source
        self.data_raw = data_raw

        #data = [(y - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement for y in data_raw]

    def __getitem__(self, i):
        return (self.data_raw[i] - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement

    @property
    def data(self):
        return [(y - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement for y in self.data_raw]

    def save_csv(self, filename, colsep_hint: bool = True, header: bool = True, column_separator: str = "\t", decimalpoint: str = ".", end: str = "\n"):
        fh = open(filename, "w")

        if colsep_hint:
            fh.write("sep=%s%s" % (column_separator, end))
        
        if header:
            fh.write("%s%s" % (
                column_separator.join(["Time [s]", "Amplitude [V]"]),
                end
            ))

        for i, v in enumerate(self.data_raw):
            
            time = ((i + self.start) - self.preamble.xorigin - self.preamble.xreference) * self.preamble.xincrement
            value = (v - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement
            times = "%.4e" % time
            values = "%.4e" % value
            if decimalpoint != ".":
                times = times.replace(".", decimalpoint)
                values = values.replace(".", decimalpoint)
            fh.write("".join([times, column_separator, values, end]))

        fh.close()