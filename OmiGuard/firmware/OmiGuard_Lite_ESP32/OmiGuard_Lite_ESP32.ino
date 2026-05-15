#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <time.h>

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <DS3231.h>
#include "DHT.h"
#include <WinsenZE03.h>
#include <SD_ZH03B.h>

#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define FIREBASE_API_KEY "YOUR_FIREBASE_WEB_API_KEY"
#define FIREBASE_DATABASE_URL "https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com/"
#define FIREBASE_USER_EMAIL "device-user@example.com"
#define FIREBASE_USER_PASSWORD "YOUR_FIREBASE_AUTH_PASSWORD"
#endif

// =============================
// DEVICE CONFIG
// =============================
#define DEVICE_ID "node_01"

// 5000 = 5 seconds, 60000 = 1 minute
const unsigned long SEND_INTERVAL_MS = 5000;

// Nigeria time = UTC+1
const long GMT_OFFSET_SEC = 3600;
const int DAYLIGHT_OFFSET_SEC = 0;

// =============================
// PIN CONFIG
// =============================
#define DHTTYPE DHT22
#define DHTPIN 45

#define GAS_TX_PIN 39
#define GAS_RX_PIN 40

#define ZH_RX_PIN 6
#define ZH_TX_PIN 7

#define LED_PIN 38
#define BUZZER_PIN 41

#define I2C_SDA 21
#define I2C_SCL 47

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 128

// =============================
// OBJECTS
// =============================
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

Adafruit_SH1107 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

DHT dht(DHTPIN, DHTTYPE);

HardwareSerial GasSerial(2);
HardwareSerial PMSerial(1);

WinsenZE03 so2Sensor;
WinsenZE03 no2Sensor;
WinsenZE03 coSensor;

SD_ZH03B ZH03B(PMSerial, SD_ZH03B::SENSOR_ZH03B);

DS3231 rtc;
RTCDateTime dt;

unsigned long lastSendTime = 0;

// =============================
// SENSOR VALUES
// =============================
float temperature = 0;
float humidity = 0;
float co = 0;
float so2 = 0;
float no2 = 0;

int pm1_0 = 0;
int pm2_5 = 0;
int pm10 = 0;

// =============================
// LED + BUZZER FEEDBACK
// Beep only on successful WiFi connection or successful Firebase upload.
// =============================
void successBeep(int times = 1) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);

    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    delay(120);
  }
}

// =============================
// WIFI SCANNER
// =============================
void scanWiFiNetworks() {
  Serial.println();
  Serial.println("Scanning WiFi networks...");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect(true);
  delay(1000);

  int n = WiFi.scanNetworks();

  if (n == 0) {
    Serial.println("No WiFi networks found.");
  } else {
    Serial.print(n);
    Serial.println(" networks found:");

    for (int i = 0; i < n; i++) {
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(WiFi.SSID(i));
      Serial.print(" | RSSI: ");
      Serial.print(WiFi.RSSI(i));
      Serial.print(" | Encryption: ");
      Serial.println(WiFi.encryptionType(i));
      delay(10);
    }
  }

  Serial.println("Scan complete.");
}

// =============================
// WIFI CONNECT
// =============================
bool connectWiFi() {
  Serial.println();
  Serial.println("Starting WiFi connection...");

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);

  WiFi.disconnect(true);
  delay(1000);

  Serial.print("Connecting to SSID: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retry = 0;

  while (WiFi.status() != WL_CONNECTED && retry < 40) {
    delay(500);
    Serial.print(".");
    retry++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi connected successfully");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal Strength RSSI: ");
    Serial.println(WiFi.RSSI());
    successBeep(2);
    return true;
  }

  Serial.println("WiFi connection failed");
  Serial.print("WiFi Status Code: ");
  Serial.println(WiFi.status());
  Serial.println("Check hotspot: 2.4GHz, WPA2, correct password, hotspot not hidden.");
  return false;
}

// =============================
// FIREBASE INIT
// =============================
void initFirebase() {
  config.api_key = FIREBASE_API_KEY;
  config.database_url = FIREBASE_DATABASE_URL;

  auth.user.email = FIREBASE_USER_EMAIL;
  auth.user.password = FIREBASE_USER_PASSWORD;

  config.token_status_callback = tokenStatusCallback;

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  Serial.println("Firebase initialized");
}

// =============================
// RTC TIME SYNC
// =============================
bool syncRTCFromInternet() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Cannot sync time: WiFi not connected");
    return false;
  }

  Serial.println("Syncing RTC from internet time...");

  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, "pool.ntp.org", "time.google.com");

  struct tm timeinfo;

  for (int i = 0; i < 15; i++) {
    if (getLocalTime(&timeinfo, 1000)) {
      rtc.setDateTime(
        timeinfo.tm_year + 1900,
        timeinfo.tm_mon + 1,
        timeinfo.tm_mday,
        timeinfo.tm_hour,
        timeinfo.tm_min,
        timeinfo.tm_sec
      );

      Serial.println("RTC time synced successfully");
      return true;
    }

    Serial.print(".");
  }

  Serial.println();
  Serial.println("Failed to sync internet time. Keeping existing RTC time.");
  return false;
}

// =============================
// TIMESTAMP
// =============================
String getTimestamp() {
  dt = rtc.getDateTime();

  char buffer[25];

  sprintf(
    buffer,
    "%04d-%02d-%02dT%02d:%02d:%02d",
    dt.year,
    dt.month,
    dt.day,
    dt.hour,
    dt.minute,
    dt.second
  );

  return String(buffer);
}

// =============================
// READ DHT22
// =============================
void readDHTSensor() {
  humidity = dht.readHumidity();
  temperature = dht.readTemperature();

  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("Failed to read DHT22");
    humidity = 0;
    temperature = 0;
  }
}

// =============================
// READ GAS SENSORS
// =============================
void readGasSensors() {
  so2 = so2Sensor.readManual();
  no2 = no2Sensor.readManual();
  co = coSensor.readManual();

  if (so2 < 0) so2 = 0;
  if (no2 < 0) no2 = 0;
  if (co < 0) co = 0;

  Serial.print("CO: ");
  Serial.println(co);

  Serial.print("SO2: ");
  Serial.println(so2);

  Serial.print("NO2: ");
  Serial.println(no2);
}

// =============================
// READ PM SENSOR
// =============================
void readPMSensor() {
  if (ZH03B.readData()) {
    pm1_0 = ZH03B.getPM1_0();
    pm2_5 = ZH03B.getPM2_5();
    pm10 = ZH03B.getPM10_0();

    Serial.print("PM1.0: ");
    Serial.println(pm1_0);

    Serial.print("PM2.5: ");
    Serial.println(pm2_5);

    Serial.print("PM10: ");
    Serial.println(pm10);
  } else {
    Serial.println("Failed to read PM sensor");
  }
}

// =============================
// OLED DISPLAY
// =============================
void updateDisplay() {
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.print("OmiGuard Lite");

  display.setCursor(0, 14);
  display.print("CO: ");
  display.print(co);
  display.print(" ppm");

  display.setCursor(0, 27);
  display.print("SO2: ");
  display.print(so2);
  display.print(" ppm");

  display.setCursor(0, 40);
  display.print("NO2: ");
  display.print(no2);
  display.print(" ppm");

  display.setCursor(0, 53);
  display.print("PM1.0: ");
  display.print(pm1_0);

  display.setCursor(0, 66);
  display.print("PM2.5: ");
  display.print(pm2_5);

  display.setCursor(0, 79);
  display.print("PM10: ");
  display.print(pm10);

  display.setCursor(0, 92);
  display.print("T: ");
  display.print(temperature);
  display.print(" C");

  display.setCursor(0, 105);
  display.print("H: ");
  display.print(humidity);
  display.print(" %");

  display.setCursor(0, 118);
  display.print(getTimestamp());

  display.display();
}

// =============================
// SEND TO FIREBASE
// =============================
void sendToFirebase() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");

    if (!connectWiFi()) {
      Serial.println("Send cancelled: WiFi still disconnected");
      return;
    }
  }

  if (!Firebase.ready()) {
    Serial.println("Firebase not ready");
    return;
  }

  FirebaseJson json;

  String timestamp = getTimestamp();

  json.set("device_id", DEVICE_ID);
  json.set("timestamp", timestamp);

  json.set("co", co);
  json.set("so2", so2);
  json.set("no2", no2);

  json.set("pm1_0", pm1_0);
  json.set("pm2_5", pm2_5);
  json.set("pm10", pm10);

  json.set("temperature", temperature);
  json.set("humidity", humidity);

  String latestPath = "/sensor_data/" + String(DEVICE_ID) + "/latest";
  String historyPath = "/sensor_data/" + String(DEVICE_ID) + "/readings";

  bool latestOk = false;
  bool historyOk = false;

  Serial.println();
  Serial.println("Sending data to Firebase...");

  if (Firebase.RTDB.setJSON(&fbdo, latestPath.c_str(), &json)) {
    Serial.println("Latest data updated successfully");
    latestOk = true;
  } else {
    Serial.print("Firebase latest error: ");
    Serial.println(fbdo.errorReason());
  }

  if (Firebase.RTDB.pushJSON(&fbdo, historyPath.c_str(), &json)) {
    Serial.println("Historical data pushed successfully");
    historyOk = true;
  } else {
    Serial.print("Firebase history error: ");
    Serial.println(fbdo.errorReason());
  }

  if (latestOk && historyOk) {
    successBeep(1);
  }
}

// =============================
// SETUP
// =============================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("Booting OmiGuard Lite ESP32-S3...");

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Wire.begin(I2C_SDA, I2C_SCL);

  dht.begin();

  rtc.begin();

  // Do not use rtc.setDateTime(__DATE__, __TIME__) here.
  // That resets the RTC to compile time on every boot.
  // The RTC is synced from internet time after WiFi connects.

  GasSerial.begin(9600, SERIAL_8N1, GAS_RX_PIN, GAS_TX_PIN);

  so2Sensor.begin(&GasSerial, SO2);
  no2Sensor.begin(&GasSerial, NO2);
  coSensor.begin(&GasSerial, CO);

  so2Sensor.setAs(QA);
  no2Sensor.setAs(QA);
  coSensor.setAs(QA);

  PMSerial.begin(9600, SERIAL_8N1, ZH_RX_PIN, ZH_TX_PIN);
  ZH03B.setMode(SD_ZH03B::IU_MODE);

  if (!display.begin(0x3C, true)) {
    Serial.println("OLED failed");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SH110X_WHITE);
    display.setCursor(0, 0);
    display.println("OmiGuard Lite");
    display.println("Starting...");
    display.display();
  }

  scanWiFiNetworks();

  bool wifiConnected = connectWiFi();

  if (wifiConnected) {
    syncRTCFromInternet();
    initFirebase();
  } else {
    Serial.println("Firebase not initialized because WiFi failed.");
  }

  Serial.println("System ready");
}

// =============================
// LOOP
// =============================
void loop() {
  readDHTSensor();
  readGasSensors();
  readPMSensor();

  updateDisplay();

  unsigned long currentMillis = millis();

  if (currentMillis - lastSendTime >= SEND_INTERVAL_MS || lastSendTime == 0) {
    lastSendTime = currentMillis;
    sendToFirebase();
  }

  delay(2000);
}
