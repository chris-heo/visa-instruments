# Yet another Rigol DS1000 Python implementation
Relevant xkcd: https://xkcd.com/927/

There are already plente of Python implementations for the Rigol DS1000-series. And yet, none of them fulfilled my needs to control the scope. So I sat down and wrote my own.

One of the main goals was to control the scope as if it was a local collection of objects, therefore there are plenty of properties and only few methods - see code example

It is based on pyVisa and is almost feature complete. The "only" missing features/subsystems are:

* :FUNCtion
* :LA
* :LAN
* :MASK
* :SOURce
* :STORage (screenshots integrated in Display subsystem)
* :TRACe
* :TRIGger:PATTern
* :TRIGger:DURATion
* :TRIGger:RS232
* :TRIGger:IIC
* :TRIGger:SPI

## Code Example
``` python
import pyvisa
from DS1000z import *

rm = pyvisa.ResourceManager()
res = rm.open_resource('USB0::0x1AB1::0x04CE::********::INSTR')
dso = DS1000z(res)

ch = dso.channel[1] # note that the channel index is based on 1
ch.display = True
ch.scale = 1
ch.offset = -3
ch.bandwidth_limit = BandwidthLimit.Off

dso.channel[2].display = False

dso.timebase.scale = 500e-6
dso.trigger.mode = TriggerMode.Edge
dso.trigger.edge.slope = TriggerEdgeSlope.Fall
dso.trigger.edge.level = 1

dso.reference.display = True
ref = dso.reference[1]
ref.enable = True
ref.save()
ref.color = ReferenceColor.Lightblue
ref.vertical_offset = 1
```

## Points of improvement
The code isn't perfect and not completely tested.

Currently, everything is mushed in one file and there are many duplicate enums.
This comes with some advantages but also many disadvantages.

I haven't found a good solution yet. If you got one, please let me know.

Also, the docstrings could be more explanatory.
