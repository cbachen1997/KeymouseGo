# -*- encoding:utf-8 -*-
import datetime
from typing import List

import json5
import os
import sys
import threading
import platform
import locale
import tempfile
import Recorder

from PySide6.QtGui import QTextCursor
from qt_material import list_themes, QtStyleTools
from PySide6.QtCore import *
from PySide6.QtWidgets import QMainWindow, QApplication, QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy
from loguru import logger

from Event import ScriptEvent, flag_multiplemonitor
from Plugin.Manager import PluginManager
from UIView import Ui_UIView

from Util.Paths import to_abs_path, get_assets_path
from Util.Sound import SoundPlayer
from Util.RunScriptClass import RunScriptClass
from Util.Global import State
from Util.Version import __version__
from Util.ClickedLabel import Label


os.environ['QT_ENABLE_HIGHDPI_SCALING'] = "1"
# if platform.system() == 'Windows':
#     HOT_KEYS = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
#                 'XButton1', 'XButton2', 'Middle']
# else:
#     HOT_KEYS = ['F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12',
#                 'Middle']

logger.remove()
if sys.stdout is not None:
    logger.add(sys.stdout, backtrace=True, diagnose=True,
               level='DEBUG')
logger.add(to_abs_path('logs', 'KeymouseGo.log'), rotation='2 MB', retention=5, backtrace=True, diagnose=False,
           level='INFO')


def format_hotkey(value):
    """Format the persisted lowercase hotkey value for display."""
    if value is None:
        return ''
    return '+'.join(part.strip().upper() for part in str(value).split('+') if part.strip())


def normalize_hotkey(value):
    parts = [part.strip().lower() for part in str(value or '').split('+') if part.strip()]
    parts = [{'escape': 'esc', 'back': 'backspace'}.get(part, part) for part in parts]
    return '+'.join(sorted(parts[:-1]) + parts[-1:])


APPLE_STYLE = """
QWidget {
    color: #1d1d1f;
}

QMainWindow, QWidget#centralwidget {
    background-color: #f5f5f7;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 14px;
    margin-top: 12px;
    padding: 16px 12px 10px 12px;
    font-size: 10pt;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #1d1d1f;
}

QLabel {
    background: transparent;
    color: #1d1d1f;
    font-size: 10pt;
}

QComboBox, QSpinBox {
    background-color: #f2f2f7;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    min-height: 29px;
    padding: 0 9px;
    selection-background-color: #007aff;
}

QComboBox:hover, QSpinBox:hover {
    border-color: #007aff;
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d1d1d6;
    selection-background-color: #007aff;
    selection-color: #ffffff;
}

QPushButton {
    background-color: #007aff;
    border: none;
    border-radius: 9px;
    color: #ffffff;
    min-height: 32px;
    padding: 0 15px;
    font-size: 10pt;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #006ee6;
}

QPushButton:pressed {
    background-color: #005cc8;
}

QPushButton:disabled {
    background-color: #d1d1d6;
    color: #8e8e93;
}

QPushButton#btrecord, QPushButton#bt_open_script_files, QPushButton#log_toggle {
    background-color: #ffffff;
    border: 1px solid #d1d1d6;
    color: #007aff;
}

QPushButton#btrecord:hover, QPushButton#bt_open_script_files:hover, QPushButton#log_toggle:hover {
    background-color: #f2f2f7;
}

QPushButton#hotkey_start, QPushButton#hotkey_record, QPushButton#hotkey_stop {
    background-color: #f2f2f7;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    color: #007aff;
    min-height: 28px;
    padding: 0 10px;
    font-weight: 500;
}

QPushButton#hotkey_start:hover, QPushButton#hotkey_record:hover, QPushButton#hotkey_stop:hover {
    background-color: #e5e5ea;
    border-color: #007aff;
}

QPushButton#hotkey_start:disabled, QPushButton#hotkey_record:disabled, QPushButton#hotkey_stop:disabled {
    background-color: #e5e5ea;
    color: #8e8e93;
}

QTextEdit {
    background-color: #ffffff;
    border: 1px solid #e5e5ea;
    border-radius: 11px;
    padding: 8px;
    selection-background-color: #b3d7ff;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #d1d1d6;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    background: #007aff;
    border-radius: 8px;
}

QStatusBar {
    background-color: #f5f5f7;
    color: #6e6e73;
}

QStatusBar::item {
    border: none;
}
"""


scripts = []
scripts_map = {'current_index': 0, 'choice_language': '简体中文'}


def get_script_list_from_dir():
    global scripts

    if not os.path.exists(to_abs_path('scripts')):
        os.mkdir(to_abs_path('scripts'))
    scripts[:] = sorted((s for s in os.listdir(to_abs_path('scripts'))
                         if s.lower().endswith(('.txt', '.json5')) and os.path.isfile(to_abs_path('scripts', s))), reverse=True)


def update_script_map():
    global scripts_map
    
    scripts_map.clear()
    for (i, item) in enumerate(scripts):
        scripts_map[item] = i

class UIFunc(QMainWindow, Ui_UIView, QtStyleTools):
    updateStateSignal: Signal = Signal(State)

    def __init__(self, app, enable_hooks=True):
        global scripts

        super(UIFunc, self).__init__()

        logger.info('assets root:{0}'.format(get_assets_path()))

        self.setupUi(self)

        self.app = app

        self.state = State(State.IDLE)
        self.hotkey_set_btn = None
        self.hotkey_previous_value = None
        self._enable_hooks = enable_hooks
        self._closing = False
        self._file_dialog_open = False

        self.config = self.loadconfig()
        self._setup_compact_layout()

        self.setFocusPolicy(Qt.NoFocus)

        self.trans = QTranslator(self)
        self.choice_language.addItems(['简体中文', 'English', '繁體中文'])

        # 获取默认的地区设置
        default_language = 'zh-cn' if QLocale.system().language() == QLocale.Chinese else 'en'
        language = {'zh-cn': '简体中文', 'en': 'English', 'zh-tw': '繁體中文'}.get(
            self.config.value('Config/Language', default_language), '简体中文')
        self.choice_language.setCurrentText(language)
        self.choice_language.currentTextChanged.connect(self.onchangelang)
        self.onchangelang()

        get_script_list_from_dir()
        update_script_map()
        self.scripts = scripts
        self.choice_script.addItems(self.scripts)
        if self.scripts:
            self.choice_script.setCurrentIndex(0)

        PluginManager.reload()

        # Config
        self.choice_theme.addItems(['Default'])
        self.choice_theme.addItems(list_themes())
        # self.choice_theme.addItems(PluginManager.resources_paths)
        self.stimes.setValue(self._config_int('LoopTimes', 1))
        self.mouse_move_interval_ms.setValue(self._config_int('Precision', 200))
        self.choice_theme.setCurrentText(self.config.value("Config/Theme"))
        if self.config.value('Config/Script') is not None and self.config.value('Config/Script') in self.scripts:
            self.choice_script.setCurrentText(self.config.value('Config/Script'))
        self.stimes.valueChanged.connect(self.onconfigchange)
        self.mouse_move_interval_ms.valueChanged.connect(self.onconfigchange)
        self.mouse_move_interval_ms.valueChanged.connect(Recorder.set_interval)
        self.choice_theme.currentTextChanged.connect(self.onchangetheme)
        self.choice_script.currentTextChanged.connect(self.onconfigchange)
        self._set_hotkey_text(self.hotkey_stop, self.config.value("Config/StopHotKey", "f9"))
        self._set_hotkey_text(self.hotkey_start, self.config.value("Config/StartHotKey", "f6"))
        self._set_hotkey_text(self.hotkey_record, self.config.value("Config/RecordHotKey", "f10"))


        self.onchangetheme()

        self.textlog.textChanged.connect(lambda: self.textlog.moveCursor(QTextCursor.End))
        self.textlog.document().setMaximumBlockCount(500)

        # For tune playing
        self.player = SoundPlayer()
        self.volumeSlider.setMaximum(100)
        self.volumeSlider.setValue(self._config_int('Volume', 50))
        self.player.setVolume(self.volumeSlider.value()/100.0)
        self.volumeSlider.valueChanged.connect(
            lambda: self.player.setVolume(
                self.volumeSlider.value()/100.0))
        self.volumeSlider.valueChanged.connect(lambda value: self.config.setValue('Config/Volume', value))

        self.record = []

        self.actioncount = 0

        # For better thread control
        self.runthread = None

        self.btrun.clicked.connect(self.OnBtrunButton)
        self.btrecord.clicked.connect(self.OnBtrecordButton)
        self.btpauserecord.clicked.connect(self.OnPauseRecordButton)
        self.bt_open_script_files.clicked.connect(self.OnBtOpenScriptFilesButton)
        self.choice_language.installEventFilter(self)
        self.choice_script.installEventFilter(self)
        self.btrun.installEventFilter(self)
        self.btrecord.installEventFilter(self)
        self.btpauserecord.installEventFilter(self)
        self.bt_open_script_files.installEventFilter(self)

        # 组合键缓冲池，[ctrl,shift,alt,cmd/start/win]可用作组合键，但不能单独用作启动热键
        self.keys_pool: List[str] = []
        self._hotkey_releases = set()
        self._mouse_hotkey_releases = set()
        self.hotkey_set_btn = None
        self.hotkey_previous_value = None
        self.hotkey_stop.clicked.connect(lambda: self.OnHotkeyButton(self.hotkey_stop))
        self.hotkey_start.clicked.connect(lambda: self.OnHotkeyButton(self.hotkey_start))
        self.hotkey_record.clicked.connect(lambda: self.OnHotkeyButton(self.hotkey_record))

        # 热键引发状态转移
        def check_hotkeys(key_name):
            if self._file_dialog_open or self._closing:
                return False
            if key_name in Recorder.globals.key_combination_trigger:
                if self.state == State.SETTING_HOT_KEYS and self.hotkey_set_btn is not None:
                    self.hotkey_set_btn.setText(format_hotkey('+'.join(self.keys_pool)))
                return False
            key_name = normalize_hotkey('+'.join([*self.keys_pool, key_name]))

            if self.state == State.SETTING_HOT_KEYS:
                return self._capture_hotkey(key_name)

            start_name = self._hotkey_value(self.hotkey_start)
            stop_name = self._hotkey_value(self.hotkey_stop)
            record_name = self._hotkey_value(self.hotkey_record)

            if key_name == start_name:
                if self.state == State.IDLE:
                    logger.debug('{0} host start'.format(key_name))
                    self.OnBtrunButton()
                elif self.state == State.RUNNING:
                    logger.info('Script pause')
                    logger.debug('{0} host pause'.format(key_name))
                    self.runthread.set_pause()
                    self.update_state(State.PAUSE_RUNNING)
                elif self.state == State.PAUSE_RUNNING:
                    logger.info('Script resume')
                    self.runthread.resume()
                    logger.debug('{0} host resume'.format(key_name))
                    self.update_state(State.RUNNING)
            elif key_name == stop_name:
                if self.state == State.RUNNING or self.state == State.PAUSE_RUNNING:
                    logger.info('Script stop')
                    self.tnumrd.setText('broken')
                    self.runthread.stop()
                    logger.debug('{0} host stop'.format(key_name))
                elif self.state == State.RECORDING or self.state == State.PAUSE_RECORDING:
                    self.recordMethod()
                    logger.info('Record stop')
                    logger.debug('{0} host stop record'.format(key_name))
            elif key_name == record_name:
                if self.state == State.RECORDING:
                    self.pauseRecordMethod()
                    logger.debug('{0} host pause record'.format(key_name))
                elif self.state == State.PAUSE_RECORDING:
                    self.pauseRecordMethod()
                    logger.debug('{0} host resume record'.format(key_name))
                elif self.state == State.IDLE:
                    self.recordMethod()
                    logger.debug('{0} host start record'.format(key_name))
            return key_name in [start_name, stop_name, record_name]

        @Slot(ScriptEvent)
        def on_record_event(event: ScriptEvent):
            if self._file_dialog_open or self._closing:
                return
            # 判断mouse热键
            if event.event_type == "EM":
                name = event.action_type
                for button, hotkey in [('x1', 'xbutton1'), ('x2', 'xbutton2'), ('middle', 'middle')]:
                    if name == f'mouse {button} up' and button in self._mouse_hotkey_releases:
                        self._mouse_hotkey_releases.discard(button)
                        return
                    if name == f'mouse {button} down':
                        capturing = self.state == State.SETTING_HOT_KEYS
                        modifiers = list(self.keys_pool)
                        if check_hotkeys(hotkey) or capturing:
                            self._mouse_hotkey_releases.add(button)
                            self._discard_hotkey_modifiers(modifiers)
                            return
            else:
                key_name = normalize_hotkey(event.action[1])
                if event.action_type == 'key down':
                    if key_name in self._hotkey_releases:
                        return  # Ignore key auto-repeat until the triggering key is released.
                    if key_name in Recorder.globals.key_combination_trigger and key_name not in self.keys_pool:
                        self.keys_pool.append(key_name)
                    capturing = self.state == State.SETTING_HOT_KEYS
                    modifiers = list(self.keys_pool)
                    handled = check_hotkeys(key_name)
                    if handled or (capturing and key_name not in Recorder.globals.key_combination_trigger):
                        self._hotkey_releases.add(key_name)
                        self._discard_hotkey_modifiers(modifiers)
                        return
                elif event.action_type == 'key up':
                    if key_name in Recorder.globals.key_combination_trigger and key_name in self.keys_pool:
                        self.keys_pool.remove(key_name)
                        check_hotkeys(key_name)
                    if key_name in self._hotkey_releases:
                        self._hotkey_releases.discard(key_name)
                        return
                # 不录制热键
                for btn in [self.hotkey_start, self.hotkey_record, self.hotkey_stop]:
                    if key_name == self._hotkey_value(btn):
                        return
            # 录制事件
            if self.state == State.RECORDING:
                if self._record_first_event:
                    event.delay = 0
                    self._record_first_event = False
                if event.event_type == 'EM' and not flag_multiplemonitor:
                    tx, ty = event.action
                    event.action = ['{0}%'.format(tx), '{0}%'.format(ty)]
                event_dict = dict(event.__dict__)
                event_dict['type'] = 'event'
                # PluginManager.call_record(event_dict)
                self.record.append(event_dict)
                self.actioncount = self.actioncount + 1
                text = '%d actions recorded' % self.actioncount
                logger.debug('Recorded %s' % event)
                self.tnumrd.setText(text)
                self.textlog.append(str(event))
        logger.debug('Initialize at thread ' + str(QThread.currentThread()))
        self._record_callback = on_record_event
        if enable_hooks:
            Recorder.setuphook()
            Recorder.set_callback(on_record_event)
            Recorder.set_cursor_pose_change(self.cursor_pos_change)
        Recorder.set_interval(self.mouse_move_interval_ms.value())

    def _discard_hotkey_modifiers(self, modifiers):
        self._hotkey_releases.update(modifiers)
        while self.record and self.record[-1]['event_type'] == 'EK' and self.record[-1]['action_type'] == 'key down' and normalize_hotkey(self.record[-1]['action'][1]) in modifiers:
            self.record.pop()
        self.actioncount = len(self.record)

    def eventFilter(self, watched, event: QEvent):
        et: QEvent.Type = event.type()
        # print(event, et)
        if et == QEvent.KeyPress or et == QEvent.KeyRelease:
            return True
        return super(UIFunc, self).eventFilter(watched, event)

    def onconfigchange(self):
        self.config.setValue("Config/LoopTimes", self.stimes.value())
        self.config.setValue("Config/Precision", self.mouse_move_interval_ms.value())
        self.config.setValue("Config/Theme", self.choice_theme.currentText())
        self.config.setValue("Config/Script", self.choice_script.currentText())
        self.config.setValue("Config/StartHotKey", self._hotkey_value(self.hotkey_start))
        self.config.setValue("Config/StopHotKey", self._hotkey_value(self.hotkey_stop))
        self.config.setValue("Config/RecordHotKey", self._hotkey_value(self.hotkey_record))

    def onchangelang(self):
        global scripts_map

        if self.choice_language.currentText() == '简体中文':
            self.trans.load(get_assets_path('i18n', 'zh-cn'))
            _app = QApplication.instance()
            _app.installTranslator(self.trans)
            self.retranslateUi(self)
        elif self.choice_language.currentText() == 'English':
            self.trans.load(get_assets_path('i18n', 'en'))
            _app = QApplication.instance()
            _app.installTranslator(self.trans)
            self.retranslateUi(self)
        elif self.choice_language.currentText() == '繁體中文':
            self.trans.load(get_assets_path('i18n', 'zh-tw'))
            _app = QApplication.instance()
            _app.installTranslator(self.trans)
            self.retranslateUi(self)
        self.retranslateUi(self)
        self._set_hotkey_text(self.hotkey_stop, self.config.value("Config/StopHotKey", "f9"))
        self._set_hotkey_text(self.hotkey_start, self.config.value("Config/StartHotKey", "f6"))
        self._set_hotkey_text(self.hotkey_record, self.config.value("Config/RecordHotKey", "f10"))
        self.config.setValue('Config/Language', {'简体中文': 'zh-cn', 'English': 'en', '繁體中文': 'zh-tw'}[self.choice_language.currentText()])
        self._update_log_toggle()

    def onchangetheme(self):
        theme = self.choice_theme.currentText()
        if theme == 'Default':
            self.apply_stylesheet(self.app, theme='default')
            self.setStyleSheet(APPLE_STYLE)
        else:
            self.setStyleSheet('')
            self.apply_stylesheet(self.app, theme=theme)
        self.config.setValue("Config/Theme", self.choice_theme.currentText())

    @Slot(str)
    def playtune(self, filename: str):
        if self._closing:
            return
        try:
            self.player.setSource(get_assets_path('sounds', filename))
            self.player.play()
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning('Cannot play notification: {}', exc)

    def closeEvent(self, event):
        if self.state in (State.RECORDING, State.PAUSE_RECORDING) and self.record:
            # Pause before opening a modal dialog so its clicks are not recorded.
            if self.state == State.RECORDING:
                self.pauseRecordMethod()
            choice = QMessageBox.question(
                self, '未保存的录制 / Unsaved recording',
                '是否保存当前录制后退出？\nSave the current recording before closing?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if choice == QMessageBox.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.Save and not self.recordMethod():
                event.ignore()
                return
        self._closing = True
        if self.runthread and self.runthread.isRunning():
            self.runthread.stop()
            if not self.runthread.wait(1500):
                # A user plugin may not return promptly. Keep Qt objects alive
                # and close after the worker finishes instead of killing it.
                self.runthread.finished.connect(self.close, Qt.UniqueConnection)
                self.statusbar.showMessage('Waiting for the running script to stop...')
                event.ignore()
                return
        self.config.sync()
        if self._enable_hooks:
            Recorder.dispose()
        self.player.close()
        event.accept()

    def _config_int(self, key, default):
        try:
            return int(self.config.value('Config/' + key, default))
        except (TypeError, ValueError):
            return default

    def _setup_compact_layout(self):
        # Reuse the designer widgets, but let Qt calculate geometry at every DPI.
        root = QVBoxLayout(self.centralwidget)
        root.setContentsMargins(16, 10, 16, 10)
        root.setSpacing(10)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(self.groupBox_2, 1)
        cards.addWidget(self.groupBox, 1)
        root.addLayout(cards)
        for card in (self.groupBox_2, self.groupBox):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions = QHBoxLayout()
        actions.addWidget(self.horizontalLayoutWidget, 3)
        actions.addWidget(self.formLayoutWidget_3, 2)
        self.log_toggle = QPushButton(self.centralwidget)
        self.log_toggle.setObjectName('log_toggle')
        self.log_toggle.setCheckable(True)
        self.log_toggle.setChecked(self.config.value('Config/ShowLog', False, type=bool))
        actions.addWidget(self.log_toggle)
        root.addLayout(actions)
        root.addWidget(self.verticalLayoutWidget, 1)
        for widget in (self.horizontalLayoutWidget, self.formLayoutWidget_3):
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.textlog.setMinimumHeight(150)
        self.tnumrd.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.label_cursor_pos.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.verticalLayout.setStretch(0, 0)
        self.verticalLayout.setStretch(1, 1)
        self.textlog.setVisible(self.log_toggle.isChecked())
        self.log_toggle.toggled.connect(self._toggle_log)
        self.menubar.hide()
        self.resize(700, 490 if self.log_toggle.isChecked() else 310)

    def _update_log_toggle(self):
        self.setWindowTitle(f'KeymouseGo v{__version__}')
        english = self.choice_language.currentText() == 'English'
        traditional = self.choice_language.currentText() == '繁體中文'
        self.log_toggle.setText(('Hide log' if english else '收起日誌' if traditional else '收起日志')
                               if self.log_toggle.isChecked() else
                               ('Show log' if english else '顯示日誌' if traditional else '显示日志'))

    def _toggle_log(self, checked):
        self.textlog.setVisible(checked)
        self.config.setValue('Config/ShowLog', checked)
        self._update_log_toggle()
        self.centralwidget.layout().activate()
        self.resize(self.width(), self.minimumSizeHint().height())

    def loadconfig(self):
        if not os.path.exists(to_abs_path('config.ini')):
            with open(to_abs_path('config.ini'), 'w', encoding='utf-8') as f:
                f.write('[Config]\n'
                        'StartHotKey=f6\n'
                        'StopHotKey=f9\n'
                        'RecordHotKey=f10\n'
                        'LoopTimes=1\n'
                        'Precision=200\n'
                        'Language=zh-cn\n'
                        'Theme=Default\n')
        return QSettings(to_abs_path('config.ini'), QSettings.IniFormat)

    def get_script_path(self):
        i = self.choice_script.currentIndex()
        if i < 0:
            return ''
        script = self.scripts[i]
        path = os.path.join(to_abs_path('scripts'), script)
        logger.info('Script path: {0}'.format(path))
        return path

    def new_script_path(self):
        now = datetime.datetime.now()
        script = '%s.json5' % now.strftime('%Y%m%d_%H%M%S_%f')
        self.scripts.insert(0, script)
        update_script_map()
        self.choice_script.clear()
        self.choice_script.addItems(self.scripts)
        self.choice_script.setCurrentIndex(0)
        return self.get_script_path()

    def pauseRecordMethod(self):
        if self.state == State.PAUSE_RECORDING:
            logger.info('Record resume')
            self.btpauserecord.setText(QCoreApplication.translate("UIView", 'Pause', None))
            self.update_state(State.RECORDING)
            self._record_first_event = True
        elif self.state == State.RECORDING:
            logger.info('Record pause')
            self.btpauserecord.setText(QCoreApplication.translate("UIView", 'Continue', None))
            self.tnumrd.setText('record paused')
            self.update_state(State.PAUSE_RECORDING)

    def OnPauseRecordButton(self):
        self.pauseRecordMethod()

    def OnBtOpenScriptFilesButton(self):
        global scripts_map

        import UIFileDialogFunc
        if self.state != State.IDLE:
            return

        scripts_map['current_index'] = self.choice_script.currentIndex()
        file_dialog = UIFileDialogFunc.FileDialog()
        self.bt_open_script_files.setDisabled(True)
        self.btrecord.setDisabled(True)
        self.btrun.setDisabled(True)
        self.hotkey_start.setDisabled(True)
        self.hotkey_stop.setDisabled(True)
        self.hotkey_record.setDisabled(True)
        self._file_dialog_open = True
        try:
            file_dialog.show()
        finally:
            self._file_dialog_open = False
        self.bt_open_script_files.setDisabled(False)
        self.btrecord.setDisabled(False)
        self.btrun.setDisabled(False)
        self.hotkey_start.setEnabled(True)
        self.hotkey_stop.setEnabled(True)
        self.hotkey_record.setEnabled(True)
        # 重新设置的为点击按钮时, 所处的位置
        self.choice_script.clear()
        self.choice_script.addItems(scripts)
        self.choice_script.setCurrentIndex(scripts_map['current_index'])

    def recordMethod(self):
        if self.state == State.RECORDING or self.state == State.PAUSE_RECORDING:
            logger.info('Record stop')
            script = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f.json5')
            target = to_abs_path('scripts', script)
            temporary = None
            try:
                # Never expose a partial script or clear the in-memory recording
                # when a disk write fails.
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                        dir=to_abs_path('scripts'), suffix='.tmp', delete=False) as f:
                    temporary = f.name
                    json5.dump({"scripts": self.record}, indent=2, ensure_ascii=False, fp=f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, target)
            except (OSError, TypeError, ValueError) as exc:
                logger.exception('Could not save recording')
                self.update_state(State.PAUSE_RECORDING)
                self.btpauserecord.setText('继续 / Continue')
                self.statusbar.showMessage('保存失败，录制仍保留在内存中 / Save failed: ' + str(exc))
                return False
            finally:
                if temporary and os.path.exists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
            self.scripts.insert(0, script)
            update_script_map()
            self.choice_script.clear()
            self.choice_script.addItems(self.scripts)
            self.btrecord.setText(QCoreApplication.translate("UIView", 'Record', None))
            self.tnumrd.setText('finished')
            self.record = []
            self.actioncount = 0
            self.choice_script.setCurrentIndex(0)
            self.btpauserecord.setText(QCoreApplication.translate("UIView", 'Pause Record', None))
            self.update_state(State.IDLE)
            return True
        elif self.state == State.IDLE:
            logger.info('Record start')
            self.textlog.clear()
            status = self.tnumrd.text()
            if 'running' in status or 'recorded' in status:
                return
            self.btrecord.setText(QCoreApplication.translate("UIView", 'Finish', None))
            self.tnumrd.setText('0 actions recorded')
            self.record = []
            self._record_first_event = True
            self.update_state(State.RECORDING)
            return True

    def OnBtrecordButton(self):
        # While paused no Finish click was recorded. Also do not discard real
        # keyboard events when the button is activated using the keyboard.
        if self.state == State.RECORDING and len(self.record) >= 2 and self.btrecord.underMouse():
            down, up = self.record[-2:]
            if (down.get('event_type') == up.get('event_type') == 'EM'
                    and down.get('action_type') == 'mouse left down'
                    and up.get('action_type') == 'mouse left up'):
                self.record = self.record[:-2]
        self.recordMethod()

    def OnBtrunButton(self):
        if self.state != State.IDLE or (self.runthread and self.runthread.isRunning()):
            return
        if not self.get_script_path():
            self.statusbar.showMessage('请先录制或选择脚本 / Select a script first', 4000)
            return
        logger.info('Script start')
        self.textlog.clear()
        self.update_state(State.RUNNING)
        if self.runthread:
            self.updateStateSignal.disconnect(self.runthread.update_state)
        self.runthread = RunScriptClass(self)
        self.runthread.finished.connect(lambda: self.handle_runscript_status(self.runthread.succeeded))
        self.runthread.start()

    def update_state(self, state):
        self.state = state
        self.choice_script.setEnabled(state == State.IDLE)
        self.bt_open_script_files.setEnabled(state == State.IDLE)
        self.choice_language.setEnabled(state == State.IDLE)
        if state != State.SETTING_HOT_KEYS and state != State.RECORDING and state != State.PAUSE_RECORDING:
            self.updateStateSignal.emit(self.state)
        if state == State.IDLE:
            self.hotkey_start.setEnabled(True)
            self.hotkey_stop.setEnabled(True)
            self.hotkey_record.setEnabled(True)
            self.btrun.setEnabled(True)
            self.btrecord.setEnabled(True)
            self.btpauserecord.setEnabled(False)
        elif state == State.RUNNING or state == State.PAUSE_RUNNING or state == State.SETTING_HOT_KEYS:
            self.hotkey_start.setEnabled(False)
            self.hotkey_stop.setEnabled(False)
            self.hotkey_record.setEnabled(False)
            self.btrun.setEnabled(False)
            self.btrecord.setEnabled(False)
            self.btpauserecord.setEnabled(False)
        elif state == State.RECORDING or state == State.PAUSE_RECORDING:
            self.hotkey_start.setEnabled(False)
            self.hotkey_stop.setEnabled(False)
            self.hotkey_record.setEnabled(False)
            self.btrun.setEnabled(False)
            self.btrecord.setEnabled(True)
            self.btpauserecord.setEnabled(True)

    def OnHotkeyButton(self, btn_obj: QObject):
        self.keys_pool.clear()
        self.hotkey_set_btn = btn_obj
        self.hotkey_previous_value = btn_obj.text()
        btn_obj.setText('...')
        self.statusbar.showMessage(QCoreApplication.translate(
            "UIView", "Press a key or key combination. Esc cancels; Delete clears."))
        self.update_state(State.SETTING_HOT_KEYS)

    def _set_hotkey_text(self, btn_obj: QObject, value):
        btn_obj.setText(format_hotkey(value))

    def _hotkey_value(self, btn_obj: QObject):
        """Return the normalized value used by the global event hook."""
        text = btn_obj.text().strip()
        if btn_obj is self.hotkey_set_btn and self.hotkey_previous_value is not None:
            text = self.hotkey_previous_value
        return normalize_hotkey(text)

    def _capture_hotkey(self, hotkey_name: str):
        """Finish a hotkey capture from a global keyboard or mouse event."""
        hotkey_name = normalize_hotkey(hotkey_name)
        if self.hotkey_set_btn is None:
            self.keys_pool.clear()
            self.update_state(State.IDLE)
            return False

        # Esc cancels only when it is pressed by itself. Ctrl+Esc, for example,
        # remains a valid combination.
        if not self.keys_pool and hotkey_name == 'esc':
            self._cancel_hotkey_capture()
            self.statusbar.showMessage(QCoreApplication.translate(
                "UIView", "Hotkey change cancelled."), 3000)
            return False

        # Delete (or Backspace) by itself clears the selected hotkey.
        if not self.keys_pool and hotkey_name in ('delete', 'backspace'):
            self.hotkey_set_btn.setText('')
            self._finish_hotkey_capture()
            self.onconfigchange()
            self.statusbar.showMessage(QCoreApplication.translate(
                "UIView", "Hotkey cleared."), 3000)
            return False

        for btn in [self.hotkey_start, self.hotkey_record, self.hotkey_stop]:
            if btn is not self.hotkey_set_btn and self._hotkey_value(btn) == hotkey_name.lower():
                self._cancel_hotkey_capture()
                self.statusbar.showMessage(QCoreApplication.translate(
                    "UIView", "That hotkey is already in use."), 3000)
                return False

        self._set_hotkey_text(self.hotkey_set_btn, hotkey_name)
        self._finish_hotkey_capture()
        self.onconfigchange()
        self.statusbar.showMessage(QCoreApplication.translate(
            "UIView", "Hotkey saved."), 3000)
        return False

    def _finish_hotkey_capture(self):
        self.keys_pool.clear()
        self.hotkey_set_btn = None
        self.hotkey_previous_value = None
        self.update_state(State.IDLE)

    def _cancel_hotkey_capture(self):
        if self.hotkey_set_btn is not None and self.hotkey_previous_value is not None:
            self.hotkey_set_btn.setText(self.hotkey_previous_value)
        self._finish_hotkey_capture()

    @Slot(bool)
    def handle_runscript_status(self, succeed):
        self.update_state(State.IDLE)

    @Slot(tuple)
    def cursor_pos_change(self, pos):
        self.label_cursor_pos.setText(f'Cursor pos: {pos}')
