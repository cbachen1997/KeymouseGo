import os
import threading
import time
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal, Qt, Slot
from loguru import logger

from Util.Global import State
from Event import ScriptEvent
from Plugin.Manager import PluginManager
from Util.Parser import parse_script


class ScriptStopped(Exception):
    pass


class RunScriptMeta:
    def init_control(self):
        self._condition = threading.Condition()
        self._stopped = False
        self.eventPause = False
        self._pressed = {}
        self._paths = []
        self.succeeded = False

    def is_stopped(self):
        return self._stopped or (hasattr(self, 'flag') and self.flag.value)

    def stop(self):
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    def set_pause(self):
        with self._condition:
            self.eventPause = True
            self._condition.notify_all()

    def resume(self):
        with self._condition:
            self.eventPause = False
            self._condition.notify_all()

    def pause(self):
        self.set_pause()
        self.sleep(0)

    def sleep(self, msecs):
        remaining = max(0, float(msecs)) / 1000
        with self._condition:
            while True:
                if self.is_stopped():
                    raise ScriptStopped()
                if self.eventPause:
                    self._condition.wait()
                    continue
                if remaining <= 0:
                    return
                started = time.monotonic()
                self._condition.wait(remaining)
                remaining -= time.monotonic() - started

    def wait_if_pause(self):
        self.sleep(0)

    def _execute_event(self, content):
        event = ScriptEvent(content)
        event.execute(self)
        kind, name, action = event.event_type, event.action_type, event.action
        token = ('key', action[0]) if kind == 'EK' else ('mouse', name.rsplit(' ', 1)[0])
        if name.endswith(' down') and kind in ('EK', 'EM') and 'wheel' not in name:
            release = dict(content, delay=0, action_type=name[:-4] + 'up')
            self._pressed[token] = release
        elif name.endswith(' up'):
            self._pressed.pop(token, None)

    def release_inputs(self):
        # Only release inputs this worker actually pressed, never unrelated keys.
        for content in reversed(list(self._pressed.values())):
            try:
                if content['event_type'] == 'EM':
                    content = dict(content, action=[-1, -1])
                ScriptEvent(content).execute(None)
            except Exception as exc:
                logger.warning('Cannot release input: {}', exc)
        self._pressed.clear()

    def run_script_from_objects(self, head_object, attach=None):
        node = head_object
        while node is not None:
            self.wait_if_pause()
            if attach:
                PluginManager.call_group(attach, node)
            node = self.run_object(node)
        return True

    def run_object(self, node):
        content = node.content
        if content.get('call'):
            PluginManager.call_group(content['call'], node)
        kind = content['type']
        if kind == 'event':
            if hasattr(self, 'logSignal'):
                self.logSignal.emit(str(ScriptEvent(content)))
            self._execute_event(content)
        elif kind == 'sequence':
            self.run_script_from_objects(content['events'], content.get('attach'))
        elif kind == 'if':
            return node.next_object if PluginManager.call(content['judge'], node) else node.next_object_if_false
        elif kind == 'subroutine':
            for path in content['path']:
                self._run_path(path, 1)
        return node.next_object

    def _run_path(self, path, repeats):
        if not os.path.isabs(path) and self._paths:
            path = os.path.join(os.path.dirname(self._paths[-1]), path)
        path = os.path.abspath(path)
        if path in self._paths or len(self._paths) >= 32:
            raise ValueError('Recursive subroutine: ' + path)
        head = parse_script(path)
        self._paths.append(path)
        try:
            count = 0
            while repeats == 0 or count < repeats:
                self.wait_if_pause()
                if hasattr(self, 'tnumrdSignal'):
                    self.tnumrdSignal.emit(f'{os.path.basename(path)} [{count + 1}/{repeats or "∞"}]')
                self.run_script_from_objects(head)
                count += 1
        finally:
            self._paths.pop()


class RunScriptClass(QThread, RunScriptMeta):
    logSignal = Signal(str)
    tnumrdSignal = Signal(str)
    btnSignal = Signal(bool)
    statusSignal = Signal(bool)
    playtuneSignal = Signal(str)

    def __init__(self, frame):
        super().__init__()
        self.init_control()
        self.state = State.RUNNING
        self.script_path = frame.get_script_path()
        self.runtimes = frame.stimes.value()
        self.logSignal.connect(frame.textlog.append)
        self.tnumrdSignal.connect(frame.tnumrd.setText)
        frame.updateStateSignal.connect(self.update_state, Qt.DirectConnection)
        self.playtuneSignal.connect(frame.playtune)

    # QThread also has sleep(); explicitly use the interruptible millisecond wait.
    def sleep(self, msecs):
        RunScriptMeta.sleep(self, msecs)

    @Slot(State)
    def update_state(self, state):
        self.state = state
        if state == State.IDLE:
            self.stop()

    def run_script_from_path(self, path):
        self._run_path(path, self.runtimes)

    def run(self):
        try:
            if not self.script_path:
                raise ValueError('No script selected')
            self.playtuneSignal.emit('start.wav')
            self.run_script_from_path(self.script_path)
            self.succeeded = True
            self.tnumrdSignal.emit('finished')
        except ScriptStopped:
            self.tnumrdSignal.emit('stopped')
        except Exception as exc:
            logger.exception('Script failed')
            self.logSignal.emit('Script failed: ' + str(exc))
            self.tnumrdSignal.emit('执行失败 / Script failed: ' + str(exc))
        finally:
            self.release_inputs()
            self.statusSignal.emit(self.succeeded)
            self.playtuneSignal.emit('end.wav')


@dataclass
class StopFlag:
    value: bool


class RunScriptCMDClass(QThread, RunScriptMeta):
    def __init__(self, script_path, run_times, flag):
        super().__init__()
        self.init_control()
        self.script_path = script_path
        self.run_times = run_times
        self.flag = flag

    def sleep(self, msecs):
        RunScriptMeta.sleep(self, msecs)

    def run_script_from_path(self, paths):
        for path in paths:
            self.wait_if_pause()
            self._run_path(path, self.run_times)

    def run(self):
        try:
            if self.run_times < 0:
                raise ValueError('Run times cannot be negative')
            self.run_script_from_path(self.script_path)
            self.succeeded = True
        except ScriptStopped:
            logger.info('Script stopped')
        except Exception:
            logger.exception('Script failed')
        finally:
            self.release_inputs()
