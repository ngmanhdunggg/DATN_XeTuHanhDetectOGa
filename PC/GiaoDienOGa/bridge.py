from PyQt5.QtCore import QObject, pyqtSlot

class PotholeBridge(QObject):
    def __init__(self, map_tab):
        super().__init__()
        self.map_tab = map_tab

    @pyqtSlot(int)
    def select_pothole(self, pothole_id):
        print(f"[Bridge] Received pothole ID: {pothole_id}")
        self.map_tab.display_pothole_by_id(pothole_id)