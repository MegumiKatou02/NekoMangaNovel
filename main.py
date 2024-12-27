import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QComboBox, QLineEdit, QPushButton, 
                           QTextEdit, QLabel, QFileDialog, QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QColor, QPalette, QFont
from PyQt5.QtCore import Qt

from MangaDownload import MangaDownloader
from MangaDex import TruyenDexImageDownloader

class DownloaderThread(QThread):
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, url, output_folder, source):
        super().__init__()
        self.url = url
        self.output_folder = output_folder
        self.source = source
        print(f"select option: {source}")
        if(source == 'TruyenQQ' or source == 'Nettruyen'):
            self.downloader = MangaDownloader(logger_callback=self.progress_signal.emit)
            self.downloader.setup_website(self.source)
        else:
            self.downloader = TruyenDexImageDownloader(logger_callback=self.progress_signal.emit)

    def run(self):
        try:
            original_cwd = os.getcwd()
            os.chdir(self.output_folder)

            self.downloader.download_manga(self.url)
            
            os.chdir(original_cwd)
            self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))

class MangaDownloaderGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.downloader_thread = None

    def init_ui(self):
        self.setWindowTitle('Neko Manga Novel Downloader')
        self.setGeometry(100, 100, 800, 600)

        font = QFont('Arial', 11)
        self.setFont(font)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        source_layout = QHBoxLayout()
        source_label = QLabel('Source:')
        source_label.setStyleSheet('font-weight: bold;')
        self.source_combo = QComboBox()
        self.source_combo.addItems(['MangaDex', 'Nettruyen', 'TruyenQQ', 'TruyenDex'])
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_combo)
        layout.addLayout(source_layout)

        url_layout = QHBoxLayout()
        url_label = QLabel('URL:')
        url_label.setStyleSheet('font-weight: bold;')
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText('Enter manga URL...')
        self.url_input.setStyleSheet('background-color: #f0f0f0; padding: 5px;')
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        folder_layout = QHBoxLayout()
        folder_label = QLabel('Output Folder:')
        folder_label.setStyleSheet('font-weight: bold;')
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setStyleSheet('background-color: #f0f0f0; padding: 5px;')
        self.folder_button = QPushButton('Browse...')
        self.folder_button.setStyleSheet('background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 5px;')
        self.folder_button.clicked.connect(self.select_output_folder)
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_button)
        layout.addLayout(folder_layout)

        button_layout = QHBoxLayout()
        self.download_button = QPushButton('Download')
        self.download_button.setStyleSheet('background-color: #4CAF50; color: white; padding: 10px; border-radius: 5px;')
        self.download_button.clicked.connect(self.start_download)

        self.pause_button = QPushButton('Pause')
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet('background-color: #ff9800; color: white; padding: 10px; border-radius: 5px;')

        self.stop_button = QPushButton('Stop')
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet('background-color: #f44336; color: white; padding: 10px; border-radius: 5px;')
        self.stop_button.clicked.connect(self.stop_download)

        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet('background-color: #f0f0f0; padding: 5px;')
        layout.addWidget(self.log_output)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self.folder_input.setText(folder)

    def start_download(self):
        url = self.url_input.text().strip()
        output_folder = self.folder_input.text().strip()
        source = self.source_combo.currentText()

        if not url:
            QMessageBox.warning(self, "Error", "Please enter a manga URL")
            return

        if not output_folder:
            QMessageBox.warning(self, "Error", "Please select an output folder")
            return

        self.download_button.setEnabled(False)
        self.source_combo.setEnabled(False)
        self.url_input.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.downloader_thread = DownloaderThread(url, output_folder, source)
        self.downloader_thread.progress_signal.connect(self.update_progress)
        self.downloader_thread.error_signal.connect(self.handle_error)
        self.downloader_thread.finished_signal.connect(self.download_finished)
        self.downloader_thread.start()

    def stop_download(self):
        if self.downloader_thread and self.downloader_thread.isRunning():
            self.downloader_thread.terminate()
            self.downloader_thread.wait()
            self.download_finished()
            self.update_progress("Download stopped by user")

    def update_progress(self, message):
        self.log_output.append(message)

    def handle_error(self, error_message):
        self.log_output.append(f"ERROR: {error_message}")
        QMessageBox.critical(self, "Error", error_message)
        self.download_finished()

    def download_finished(self):
        self.download_button.setEnabled(True)
        self.source_combo.setEnabled(True)
        self.url_input.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.stop_button.setEnabled(False)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MangaDownloaderGUI()
    window.show()
    sys.exit(app.exec_())