import sys
import re
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import (
    QApplication, QLabel, QMainWindow, QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QGroupBox, QWidget, QSlider, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from bluepy import btle
import time
import datetime

class SensorData:
    def __init__(self, timestamp=None, anp35=None, anp39=None, anp37=None, anp36=None, anp34=None, anp38=None):
        self.timestamp = timestamp
        self.anp35 = anp35
        self.anp39 = anp39
        self.anp37 = anp37
        self.anp36 = anp36
        self.anp34 = anp34
        self.anp38 = anp38

    def update(self, timestamp, sensor, value):
        self.timestamp = timestamp  # Update timestamp with each message
        if sensor == "AnP35":
            self.anp35 = value
        elif sensor == "AnP39":
            self.anp39 = value
        elif sensor == "AnP37":
            self.anp37 = value
        elif sensor == "AnP36":
            self.anp36 = value
        elif sensor == "AnP34":
            self.anp34 = value
        elif sensor == "AnP38":
            self.anp38 = value

    def is_complete(self):
        return all(sensor is not None for sensor in [self.anp35, self.anp39, self.anp37, self.anp36, self.anp34, self.anp38])

class WorkerSignals(QObject):
    signalMsg = pyqtSignal(str)
    signalRes = pyqtSignal(str)
    signalConnecting = pyqtSignal(bool)
    signalConnected = pyqtSignal(bool)
    signalDataParsed = pyqtSignal(SensorData)

class MyDelegate(btle.DefaultDelegate):
    def __init__(self, sgn, sensor_data):
        btle.DefaultDelegate.__init__(self)
        self.sgn = sgn
        self.sensor_data = sensor_data

    def handleNotification(self, cHandle, data):
        try:
            dataDecoded = data.decode()
            self.sgn.signalRes.emit(dataDecoded)
            print("Data: ", dataDecoded)

            # Parse the data values
            match = re.search(r'(\d+:\d+\.\d+),AnP(\d+):(\d+)', dataDecoded)
            if match:
                timestamp = match.group(1)
                sensor = f"AnP{match.group(2)}"
                value = int(match.group(3))

                self.sensor_data.update(timestamp, sensor, value)

                # Emit the sensor data only if all fields are populated
                if self.sensor_data.is_complete():
                    self.sgn.signalDataParsed.emit(self.sensor_data)
                    # Reset the sensor data after emitting so it can be re-populated with new values
                    self.sensor_data = SensorData()

        except UnicodeError:
            print("UnicodeError: ", data)

class WorkerBLE(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self.rqsToSend = False
        self.bytestosend = b''
        self.sensor_data = SensorData()  # Maintain the sensor data state

    @pyqtSlot()
    def run(self):
        self.signals.signalMsg.emit("WorkerBLE start")

        while True:
            try:
                self.signals.signalConnecting.emit(True)
                # Attempt to connect to the Bluetooth device
                p = btle.Peripheral("08:F9:E0:20:3E:0A")
                self.signals.signalConnected.emit(True)  # Emit connection status
                p.setDelegate(MyDelegate(self.signals, self.sensor_data))
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

        # Group Box for Analog Values Table
        analogGroupBox = QGroupBox("Analog Values")

        self.timestampLabel = QLabel("Timestamp: N/A")
        self.analogTable = QTableWidget(6, 1)  # 6 rows, 1 column
        # Remove header labels
        self.analogTable.horizontalHeader().setVisible(False)
        self.analogTable.verticalHeader().setVisible(False)
        self.analogTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.analogTable.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        analogLayout = QVBoxLayout()
        analogLayout.addWidget(self.timestampLabel)
        analogLayout.addWidget(self.analogTable)
        analogGroupBox.setLayout(analogLayout)

        # Group Box for Tare Controls
        tareGroupBox = QGroupBox("Tare")
        tareLayout = QVBoxLayout()

        buttonTare = QPushButton("Tare")
        buttonTare.pressed.connect(self.sendTare)

        tareLayout.addWidget(buttonTare)
        tareGroupBox.setLayout(tareLayout)

        # Group Box for Calibrate Controls
        calGroupBox = QGroupBox("Calibrate Load Cells")
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

        # Group Box for BPM Controls
        bpmGroupBox = QGroupBox("BPM Controls")

        self.bpmLabel = QLabel("BPM: 0")
        self.bpmSlider = QSlider(Qt.Horizontal)
        self.bpmSlider.setRange(40, 200)
        self.bpmSlider.setValue(60)

        self.tapButton = QPushButton("Tap")
        self.tapButton.pressed.connect(self.tapBPM)

        self.bpmSlider.valueChanged.connect(self.updateBPM)

        bpmLayout = QVBoxLayout()
        bpmLayout.addWidget(self.bpmLabel)

        bpmControlsLayout = QHBoxLayout()
        bpmControlsLayout.addWidget(self.tapButton)
        bpmControlsLayout.addWidget(self.bpmSlider)

        bpmLayout.addLayout(bpmControlsLayout)
        bpmGroupBox.setLayout(bpmLayout)

        # Group Box for Calibrate FSR
        fsrGroupBox = QGroupBox("Calibrate FSR")

        self.fsrSlider = QSlider(Qt.Horizontal)
        self.fsrSlider.setRange(0, 4095)
        self.fsrSlider.setValue(0)
        self.fsrSlider.valueChanged.connect(self.updateFSR)

        self.fsrLabel = QLabel("FSR Value: 0")

        fsrLayout = QVBoxLayout()
        fsrLayout.addWidget(self.fsrSlider)
        fsrLayout.addWidget(self.fsrLabel)
        fsrGroupBox.setLayout(fsrLayout)

        # Adding widgets to the main layout
        mainLayout.addWidget(self.buttonStartBLE)
        mainLayout.addWidget(bpmGroupBox)          # Add the BPM Controls group box
        mainLayout.addWidget(self.connectingLabel) # Add connecting text label to the layout
        mainLayout.addWidget(weightGroupBox)       # Add the weight group box here
        mainLayout.addWidget(analogGroupBox)       # Add the analog values table group box
        mainLayout.addWidget(self.console)         # Add console below the weight group box
        mainLayout.addWidget(tareGroupBox)
        mainLayout.addWidget(calGroupBox)
        mainLayout.addWidget(fsrGroupBox)          # Add the Calibrate FSR group box

        widget = QWidget()
        widget.setLayout(mainLayout)

        self.setCentralWidget(widget)

        self.showFullScreen()
        self.threadpool = QThreadPool()
        print("Multithreading with Maximum %d threads" % self.threadpool.maxThreadCount())

        self.tap_times = []
        self.fsr_value = 0

        # Dictionary to keep track of the last exceed timestamps for each sensor
        self.sensor_exceed_timestamps = { "AnP35": [], "AnP39": [], "AnP37": [], "AnP36": [], "AnP34": [], "AnP38": [] }

    def updateSliderLabel(self, value):
        self.sliderLabel.setText(f"Value: {value}")

    def updateBPM(self, value):
        self.bpmLabel.setText(f"BPM: {value}")

    def tapBPM(self):
        now = datetime.datetime.now()
        self.tap_times.append(now)

        # Keep only the last 5 tap times to calculate the BPM:
        self.tap_times = self.tap_times[-5:]

        if len(self.tap_times) >= 2:
            intervals = [(self.tap_times[i] - self.tap_times[i-1]).total_seconds() for i in range(1, len(self.tap_times))]
            avg_interval = sum(intervals) / len(intervals)
            bpm = int(60 / avg_interval)
            self.bpmSlider.setValue(bpm)
            self.updateBPM(bpm)

    def updateFSR(self, value):
        self.fsrLabel.setText(f"FSR Value: {value}")
        self.fsr_value = value

    def startBLE(self):
        # Disable the button after it's clicked
        self.buttonStartBLE.setEnabled(False)
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
        # Update the timestamp label
        self.timestampLabel.setText(f"Timestamp: {data.timestamp}")

        # Dictionary to map sensor indexes to their keys and table cell coordinates
        sensor_map = {0: ("AnP35", 0), 1: ("AnP34", 1), 2: ("AnP39", 2), 3: ("AnP38", 3), 4: ("AnP37", 4), 5: ("AnP36", 5)}

        # Clear the table first
        self.analogTable.clearContents()

        # Loop over the sensor values and update the table
        for i, (sensor_key, row) in enumerate(sensor_map.values()):
            sensor_value = getattr(data, sensor_key.lower())
            item = QTableWidgetItem(f"{sensor_key}: {sensor_value}")

            # Check if the sensor value exceeds the fsr_value
            if sensor_value > self.fsr_value:
                item.setBackground(QBrush(QColor(0, 255, 0)))  # Set background to green
                self.registerExceed(sensor_key)

            self.analogTable.setItem(row, 0, item)

    def registerExceed(self, sensor_key):
        now = datetime.datetime.now()
        timestamps = self.sensor_exceed_timestamps[sensor_key]
        timestamps.append(now)

        # Keep only the last 5 timestamps to calculate the rhythm
        self.sensor_exceed_timestamps[sensor_key] = timestamps[-5:]

        if len(timestamps) >= 2:
            intervals = [(timestamps[i] - timestamps[i-1]).total_seconds() for i in range(1, len(timestamps))]
            avg_interval = sum(intervals) / len(intervals)
            rhythm = 1 / avg_interval  # Adjust this calculation based on desired output
            print(f"Rhythm for {sensor_key}: {rhythm} Hz")

    def setConnectingLabelVisible(self, isVisible):
        self.connectingLabel.setVisible(isVisible)

    def updateBLEButton(self, connected):
        if connected:
            self.buttonStartBLE.setText("BLE Connected")
            self.buttonStartBLE.setEnabled(False)
        else:
            self.buttonStartBLE.setText("Start BLE")
            self.buttonStartBLE.setEnabled(False)  # Keep the button disabled if not connected

app = QApplication(sys.argv)
window = MainWindow()
app.exec()

