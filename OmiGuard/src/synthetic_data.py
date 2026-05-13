import pandas as pd
import numpy as np
from pathlib import Path

np.random.seed(42)

def compute_risk(co_ppm, so2_ppm, temperature_c, humidity_pct, near_school, near_clinic):
    score = 0
    if co_ppm > 35: score += 3
    elif co_ppm > 20: score += 2
    elif co_ppm > 10: score += 1
    if so2_ppm > 20: score += 3
    elif so2_ppm > 10: score += 2
    elif so2_ppm > 5: score += 1
    if temperature_c > 38: score += 1
    if humidity_pct < 25: score += 1
    if near_school: score += 1
    if near_clinic: score += 1
    if score >= 7: return 'emergency'
    elif score >= 4: return 'high'
    elif score >= 2: return 'medium'
    return 'low'

def generate_data(n=5000):
    rows = []
    for _ in range(n):
        co_ppm = np.clip(np.random.gamma(shape=2.0, scale=7.0), 0, 80)
        so2_ppm = np.clip(np.random.gamma(shape=2.0, scale=4.0), 0, 50)
        temperature_c = np.random.uniform(20, 45)
        humidity_pct = np.random.uniform(20, 95)
        device_health = np.random.choice([0, 1], p=[0.08, 0.92])
        hour = np.random.randint(0, 24)
        near_school = np.random.choice([0, 1], p=[0.7, 0.3])
        near_clinic = np.random.choice([0, 1], p=[0.8, 0.2])
        risk_class = compute_risk(co_ppm, so2_ppm, temperature_c, humidity_pct, near_school, near_clinic)
        rows.append({
            'co_ppm': round(float(co_ppm), 2),
            'so2_ppm': round(float(so2_ppm), 2),
            'temperature_c': round(float(temperature_c), 2),
            'humidity_pct': round(float(humidity_pct), 2),
            'device_health': int(device_health),
            'hour': int(hour),
            'near_school': int(near_school),
            'near_clinic': int(near_clinic),
            'risk_class': risk_class
        })
    df = pd.DataFrame(rows)
    Path('data').mkdir(exist_ok=True)
    df.to_csv('data/synthetic_gas_data.csv', index=False)
    print('Dataset generated')

if __name__ == '__main__':
    generate_data()
