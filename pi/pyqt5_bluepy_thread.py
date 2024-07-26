import sys
import re  # Import re for regex to parse the Bluetooth message
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QWidget, QSlider, QComboBox,
)

from bluepy import btle

class SensorData:
    def __init__(self, timestamp, anp35=None, anp39=None, anp37=None, anp36=None, anp34=None, anp38=None):
        self.timestamp = timestamp
        self.anp35 = anp35
        self.anp39 = anp39
        self.anp37 = anp37
        self.anp36 = anp36
        self.anp34 = anp34
        self.anp38 = anp38

    def __str__(self):
        data_str = f"Timestamp: {self.timestamp}"
        if self.anp35 is not None:
            data_str += f", AnP35: {self.anp35}"
        if self.anp39 is not None:
            data_str += f", AnP39: {self.anp39}"
        if self.anp37 is not None:
            data_str += f", AnP37: {self.anp37}"
        if self.anp36 is not None:
            data_str += f", AnP36: {self.anp36}"
        if self.anp34 is not None:
            data_str += f", AnP34: {self.anp34}"
        if self.anp38 is not None:
            data_str += f", AnP38: {self.anp38}"
        return data_str

class WorkerSignals(QObject):
    signalMsg = pyqtSignal(str)
    signalRes = pyqtSignal(str)
    signalConnecting = pyqtSignal(bool)
    signalConnected = pyqtSignal(bool)
    signalDataParsed = pyqtSignal(SensorData)

class MyDelegate(btle.DefaultDelegate):
    def __init__(self, sgn):
        btle.DefaultDelegate.__init__(self)
        self.sgn = sgn

    def handleNotification(self, cHandle, data):
        try:
            dataDecoded = data.decode()
            self.sgn.signalRes.emit(dataDecoded)
            print("Data: ", dataDecoded)

            # Parse the data values
            matches = re.findall(r'(\d+:\d+\.\d+),AnP(\d+):(\d+)', dataDecoded)
            for match in matches:
                timestamp = match[0]
                sensor = f"AnP{match[1]}"
                value = int(match[2])

                if sensor == "AnP35":
                    sensor_data = SensorData(timestamp, anp35=value)
                elif sensor == "AnP39":
                    sensor_data = SensorData(timestamp, anp39=value)
                elif sensor == "AnP37":
                    sensor_data = SensorData(timestamp, anp37=value)
                elif sensor == "AnP36":
                    sensor_data = SensorData(timestamp, anp36=value)
                elif sensor == "AnP34":
                    sensor_data = SensorData(timestamp, anp34=value)
                elif sensor == "AnP38":
                    sensor_data = SensorData(timestamp, anp38=value)

                # Emit the parsed data
                self.sgn.signalDataParsed.emit(sensor_data)

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
        
        while True:
            try:
                self.signals.signalConnecting.emit(True)
                # Attempt to connect to the Bluetooth device
                p = btle.Peripheral("08:F9:E0:20:3E:0A")
                self.signals.signalConnected.emit(True)  # Emit connection status
                p.setDelegate(MyDelegate(self.signals))
                self.signals.signalConnecting.emit(False)

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
            except btle.BTLEException as e:
                self.signals.signalConnected.emit(False)  # Emit disconnection status
                self.signals.signalConnecting.emit(False)
                print(f"Failed to connect: {e}")
                time.sleep(5)  # Wait before retrying

        self.signals.signalMsg.emit("WorkerBLE end")
        
    def toSendBLE(self, tosend):
        self.bytestosend = bytes(tosend, 'utf-8')
        self.rqsToSend = True

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        mainLayout = QVBoxLayout()
        
        self.buttonStartBLE = QPushButton("Start BLE")
        self.buttonStartBLE.pressed.connect(self.startBLE)
        
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        
        # Connecting text label setup
        self.connectingLabel = QLabel("Trying to connect to Bluetooth...", self)
        self.connectingLabel.setAlignment(Qt.AlignCenter)
        self.connectingLabel.setVisible(False)
        
        # Group Box for Weight Display
        weightGroupBox = QGroupBox("Weight")
        self.weightLabel = QLabel("Weight: N/A")
        weightLayout = QVBoxLayout()
        weightLayout.addWidget(self.weightLabel)
        weightGroupBox.setLayout(weightLayout)

        # Group Box for Analog Values Display
        analogGroupBox = QGroupBox("Analog Values")
        self.analogLabel = QLabel("No Data")
        analogLayout = QVBoxLayout()
        analogLayout.addWidget(self.analogLabel)
        analogGroupBox.setLayout(analogLayout)

        # Group Box for Tare Controls
        tareGroupBox = QGroupBox("Tare")
        tareLayout = QVBoxLayout()

        buttonTare = QPushButton("Tare")
        buttonTare.pressed.connect(self.sendTare)
        
        tareLayout.addWidget(buttonTare)
        tareGroupBox.setLayout(tareLayout)

        # Group Box for Calibrate Controls
        calGroupBox = QGroupBox("Calibrate")
        calLayout = QVBoxLayout()

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

        buttonCalibrateBLE = QPushButton("Calibrate")
        buttonCalibrateBLE.pressed.connect(self.sendCalibrateBLE)

        calLayout.addLayout(sliderLayout)
        calLayout.addWidget(buttonCalibrateBLE)
        calGroupBox.setLayout(calLayout)

        # Adding widgets to the main layout
        mainLayout.addWidget(self.buttonStartBLE)
        mainLayout.addWidget(self.connectingLabel)  # Add connecting text label to the layout
        mainLayout.addWidget(weightGroupBox)  # Add the weight group box here
        mainLayout.addWidget(analogGroupBox)  # Add the analog values group box
        mainLayout.addWidget(self.console)    # Add console below the weight group box
        mainLayout.addWidget(tareGroupBox)
        mainLayout.addWidget(calGroupBox)

        widget = QWidget()
        widget.setLayout(mainLayout)
        
        self.setCentralWidget(widget)
        
        self.show()
        self.threadpool = QThreadPool()
        print("Multithreading with Maximum %d threads" % self.threadpool.maxThreadCount())
    
    def updateSliderLabel(self, value):
        self.sliderLabel.setText(f"Value: {value}")

    def startBLE(self):
        self.workerBLE = WorkerBLE()
        self.workerBLE.signals.signalMsg.connect(self.slotMsg)
        self.workerBLE.signals.signalRes.connect(self.slotRes)
        self.workerBLE.signals.signalConnecting.connect(self.setConnectingLabelVisible)
        self.workerBLE.signals.signalConnected.connect(self.updateBLEButton)
        self.workerBLE.signals.signalDataParsed.connect(self.updateAnalogValues)
        self.threadpool.start(self.workerBLE)
        
    def sendTare(self):
        tareCommand = "Tare"
        self.workerBLE.toSendBLE(tareCommand)

    def sendCalibrateBLE(self):
        calibrateCommand = "Calibrate"
        sliderValue = self.slider.value()
        unit = self.unitToggle.currentText()
        fullCommand = f"{calibrateCommand} {sliderValue} {unit}"
        self.workerBLE.toSendBLE(fullCommand)
        
    def slotMsg(self, msg):
        print(msg)
        
    def slotRes(self, res):
        self.console.appendPlainText(res)
        self.updateWeightDisplay(res)
    
    def updateWeightDisplay(self, message):
        # Extract weight from the message
        match = re.search(r'W:(\d+)', message)
        if match:
            weight = match.group(1)
            unit = self.unitToggle.currentText()  # Get current unit from the combo box
            self.weightLabel.setText(f"Weight: {weight} {unit}")

    def updateAnalogValues(self, data):
        self.console.appendPlainText(str(data))  # Display each sensor data in the console widget

    def setConnectingLabelVisible(self, isVisible):
        self.connectingLabel.setVisible(isVisible)
    
    def updateBLEButton(self, connected):
        if connected:
            self.buttonStartBLE.setText("BLE Connected")
            self.buttonStartBLE.setEnabled(False)
        else:
            self.buttonStartBLE.setText("Start BLE")
            self.buttonStartBLE.setEnabled(True)
        
app = QApplication(sys.argv)
window = MainWindow()
app.exec()

