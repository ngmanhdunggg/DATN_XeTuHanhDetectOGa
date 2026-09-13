import sys
import os
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread

from splash import SplashScreen, AppInitializer
from main_window import MainWindow

main_window = None

def on_init_finished(init_data, splash, init_thread, app):
    global main_window
    init_thread.quit()
    init_thread.wait()
    try:
        main_window = MainWindow(init_data=init_data)
        main_window.showMaximized()
        splash.close()
        splash.deleteLater()
    except Exception as e:
        traceback.print_exc()
        splash.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    logo_path = os.path.join("database", "logo_start.png")
    if not os.path.exists(logo_path):
        logo_path = r"C:\Users\dung2\Desktop\GiaoDienOGa\database\logo_start.png"

    splash = SplashScreen(logo_path)
    splash.show()

    init_thread = QThread()
    initializer = AppInitializer()
    initializer.moveToThread(init_thread)

    initializer.progress.connect(splash.update_progress)
    initializer.finished.connect(lambda data: on_init_finished(data, splash, init_thread, app))
    init_thread.started.connect(initializer.run)

    init_thread.start()

    sys.exit(app.exec_())