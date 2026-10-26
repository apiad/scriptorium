# A tone {#a-tone}

The simplest sound is a sine wave at one frequency. This block writes one
second of it to a WAV file with Python's standard library and prints the line
of Markdown that puts a player under it.

## Sampling {#sec-sampling}

```python {run}
import math
import struct
import wave
from pathlib import Path

rate, freq = 44100, 440.0
frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * n / rate)))
                  for n in range(rate))
Path("build").mkdir(exist_ok=True)
with wave.open("build/tone.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(frames)
print("![A 440 Hz tone](build/tone.wav){#aud-tone}")
```

@aud-tone is the A from [Frequency](#sec-frequency), one second long,
sampled 44 100 times.

## Listening {#sec-listening}

In the site the player plays the file. In the PDF the figure prints its
caption and file name, linked to this page of the site.
