# ensemble_api.py  数据层，独立负责与网络气象数据交互
import requests
from datetime import datetime

class EnsembleForecastAPI:
    def __init__(self, lat=31.1433, lon=121.8053):
        self.base_url = "https://ensemble-api.open-meteo.com/v1/ensemble"
        self.lat = lat
        self.lon = lon

    def fetch_raw_ensemble(self, target_date):
        """拉取 GEFS 原始集合成员数据"""
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "daily": "temperature_2m_max",
            "models": "gfs_seamless",
            "timezone": "Asia/Shanghai"
        }
        try:
            resp = requests.get(self.base_url, params=params, timeout=10)
            data = resp.json()
            # 提取目标日期的所有成员温度
            times = data["daily"]["time"]
            if target_date not in times: return []
            idx = times.index(target_date)
            
            members = [v[idx] for k, v in data["daily"].items() if "member" in k and v[idx] is not None]
            return members
        except:
            return []