def fetch_latest_sensor_record():
    return {
        'co_ppm': 18.4,
        'so2_ppm': 6.2,
        'temperature_c': 33.1,
        'humidity_pct': 58.0,
        'device_health': 1,
        'hour': 14,
        'near_school': 1,
        'near_clinic': 0
    }

if __name__ == '__main__':
    print(fetch_latest_sensor_record())
