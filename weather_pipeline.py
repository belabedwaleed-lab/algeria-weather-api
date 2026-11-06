import os
import json
import numpy as np
from ecmwf.opendata import Client
import xarray as xr

def fetch_and_process_aifs():
    print("--- [1/3] جاري الاتصال بسخاورد ECMWF وسحب بيانات AIFS الذكية ---")
    
    # تهيئة العميل لنموذج الذكاء الاصطناعي AIFS
    client = Client(source="ecmwf", model="aifs-single", resol="0p25")
    
    # المعطيات الأساسية المطلوبة (حرارة، ضغط، أمطار، ريح)
    parameters = ["2t", "msl", "tp", "u10", "v10"]
    target_file = "aifs_algeria_raw.grib2"
    
    try:
        # سحب التوقعات للخطوة الزمنية (مثلاً بعد 24 ساعة)
        client.retrieve(
            type="fc",
            step=24,
            param=parameters,
            target=target_file
        )
        print(f"تم تحميل الملف الخام بنجاح: {target_file}")
        
    except Exception as e:
        print(f"خطأ أثناء سحب البيانات من المصدر: {e}")
        return

    print("--- [2/3] جاري تحليل الملف وقص النطاق الجغرافي للجزائر ---")
    
    try:
        # فتح الملف بواسطة xarray ومحرك cfgrib
        dataset = xr.open_dataset(target_file, engine="cfgrib")
        
        # قائمة بأبرز المدن الجزائرية لإستخراج حالتها بدقة
        cities = {
            "Algiers": {"lat": 36.7538, "lon": 3.0588},
            "Oran": {"lat": 35.6971, "lon": -0.6309},
            "Constantine": {"lat": 36.365, "lon": 6.6147},
            "Annaba": {"lat": 36.9, "lon": 7.7667},
            "Tlemcen": {"lat": 34.8783, "lon": -1.315},
            "Biskra": {"lat": 34.85, "lon": 5.728},
            "Ouargla": {"lat": 31.9493, "lon": 5.325},
            "Tamanrasset": {"lat": 22.785, "lon": 5.5228},
            "Bejaia": {"lat": 36.751, "lon": 5.0557},
            "El Milia": {"lat": 36.7558, "lon": 6.2653}
        }
        
        extracted_data = {}
        
        for city_name, coords in cities.items():
            # معالجة خطوط الطول لتتوافق مع نظام 0-360 إذا لزم الأمر
            target_lon = coords["lon"] if coords["lon"] >= 0 else coords["lon"] + 360
            
            # اختيار أقرب نقطة شبكية للمدينة
            point = dataset.sel(latitude=coords["lat"], longitude=target_lon, method="nearest")
            
            # استخراج القيم وتحويلها لوحدات مفهومة
            temp_k = float(point['t2t'].values) if 't2t' in point else (float(point['t2m'].values) if 't2m' in point else 293.15)
            temp_c = round(temp_k - 273.15, 1)
            
            pressure = float(point['msl'].values) / 100 if 'msl' in point else 1013.25
            precipitation = float(point['tp'].values) * 1000 if 'tp' in point else 0.0
            
            u10 = float(point['u10'].values) if 'u10' in point else 0.0
            v10 = float(point['v10'].values) if 'v10' in point else 0.0
            wind_speed = round(np.sqrt(u10**2 + v10**2) * 3.6, 1)
            
            # حساب تقديري لمؤشرات الظواهر (رعود، ثلج، غبار) بناءً على القيم الفيزيائية
            thunder_risk = "LOW"
            if temp_c > 22 and precipitation > 1.5:
                thunder_risk = "MODERATE"
            if temp_c > 28 and precipitation > 5:
                thunder_risk = "HIGH"
                
            snow_mm = precipitation if temp_c <= 0 else 0.0
            dust_risk = "HIGH" if wind_speed > 35 and precipitation == 0 and coords["lat"] < 32 else "LOW"

            extracted_data[city_name] = {
                "temperature_celsius": temp_c,
                "pressure_hpa": round(pressure, 1),
                "precipitation_mm": round(precipitation, 1),
                "snow_mm": round(snow_mm, 1),
                "wind_speed_kmh": wind_speed,
                "thunder_risk": thunder_risk,
                "dust_risk": dust_risk,
                "condition": "Rain" if precipitation > 0 else ("Clear" if temp_c > 20 else "Clouds")
            }

        # حفظ النتائج في ملف JSON نظيف
        output_json = "weather_algeria.json"
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=4)
            
        print(جاري توليد ملف الـ JSON بنجاح: {output_json})

    except Exception as e:
        print(f"حدث خطأ أثناء معالجة بيانات الـ GRIB: {e}")
    
    finally:
        # تنظيف الملفات المؤقتة لتوفير المساحة
        if os.path.exists(target_file):
            os.remove(target_file)

if __name__ == "__main__":
    fetch_and_process_aifs()

