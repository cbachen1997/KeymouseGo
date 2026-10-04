import os
import sys
import math
from PySide6.QtWidgets import QApplication, QWidget, QSpinBox
from PySide6.QtCore import Qt, Slot, QRect

import Recorder
import argparse
from Event import ScriptEvent
from loguru import logger

from Plugin.Manager import PluginManager
from Util.RunScriptClass import RunScriptCMDClass, StopFlag
from Util.Paths import to_abs_path


def resize_layout(ui, ratio_w, ratio_h):
    ui.resize(ui.width() * ratio_w, ui.height() * ratio_h)

    for q_widget in ui.findChildren(QWidget):
        q_widget.setGeometry(QRect(q_widget.x() * ratio_w,
                                   q_widget.y() * ratio_h,
                                   q_widget.width() * ratio_w,
                                   q_widget.height() * ratio_h))
        q_widget.setStyleSheet('font-size: ' + str(
                                math.ceil(9 * min(ratio_h, ratio_w))) + 'px')
        if isinstance(q_widget, QSpinBox):
            q_widget.setStyleSheet('padding-left: 7px')


def main():
    import UIFunc
    app = QApplication(sys.argv)
    ui = UIFunc.UIFunc(app)
    ui.show()
    sys.exit(app.exec())


@logger.catch
def single_run(script_path, run_times):
    eventloop = QApplication.instance() or QApplication([])
    flag = StopFlag(False)
    thread = RunScriptCMDClass(script_path, run_times, flag)

    stop_name = 'f9'

    @Slot(ScriptEvent)
    def on_keyboard_event(event):
        key_name = event.action[1].lower()
        if key_name == stop_name:
            logger.debug('break exit!')
            flag.value = True
            thread.resume()
        return True

    Recorder.setuphook(commandline=True)
    Recorder.set_callback(on_keyboard_event)

    PluginManager.reload()
    thread.finished.connect(eventloop.exit)
    thread.start()

    eventloop.exec()
    thread.wait()
    Recorder.dispose()
    sys.exit(0 if thread.succeeded else 1)


if __name__ == '__main__':
    logger.debug(sys.argv)
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from Util.Diagnostics import run
        sys.exit(run(sys.argv[2]))
    elif len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        parser.add_argument('scripts',
                            help='Path for the scripts',
                            type=str,
                            nargs='+'
                            )
        parser.add_argument('-rt', '--runtimes',
                            help='Run times for the script',
                            type=int,
                            default=1
                            )
        args = vars(parser.parse_args())
        logger.debug(args)
        single_run(args['scripts'],
                   run_times=args['runtimes']
                   )
    else:
        main()
