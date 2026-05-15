# OmiGuard Lite ESP32-S3 Firmware

Arduino firmware for the OmiGuard Lite ESP32-S3 environmental monitoring node.

The sketch reads:

- DHT22 temperature and humidity
- Winsen ZE03 gas sensors for CO, SO2, and NO2
- ZH03B particulate matter sensor for PM1.0, PM2.5, and PM10
- DS3231 RTC timestamp
- SH1107 OLED display output

It publishes the latest and historical readings to Firebase Realtime Database.

## Required Hardware

- ESP32-S3 board
- DHT22 sensor
- Winsen ZE03 gas sensors
- ZH03B particulate matter sensor
- DS3231 RTC module
- SH1107 128x128 OLED display
- LED and buzzer for status feedback

## Required Arduino Libraries

Install these from Arduino Library Manager where available:

- Firebase ESP Client by Mobizt
- Adafruit GFX Library
- Adafruit SH110X
- DHT sensor library
- DS3231
- WinsenZE03
- SD_ZH03B

The ESP32 board package is also required.

## Setup

1. Copy `secrets.example.h` to `secrets.h`.
2. Add your WiFi and Firebase values to `secrets.h`.
3. Keep `secrets.h` private. It is ignored by git.
4. Open `OmiGuard_Lite_ESP32.ino` in Arduino IDE.
5. Select your ESP32-S3 board and upload.

## Firebase Path

The firmware writes to:

```text
/sensor_data/<DEVICE_ID>/latest
/sensor_data/<DEVICE_ID>/readings
```

Change `DEVICE_ID` in the sketch when deploying multiple devices.

## Security

This public firmware folder does not include real WiFi credentials, Firebase API keys, database URLs, emails, or passwords.
