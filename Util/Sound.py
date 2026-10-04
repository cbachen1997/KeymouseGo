"""Short WAV notifications without Qt's video/multimedia stack on Windows."""
import sys
import tempfile
import wave
from array import array
from pathlib import Path

from PySide6.QtCore import QUrl


class SoundPlayer:
    def __init__(self):
        self.volume = 0.5
        self.source = None
        self._temp = None
        if sys.platform == 'win32':
            import winsound
            self._sound = winsound
            self._temp = tempfile.TemporaryDirectory(prefix='keymousego-sounds-')
        else:
            from PySide6.QtMultimedia import QSoundEffect
            self._sound = QSoundEffect()

    def setVolume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
        if sys.platform != 'win32':
            self._sound.setVolume(self.volume)

    def setSource(self, source):
        self.source = source.toLocalFile() if isinstance(source, QUrl) else str(source)
        if sys.platform != 'win32':
            self._sound.setSource(QUrl.fromLocalFile(self.source))

    def play(self):
        if not self.source or self.volume <= 0:
            return
        if sys.platform != 'win32':
            self._sound.play()
            return
        # Scale samples, not the system mixer: the volume slider stays local to
        # this application. Cache just the latest volume of each bundled sound.
        target = Path(self._temp.name) / Path(self.source).name
        self._sound.PlaySound(None, 0)
        with wave.open(self.source, 'rb') as src:
            params = src.getparams()
            if params.sampwidth != 2:
                raise ValueError('Notification sounds must use 16-bit PCM')
            samples = array('h', src.readframes(params.nframes))
        samples = array('h', (int(sample * self.volume) for sample in samples))
        with wave.open(str(target), 'wb') as dst:
            dst.setparams(params)
            dst.writeframes(samples.tobytes())
        self._sound.PlaySound(str(target), self._sound.SND_FILENAME | self._sound.SND_ASYNC | self._sound.SND_NODEFAULT)

    def close(self):
        if self._temp:
            self._sound.PlaySound(None, 0)
            self._temp.cleanup()
            self._temp = None
        elif sys.platform != 'win32':
            self._sound.stop()
