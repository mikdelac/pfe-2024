#include "Adafruit_HX711.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <esp_system.h>

// See the following for generating UUIDs:
// https://www.uuidgenerator.net/

#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E" // UART service UUID
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

// Define the pins for the HX711 communication
const uint8_t DATA_PIN1 = 33;  // Can use any pins!
const uint8_t CLOCK_PIN1 = 25; // Can use any pins!
const uint8_t DATA_PIN2 = 26;  // Can use any pins!
const uint8_t CLOCK_PIN2 = 27; // Can use any pins!

uint8_t needTaring = 1;

BLEServer *pServer = NULL;
BLECharacteristic *pTxCharacteristic;
bool deviceConnected = false;
bool oldDeviceConnected = false;

Adafruit_HX711 hx711_1(DATA_PIN1, CLOCK_PIN1);
Adafruit_HX711 hx711_2(DATA_PIN2, CLOCK_PIN2);

void tareSensors() {
  Serial.println("Tareing....");
  for (uint8_t t = 0; t < 3; t++) {
    hx711_1.tareA(hx711_1.readChannelRaw(CHAN_A_GAIN_128));
    hx711_1.tareA(hx711_1.readChannelRaw(CHAN_A_GAIN_128));
    hx711_1.tareB(hx711_1.readChannelRaw(CHAN_B_GAIN_32));
    hx711_1.tareB(hx711_1.readChannelRaw(CHAN_B_GAIN_32));
    hx711_2.tareA(hx711_2.readChannelRaw(CHAN_A_GAIN_128));
    hx711_2.tareA(hx711_2.readChannelRaw(CHAN_A_GAIN_128));
    hx711_2.tareB(hx711_2.readChannelRaw(CHAN_B_GAIN_32));
    hx711_2.tareB(hx711_2.readChannelRaw(CHAN_B_GAIN_32));
  }
}


class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
    }
};

class MyCallbacks : public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic *pCharacteristic) {
        // Convert the String object returned by pCharacteristic->getValue() into a const char*
        String value = pCharacteristic->getValue();
        const char* valueCStr = value.c_str();
        
        // Use const char* to initialize std::string
        std::string rxValue(valueCStr);

        if (rxValue.length() > 0) {
            Serial.println("*********");
            Serial.print("Received Value: ");
            for (int i = 0; i < rxValue.length(); i++)
                Serial.print(rxValue[i]);

            Serial.println();
            Serial.println("*********");

            if (rxValue == "Tare") {
                Serial.println("Executing Tare command...");
                
                // Perform tare operation
                needTaring = 1;
                // Measure the weight after tare
                // TODO
                // Send the measured weights back via BLE
                /*
                char weightStr[100];
                //snprintf(weightStr, sizeof(weightStr), "Weight 1: %.2f, Weight 2: %.2f", weight1, weight2);
                if (deviceConnected) {
                    //pTxCharacteristic->setValue(weightStr);
                    //pTxCharacteristic->notify();
                }*/
            } else {
                Serial.print("Unknown command received: ");
                Serial.println(rxValue.c_str());
            }
        }
    }
};

void setup() {
  Serial.begin(115200);
  pinMode(36, INPUT);
  pinMode(37, INPUT);
  pinMode(38, INPUT);
  pinMode(39, INPUT);
  pinMode(34, INPUT);
  pinMode(35, INPUT);

  // Create the BLE Device
  BLEDevice::init("esp32");  // Set the device name to "esp32"

  // Create the BLE Server
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  // Create the BLE Service
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Create a BLE Characteristic
  pTxCharacteristic = pService->createCharacteristic(
     CHARACTERISTIC_UUID_TX,
     BLECharacteristic::PROPERTY_NOTIFY
  );
                  
  pTxCharacteristic->addDescriptor(new BLE2902());

  BLECharacteristic * pRxCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID_RX,
    BLECharacteristic::PROPERTY_WRITE
  );

  pRxCharacteristic->setCallbacks(new MyCallbacks());

  // Start the service
  pService->start();

  // Start advertising
  pServer->getAdvertising()->start();
  Serial.println("Waiting a client connection to notify...");

  // wait for serial port to connect. Needed for native USB port only
  while (!Serial) {
    delay(10);
  }

  Serial.println("Adafruit HX711 Test!");

  // Initialize the HX711
  Serial.print("Initialising HX711_1 on pins ");
  Serial.print(DATA_PIN1);
  Serial.print(", ");
  Serial.println(CLOCK_PIN1);
  hx711_1.begin();
  Serial.print("Initialising HX711_2 on pins ");
  Serial.print(DATA_PIN2);
  Serial.print(", ");
  Serial.println(CLOCK_PIN2);
  hx711_2.begin();

}

void loop() {

  if (needTaring == 1) {
    // tare
    tareSensors();
    needTaring = 0;
  }
  // Read weight values
  int32_t weightA128_1 = hx711_1.readChannelBlocking(CHAN_A_GAIN_128);
  int32_t weightB32_1 = hx711_1.readChannelBlocking(CHAN_B_GAIN_32);
  int32_t weightA128_2 = hx711_2.readChannelBlocking(CHAN_A_GAIN_128);
  int32_t weightB32_2 = hx711_2.readChannelBlocking(CHAN_B_GAIN_32);

  // Read analog values
  int analogValP35 = analogRead(35);
  int analogValP39 = analogRead(39);
  int analogValP37 = analogRead(37);
  int analogValP36 = analogRead(36);
  int analogValP34 = analogRead(34);
  int analogValP38 = analogRead(38);

  // Get the current time in milliseconds
  unsigned long currentMillis = millis();
  unsigned long currentSeconds = currentMillis / 1000;
  unsigned long currentMilliseconds = currentMillis % 1000;

  // Format the time as HH:MM:SS.mmm
  char timeStr[20];
  snprintf(timeStr, sizeof(timeStr), "%02lu:%02lu:%02lu.%03lu", 
           (currentSeconds / 3600) % 24, 
           (currentSeconds / 60) % 60, 
           currentSeconds % 60, 
           currentMilliseconds);

  // Format the data into a string
  char dataStr[300];
  snprintf(dataStr, sizeof(dataStr), "%s, A1:%ld,B1:%ld,A2:%ld,B2:%ld,AnP35:%d,AnP39:%d,AnP37:%d,AnP36:%d,AnP34:%d,AnP38:%d",
           timeStr, weightA128_1, weightB32_1, weightA128_2, weightB32_2, analogValP35, analogValP39, analogValP37, analogValP36, analogValP34, analogValP38);

  Serial.println(dataStr);

  if (deviceConnected) {
    // Send the data via Bluetooth
    pTxCharacteristic->setValue(dataStr);
    pTxCharacteristic->notify();
    //delay(50); // Delay to avoid congestion
  }

  // disconnecting
  if (!deviceConnected && oldDeviceConnected) {
    delay(500); // give the bluetooth stack the chance to get things ready
    pServer->startAdvertising(); // restart advertising
    Serial.println("start advertising");
    oldDeviceConnected = deviceConnected;
  }
  // connecting
  if (deviceConnected && !oldDeviceConnected) {
    // do stuff here on connecting
    oldDeviceConnected = deviceConnected;
  }
}
