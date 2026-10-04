"""Windows regression checks. No real keyboard/mouse input is sent."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import json5
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from Event import ScriptEvent
from Util.Parser import ScriptParser, parse_script
from Util.RunScriptClass import RunScriptCMDClass, StopFlag, ScriptStopped
from Util.Global import State
import UIFunc
import UIFileDialogFunc


def key(name, direction='down', delay=0):
    return dict(type='event', delay=delay, event_type='EK', action_type='key ' + direction, action=[65, name, 0])


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        UIFunc.logger.remove()
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        def path(*parts):
            return str(self.root.joinpath(*parts))
        self.patches = [patch.object(UIFunc, 'to_abs_path', path), patch.object(UIFileDialogFunc, 'to_abs_path', path),
                        patch.object(UIFunc.PluginManager, 'reload')]
        for p in self.patches:
            p.start()
        self.ui = UIFunc.UIFunc(self.app, enable_hooks=False)
        self.ui.player.setVolume(0)

    def tearDown(self):
        self.ui.close()
        self.app.processEvents()
        self.app.removeTranslator(self.ui.trans)
        self.ui.deleteLater()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def save(self, name, content):
        p = self.root / name
        p.write_text(json5.dumps(content), encoding='utf8')
        return str(p)

    def worker(self, path, count=1):
        return RunScriptCMDClass([path], count, StopFlag(False))

    def test_empty_selection_does_not_lock_ui(self):
        self.ui.OnBtrunButton()
        self.assertEqual(self.ui.state, State.IDLE)
        self.assertTrue(self.ui.btrecord.isEnabled())

    def test_hotkey_save_cancel_clear_conflict_and_language(self):
        self.ui.OnHotkeyButton(self.ui.hotkey_start)
        self.ui._capture_hotkey('f7')
        self.assertEqual(self.ui.hotkey_start.text(), 'F7')
        self.assertEqual(self.ui.config.value('Config/StartHotKey'), 'f7')
        self.ui.OnHotkeyButton(self.ui.hotkey_start)
        self.ui._capture_hotkey('f9')
        self.assertEqual(self.ui.hotkey_start.text(), 'F7')
        self.ui.OnHotkeyButton(self.ui.hotkey_start)
        self.ui.keys_pool.append('lcontrol')
        self.ui.hotkey_start.setText('LCONTROL')
        self.ui.onconfigchange()
        self.assertEqual(self.ui.config.value('Config/StartHotKey'), 'f7')
        self.ui.keys_pool.clear()
        self.ui._capture_hotkey('Escape')
        self.assertEqual(self.ui.hotkey_start.text(), 'F7')
        self.ui.OnHotkeyButton(self.ui.hotkey_start)
        self.ui._capture_hotkey('delete')
        self.assertEqual(self.ui.config.value('Config/StartHotKey'), '')
        self.ui.choice_language.setCurrentText('English')
        self.ui.config.sync()
        saved = QSettings(str(self.root / 'config.ini'), QSettings.IniFormat)
        self.assertEqual(saved.value('Config/Language'), 'en')

    def test_combo_not_recorded_or_repeated(self):
        self.ui._set_hotkey_text(self.ui.hotkey_record, 'lcontrol+lshift+f10')
        self.ui.onconfigchange()
        for name in ['Lshift', 'Lcontrol', 'F10', 'F10']:
            self.ui._record_callback(ScriptEvent(key(name)))
        self.assertEqual(self.ui.state, State.RECORDING)
        for name in ['F10', 'Lcontrol', 'Lshift']:
            self.ui._record_callback(ScriptEvent(key(name, 'up')))
        self.assertEqual(self.ui.record, [])
        self.ui._record_callback(ScriptEvent(key('A', delay=8000)))
        self.assertEqual(self.ui.record[0]['delay'], 0)

    def test_parser_reports_empty_bad_delay_missing_label(self):
        for document in [{'scripts': []}, {'scripts': [key('A', delay=-1)]},
                         {'scripts': [{'type': 'goto', 'tolabel': 'missing'}]},
                         {'scripts': [{'type': 'unknown'}]}]:
            with self.assertRaises(ValueError):
                ScriptParser.from_content(document)
        path = self.save('bad.json5', {'scripts': []})
        w = self.worker(path, 0)
        w.run()
        self.assertFalse(w.succeeded)

    def test_legacy_and_empty_conditional_continue(self):
        path = self.save('old.txt', [[0, 'EK', 'key down', [65, 'A', 0]]])
        self.assertEqual(parse_script(path).content['action_type'], 'key down')
        events = [{'type': 'if', 'judge': 'test', 'do': [], 'else': []}, key('A')]
        node = ScriptParser.from_content({'scripts': events})
        self.assertIs(node.next_object, node.next_object_if_false)
        self.assertEqual(node.next_object.content['action'][1], 'A')
        self.assertEqual(events[0]['type'], 'if')

    def test_stop_during_delay_never_sends_input(self):
        path = self.save('wait.json5', {'scripts': [key('A', delay=5000)]})
        w = self.worker(path)
        entered = threading.Event()
        sent = []
        def execute(event, worker=None):
            entered.set()
            event.sleep(worker)
            sent.append(event.action_type)
        with patch.object(ScriptEvent, 'execute', execute):
            w.start()
            self.assertTrue(entered.wait(2))
            w.stop()
            self.assertTrue(w.wait(1500))
        self.assertEqual(sent, [])

    def test_gui_failed_script_restores_idle_and_can_retry(self):
        path = self.root / 'scripts' / 'empty.json5'
        path.write_text('{scripts: []}', encoding='utf8')
        UIFunc.get_script_list_from_dir()
        self.ui.choice_script.addItems(UIFunc.scripts)
        for _ in range(2):
            self.ui.OnBtrunButton()
            self.assertTrue(self.ui.runthread.wait(2000))
            self.app.processEvents()
            self.assertEqual(self.ui.state, State.IDLE)
            self.assertTrue(self.ui.btrecord.isEnabled())
            self.assertFalse(self.ui.runthread.succeeded)

    def test_close_during_run_waits_for_worker(self):
        path = self.root / 'scripts' / 'wait.json5'
        path.write_text(json5.dumps({'scripts': [key('A', delay=5000)]}), encoding='utf8')
        UIFunc.get_script_list_from_dir()
        self.ui.choice_script.addItems(UIFunc.scripts)
        sent = []
        def execute(event, worker=None):
            event.sleep(worker)
            sent.append(event.action_type)
        with patch.object(ScriptEvent, 'execute', execute):
            self.ui.OnBtrunButton()
            self.ui.close()
        self.assertFalse(self.ui.runthread.isRunning())
        self.assertEqual(sent, [])

    def test_plugin_errors_are_reported_as_failure(self):
        path = self.save('plugin.json5', {'scripts': [{'type': 'custom', 'call': ['not_registered']}]})
        w = self.worker(path)
        w.run()
        self.assertFalse(w.succeeded)

    def test_pause_blocks_and_resume_retains_delay(self):
        w = self.worker('unused')
        w.set_pause()
        done = threading.Event()
        t = threading.Thread(target=lambda: (w.sleep(70), done.set()))
        t.start()
        self.assertFalse(done.wait(0.1))
        start = time.monotonic()
        w.resume()
        self.assertTrue(done.wait(1))
        t.join()
        self.assertGreaterEqual(time.monotonic() - start, 0.055)

    def test_release_only_owned_keys_after_stop(self):
        path = self.save('press.json5', {'scripts': [key('A')]})
        w = self.worker(path)
        sent = []
        with patch.object(ScriptEvent, 'execute', lambda event, worker=None: sent.append(event.action_type)):
            w.run()
        self.assertEqual(sent, ['key down', 'key up'])

    def test_relative_subroutine_runs_once_per_parent_loop(self):
        child = self.save('child.json5', {'scripts': [key('A')]})
        parent = self.save('parent.json5', {'scripts': [{'type': 'subroutine', 'path': ['child.json5']}]})
        w = self.worker(parent, 3)
        sent = []
        with patch.object(ScriptEvent, 'execute', lambda event, worker=None: sent.append(event.action_type)):
            w.run()
        self.assertTrue(w.succeeded)
        self.assertEqual(sent.count('key down'), 3)

    def test_import_external_script_without_overwriting(self):
        path = self.save('external.json5', {'scripts': [key('A')]})
        dialog = UIFileDialogFunc.FileDialog()
        dialog.import_script(path)
        dialog.import_script(path)
        self.assertTrue((self.root / 'scripts' / 'external.json5').is_file())
        self.assertTrue((self.root / 'scripts' / 'external_1.json5').is_file())

    def test_log_bounded_and_toggle_compact(self):
        self.assertTrue(self.ui.textlog.isHidden())
        for index in range(650):
            self.ui.textlog.append(str(index))
        self.assertLessEqual(self.ui.textlog.document().blockCount(), 500)
        self.ui.log_toggle.setChecked(True)
        self.assertFalse(self.ui.textlog.isHidden())
        self.ui.log_toggle.setChecked(False)
        self.assertTrue(self.ui.textlog.isHidden())

    def test_sequence_condition_and_goto(self):
        events = [
            {'type': 'sequence', 'events': [key('A'), key('A', 'up')]},
            {'type': 'if', 'judge': 'test_false', 'do': [key('B')],
             'else': [key('C'), key('C', 'up')]},
            {'type': 'goto', 'tolabel': 'end'}, key('D'),
            dict(key('E'), label='end'), key('E', 'up'),
        ]
        w = self.worker(self.save('control.json5', {'scripts': events}))
        sent = []
        with patch.object(UIFunc.PluginManager, 'functions', {'test_false': lambda node: False}), \
             patch.object(ScriptEvent, 'execute', lambda event, worker=None: sent.append(event.action[1])):
            w.run()
        self.assertTrue(w.succeeded)
        self.assertEqual(sent, ['A', 'A', 'C', 'C', 'E', 'E'])

    def test_recursive_subroutine_fails_without_hanging(self):
        path = self.save('recursive.json5', {'scripts': [{'type': 'subroutine', 'path': ['recursive.json5']}]})
        w = self.worker(path)
        w.run()
        self.assertFalse(w.succeeded)

    def test_mouse_side_buttons_and_release_at_current_position(self):
        import win32con
        for button, identifier in [('x1', 1), ('x2', 2)]:
            event = dict(type='event', delay=0, event_type='EM',
                         action_type=f'mouse {button} down', action=[-1, -1])
            w = self.worker(self.save('mouse.json5', {'scripts': [event]}))
            with patch('Event.WindowsEvents.win32api.mouse_event') as mouse:
                w.run()
            self.assertTrue(w.succeeded)
            self.assertEqual([tuple(call.args) for call in mouse.call_args_list], [
                (win32con.MOUSEEVENTF_XDOWN, 0, 0, identifier, 0),
                (win32con.MOUSEEVENTF_XUP, 0, 0, identifier, 0),
            ])

    def test_injected_input_is_not_recorded(self):
        from types import SimpleNamespace
        import Recorder.WindowsRecorder as recorder
        with patch.object(recorder, 'record_signals') as signals:
            self.assertTrue(recorder.get_keyboard_event(SimpleNamespace(Injected=True)))
            self.assertTrue(recorder.mouse_handler(0x0201, 0, 0, 0, 1, 0, 0, 'test'))
        signals.event_signal.emit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
