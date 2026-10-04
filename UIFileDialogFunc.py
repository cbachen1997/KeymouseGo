import os
import re
import platform
import subprocess
import shutil
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog
from PySide6.QtWidgets import QMainWindow, QMessageBox

from UIFileDialogView import Ui_Dialog
from UIFunc import scripts, scripts_map

from Util.Paths import to_abs_path
from Util.Parser import parse_script


class FileDialog(Ui_Dialog):
    def __init__(self):
        self.dialog = QDialog()
        self.setupUi(self.dialog)
        self.dialog.setFixedSize(self.dialog.width(), self.dialog.height())
        self.choice.clicked.connect(self.choice_file)
        self.edit.clicked.connect(self.edit_file)
        self.rename.clicked.connect(lambda: self.rename_file(self.lineEdit.text()))

        self.main_window = QMainWindow()
        index = scripts_map.get('current_index', -1)
        self.filename = scripts[index] if 0 <= index < len(scripts) else ''
        self.lineEdit.setText(self.filename)
        self.lineEdit.setReadOnly(True)
        self.path = os.path.join(to_abs_path("scripts"))
        
        self.dialog.setWindowTitle(QCoreApplication.translate('Dialog', 'File Manage', None))
        self.file_name.setText(QCoreApplication.translate('Dialog', 'file name', None))
        self.choice.setText(QCoreApplication.translate('Dialog', 'choice', None))
        self.edit.setText(QCoreApplication.translate('Dialog', 'edit', None))
        self.rename.setText(QCoreApplication.translate('Dialog', 'rename', None))
    

    def choice_file(self):
        file = QFileDialog.getOpenFileName(self.main_window, "选择文件", dir=to_abs_path('scripts'), filter='*.txt *.json5')[0]
        if file:
            try:
                self.import_script(file)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                QMessageBox.warning(self.dialog, 'Import failed', str(exc))

    def import_script(self, filename):
        source = Path(filename).resolve()
        parse_script(str(source))
        destination = Path(self.path) / source.name
        if source != destination.resolve():
            index = 1
            while destination.exists():
                destination = Path(self.path) / f'{source.stem}_{index}{source.suffix}'
                index += 1
            shutil.copy2(source, destination)
        name = destination.name
        if name not in scripts:
            scripts.append(name)
        scripts_map.update({name: index for index, name in enumerate(scripts)})
        scripts_map['current_index'] = scripts.index(name)
        self.lineEdit.setText(name)


    def edit_file(self):
        if not self.lineEdit.text():
            return
        user_platform = platform.system()
        try:
            if user_platform == 'Linux':
                subprocess.call(['xdg-open', os.path.join(self.path, self.lineEdit.text())])
            elif user_platform == 'Darwin':
                # mac
                subprocess.call(['open', os.path.join(self.path, self.lineEdit.text())])
            else:
                os.startfile(os.path.join(self.path, self.lineEdit.text()))
        except FileNotFoundError:
            QMessageBox().warning(self.main_window, "warning", QCoreApplication.translate('Dialog', 'FNF', None))
            self.lineEdit.setText('')


    def rename_file(self, filename):
        if not filename:
            return
        new_file_name, accepted = QInputDialog.getText(self.main_window,
                                                 QCoreApplication.translate('Dialog', 'rename', None), 
                                                 QCoreApplication.translate('Dialog', 'PINFN', None))
        if not accepted:
            return
        new_file_name = new_file_name.strip()
        if any(char in new_file_name for char in '/\\:*?"<>|') or new_file_name in ('.', '..'):
            QMessageBox.warning(self.dialog, 'Invalid name', 'Please enter a filename without path separators.')
            return

        if new_file_name != None and new_file_name.strip() != '':
            if filename.endswith('.txt'):
                if not new_file_name.endswith('.txt'):
                    new_file_name = new_file_name + '.txt'
            elif filename.endswith('.json5'):
                if not new_file_name.endswith('.json5'):
                    new_file_name = new_file_name + '.json5'

            try:
                if os.path.exists(os.path.join(self.path, new_file_name)):
                    QMessageBox.warning(self.dialog, 'Rename', 'A file with that name already exists.')
                    return
                os.rename(os.path.join(self.path, self.lineEdit.text()), os.path.join(self.path, new_file_name))
                QMessageBox().information(self.main_window, 'info', QCoreApplication.translate('Dialog', 'Success', None))
                # 更新
                filename = self.lineEdit.text()
                index = scripts_map.get(filename)
                scripts_map.pop(filename)
                scripts_map[new_file_name] = index
                scripts[index] = new_file_name
                self.lineEdit.setText(new_file_name)
            except OSError as exc:
                QMessageBox.warning(self.main_window, 'warning', str(exc))
        else:
            QMessageBox.warning(self.main_window, 'warning', QCoreApplication.translate('Dialog', 'FNCBEOS', None))


    def show(self):
        self.dialog.show()
        self.dialog.exec_()
        
