"""Explicit, isolated smoke check for a source or frozen build (--self-test DIR)."""
import json
import os
import tempfile
from pathlib import Path


def run(output_dir):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFontDatabase, QFont
    from PySide6.QtCore import QSettings
    import UIFunc
    import Recorder
    from Util.Paths import get_assets_path

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    # Qt's headless platform does not automatically discover Windows fonts.
    if os.environ.get('QT_QPA_PLATFORM') == 'offscreen' and os.name == 'nt':
        fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        for font in ('msyh.ttc', 'segoeui.ttf'):
            QFontDatabase.addApplicationFont(str(fonts / font))
        app.setFont(QFont('Microsoft YaHei', 9))
    result = {'success': False}
    original_path = UIFunc.to_abs_path
    try:
        with tempfile.TemporaryDirectory(prefix='keymousego-check-') as tmp:
            UIFunc.to_abs_path = lambda *parts: str(Path(tmp).joinpath(*parts))
            # Prevent user plugins from running during package diagnostics.
            reload_plugins = UIFunc.PluginManager.reload
            UIFunc.PluginManager.reload = lambda: None
            try:
                ui = UIFunc.UIFunc(app, enable_hooks=False)
            finally:
                UIFunc.PluginManager.reload = reload_plugins
            ui.choice_language.setCurrentText('简体中文')
            ui.show()
            app.processEvents()
            result['compact_size'] = [ui.width(), ui.height()]
            result['hotkeys'] = [ui.hotkey_start.text(), ui.hotkey_stop.text(), ui.hotkey_record.text()]
            assert result['hotkeys'] == ['F6', 'F9', 'F10']
            assert ui.textlog.isHidden()
            assert ui.grab().save(str(output / 'compact.png'))
            ui.log_toggle.setChecked(True)
            ui.textlog.append('就绪 · 录制 / 回放 / 热键设置')
            app.processEvents()
            assert ui.grab().save(str(output / 'expanded.png'))
            result['expanded_size'] = [ui.width(), ui.height()]
            for lang in ['English', '繁體中文', '简体中文']:
                ui.choice_language.setCurrentText(lang)
                app.processEvents()
                assert ui.hotkey_start.text() == 'F6'
            for theme in ['dark_blue.xml', 'light_blue.xml', 'Default']:
                ui.choice_theme.setCurrentText(theme)
                ui.onchangetheme()  # Exceptions in Qt slots alone do not fail Python assertions.
                app.processEvents()
                assert ui.choice_theme.currentText() == theme
                if theme != 'Default':
                    assert app.styleSheet()
            ui.OnHotkeyButton(ui.hotkey_start)
            ui._capture_hotkey('f8')
            ui.config.sync()
            saved = QSettings(str(Path(tmp) / 'config.ini'), QSettings.IniFormat)
            assert saved.value('Config/StartHotKey') == 'f8'
            result['translations_themes_settings'] = 'passed'
            # Very short native hook registration check, without generating input.
            Recorder.setuphook()
            Recorder._Recorder.dispose()
            Recorder._Recorder.dispose()
            result['hook_lifecycle'] = 'passed'
            # Verify the system WAV backend at low volume. Never touch system volume.
            ui.player.setVolume(0.01)
            ui.player.setSource(get_assets_path('sounds', 'start.wav'))
            ui.player.play()
            result['sound_backend'] = 'passed'
            ui.close()
            app.processEvents()
            result['success'] = True
    except Exception as exc:
        import traceback
        result['error'] = str(exc)
        result['traceback'] = traceback.format_exc()
    finally:
        UIFunc.to_abs_path = original_path
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    return 0 if result['success'] else 1
