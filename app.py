import streamlit as st
import requests
import json
from streamlit_autorefresh import st_autorefresh

LAT = 31.1443
LON = 121.8083
BANKROLL = 10000

# -----------------------
# 自动刷新（30秒）
# -----------------------
st_autorefresh(interval=30000, key="refresh")

st.set_page_config(page_title="天气交易系统", layout="centered")

# -----------------------
# 缓存（关键）
# -----------------------
@st.cache_data(ttl=30)
def get_temp():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true"
        res = requests.get(url, timeout=5).json()
        return res["current_weather"]["temperature"]
    except:
        return None

@st.cache_data(ttl=60)
def get_market():
    try:
        url = "https://gamma-api.polymarket.com/markets"
        res = requests.get(url, timeout=5).json()

        probs = {"14":0.33,"15":0.34,"16":0.33}

        for m in res:
            q = m.get("question","")

            if "Shanghai" in q and "temperature" in q:
                outcomes = m.get("outcomes", [])

                if not outcomes:
                    continue

                try:
                    price = float(outcomes[0].get("price",0))
                except:
                    continue

                if "14" in q:
                    probs["14"] = price
                elif "15" in q:
                    probs["15"] = price
                elif "16" in q:
                    probs["16"] = price

        return probs
    except:
        return {"14":0.33,"15":0.34,"16":0.33}

# -----------------------
# 参数读取
# -----------------------
def load_params():
    try:
        with open("params.json","r") as f:
            return json.load(f)
    except:
        return {"speed":1.0,"hour":10,"updated":"N/A"}

# -----------------------
# 模型
# -----------------------
def model_probs(temp):
    if temp is None:
        return {"14":0.33,"15":0.34,"16":0.33}
    if temp <= 13:
        return {"14":0.6,"15":0.3,"16":0.1}
    elif temp == 14:
        return {"14":0.4,"15":0.4,"16":0.2}
    elif temp == 15:
        return {"14":0.1,"15":0.6,"16":0.3}
    else:
        return {"14":0.05,"15":0.3,"16":0.65}

# -----------------------
# Kelly
# -----------------------
def kelly(p, m):
    if m <= 0:
        return 0
    b = (1/m) - 1
    q = 1 - p
    f = (b*p - q) / b
    return max(f*0.3, 0)

# -----------------------
# UI
# -----------------------
st.title("🌡️ 自动天气交易系统 Pro")

params = load_params()
temp = get_temp()
market = get_market()
model = model_probs(temp)

st.subheader("📅 今日策略")
st.json(params)

st.subheader("🌡️ 当前温度")
if temp:
    st.metric("温度", f"{temp}°C")
else:
    st.warning("天气数据获取失败")

st.subheader("📡 市场（Polymarket）")
for k in market:
    st.write(f"{k}°C → {market[k]*100:.1f}%")

st.subheader("🧠 模型概率")
for k in model:
    st.write(f"{k}°C → {model[k]*100:.1f}%")

st.subheader("💰 交易建议")

best = None
best_edge = -999

for k in model:
    edge = model[k] - market[k]
    bet = min(kelly(model[k], market[k]) * BANKROLL, BANKROLL * 0.2)

    if edge > best_edge:
        best_edge = edge
        best = k

    st.write(f"{k}°C → Edge {edge*100:.1f}% | 建议 ${bet:.0f}")

if best_edge > 0.15:
    st.success(f"🔥 强信号：{best}°C")
elif best_edge > 0.05:
    st.info(f"👉 中等信号：{best}°C")
else:
    st.warning("⚠️ 无交易机会")

st.caption("自动刷新：30秒")