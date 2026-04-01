import streamlit.components.v1 as components
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import re
import math
from datetime import datetime, timedelta, timezone # 增加 timezone 导入
from streamlit_autorefresh import st_autorefresh

# =========================================================
# 1. 页面基础配置 (必须作为第一个 Streamlit 命令执行)
# =========================================================
st.set_page_config(page_title="METAR监控系统", layout="wide")

# =========================================================
# 2. 功能函数定义
# =========================================================
def now_local():
# """获取北京时间 (UTC+8)"""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)

# =========================================================
# 3. 自动刷新与 CSS 注入 (极致紧凑布局)
# =========================================================
st_autorefresh(interval=30000, key="refresh")
# 标题自定义
# 1. 注入全局 CSS，彻底消除顶部间隙
st.markdown("""
    <style>
        /* 1. 顶部 Header 彻底归零 */
        header[data-testid="stHeader"] {
            visibility: hidden;
            height: 0px;
        }
        
        /* 2. 主容器内边距归零，利用负外边距进一步上提 */
        .block-container {
            padding-top: 0rem !important; 
            padding-bottom: 0rem !important;
            margin-top: -35px !important; 
        }

        /* 3. 移除 Streamlit 默认的锚点间距 */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# 2. 修复并优化后的标题 HTML 模块
# 增加了 margin-top: -20px 来抵消最后一点无法消除的物理间隙
st.markdown(f"""
    <div style='text-align:center; margin-top: -20px; padding-top: 0px;'>
        <h1 style='margin: 0px; padding: 0px; color: #00aaff; font-size: 34px;'>
            🚀 METAR 智能监控终端
        </h1>
        <p style='margin: 5px 0; color: #00aaff; font-size: 16px; font-weight: bold;'>
            实时气象 · 概率模型 · 信号系统
        </p>
        <p style='margin: 2px 0; font-size: 14px; color: #888; font-weight: bold;'>
            更新时间：{now_local().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
        <p style='margin: 2px 0; font-size: 14px; color: #666; font-weight: bold;'>
            数据来源：METAR(ZSPD) ｜ 系统每30S自动刷新 ｜ Design by Kylin
        </p>
    </div>
""", unsafe_allow_html=True)

# ======================
# 🌌 科幻UI样式（优化为浅色）
# ======================
st.markdown("""
<style>
body, .stApp {
    background: linear-gradient(135deg, #e6f7ff, #f0fbff, #ffffff);
    color: #003344;
}
/* 强制缩小 Streamlit 默认的内容区顶部间隙 */
[data-testid="stAppViewBlockContainer"] {
    padding-top: 1rem !important;    /* 默认通常是 6rem，改为 1rem 显著缩小间隙 */
    padding-bottom: 1rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

h1 {
    text-align: center;
    color: #00aaff;
    text-shadow: 0 0 6px rgba(0,170,255,0.4);
}

section[data-testid="stHorizontalBlock"] > div {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(0, 170, 255, 0.2);
    border-radius: 12px;
    padding: 15px;
    box-shadow: 0 4px 12px rgba(0, 170, 255, 0.15);
}

[data-testid="stMetricValue"] {
    color: #0099cc;
    font-size: 28px;
}

h2, h3 {
    color: #0077aa;
}

.stSuccess {
    background-color: rgba(0,200,150,0.15);
    color: #009966;
    border: 1px solid #00aa88;
}

.stWarning {
    background-color: rgba(255,180,0,0.15);
    color: #cc8800;
    border: 1px solid #ffaa00;
}

.stError {
    background-color: rgba(255,0,80,0.12);
    color: #cc0033;
    border: 1px solid #ff4d6d;
}
/* 优化卡片容器，增加科技感边框和轻微动画 */
section[data-testid="stHorizontalBlock"] > div {
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(0, 170, 255, 0.3);
    border-radius: 15px;
    backdrop-filter: blur(10px); /* 增加毛玻璃效果 */
    padding: 20px;
    box-shadow: 0 8px 32px rgba(0, 170, 255, 0.1);
    transition: all 0.3s ease;
}

/* 模拟“扫描”呼吸灯效果 */
@keyframes border-glow {
    0% { border-color: rgba(0, 170, 255, 0.3); box-shadow: 0 0 5px rgba(0, 170, 255, 0.1); }
    50% { border-color: rgba(0, 170, 255, 0.6); box-shadow: 0 0 15px rgba(0, 170, 255, 0.3); }
    100% { border-color: rgba(0, 170, 255, 0.3); box-shadow: 0 0 5px rgba(0, 170, 255, 0.1); }
}

section[data-testid="stHorizontalBlock"] > div:hover {
    animation: border-glow 2s infinite ease-in-out;
}

/* 针对 Metric 的特殊样式 */
[data-testid="stMetric"] {
    background: linear-gradient(to right, rgba(0,170,255,0.05), transparent);
    padding: 10px;
    border-radius: 10px;
}

/* METAR解码模块样式 */
.metar-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-top: 10px;
}
.metar-item {
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid rgba(0, 170, 255, 0.3);
    border-radius: 8px;
    padding: 10px;
    box-shadow: 0 2px 6px rgba(0, 170, 255, 0.1);
    transition: transform 0.2s;
}
.metar-item:hover {
    transform: translateY(-2px);
    border-color: #00aaff;
}
.metar-item-title {
    color: #0077aa;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 5px;
    display: flex;
    align-items: center;
    gap: 5px;
}
.metar-item-value {
    color: #003344;
    font-size: 14px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ======================
# 时间
# ======================
def now_local():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    

# def utc_to_local(day, hour, minute):
#    now = datetime.now(timezone.utc).replace(tzinfo=None)
#    dt = datetime(now.year, now.month, int(day), int(hour), int(minute))
#    return dt + timedelta(hours=8)

def utc_to_local(day_str, hour_str, min_str):
    """将 METAR 报文中的 日/时/分 转换为北京时间，自动处理跨月"""
    now = now_local()
    day = int(day_str)
    hour = int(hour_str)
    minute = int(min_str)
    
    try:
        # 尝试以当前月份构造 UTC 时间
        utc_dt = datetime(now.year, now.month, day, hour, minute)
        
        # 如果构造出的时间比现在还晚（例如现在1号，报文是31号），说明是上个月的
        if utc_dt > datetime.now().replace(tzinfo=None) + timedelta(hours=2): 
            raise ValueError("Future date")
            
    except ValueError:
        # 进入此处说明：要么4月没有31日，要么时间超前了，判定为上个月
        # 计算上个月的年份和月份
        first_of_this_month = now.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        utc_dt = datetime(last_month_end.year, last_month_end.month, day, hour, minute)
    
    # 返回北京时间 (UTC+8)
    return utc_dt + timedelta(hours=8)

# ======================
# 缓存
# ======================
def load_cache():
    try:
        with open("cache.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_cache(data):
    with open("cache.json", "w") as f:
        json.dump(data, f)

# ======================
# 历史数据（双源修复版：精准拉取本地凌晨数据）
# ======================
def init_today_history():
    print("🔍 进入 init_today_history 函数...")
    # 模拟浏览器请求头，增加成功率
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # --- 数据源 1：Aviation Weather ---
    try:
        url = "https://aviationweather.gov/api/data/metar"
        params = {"ids": "ZSPD", "format": "json", "hours": 48}
        res = requests.get(url, params=params, headers=headers, timeout=15) # 增加超时
        metars = res.json()

        data = []
        for m in metars:
            temp = m.get("temp") or m.get("temp_c")
            raw = m.get("rawOb") or m.get("raw_text")
            obs = m.get("obsTime") or m.get("observation_time")

            if temp is not None and obs:
                dt = datetime.strptime(obs, "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=8)
                if dt.date() == now_local().date():
                    data.append({
                        "metar_time": dt.strftime("%d%H%M"),
                        "time": dt.strftime("%Y-%m-%d %H:%M"),
                        "temp": int(temp),
                        "raw": raw
                    })

        if len(data) >= 1:
            data = sorted(data, key=lambda x: x["time"])
            print("✅ 历史源1(Aviation Weather)抓取成功")
            print(f"✅ 抓取成功，获取到 {len(data)} 条历史记录")
            save_cache(data)
            return data
    except Exception as e:
        print(f"⚠️ 历史源1抓取跳过: {e}")

    # --- 数据源 2：Ogimet (重点修改区域) ---
    try:
        now_loc = now_local()
        
        # 【修改点 1：安全构造北京时间凌晨】
        # 直接通过 timedelta 计算，避免手动填入 day=31 这种可能溢出的数字
        local_start = now_loc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 【修改点 2：安全构造 UTC 时间】
        # 减去 8 小时会自动处理跨月、跨年（例如从 4月1日 变成 3月31日）
        utc_start = local_start - timedelta(hours=8)
        
        # 结束时间
        from datetime import timezone
        utc_end = datetime.now(timezone.utc).replace(tzinfo=None)

        # URL 拼接保持不变，此时的 utc_start.day 已经是安全的了
        url = f"https://www.ogimet.com/display_metars2.php?lang=en&lugar=ZSPD&tipo=ALL&ord=REV&nil=NO&fmt=txt&ano={utc_start.year}&mes={utc_start.month:02d}&day={utc_start.day:02d}&hora={utc_start.hour:02d}&anof={utc_end.year}&mesf={utc_end.month:02d}&dayf={utc_end.day:02d}&horaf={utc_end.hour:02d}&minf=59"
        
        print(f"📡 正在尝试 Ogimet URL: {url}")
        text = requests.get(url, headers=headers, timeout=15).text
        lines = text.split("\n")

        data = []
        for line in lines:
            if "ZSPD" not in line: continue
            t = re.search(r'(\d{2})(\d{2})(\d{2})Z', line)
            temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', line)
            if not t or not temp_match: continue

            day, hour, minute = t.groups()
            temp = int(temp_match.group(1).replace("M", "-"))
            
            # 【修改点 3：修复 utc_to_local 内部可能的跨月逻辑】
            # 确保 utc_to_local 函数能正确处理“报文是31日，现在是1日”的情况
            dt = utc_to_local(day, hour, minute)

            if dt.date() == now_loc.date():
                data.append({
                    "metar_time": f"{day}{hour}{minute}",
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": line.strip()
                })

        if len(data) >= 1:
            data = sorted(data, key=lambda x: x["time"])
            print("✅ 历史源2(Ogimet)抓取成功")
            print(f"✅ 抓取成功，获取到 {len(data)} 条历史记录")
            save_cache(data)
            return data
            
    except Exception as e:
        print(f"❌ 历史源2最终失败: {e}")
        # 这里会打印具体的错误原因

    return load_cache()


# ======================
# 实时数据
# ======================
def get_today_data():
    data = load_cache()
    is_new = False
    source = "CACHE"

    try:
        url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/ZSPD.TXT"
        txt = requests.get(url, timeout=2).text
        metar = txt.strip().split("\n")[1]

        t = re.search(r'(\d{6})Z', metar)
        temp_match = re.search(r' (M?\d{2})/(M?\d{2}) ', metar)

        if t and temp_match:
            source = "REALTIME"
            metar_time = t.group(1)
            temp = int(temp_match.group(1).replace("M", "-"))

            if len(data) == 0 or data[-1]["metar_time"] != metar_time:
                is_new = True
                data.append({
                    "metar_time": metar_time,
                    "time": now_local().strftime("%Y-%m-%d %H:%M"),
                    "temp": temp,
                    "raw": metar
                })
                save_cache(data)

    except:
        pass

    return data, is_new, source
# ======================
# METAR 解码引擎（进阶版：支持单位自动换算）
# ======================
def decode_metar(raw, obs_time):
    # 步骤 1：初始化数据字典（设定安全默认值）
    data = {
        "time": obs_time,
        "wx": "无显著天气",  # 默认无复杂天气现象
        "wind": "数据缺失",  # 将"未知"改为更专业的"数据缺失"
        "cloud": "晴空",
        "vis": "数据缺失",
        "qnh": "数据缺失",
        "dew": "数据缺失",
        "rh": "数据缺失"
    }
    
    # 步骤 2：解析风速风向 (支持 MPS 和 KT 两种单位)
    # 正则解释：匹配 3位数字或VRB(方向) + 2到3位数字(速度) + 可选的G及阵风速度 + MPS或KT(单位)
    wind_match = re.search(r'\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(MPS|KT)\b', raw)
    if wind_match:
        # 获取风向
        dir_str = "变向" if wind_match.group(1) == "VRB" else f"{wind_match.group(1)}°"
        # 获取风速数值
        speed_raw = int(wind_match.group(2))
        # 获取单位
        unit = wind_match.group(4)
        
        # 核心逻辑：单位转换
        if unit == "KT":
            # 1 节(Knot) = 0.51444 米/秒，保留一位小数
            speed_mps = round(speed_raw * 0.5144, 1)
        else:
            speed_mps = speed_raw # 如果已经是 MPS，则保持不变
            
        data["wind"] = f"{dir_str}  {speed_mps} m/s"
        
    # 步骤 3：解析能见度 (例如 9999, 0800)
    # 增加前后空格限制，防止错误匹配到时间戳等其他4位数字
    vis_match = re.search(r'\s(\d{4})\s', raw + " ") 
    if vis_match:
        vis = vis_match.group(1)
        data["vis"] = "> 10 公里" if vis == "9999" else f"{vis} 米"
        
    # 步骤 4：解析云况
    clouds = re.findall(r'\b(FEW|SCT|BKN|OVC|VV)(\d{3})(CB|TCU)?\b', raw)
    if clouds:
        cloud_map = {"FEW": "少云", "SCT": "疏云", "BKN": "多云", "OVC": "阴天", "VV": "垂直能见度"}
        # 将飞行高度层(FL)转换为大致的米 (x30)
        c_list = [f"{cloud_map.get(c[0], c[0])} {int(c[1])*30}m" for c in clouds]
        data["cloud"] = " / ".join(c_list)
    elif "CAVOK" in raw:
        # CAVOK 代表能见度好、无云、无复杂天气
        data["cloud"] = "晴空良好 (CAVOK)"
        data["vis"] = "> 10 公里"
        
    # 步骤 5：解析气压 (例如 Q1018)
    qnh_match = re.search(r'\bQ(\d{4})\b', raw)
    if qnh_match:
        data["qnh"] = f"{qnh_match.group(1)} hPa"
        
    # 步骤 6：解析温度、露点，并计算相对湿度
    temp_match = re.search(r'\b(M?\d{2})/(M?\d{2})\b', raw)
    if temp_match:
        t = int(temp_match.group(1).replace("M", "-"))
        td = int(temp_match.group(2).replace("M", "-"))
        data["dew"] = f"{td}°C"
        
        # 使用马格努斯公式 (Magnus formula) 计算相对湿度
        es = 6.112 * math.exp((17.67 * t) / (t + 243.5))
        e = 6.112 * math.exp((17.67 * td) / (td + 243.5))
        rh = max(0, min(100, (e / es) * 100))
        data["rh"] = f"{int(rh)}%"
        
    # 步骤 7：解析特殊天气现象 (扫描常见标识符)
    wx_map = {"-RA": "小雨", "RA": "中雨", "+RA": "大雨", "SN": "降雪", "DZ": "毛毛雨", 
              "FG": "大雾", "BR": "轻雾", "HZ": "霾", "TS": "雷暴", "VCTS": "周边雷暴", "SHRA": "阵雨"}
    wx_list = []
    for code, name in wx_map.items():
        if re.search(r'\b' + re.escape(code) + r'\b', raw):
            wx_list.append(name)
    
    # 如果找到了匹配的天气现象，就会覆盖掉初始的"无显著天气"
    if wx_list:
        data["wx"] = ", ".join(wx_list)
        
    return data
# ======================
# 模型
# ======================
def peak_probability(data):
    if len(data) < 5:
        return 0

    if data[-1]["temp"] < data[-2]["temp"]:
        return 95

    temps = [x["temp"] for x in data[-5:]]
    acc = (temps[-1] - temps[-2]) - (temps[-2] - temps[-3])
    position = temps[-1] / max(temps)

    score = 0
    score += max(0, -acc) * 30
    score += position * 50

    return min(round(score), 100)

# ======================
# 启动 (彻底修复版)
# ======================
# --- 在启动逻辑之前添加 ---
delay_min = 0  # 赋初始值，防止报错
source = "UNKNOWN"
is_new = False
data = load_cache()

# 重点修复：不再只判断“是否为空”，而是判断“数据够不够”
# 只要少于 5 条，就认为历史数据补全失败，强制再运行一次
if len(data) < 1:
    # 强制在控制台和网页同时输出，确保你能看到
    print(f"📡 [DEBUG] 当前缓存数据量 {len(data)} 条，开始执行 init_today_history...")
    st.toast("正在尝试补全今日历史报文...", icon="🔄")
    data = init_today_history()

# 获取实时数据
data, is_new, source = get_today_data()

# 检查最终结果
if not data:
    st.error("❌ 无法获取任何数据，请检查网络连接或 API 状态")
    print("❌ [ERROR] 最终数据列表为空！")
    st.stop()


# ======================
# 🔊 声音系统（终极修复版）
# ======================
if "audio_unlocked" not in st.session_state:
    st.session_state.audio_unlocked = False

if st.button("🔊 启用声音提醒"):
    st.session_state.audio_unlocked = True
    # 更换为极其稳定、无防盗链的 Google 官方测试提示音
    test_audio_url = "https://actions.google.com/sounds/v1/alarms/beep_short.ogg"
    st.markdown(f'<audio autoplay><source src="{test_audio_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    st.success("✅ 声音提醒已解锁！您刚才应该已经听到了一声测试的“滴”声。")

# ✅ 直接利用你原本代码中完美的 is_new 变量，最精准！
if st.session_state.audio_unlocked and is_new:
    # 加上时间戳防止浏览器缓存，确保每次新数据都响
    alert_url = f"https://actions.google.com/sounds/v1/alarms/beep_short.ogg?t={datetime.now(timezone.utc).timestamp()}"
    st.markdown(f'<audio autoplay><source src="{alert_url}" type="audio/ogg"></audio>', unsafe_allow_html=True)
    
    # 加上一个视觉弹窗，做双重保障
    st.toast("🔔 抓取到新 METAR 数据，已触发声音警报！", icon="🔊")

# 数据来源
delay_info = f"**{int(delay_min)}** 分钟" 
space = "&nbsp;" * 80

if source == "REALTIME":
    st.success(f" {space} 🟢 数据来源：实时METAR {space} ⌛⌛截至当前时间，距离上一次获取实时数据已经延迟：{delay_info}")
else:
    st.warning(f"🟡 数据来源：缓存 (🚨🚨注意，缓存数据无意义,联系作者排查数据原因: {delay_info})")

# 🔔 新数据提醒
if is_new and len(data) >= 2:
    prev_temp = data[-2]["temp"]
    curr_temp = data[-1]["temp"]
    delta_temp = curr_temp - prev_temp

    if delta_temp > 0:
        st.success(f"🟢 新数据：{prev_temp}°C → {curr_temp}°C（+{delta_temp}°C）")
    elif delta_temp < 0:
        st.error(f"🔻 新数据：{prev_temp}°C → {curr_temp}°C（{delta_temp}°C）")
    else:
        st.info(f"➖ 新数据：{curr_temp}°C（无变化）")

# ======================
# 三栏（完全未改）
# ======================
col1, col2, col3 = st.columns([1,1.2,1])

with col1:
    st.markdown("### 🧠 见顶概率")
    prob = peak_probability(data)
    st.metric("概率", f"{prob}%")
    st.progress(prob/100)

    st.markdown("### 📊 概率解释")
    if len(data) >= 2:
        if data[-1]["temp"] < data[-2]["temp"]:
            st.write("🔻 已下降（已见顶）")
        else:
            st.write("📈 上升中")

    st.markdown("### 🚨 信号面板")
    if is_delayed:
        st.error(f"🚨 数据延迟：{int(delay_min)} 分钟")
        st.error("🔴 信号已降级")
    else:
        if prob >= 90:
            st.error("🔴 强卖")
        elif prob > 60:
            st.warning("🟡 接近顶部")
        else:
            st.success("🟢 上升趋势")
            
 # === METAR 解码 ===     
    st.markdown("---")
    st.markdown("### 🔍 METAR 解码")
    
    # 提取并解码最新一条数据
    decoded = decode_metar(current["raw"], formatted_time)
    
    html_content = f"""
    <div class="metar-grid">
        <div class="metar-item" style="grid-column: span 2;">
            <div class="metar-item-title">🕒 观测时间</div>
            <div class="metar-item-value">{decoded['time']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">🌬️ 风速风向</div>
            <div class="metar-item-value">{decoded['wind']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">👁️ 能见度</div>
            <div class="metar-item-value">{decoded['vis']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">☁️ 云况</div>
            <div class="metar-item-value">{decoded['cloud']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">⏱️ 气压 (QNH)</div>
            <div class="metar-item-value">{decoded['qnh']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">💧 相对湿度</div>
            <div class="metar-item-value">{decoded['rh']}</div>
        </div>
        <div class="metar-item">
            <div class="metar-item-title">🌡️ 露点</div>
            <div class="metar-item-value">{decoded['dew']}</div>
        </div>
        <div class="metar-item" style="grid-column: span 2; background: rgba(0, 170, 255, 0.05);">
            <div class="metar-item-title">⛈️ 当前天气</div>
            <div class="metar-item-value">{decoded['wx']}</div>
        </div>
    </div>
    """
    st.markdown(html_content, unsafe_allow_html=True)

with col2:
    st.markdown("### 📡 当前数据")
    
    col_a, col_b = st.columns(2)

    with col_a:
#st.metric("当前温度", f"{current['temp']}°C")
# 1. 定义温度显示样式
# font-size: 48px 控制数值大小，你可以根据需要调整
# color: #00aaff 是科幻感蓝色
        temp_style = """
        <style>
            .temp-container {
                text-align: left;
                font-family: 'Inter', sans-serif;
                margin-bottom: 20px;
            }
            .temp-label {
                font-size: 16px;
                color: #888;
                margin-bottom: 4px;
            }
            .temp-value {
                font-size: 52px; /* 加大显示 */
                font-weight: 450; /* 极致加粗 */
                color: #00aaff;  /* 亮蓝色 */
                line-height: 1.2;
                text-shadow: 0px 0px 10px rgba(0, 170, 255, 0.3); /* 轻微发光效果 */
            }
        </style>
        """
        
        # 2. 注入 CSS 样式
        st.markdown(temp_style, unsafe_allow_html=True)
        
        # 3. 渲染自定义的温度模块
        # 使用 f-string 将实时数据嵌入 HTML
        st.markdown(f"""
            <div class="temp-container">
                <div class="temp-label">当前温度</div>
                <div class="temp-value">{current['temp']}°C</div>
            </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.metric("截至当前已捕获的今日最高温度", f"{max_temp}°C", delta=f"捕获发生在：{max_time_str}")

    st.markdown(f"**METAR最新发布：{formatted_time}**")

    st.info("📌 当系统启动运行将自动获取当天0点开始的历史数据以填充温度图")
    
    st.markdown("### 📈 温度曲线")    
    # 准备数据
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    
    # 创建 Plotly 科技感图表
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df["time"], 
        y=df["temp"],
        mode='lines+markers',
        name='温度',
        # 设置线条颜色、粗细和平滑度(spline)
        line=dict(color='#00aaff', width=3, shape='spline'),
        # 设置数据点标记的样式
        marker=dict(size=6, color='#0077aa', symbol='circle', line=dict(color='white', width=1)),
        # 添加曲线下方的半透明浅蓝填充，增加全息科技感
        fill='tozeroy',
        fillcolor='rgba(0, 170, 255, 0.15)',
        # 自定义悬停提示框格式
        hovertemplate='时间: %{x|%H:%M}<br>温度: %{y}°C<extra></extra>'
    ))
    
    # 优化布局与背景（高兼容性版本）
    fig.update_layout(
        height=350,  
        margin=dict(l=0, r=0, t=10, b=0),  
        plot_bgcolor='rgba(0,0,0,0)',  
        paper_bgcolor='rgba(0,0,0,0)', 
        xaxis=dict(
            showgrid=True, 
            gridcolor='rgba(0, 170, 255, 0.1)', 
            tickformat='%H:%M', 
            tickfont=dict(color='#0077aa')  # 修复点 1：明确指定刻度文本颜色
        ),
        yaxis=dict(
            showgrid=True, 
            gridcolor='rgba(0, 170, 255, 0.1)',
            title=dict(
                text='温度 (°C)',
                font=dict(color='#0077aa')  # 修复点 2：使用标准嵌套字典设置标题与颜色
            ),
            tickfont=dict(color='#0077aa'), # 修复点 3：明确指定刻度文本颜色
            zeroline=False 
        ),
        hovermode='x unified' 
    )

    # 使用 Streamlit 渲染图表
    # st.plotly_chart(fig, use_container_width=True)  Streamlit 提示 use_container_width 参数将在 2025 年底移除
    st.plotly_chart(fig, width="stretch")


# 1. 重新构建数据逻辑
    st.markdown("### 🧩 数据完整性")
    gaps = []
    for i in range(1, len(data)):
        t1 = pd.to_datetime(data[i-1]["time"])
        t2 = pd.to_datetime(data[i]["time"])
        if (t2 - t1).total_seconds()/60 > 60:
            gaps.append(1)

    total_records = len(data)
    
    # 2. 动态样式定义
    if not gaps:
        status_color, status_bg, border_c = "#009966", "rgba(0,200,150,0.1)", "#00aa88"
        status_text = "🟢 数据链条完整"
    else:
        status_color, status_bg, border_c = "#cc0033", "rgba(255,0,80,0.1)", "#ff4d6d"
        status_text = f"🔴 检测到 {len(gaps)} 处缺失"

    # 3. 核心 HTML 字符串 (注意：不要在 f-string 内部的样式里使用回车，保持紧凑)
    integrity_html = f"""
    <div style="background:{status_bg}; border:1px solid {border_c}; border-radius:12px; padding:15px; min-height:228px; display:flex; flex-direction:column; justify-content:space-between; box-shadow:0 4px 12px rgba(0,170,255,0.1);">
        <div style="font-size:30px; font-weight:bold; color:{status_color}; text-align:center; margin-bottom:10px;">
            {status_text}
        </div>
        <div style="display:flex; justify-content:space-between; border-top:1px dashed rgba(0,170,255,0.2); padding-top:12px;">
            <div style="text-align:left;">
                <span style="font-size:20px; color:#888;">捕获样本</span><br>
                <span style="font-size:40px; color:#0077aa; font-weight:900;">{total_records}</span><span style="font-size:30px; color:#666;"> 条</span>
            </div>
            <div style="text-align:right;">
                <span style="font-size:20px; color:#888;">防御状态</span><br>
                <span style="font-size:30px; color:{status_color}; font-weight:bold;">实时监控中 🛡️</span>
            </div>
        </div>
    </div>
    """

    st.markdown(integrity_html, unsafe_allow_html=True)


with col3:
    st.markdown("### 📋 历史数据")

    if data:
        # 1. 准备数据并按时间倒序排列
        df_raw = pd.DataFrame(data)
        df_raw["time_dt"] = pd.to_datetime(df_raw["time"])
        df_raw = df_raw.sort_values(by="time_dt", ascending=False).reset_index(drop=True)

        # 2. 浅蓝色科幻风格与滚动条 CSS
        # 注意：这里将 <style> 标签顶格写，防止被 Markdown 当作代码块
        table_style = """<style>
.custom-table-wrapper {
    max-height: 380px;
    overflow-y: auto;
    border: 1px solid rgba(0, 170, 255, 0.4);
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(230, 247, 255, 0.4));
    box-shadow: 0 4px 15px rgba(0, 170, 255, 0.1);
    margin-bottom: 15px;
}
.custom-table-wrapper::-webkit-scrollbar { width: 6px; }
.custom-table-wrapper::-webkit-scrollbar-track { background: rgba(230, 247, 255, 0.2); border-radius: 10px; }
.custom-table-wrapper::-webkit-scrollbar-thumb { background: rgba(0, 170, 255, 0.4); border-radius: 10px; }
.custom-table-wrapper::-webkit-scrollbar-thumb:hover { background: rgba(0, 170, 255, 0.7); }
.sci-fi-table { width: 100%; border-collapse: collapse; font-size: 15px; color: #003344; text-align: center; }
.sci-fi-table thead th {
    position: sticky; top: 0; background: rgba(230, 247, 255, 0.95);
    backdrop-filter: blur(5px); color: #0077aa; padding: 12px 8px;
    border-bottom: 2px solid #00aaff; z-index: 2; font-weight: bold;
}
.sci-fi-table tbody td { padding: 10px 8px; border-bottom: 1px solid rgba(0, 170, 255, 0.15); }
.sci-fi-table tbody tr { transition: background-color 0.2s ease; }
.sci-fi-table tbody tr:hover { background-color: rgba(0, 170, 255, 0.1); }
.highlight-top-row {
    background: linear-gradient(90deg, rgba(0, 170, 255, 0.2) 0%, rgba(0, 170, 255, 0.05) 100%) !important;
    border-left: 4px solid #00aaff; font-weight: bold; color: #005588;
}
.highlight-top-row td { border-bottom: 1px solid rgba(0, 170, 255, 0.4); }
</style>"""

        # 3. 循环构建表格行 HTML
        rows_html = ""
        for i, row in df_raw.iterrows():
            row_class = 'class="highlight-top-row"' if i == 0 else ""
            obs_time = row["time_dt"].strftime("%Y-%m-%d %H:%M")
            # 注意：采用单行拼接或顶格拼接，彻底避免前面带有空格
            rows_html += f"<tr {row_class}><td>{obs_time}</td><td>{row['temp']}°C</td><td>{row['metar_time']}</td></tr>\n"

        # 4. 组装并渲染完整的 HTML（外部的 div 和 table 也必须顶格）
        full_html = f"""{table_style}
<div class="custom-table-wrapper">
<table class="sci-fi-table">
<thead>
<tr><th>观测时间</th><th>温度</th><th>原始报文时间</th></tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>"""
        
        st.markdown(full_html, unsafe_allow_html=True)
        
    else:
        st.info("⌛ 暂无历史观测数据")

    st.markdown("---")
    st.markdown("### 📡 最近METAR")
    
    # 最近报文原始数据显示（同样修复了缩进问题）
    if data:
        metar_blocks = ""
        recent_items = data[-10:] if len(data) >= 10 else data
        for row in reversed(recent_items):
            dt_display = pd.to_datetime(row['time']).strftime("%Y-%m-%d %H:%M:%S")
            # 将 HTML 写成紧凑格式，防止空格缩进触发代码块
            metar_blocks += f'<div style="background: rgba(0, 170, 255, 0.05); border-left: 4px solid #00aaff; padding: 8px; margin-bottom: 6px; border-radius: 4px; transition: all 0.2s ease;"><span style="color: #0077aa; font-size: 15px; font-weight: bold;">● {dt_display}</span><br><code style="color: #003344; font-size: 11px; background: transparent;">{row["raw"]}</code></div>\n'
            
        st.markdown(f'<div style="max-height: 450px; overflow-y: auto; padding-right: 5px;">\n{metar_blocks}\n</div>', unsafe_allow_html=True)

# =========================================================
# 🏛️ 模块：Wunderground 官方结算参考 (新增)
# =========================================================
st.markdown("---") 
st.markdown("### 🏛️ Wunderground 官方结算参考")

# 1. 准备动态数据
target_date = now_local().strftime('%Y-%m-%d')
wunderground_url = f"https://www.wunderground.com/history/daily/cn/shanghai/ZSPD/date/{target_date}"

# 2. 构建 HTML 字符串 (确保 div 标签前没有任何多余的缩进/空格)
# 注意：这里使用变量存储，避免在 st.markdown 内部编写长文本导致格式混乱
settlement_html = f"""
<div style="background: rgba(255, 255, 255, 0.8); border: 2px solid #ffaa00; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(255, 170, 0, 0.15); font-family: sans-serif;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h4 style="margin: 0; color: #cc8800;">⚠️ Polymarket 结算预言机校验</h4>
            <p style="margin: 5px 0; font-size: 14px; color: #666;">
                当前监控站点：<b>ZSPD (Pudong Intl)</b> | 结算基准日期：<b>{target_date}</b>
            </p>
        </div>
        <a href="{wunderground_url}" target="_blank" style="text-decoration: none; background: #ffaa00; color: white; padding: 10px 20px; border-radius: 8px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">打开 Wunderground 官方页 🔗</a>
    </div>
        <div style="margin-top: 15px; padding: 10px; background: rgba(255, 180, 0, 0.1); border-radius: 8px; font-size: 13px; color: #444; line-height: 1.6; border-left: 4px solid #ffaa00;">
        <b style="color: #cc8800;">💡 交易员笔记：</b><br>
        1. <b>基差风险：</b>通常情况下METAR 每 30分钟发布一次数据，而 Wunderground 的结算数据可能包含报文间隙中的极值。<br>
        2. <b>时间差：</b>Wunderground 的数据同步可能存在 1-2 小时延迟，请以该页面最终显示的 <i>"Daily Observations"</i> 表格中"Temperature"列的 MaxTemp值为准。<br>
        3. <b>数据风险：</b>METAR 体系：坚如磐石。它是受各国政府和国际航空法严格监管的航空安全设施，篡改难度极高，基本可以排除人为操控。<br>
        4. <b>极端情况：</b>METAR ZSPD站点掉线，Wunderground 的算法是否会自动回退（Fallback）到附近的某个私人气象站？本系统截止2026年4月，尚未观测到此极端情形发生。<br>
        </div>
</div>
"""

# 3. 渲染 HTML (确保参数正确)
st.markdown(settlement_html, unsafe_allow_html=True)

# 4. 预览窗口
with st.expander("👁️ 快速预览 Wunderground 表格 (若加载失败请点击上方按钮)"):
    st.iframe(wunderground_url, height=600, scrolling=True)


