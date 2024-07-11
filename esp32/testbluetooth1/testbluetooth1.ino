#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <string> // Inclure la librairie standard C++ string

BLEServer *pServer = NULL;
BLECharacteristic *pTxCharacteristic;
bool deviceConnected = false;
bool oldDeviceConnected = false;
uint8_t txValue = 0;

// Voir le site suivant pour générer des UUIDs :
// https://www.uuidgenerator.net/

#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E" // UUID du service UART
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

class MyServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
    }

    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;
    }
};

class MyCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
        // Convertir l'objet String retourné par pCharacteristic->getValue() en const char*
        String value = pCharacteristic->getValue();
        const char* valueCStr = value.c_str();
        
        // Utiliser const char* pour initialiser std::string
        std::string rxValue(valueCStr);

        if (rxValue.length() > 0) {
            Serial.println("*********");
            Serial.print("Received Value: ");
            for (int i = 0; i < rxValue.length(); i++)
                Serial.print(rxValue[i]);

            Serial.println();
            Serial.println("*********");
        }
    }
};

void setup() {
    Serial.begin(115200);

    // Créer l'appareil BLE
    BLEDevice::init("esp32");  // Nommer l'appareil "esp32"

    // Créer le serveur BLE
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());

    // Créer le service BLE
    BLEService *pService = pServer->createService(SERVICE_UUID);

    // Créer une caractéristique BLE
    pTxCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID_TX,
        BLECharacteristic::PROPERTY_NOTIFY
    );

    pTxCharacteristic->addDescriptor(new BLE2902());

    BLECharacteristic *pRxCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID_RX,
        BLECharacteristic::PROPERTY_WRITE
    );

    pRxCharacteristic->setCallbacks(new MyCallbacks());

    // Démarrer le service
    pService->start();

    // Démarrer la publicité
    pServer->getAdvertising()->start();
    Serial.println("Waiting for a client connection to notify...");
}

void loop() {
    if (deviceConnected) {
        pTxCharacteristic->setValue(&txValue, 1);
        pTxCharacteristic->notify();
        txValue++;
        delay(10); // le stack Bluetooth peut se congestionner si trop de paquets sont envoyés
    }

    // déconnexion
    if (!deviceConnected && oldDeviceConnected) {
        delay(500); // donner le temps au stack Bluetooth de se préparer
        pServer->startAdvertising(); // redémarrer la publicité
        Serial.println("start advertising");
        oldDeviceConnected = deviceConnected;
    }
    // connexion
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
    }
}
