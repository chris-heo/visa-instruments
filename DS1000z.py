from email import message
import math
import os
from unicodedata import decimal
import pyvisa
from enum import Enum


class _Scpihelper():
    def __init__(self, resource, message_prefix: str = ""):
        self.resource = resource
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
    
    def _querybool(self, message: str) -> bool:
        answer = self.resource.query("%s%s" % (self.message_prefix, message)).strip().upper()
        if answer in ("1", "ON"):
            return True
        elif answer in ("0", "OFF"):
            return False
        else:
            raise Exception("unexpected answer '%s'" % (answer))

    def _querynumber(self, message: str):
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

    def _queryint(self, message: str) -> int:
        answer = self._querynumber(message)
        if isinstance(answer, str):
            return int(answer)
        else:
            return answer

    def _queryfloat(self, message: str) -> float:
        answer = self._querynumber(message)
        if isinstance(answer, str):
            return float(answer)
        else:
            return answer


class DS1000z(_Scpihelper):
    def __init__(self, resource):
        #self.resource = resource
        super().__init__(resource)

        self.channel = [
            _Channel(self, 1),
            _Channel(self, 2),
            _Channel(self, 3),
            _Channel(self, 4),
        ]
        self.cursor = _Cursor(self)
        self.display = _Display(self)
        self.measure = _Measure(self)
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
        return self._queryint("*ESE?")

    @events_status.setter
    def events_status(self, value: int):
        assert True
        self._write("*ESE %u" % (value))
    
    @property
    def events_query_clear(self) -> int:
        """Query and clear the event register for the standard event status register."""
        return self._queryint("*ESR?")

    @property
    def id(self) -> str:
        """Query the ID string of the instrument."""
        return self._query("*IDN?")

    @property
    def operation_finished(self) -> bool:
        """The command is used to query whether the current operation is finished. """
        return self._querybool("*OPC?")
    
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
        return self._queryint("*SRE?")

    @status_byte.setter
    def status_byte(self, value: int):
        assert value >= 0 and value <= 255
        self._write("*SRE %u" % (value))

    @property
    def status_events(self) -> int:
        """Query the event register for the status byte register. 
        The value of the status byte register is set to 0 after this command is executed."""
        return self._queryint("*STB?")
    
    def selftest(self) -> int:
        """Perform a self-test and then return the seilf-test results."""
        return self._queryint("*TST?")

    def wait(self):
        """Wait for the operation to finish."""
        self._write("*WAI")

#TODO: Acquire

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
        super().__init__(scope.resource, ":CHAN%u" % (channel))
        self.scope = scope
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
        return self._querybool(":DISP?")
    
    @display.setter
    def display(self, value: bool):
        self._write(":DISP %u" % (1 if value else 0))

    @property
    def invert(self) -> bool:
        """Enable or disable the waveform invert of the specified channel or 
        query the status of the waveform invert of the specified channel."""
        return self._querybool(":INV?")
    
    @invert.setter
    def invert(self, value: bool):
        self._write(":INV %u" % (1 if value else 0))

    @property
    def offset(self) -> float:
        """Set or query the vertical offset of the specified channel. 
        The default unit is V.
        
        probe ratio  1X & vertical scale >= 0.5 V/div:  -100 V ...  +100 V
        probe ratio  1X & vertical scale  < 0.5 V/div:    -2 V ...    +2 V
        probe ratio 10X & vertical scale >= 5   V/div: -1000 V ... +1000 V
        probe ratio 10X & vertical scale  < 5   V/div:   -20 V ...   +20 V
        """
        return self._queryfloat(":OFFS?")

    @offset.setter
    def offset(self, value: float):
        assert value >= -1000 and value <= 1000
        self._write(":OFFS %.4e" % (value))

    @property
    def range(self) -> float:
        """Set or query the vertical range of the specified channel. 
        The default unit is V."""
        return self._queryfloat(":RANG?")

    @range.setter
    def range(self, value: float):
        assert value >= 8e-3 and value >= 800
        self._write(":RANG %.4e" % (value))

    @property
    def delay_calibration(self) -> float:
        """Set or query the delay calibration time of the specified channel 
        to calibrate the zero offset of the corresponding channel. 
        The default unit is s."""
        return self._queryfloat(":TCAL?")
    
    @delay_calibration.setter
    def delay_calibration(self, value: float):
        assert value > 100e-12
        self._write(":TCAL %.4e" % (value))
    
    @property
    def scale(self) -> float:
        """Set or query the vertical scale of the specified channel.
        The default unit is V.
        if vernier function is disabled, the scale is in 1-2-5 step"""
        return self._queryfloat(":SCAL?")

    @scale.setter
    def scale(self, value: float):
        assert value >= 1e-3 and value <= 100
        self._write(":SCAL %.4e" % (value))

    @property
    def probe(self) -> float:
        """Set or query the probe ratio of the specified channel.
        must be in discrete steps"""
        return self._queryfloat(":PROB?")

    @probe.setter
    def probe(self, value: float):
        assert value in (0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
            1, 2, 5, 10, 20, 50, 100, 200, 500, 1000)
        self._write(":PROB %.4e" % (value))

    @property
    def vertical_unit(self) -> VerticalUnit:
        """Set or query the amplitude display unit of the specified channel."""
        return Coupling(self._query(":UNIT?"))

    @vertical_unit.setter
    def vertical_unit(self, value: Coupling):
        self._write(":UNIT %s" % (value.value))

    @property
    def vernier(self) -> bool:
        """Enable or disable the fine adjustment of the vertical scale 
        of the specified channel, or query the fine adjustment status 
        of the vertical scale of the specified channel."""
        return self._querybool(":VERN?")
    
    @vernier.setter
    def vernier(self, value: bool):
        self._write(":VERN %u" % (1 if value else 0))

class CursorMode(Enum):
    Off = "OFF"
    Manual = "MAN"
    Track = "TRAC"
    Auto = "AUTO"
    XY = "XY"

class _Cursor(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":CURS")

        self.manual = _Cursor_Manual(scope)
        self.track = _Cursor_Track(scope)
        #self.auto = _Cursor_Auto(scope)

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

class _Cursor_Manual(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":CURS:MAN")

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
        return self._queryint(":AX?")

    @ax.setter
    def ax(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":AX %u" % (value))

    @property
    def bx(self) -> int:
        """Set or query the horizontal position of cursor B 
        in the manual cursor measurement mode."""
        return self._queryint(":BX?")

    @bx.setter
    def bx(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":BX %u" % (value))

    @property
    def ay(self) -> int:
        """Set or query the vertical position of cursor A 
        in the manual cursor measurement mode."""
        return self._queryint(":AY?")

    @ay.setter
    def ay(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":AY %u" % (value))

    @property
    def by(self) -> int:
        """Set or query the vertical position of cursor B 
        in the manual cursor measurement mode."""
        return self._queryint(":BY?")

    @by.setter
    def by(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":BY %u" % (value))

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in the manual cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in the manual cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in the manual cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in the manual cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":BYV?")

    @property
    def x_delta(self) -> float:
        """Query the difference between the X values of cursor A and cursor B (BX-AX)
        in the manual cursor measurement mode. 
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":XDEL?")

    @property
    def x_delta_inverse(self) -> float:
        """Query the reciprocal of the absolute value of the difference 
        between the X values of cursor A and cursor B (1/|dX|) 
        in the manual cursor measurement mode. The unit depends on the 
        horizontal unit currently selected."""
        return self._queryfloat(":IXDEL?")

    @property
    def y_delta(self) -> float:
        """Query the difference between the Y values of cursor A and cursor B (BY-AY)
        in the manual cursor measurement mode. 
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":YDEL?")


class CursorTrackSource(Enum):
    Off = "OFF"
    Channel1 = "CHAN1"
    Channel2 = "CHAN2"
    Channel3 = "CHAN3"
    Channel4 = "CHAN4"
    Math = "MATH"

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

class _Cursor_Track(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":CURS:TRAC")

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
        return self._queryint(":AX?")

    @ax.setter
    def ax(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":AX %u" % (value))

    @property
    def bx(self) -> int:
        """Set or query the horizontal position of cursor B 
        in the track cursor measurement mode."""
        return self._queryint(":BX?")

    @bx.setter
    def bx(self, value: int):
        assert value >= 5 and value <= 594
        self._write(":BX %u" % (value))

    @property
    def ay(self) -> int:
        """Set or query the vertical position of cursor A 
        in the track cursor measurement mode."""
        return self._queryint(":AY?")

    @ay.setter
    def ay(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":AY %u" % (value))

    @property
    def by(self) -> int:
        """Set or query the vertical position of cursor B 
        in the track cursor measurement mode."""
        return self._queryint(":BY?")

    @by.setter
    def by(self, value: int):
        assert value >= 5 and value <= 394
        self._write(":BY %u" % (value))

    @property
    def ax_value(self) -> float:
        """Query the X value of cursor A in the track cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":AXV?")

    @property
    def ay_value(self) -> float:
        """Query the Y value of cursor A in the track cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":AYV?")

    @property
    def bx_value(self) -> float:
        """Query the X value of cursor B in the track cursor measurement mode.
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":BXV?")

    @property
    def by_value(self) -> float:
        """Query the Y value of cursor B in the track cursor measurement mode.
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":BYV?")

    @property
    def x_delta(self) -> float:
        """Query the difference between the X values of cursor A and cursor B (BX-AX)
        in the track cursor measurement mode. 
        The unit depends on the horizontal unit currently selected."""
        return self._queryfloat(":XDEL?")

    @property
    def x_delta_inverse(self) -> float:
        """Query the reciprocal of the absolute value of the difference 
        between the X values of cursor A and cursor B (1/|dX|) 
        in the track cursor measurement mode. The unit depends on the 
        horizontal unit currently selected."""
        return self._queryfloat(":IXDEL?")

    @property
    def y_delta(self) -> float:
        """Query the difference between the Y values of cursor A and cursor B (BY-AY)
        in the track cursor measurement mode. 
        The unit depends on the vertical unit currently selected."""
        return self._queryfloat(":YDEL?")

#TODO: _Cursor_Auto
#TODO: _Cursor_XY

#TODO: _Decoder

class DisplayDataFormat(Enum):
    BMP24 = "BMP24"
    BMP8 = "BMP8"
    PNG = "PNG"
    JPEG = "JPEG"
    TIFF = "TIFF"


class _Display(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":DISP")

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

        #self.scope.resource.write(cmd)
        #data = self.scope.resource.read_raw()
        #
        ##remove the TMC block header
        #if data[0] != 0x23: #first character must be a #
        #    raise Exception("No SOF for TMC block header")
        #header_len = data[1] - 0x30 # it's an ASCII number, so just substract the offset of 0
        #
        #data = data[header_len + 2:-1]
        #

        data = bytearray(res.query_binary_values(cmd, "B"))

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
        return self._queryint(":WBR?")

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
        """"""
        return self._queryint(":GBR?")

    @grid_brightness.setter
    def grid_brightness(self, value: int):
        assert value >= 0 and value <= 100
        self._write(":GBR %u" % (value))

#TODO: Event Table
#TODO: Function
#TODO: digital channels
#TODO: LAN
#TODO: Math
#TODO: Mask

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

class _Measure(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":MEAS")

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
        return self._queryfloat(":COUN:VAL?")
    
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
        return self._querybool(":ADIS?")
    
    @all_display.setter
    def all_display(self, value: bool):
        self._write(":ADIS %u" % (1 if value else 0))

    #TODO: AMSource

    @property
    def setup_max(self) -> int:
        """Set or query the upper limit of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._queryint(":SET:MAX?")

    @setup_max.setter
    def setup_max(self, value: int = 90):
        assert value >= 7 and value <= 95
        self._write(":SET:MAX %u" % (value))

    @property
    def setup_mid(self) -> int:
        """Set or query the middle point of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._queryint(":SET:MID?")

    @setup_mid.setter
    def setup_mid(self, value: int = 50):
        assert value >= 6 and value <= 94
        self._write(":SET:MID %u" % (value))

    @property
    def setup_min(self) -> int:
        """Set or query the middle point of the threshold (expressed in the percentage of amplitude) 
        in time, delay, and phase measurements."""
        return self._queryint(":SET:MIN?")

    @setup_min.setter
    def setup_min(self, value: int = 10):
        assert value >= 5 and value <= 93
        self._write(":SET:MIN %u" % (value))

    #TODO: SET:PSA
    #TODO: SET:PSB
    #TODO: SET:DSA
    #TODO: SET:DSB

    @property
    def statistics_display(self) -> bool:
        """Enable or disable the statistic function, or query the status of the statistic function."""
        return self._querybool(":STAT:DISP?")
    
    @statistics_display.setter
    def statistics_display(self, value: bool):
        self._write(":STAT:DISP %u" % (1 if value else 0))

    @property
    def statistics_mode(self) -> MeasureStatisticMode:
        """Set or query the statistic mode."""
        return MeasureStatisticMode(self._query(":STAT:MODE?"))

    @statistics_mode.setter
    def statistics_mode(self, value: MeasureStatisticMode = MeasureStatisticMode.Extremum):
        self._write(":STAT:MODE %s" % (value.value))

    def statistics_reset(self):
        self._write(":STAT:RES")

    def statistics_item_add(self, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Enable the statistic function of any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        assert item in (MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase) and source1 is not None

        message = ":STAT:ITEM %s" % (item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        self._write(message)

    def statistics_reset(self):
        """Clear the history data and make statistic again."""
        self._write(":STAT:RES")

    def statistics_item_read(self, type: MeasureStatisticType, item: MeasureItem, source1: MeasureSource, source2: MeasureSource = None):
        """Query the statistic function of any waveform parameter of the specified source"""
        assert not (source1 is None and source2 is not None)
        assert item in (MeasureItem.RisingEdgeDelay, MeasureItem.FallingEdgeDelay, 
            MeasureItem.RisingEdgePhase, MeasureItem.FallingEdgePhase) and source2 is not None

        message = ":STAT:ITEM? %s,%s" % (type.value, item.value)
        if source1 is not None:
            message += ",%s" % (source1.value)
        if source2 is not None:
            message += ",%s" % (source2.value)

        return self._queryfloat(message)

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

        return self._queryfloat(message)


#TODO: Reference
#TODO: Source
#TODO: Storage
#TODO: System
#TODO: Trace

class TimebaseMode(Enum):
    Main = "MAIN"
    XY = "XY"
    Roll = "ROLL"

class _Timebase(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":TIM")

    @property
    def delay_enable(self) -> bool:
        """Enable or disable the delayed sweep, or query the status of the delayed sweep."""
        return self._querybool(":DEL:ENAB?")
    
    @delay_enable.setter
    def delay_enable(self, value: bool):
        self._write(":DEL:ENAB %u" % (1 if value else 0))

    @property
    def delay_offset(self) -> float:
        """Set or query the delayed timebase offset. The default unit is s."""
        return self._queryfloat(":DEL:OFFS?")

    @delay_offset.setter
    def delay_offset(self, value: float):
        assert True
        self._write(":DEL:OFFS %.4e" % (value))

    @property
    def delay_scale(self) -> float:
        """Set or query the delayed timebase scale. The default unit is s/div."""
        return self._queryfloat(":DEL:SCAL?")

    @delay_scale.setter
    def delay_scale(self, value: float):
        assert True
        self._write(":DEL:SCAL %.4e" % (value))

    @property
    def offset(self) -> float:
        """Set or query the main timebase offset. The default unit is s."""
        return self._queryfloat(":OFFS?")

    @offset.setter
    def offset(self, value: float):
        assert True
        self._write(":OFFS %.4e" % (value))

    @property
    def scale(self) -> float:
        """Set or query the main timebase scale. The default unit is s/div."""
        return self._queryfloat(":SCAL?")

    @scale.setter
    def scale(self, value: float):
        assert True
        self._write(":SCAL %.4e" % (value))

    @property
    def mode(self) -> TimebaseMode:
        """Set or query the mode of the horizontal timebase."""
        return TimebaseMode(self._query(":msg?"))

    @mode.setter
    def mode(self, value: TimebaseMode):
        self._write(":msg %s" % (value.value))

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
        self.scope = scope
        super().__init__(scope.resource, ":TRIG")

        self.edge = _Trigger_Edge(scope)

    @property
    def mode(self) -> TriggerMode:
        """Select or query the trigger type."""
        return TriggerMode(self._query(":MODE?"))

    @mode.setter
    def mode(self, value: TriggerMode):
        self._write(":MODE %s" % (value.value))

    @property
    def coupling(self) -> TriggerCoupling:
        """"""
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
        return self._queryfloat(":HOLD?")

    @holdoff.setter
    def holdoff(self, value: float):
        assert value >= 16e-9 and value <= 10
        self._write(":HOLD %.4e" % (value))

    @property
    def noise_rejection(self) -> bool:
        """Enable or disable noise rejection, or query the status of noise rejection."""
        return self._querybool(":NREJ?")
    
    @noise_rejection.setter
    def prop_bool(self, value: bool):
        self._write(":NREJ %u" % (1 if value else 0))

    @property
    def position(self) -> int:
        """Query the position in the internal memory that corresponds to the waveform trigger position.
        -2 denotes that the instrument is not triggered and there is no trigger position.
        -1 denotes the instrument is triggered outside the internal memory; namely, at this point,
           users cannot set the instrument to read the data in the internal memory starting 
           from the trigger position.
        An integer that is greater than 0 denotes that the return value is the position in the internal
        memory that corresponds to the trigger position."""
        return self._queryint(":POS?")

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

class _Trigger_Edge(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":TRIG:EDG")

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
        return self._queryfloat(":LEV?")

    @level.setter
    def level(self, value: float):
        assert True
        self._write(":LEV %.4e" % (value))


#TODO: :TRIGger:PULSe
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
        if preambledata[1] == "":
            self.type = WaveformMode.Normal
        elif preambledata[1] == "":
            self.type = WaveformMode.Maximum
        elif preambledata[1] == "":
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
        super().__init__(scope.resource, ":WAV")

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

    #TODO: :WAVeform:DATA? 

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
        return self._queryfloat(":XINC?")

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
        return self._queryfloat(":XOR?")

    @property
    def x_reference_time(self) -> float:
        """Query the reference time of the specified channel source in the X direction."""
        return self._queryfloat(":XREF?")

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
        return self._queryfloat(":YINC?")

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
        return self._queryfloat(":YOR?")

    @property
    def y_reference(self) -> int:
        """Query the vertical reference position of the specified channel source in the Y direction."""
        return self._queryint(":YREF?")

    @property
    def start(self) -> int:
        """Set or query the start point of waveform data reading."""
        return self._queryint(":STAR?")

    @start.setter
    def start(self, value: int):
        assert value >= 1
        self._write(":STAR %u" % (value))

    @property
    def stop(self) -> int:
        """Set or query the stop point of waveform data reading."""
        return self._queryint(":STOP?")

    @stop.setter
    def stop(self, value: int):
        assert value >= 1
        self._write(":STOP %u" % (value))

    @property
    def preamble(self) -> str:
        """Query and return all the waveform parameters."""
        #TODO: split and interpret values
        tmp = self._query(":PRE?").split(",")
        return WaveformPreamble(tmp)
    
    def get_data(self, 
        source: WaveformSource = None, 
        mode: WaveformMode = WaveformMode.Normal, 
        start: int = 1, stop: int = math.inf):
        assert start >= 1 or start < 0
        assert stop >= start

        self.scope.stop()
        if source is not None:
            self.source = source
        
        self.mode = mode
        self.format = WaveformFormat.Byte

        info = self.preamble

        # allow pythonic negative start points
        if start < 0:
            start = info.points + start
        
        if start < 1:
            start = 1

        if info.points < stop:
            stop = info.points

        print("start: %u" % start)
        print("stop: %u" % stop)
        
        point_cnt = stop - start + 1

        block_size = 250000 # maximum number of waveform points for each read
        #block_size = 1000 # maximum number of waveform points for each read
        
        block_cnt = int(math.ceil(point_cnt / block_size))
        offset = start
        data_raw = []

        for i in range(0, block_cnt):
            print("reading from: %u" % offset)
            self.start = offset
            offset += block_size - 1
            
            if offset > stop:
                offset = stop
            print("reading to: %u" % offset)
            self.stop = offset
            offset += 1

            chunk = res.query_binary_values("%s:DATA?" % (self.message_prefix), "B")
            data_raw.extend(chunk)

        return WaveformData(info, data_raw)

class WaveformData():
    def __init__(self, preamble: WaveformPreamble, data_raw: list):
        self.preamble = preamble
        self.data_raw = data_raw

        #data = [(y - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement for y in data_raw]

    def __getitem__(self, i):
        return (self.data_raw[i] - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement

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
            time = (i - self.preamble.xorigin - self.preamble.xreference) * self.preamble.xincrement
            value = (v - self.preamble.yorigin - self.preamble.yreference) * self.preamble.yincrement
            times = "%.4e" % time
            values = "%.4e" % value
            if decimalpoint != ".":
                times = times.replace(".", decimalpoint)
                values = values.replace(".", decimalpoint)
            fh.write("".join([times, column_separator, values, end]))

        fh.close()


### Templates
class _Template(_Scpihelper):
    def __init__(self, scope: DS1000z):
        self.scope = scope
        super().__init__(scope.resource, ":TEMPLATE")

    @property
    def prop_bool(self) -> bool:
        """"""
        return self._querybool(":msg?")
    
    @prop_bool.setter
    def prop_bool(self, value: bool):
        self._write(":msg %u" % (1 if value else 0))

    @property
    def prop_float(self) -> float:
        """"""
        return self._queryfloat(":msg?")

    @prop_float.setter
    def prop_float(self, value: float):
        assert True
        self._write(":msg %.4e" % (value))

    @property
    def prop_int(self) -> int:
        """"""
        return self._queryint(":msg?")

    @prop_int.setter
    def prop_int(self, value: int):
        assert True
        self._write(":msg %u" % (value))


    @property
    def prop_enum(self) -> Enum:
        """"""
        return Enum(self._query(":msg?"))

    @prop_enum.setter
    def prop_enum(self, value: Enum):
        self._write(":msg %s" % (value.value))

if __name__ == "__main__":

    rm = pyvisa.ResourceManager()
    res = rm.open_resource('USB0::0x1AB1::0x04CE::DS1ZA171104975::INSTR')
    dso = DS1000z(res)
    data = dso.waveform.get_data(WaveformSource.Channel1, start = 1)
    data.save_csv("waveform2.csv", decimalpoint=",")