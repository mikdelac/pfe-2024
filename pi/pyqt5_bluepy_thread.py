import sys
import time

import requests
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QWidget, QSlider, QComboBox,
)

from bluepy import btle

class WorkerSignals(QObject):
    signalMsg = pyqtSignal(str)
    signalRes = pyqtSignal(str)

class MyDelegate(btle.DefaultDelegate):
    def __init__(self, sgn):
        btle.DefaultDelegate.__init__(self)
        self.sgn = sgn

    def handleNotification(self, cHandle, data):
        try:
            dataDecoded = data.decode()
            self.sgn.signalRes.emit(dataDecoded)
        except UnicodeError:
            print("UnicodeError: ", data)

class WorkerBLE(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self.rqsToSend = False
        self.bytestosend = b''
        
    @pyqtSlot()
    def run(self):
        self.signals.signalMsg.emit("WorkerBLE start")
        
        #---------------------------------------------
        p = btle.Peripheral("08:F9:E0:20:3E:0A")
        p.setDelegate(MyDelegate(self.signals))

        svc = p.getServiceByUUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        self.ch_Tx = svc.getCharacteristics("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")[0]
        ch_Rx = svc.getCharacteristics("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")[0]

        setup_data = b"\x01\x00"
        p.writeCharacteristic(ch_Rx.valHandle + 1, setup_data)

        # BLE loop --------
        while True:
            p.waitForNotifications(1.0)
            
            if self.rqsToSend:
                self.rqsToSend = False
                try:
                    self.ch_Tx.write(self.bytestosend, True)
                except btle.BTLEException:
                    print("btle.BTLEException")
            
        self.signals.signalMsg.emit("WorkerBLE end")
        
    def toSendBLE(self, tosend):
        self.bytestosend = bytes(tosend, 'utf-8')
        self.rqsToSend = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        
        buttonStartBLE = QPushButton("Start BLE")
        buttonStartBLE.pressed.connect(self.startBLE)
        
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        
        self.outconsole = QPlainTextEdit()
        
        # Group Box for Tare Controls
        tareGroupBox = QGroupBox("Tare")
        tareLayout = QVBoxLayout()
        
        sliderLayout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 300)
        self.slider.setTickInterval(10)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setValue(0)
        self.sliderLabel = QLabel("Value: 0")

        self.slider.valueChanged.connect(self.updateSliderLabel)

        self.unitToggle = QComboBox()
        self.unitToggle.addItems(["kg", "lbs"])

        sliderLayout.addWidget(self.slider)
        sliderLayout.addWidget(self.sliderLabel)
        sliderLayout.addWidget(self.unitToggle)

        buttonSendBLE = QPushButton("Send Tare")
        buttonSendBLE.pressed.connect(self.sendBLE)
        
        tareLayout.addLayout(sliderLayout)
        tareLayout.addWidget(buttonSendBLE)
        tareGroupBox.setLayout(tareLayout)

        layout.addWidget(buttonStartBLE)
        layout.addWidget(self.console)
        layout.addWidget(self.outconsole)
        layout.addWidget(tareGroupBox)
        
        w = QWidget()
        w.setLayout(layout)
        
        self.setCentralWidget(w)
        
        self.show()
        self.threadpool = QThreadPool()
        print("Multithreading with Maximum %d threads" % self.threadpool.maxThreadCount())
    
    def updateSliderLabel(self, value):
        self.sliderLabel.setText(f"Value: {value}")

    def startBLE(self):
        self.workerBLE = WorkerBLE()
        self.workerBLE.signals.signalMsg.connect(self.slotMsg)
        self.workerBLE.signals.signalRes.connect(self.slotRes)
        self.threadpool.start(self.workerBLE)
        
    def sendBLE(self):
        tareCommand = "Tare"
        sliderValue = self.slider.value()
        unit = self.unitToggle.currentText()
        fullCommand = f"{tareCommand} {sliderValue} {unit}"
        self.workerBLE.toSendBLE(fullCommand)
        
    def slotMsg(self, msg):
        print(msg)
        
    def slotRes(self, res):
        self.console.appendPlainText(res)
        
app = QApplication(sys.argv)
window = MainWindow()
app.exec()

