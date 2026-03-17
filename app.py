import streamlit as st
import pandas as pd
import re
import urllib.parse  # <-- 全新加入：用來轉換網址以生成 QR Code
from datetime import datetime
import os

# ==========================================
# 系統設定與全域變數
# ==========================================
st.set_page_config(page_title="急診臨床決策輔助系統", page_icon="🚨", layout="wide")
LOG_FILE = "assessment_log.csv"

# ==========================================
# 核心解析神經中樞 (強化版防呆機制)
# ==========================================
def parse_his_vitals(raw_text):
    parsed_data = []
    for line in raw_text.strip().split('\n'):
        line = line.strip('\r')
        if not line.strip(): continue
        has_tabs = '\t' in line
        tokens = line.split('\t') if has_tabs else line.split()
        bp_idx = -1
        for i, t in enumerate(tokens):
            t_clean = t.strip()
            if '/' in t_clean and len(t_clean.split('/')) == 2 and t_clean.split('/')[0].isdigit():
                bp_idx = i; break
        if bp_idx >= 2:
            try:
                sbp = int(tokens[bp_idx].strip().split('/')[0])
                hr = None
                if has_tabs and (bp_idx - 2) >= 0:
                    hr_str = tokens[bp_idx - 2].strip()
                    if hr_str.isdigit(): hr = int(hr_str)
                if hr is None:
                    clean_tokens = line.split()
                    clean_bp_idx = -1
                    for i, t in enumerate(clean_tokens):
                        if '/' in t and len(t.split('/')) == 2 and t.split('/')[0].isdigit():
                            clean_bp_idx = i; break
                    if clean_bp_idx >= 2:
                        sub_tokens = clean_tokens[2:clean_bp_idx]
                        ints = [int(x) for x in sub_tokens if x.isdigit()]
                        if len(ints) == 1: hr = ints[0]
                        elif len(ints) >= 2:
                            if ints[-1] <= 45 and ints[-2] >= 40: hr = ints[-2]
                            elif 34 <= ints[-2] <= 42 and ints[-1] > 40: hr = ints[-1]
                            else: hr = ints[-2]
                if hr is not None:
                    date_str = tokens[0].strip() if has_tabs else clean_tokens[0]
                    time_str = tokens[1].strip() if has_tabs else clean_tokens[1]
                    if len(time_str) >= 4 and time_str[:4].isdigit(): time_formatted = f"{time_str[:2]}:{time_str[2:4]}"
                    else: time_formatted = time_str
                    if len(date_str) == 7 and date_str.startswith('1'): dt_str = f"{date_str[3:5]}/{date_str[5:7]} {time_formatted}"
                    else: dt_str = f"{date_str} {time_formatted}"
                    parsed_data.append({"時間": dt_str, "心跳 (HR)": hr, "收縮壓 (SBP)": sbp, "休克指數 (SI)": round(hr / sbp, 2)})
            except Exception as e:
                pass 
    return pd.DataFrame(parsed_data)

# ==========================================
# 側邊欄 (Sidebar)：導覽、衛教 QR、學理搜尋
# ==========================================
st.sidebar.title("🏥 急診臨床決策輔助系統")
page = st.sidebar.radio("請選擇功能模組：", [
    "📝 留觀風險評估 (交班)", 
    "📈 生命徵象趨勢 (查房)",
    "🩸 ABG 血液氣體判讀",
    "💉 血液檢驗報告 (CBC+BCS)",
    "💧 DKA/HHS 動態導航 (ADA標準)"
])

st.sidebar.divider()

# --- 全新功能：出院/留觀飲食衛教 (QR Code 生成) ---
st.sidebar.subheader("🍽️ 家屬飲食衛教 (QR Code)")
st.sidebar.caption("選擇主題，讓家屬直接用手機掃描帶走！")
edu_topic = st.sidebar.selectbox("選擇衛教主題：", ["-- 請選擇 --", "🩸 糖尿病飲食 (DM)", "💧 腎臟病飲食 (CKD)", "🍷 肝臟疾病飲食", "🩸 腸胃道出血後飲食"])

if edu_topic != "-- 請選擇 --":
    qr_url = ""
    if edu_topic == "🩸 糖尿病飲食 (DM)":
        st.sidebar.info("1. 規律進食，避免空腹過久。\n2. 拒絕含糖飲料與精緻甜點。\n3. 多吃高纖蔬菜延緩血糖上升。")
        qr_url = "https://www.hpa.gov.tw/Pages/EBook.aspx?nodeid=1208" # 國健署糖尿病衛教手冊
    elif edu_topic == "💧 腎臟病飲食 (CKD)":
        st.sidebar.info("1. 嚴格避免高鉀食物 (如香蕉、濃湯、奇異果)。\n2. 避免高磷食物 (如堅果、內臟、加工肉品)。\n3. 依醫囑限制水分與鹽分攝取。")
        qr_url = "https://www.hpa.gov.tw/Pages/Detail.aspx?nodeid=54&pid=11255" # 國健署腎臟病衛教
    elif edu_topic == "🍷 肝臟疾病飲食":
        st.sidebar.info("1. 絕對禁酒！\n2. 若有腹水，嚴格限制鹽分(低鈉)。\n3. 避免攝取生食(如生蠔、生魚片)防海洋弧菌感染。")
        qr_url = "https://www.mohw.gov.tw/cp-4252-48731-1.html" # 衛福部肝病護理
    elif edu_topic == "🩸 腸胃道出血後飲食":
        st.sidebar.info("1. 醫師許可進食後，先喝溫冷水測試。\n2. 前三天採「溫冷流質」或「溫冷軟食」。\n3. 絕對禁止辛辣、熱湯、咖啡及酒精。")
        qr_url = "https://www.google.com/search?q=%E8%85%B8%E8%83%83%E9%81%93%E5%87%BA%E8%A1%80+%E9%A3%B2%E9%A3%9F+%E8%A1%9B%E6%95%99" # Google 搜尋捷徑
    
    if qr_url:
        # 呼叫免費 QR Code API 產生圖片，零安裝套件！
        encoded_url = urllib.parse.quote(qr_url)
        st.sidebar.image(f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={encoded_url}", caption=f"📱 掃描查看【{edu_topic}】詳細指南")

st.sidebar.divider()

st.sidebar.subheader("🔗 實用快速連結")
st.sidebar.markdown("💊 [**院內藥物查詢系統**](https://hldrug.tzuchi.com.tw/tchw/IphqryChinese/DesktopModules/WesternMedicine/Pill_Search.aspx?Hospital=HL)", unsafe_allow_html=True)

st.sidebar.divider()

st.sidebar.subheader("📚 臨床機轉小寶典 (EBP)")
search_query = st.sidebar.text_input("🔍 搜尋 (例: 酮體, 鉀, 腦水腫, AKI)", "").strip().lower()

ebp_dict = {
    "預警分數 (MEWS/PEWS) 與休克指數": "MEWS ≥ 5 分 或 SI ≥ 1.0 代表高度休克與惡化風險，列為紅區。PEWS 整合兒童行為、膚色與呼吸費力程度提供早期預警。",
    "高危輸液 (IV Pump) 與假性穩定": "依賴升壓劑維持血壓即代表重度心血管衰竭，無視當下血壓直接列為紅區。降壓劑則列黃區監測。",
    "鈣離子校正 (Corrected Ca) 與鎂離子 (Mg)": "Albumin < 4.0 會導致假性低血鈣，校正公式：Ca + 0.8×(4.0-Alb)。Mg < 1.5 易引發致命心律不整 (TdP) 及頑固性低血鉀。",
    "肝功能與黃疸 (AST/ALT/Bil)": "AST/ALT > 100 提示實質性肝炎；> 1000 強烈提示猛爆性肝炎或缺血性肝炎 (Shock Liver)。T.Bil > 1.2 或 D.Bil 異常提示膽道阻塞或肝衰竭。",
    "腎臟功能與 BUN/CRE 比例": "BUN/CRE > 20 提示腎前性氮血症 (Prerenal Azotemia)，急診常見於嚴重脫水或急性腸胃道出血 (UGIB)。",
    "DKA 為什麼會變酸？ (機轉)": "【絕對缺乏胰島素】當體內沒有胰島素時，細胞開始瘋狂分解脂肪。脂肪分解的副產物就是「酮體 (Ketones)」，造成高陰離子間隙代謝性酸中毒。打 Insulin 是為了關閉酮體製造工廠！",
    "HHS 為什麼會極度脫水？ (機轉)": "【相對缺乏胰島素】微量胰島素足以阻止脂肪分解(無酮體)，但無法降血糖。超高血糖會從腎臟引發強烈的「滲透壓性利尿」，把水分大量排光。HHS 前期大量灌注 N/S 比打 Insulin 更重要！",
    "致命陷阱：血鉀的捉迷藏 (K+ Shift)": "【抽血鉀很高，卻不能打 Insulin？】嚴重酸血症時身體會把 K+ 趕出細胞到血液中，所以抽血正常或偏高其實是「假象」！打了 Insulin 瞬間把 K+ 掃回細胞內，若原本血鉀就不高 (< 3.3) 會引發致命性心律不整。",
    "為什麼會有假性低血鈉？ (校正公式)": "【高血糖的稀釋效應】血管極高葡萄糖產生巨大滲透壓，把細胞內水分吸進血管稀釋血鈉。必須用 1.6 或 2.4 的常數去「還原」真實血鈉，決定要給 0.45% 還是 0.9% 點滴。",
    "防護期：預防腦水腫 (Cerebral Edema)": "【為何 200/300 要加糖水？】高血糖時腦細胞內有滲透壓物質。若 Insulin 把血糖降得太快，血管滲透壓暴跌，水分會瘋狂灌進腦細胞引發腦水腫。所以必須提早踩煞車加 D5W。"
}
found = False
for title, content in ebp_dict.items():
    if search_query == "" or search_query in title.lower() or search_query in content.lower():
        found = True
        with st.sidebar.expander(title, expanded=(search_query != "")):
            st.write(content)

st.sidebar.divider()
st.sidebar.subheader("🔒 管理員後台")
admin_password = st.sidebar.text_input("輸入密碼解鎖後台", type="password")
if admin_password == "alex":
    st.sidebar.success("✅ 身分驗證成功")
    if os.path.exists(LOG_FILE):
        df_log = pd.read_csv(LOG_FILE)
        st.sidebar.download_button("📥 下載完整紀錄", data=df_log.to_csv(index=False, encoding='utf-8-sig'), file_name="ed_obs_log.csv", mime="text/csv", use_container_width=True)
        if st.sidebar.button("🗑️ 清空所有紀錄", use_container_width=True):
            os.remove(LOG_FILE); st.rerun()

# ==========================================
# 模組 1：留觀單次評估與交班 (含自動飲食防呆)
# ==========================================
if page == "📝 留觀風險評估 (交班)":
    st.title("🚨 急診留觀風險自動評估與交班")
    patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS標準)", "👶 兒科 (PEWS標準)"], horizontal=True)
    vitals_input = st.text_area("📋 1. 請貼上單次生命徵象：", height=100)
    
    total_score = 0
    if patient_type == "🧑 成人 (MEWS標準)":
        gcs_input = st.number_input("🧠 意識狀態 (GCS 分數) ⚠️必填", min_value=3, max_value=15, value=None, step=1)
        log_score_name = "MEWS"
    else:
        gcs_input = 15 # 兒科預設
        age_group = st.selectbox("👶 選擇病童年齡區間：", ["0-3個月", "4-11個月", "1-4歲", "5-11歲", "12歲以上"])
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1: pews_behavior = st.radio("行為狀態", ["正常(0分)", "焦躁/嗜睡(1分)", "對痛無反應(2分)"])
        with col_p2: pews_cv = st.radio("心血管/膚色", ["粉紅/充填<2秒(0分)", "蒼白/充填2-3秒(1分)", "發紺/大理石斑/充填>3秒(2分)"])
        with col_p3: pews_resp = st.radio("呼吸狀態", ["正常且無費力(0分)", "呼吸急促/需給氧(1分)", "胸凹/呻吟/SPO2<90%(2分)"])
        log_score_name = "PEWS"

    st.subheader("💉 2. 高危險連續輸液 (IV Pump)")
    iv_pumps = st.multiselect("➤ 病患是否使用滴注藥物？", ["Levophed", "easydopamine", "Isoket", "Perdipine", "其他降壓或強心"])

    st.subheader("⚠️ 3. 潛在不穩定主訴與病史")
    high_risk_cc = st.multiselect("➤ 是否有易發生「突發惡化」狀況？", 
                                  ["🧠 癲癇/TIA", "🫀 暈厥/胸痛", "🩸 疑似 GI Bleeding", "🫁 嚴重氣喘/COPD", "☠️ 嚴重低血糖/酒精戒斷"])

    st.subheader("🧪 4. 補充檢驗報告")
    col1, col2 = st.columns(2)
    with col1: k_input, crp_input = st.text_input("➤ K："), st.text_input("➤ CRP：")
    with col2: tni_input, lactate_input = st.text_input("➤ Hs-TnI："), st.text_input("➤ Lactate：")

    if st.button("🚀 開始評估並生成紀錄", type="primary"):
        if vitals_input.strip() == "": st.error("⚠️ 請先貼上生命徵象！")
        elif patient_type == "🧑 成人 (MEWS標準)" and gcs_input is None: st.error("⚠️ 請輸入 GCS 意識分數！")
        else:
            temp = hr = rr = sbp = None 
            if re.search(r'體溫：([\d.]+)', vitals_input): temp = float(re.search(r'體溫：([\d.]+)', vitals_input).group(1))
            if re.search(r'脈搏：(\d+)', vitals_input): hr = int(re.search(r'脈搏：(\d+)', vitals_input).group(1))
            if re.search(r'呼吸：(\d+)', vitals_input): rr = int(re.search(r'呼吸：(\d+)', vitals_input).group(1))
            if re.search(r'血壓：(\d+)/', vitals_input): sbp = int(re.search(r'血壓：(\d+)/', vitals_input).group(1))

            if patient_type == "🧑 成人 (MEWS標準)":
                if temp: total_score += (2 if temp < 35 or temp >= 38.5 else 1 if temp < 36 else 0)
                if hr: total_score += (3 if hr <= 40 or hr >= 130 else 2 if 111 <= hr <= 129 else 1 if 41 <= hr <= 50 or 101 <= hr <= 110 else 0)
                if rr: total_score += (3 if rr >= 30 else 2 if rr <= 8 or 21 <= rr <= 29 else 1 if 15 <= rr <= 20 else 0)
                if sbp: total_score += (3 if sbp <= 70 else 2 if sbp <= 80 or sbp >= 200 else 1 if sbp <= 100 else 0)
                gcs_score = 0 if gcs_input == 15 else 1 if 13 <= gcs_input <= 14 else 2 if 9 <= gcs_input <= 12 else 3
                total_score += gcs_score
                score_display = f"MEWS {total_score}分 (GCS {gcs_input})"
            else:
                total_score = int(pews_behavior[-2]) + int(pews_cv[-2]) + int(pews_resp[-2])
                score_display = f"PEWS {total_score}分"

            shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

            lab_alert = False; lab_records_list = []
            if k_input.strip() and (float(k_input) < 3.0 or float(k_input) > 6.0): lab_alert = True; lab_records_list.append(f"K {k_input}")
            elif k_input.strip(): lab_records_list.append(f"K {k_input}")
            if tni_input.strip() and float(tni_input) > 17.5: lab_alert = True; lab_records_list.append(f"TnI {tni_input}")
            elif tni_input.strip(): lab_records_list.append(f"TnI {tni_input}")
            if crp_input.strip() and float(crp_input) >= 10.0: lab_alert = True; lab_records_list.append(f"CRP {crp_input}(≥10)")
            elif crp_input.strip(): lab_records_list.append(f"CRP {crp_input}")
            if lactate_input.strip() and float(lactate_input) >= 4.0: lab_alert = True; lab_records_list.append(f"Lac {lactate_input}(≥4)")
            elif lactate_input.strip(): lab_records_list.append(f"Lac {lactate_input}")
            lab_record_text = " / ".join(lab_records_list) if lab_records_list else "無異常"

            has_vasopressor = any("Levophed" in p or "easydopamine" in p for p in iv_pumps)
            has_vasodilator = any("Isoket" in p or "Perdipine" in p for p in iv_pumps)
            pump_record_text = " / ".join(iv_pumps) if iv_pumps else "無"
            
            has_high_risk_cc = len(high_risk_cc) > 0
            cc_record_text = " / ".join(high_risk_cc) if has_high_risk_cc else "無"

            # --- 全新加入：自動飲食防呆邏輯 ---
            diet_warning = "🟢 飲食建議：普通飲食 (Normal Diet) 或依醫囑。"
            if gcs_input is not None and gcs_input <= 12:
                diet_warning = "🛑 飲食建議：絕對 NPO (禁食)！意識不清，極易發生吸入性肺炎。"
            elif has_high_risk_cc and any("GI Bleeding" in cc for cc in high_risk_cc):
                diet_warning = "🛑 飲食建議：絕對 NPO (禁食)！疑似腸胃道出血，請保留內視鏡或手術空腹時間。"
            elif has_high_risk_cc and any("氣喘" in cc or "癲癇" in cc for cc in high_risk_cc):
                diet_warning = "⚠️ 飲食建議：暫時 NPO 或視情況給予流質，預防突發惡化嗆咳。"

            if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0) or has_vasopressor:
                risk_level, disposition = "🔴 紅區", "具高度惡化休克風險，建議收治或轉急救區。"
                st.error(f"判定：{risk_level}")
            elif total_score >= 3 or has_vasodilator or has_high_risk_cc:
                risk_level, disposition = "🟡 黃區", "潛在突發惡化風險，請落實密切監測並縮短 Vital signs 頻率。"
                st.warning(f"判定：{risk_level}")
            else:
                risk_level, disposition = "🟢 綠區", "生命徵象穩定，持續常規留觀。"
                st.success(f"判定：{risk_level}")

            st.code(f"""[留觀風險自動評估紀錄]
1. 對象：{patient_type}
2. 生理：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}mmHg
3. 預警：{score_display} / SI {shock_index}
4. 輸液/風險：{pump_record_text} / {cc_record_text}
5. 檢驗：{lab_record_text}
6. 判定/處置：{risk_level} - {disposition}
7. 飲食動向：{diet_warning}""", language="text")

            new_record = pd.DataFrame([{
                "評估時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "類別": log_score_name, "分數": total_score, "休克指數": shock_index,
                "高危主訴": "有" if has_high_risk_cc else "無", "檢驗項目": lab_record_text, "系統判定": risk_level
            }])
            if not os.path.exists(LOG_FILE): new_record.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
            else: new_record.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

# ==========================================
# 模組 2：生命徵象趨勢 (查房)
# ==========================================
elif page == "📈 生命徵象趨勢 (查房)":
    st.title("📈 留觀生命徵象趨勢分析")
    batch_vitals = st.text_area("📋 請貼上 HIS 系統的多筆生命徵象表格：", height=200)
    if st.button("📊 解析與繪製趨勢", type="primary") and batch_vitals.strip() != "":
        df = parse_his_vitals(batch_vitals)
        if not df.empty:
            tab1, tab2, tab3 = st.tabs(["🗂️ 數據表", "📉 SI 趨勢", "💓 血流動力交叉圖"])
            with tab1:
                def highlight_risk(row):
                    si = row['休克指數 (SI)']
                    if pd.isna(si): return [''] * len(row)
                    elif si >= 1.0: return ['background-color: #ffcccc; color: #900000;'] * len(row)
                    elif si >= 0.8: return ['background-color: #fff2cc; color: #8a6d3b;'] * len(row)
                    else: return ['background-color: #e6ffe6; color: #2b542c;'] * len(row)
                st.dataframe(df.style.apply(highlight_risk, axis=1), use_container_width=True)
            with tab2: st.line_chart(df.set_index("時間")[["休克指數 (SI)"]], color="#FF4B4B")
            with tab3: st.line_chart(df.set_index("時間")[["心跳 (HR)", "收縮壓 (SBP)"]])

# ==========================================
# 模組 3：ABG 血液氣體判讀
# ==========================================
elif page == "🩸 ABG 血液氣體判讀":
    st.title("🩸 動脈血液氣體分析 (ABG) 快速判讀")
    abg_input = st.text_area("📋 請貼上 HIS 系統的 Blood Gas 報告：", height=200)
    if st.button("🔬 解析 ABG 報告", type="primary") and abg_input.strip() != "":
        ph = float(re.search(r'pH\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pH\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        pco2 = float(re.search(r'pCO2\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pCO2\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        hco3 = float(re.search(r'HCO3\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'HCO3\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        po2 = float(re.search(r'pO2\s+([\d.]+)', abg_input, re.IGNORECASE).group(1)) if re.search(r'pO2\s+([\d.]+)', abg_input, re.IGNORECASE) else None
        if ph and pco2 and hco3:
            ph_status = "正常" if 7.35 <= ph <= 7.45 else "酸血症" if ph < 7.35 else "鹼血症"
            primary, comp = "", ""
            if ph < 7.35:
                if pco2 > 45 and hco3 < 22: primary = "混合性酸中毒"
                elif pco2 > 45: primary, comp = "呼吸性酸中毒", "伴隨代償" if hco3 > 26 else "(未代償)"
                elif hco3 < 22: primary, comp = "代謝性酸中毒", "伴隨代償" if pco2 < 35 else "(未代償)"
            elif ph > 7.45:
                if pco2 < 35 and hco3 > 26: primary = "混合性鹼中毒"
                elif pco2 < 35: primary, comp = "呼吸性鹼中毒", "伴隨代償" if hco3 < 22 else "(未代償)"
                elif hco3 > 26: primary, comp = "代謝性鹼中毒", "伴隨代償" if pco2 > 45 else "(未代償)"
            else: primary = "正常或完全代償"
            oxy = "正常" if po2 and po2 >= 80 else "低血氧" if po2 else "未提供"
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("pH", ph, ph_status, delta_color="inverse")
            col2.metric("pCO2", pco2, "異常" if pco2<35 or pco2>45 else "正常", delta_color="inverse")
            col3.metric("HCO3", hco3, "異常" if hco3<22 or hco3>26 else "正常", delta_color="inverse")
            if po2: col4.metric("pO2", po2, oxy, delta_color="inverse")
            st.code(f"[ABG 判讀]\npH {ph} / pCO2 {pco2} / HCO3 {hco3} / pO2 {po2}\n判讀: {primary} {comp} ({oxy})", language="text")

# ==========================================
# 模組 4：綜合抽血報告 (含自動飲食防呆)
# ==========================================
elif page == "💉 血液檢驗報告 (CBC+BCS)":
    st.title("💉 綜合抽血報告快速判讀 (CBC + BCS)")
    blood_input = st.text_area("📋 請貼上抽血報告 (可直接 Ctrl+A 全選貼上)：", height=250)
    if st.button("🔬 綜合解析報告", type="primary") and blood_input.strip() != "":
        wbc = float(re.search(r'WBC\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'WBC\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        hb = float(re.search(r'Hb\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'Hb\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        mcv = float(re.search(r'MCV\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'MCV\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        n_band = float(re.search(r'N\.?band\.?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'N\.?band\.?\s+([\d.]+)', blood_input, re.IGNORECASE) else 0.0
        n_seg = float(re.search(r'N\.?seg\.?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'N\.?seg\.?\s+([\d.]+)', blood_input, re.IGNORECASE) else 0.0
        
        na = float(re.search(r'Na\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'Na\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        k = float(re.search(r'K\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'K\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        glu = float(re.search(r'GLU\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'GLU\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        bun = float(re.search(r'BUN\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'BUN\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        cre_matches = re.findall(r'CRE\s+([\d.]+)', blood_input, re.IGNORECASE)
        cre = float(cre_matches[0]) if cre_matches else None
        egfr = float(re.search(r'eGFR[^\n\d]*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'eGFR[^\n\d]*([\d.]+)', blood_input, re.IGNORECASE) else None
        ast = float(re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        alt = float(re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', blood_input, re.IGNORECASE) else None
        
        tbil = float(re.search(r'(?:T[\.\-]?Bil|Total Bilirubin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'(?:T[\.\-]?Bil|Total Bilirubin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE) else None
        dbil = float(re.search(r'(?:D[\.\-]?Bil|Direct Bilirubin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'(?:D[\.\-]?Bil|Direct Bilirubin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE) else None
        alb = float(re.search(r'(?:Alb|Albumin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'(?:Alb|Albumin)[^\d\n]*([\d.]+)', blood_input, re.IGNORECASE) else None
        ca = float(re.search(r'\b(?:Ca|Calcium)\s*[:=]?\s*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'\b(?:Ca|Calcium)\s*[:=]?\s*([\d.]+)', blood_input, re.IGNORECASE) else None
        mg = float(re.search(r'\b(?:Mg|Magnesium)\s*[:=]?\s*([\d.]+)', blood_input, re.IGNORECASE).group(1)) if re.search(r'\b(?:Mg|Magnesium)\s*[:=]?\s*([\d.]+)', blood_input, re.IGNORECASE) else None

        anc, anc_status = None, "未提供 WBC"
        if wbc:
            anc = round(wbc * 1000 * ((n_band + n_seg) / 100), 1)
            anc_status = "🔴 重度低下 (<500)" if anc < 500 else "🟡 中度低下 (<1000)" if anc < 1000 else "🟡 輕度低下 (<1500)" if anc < 1500 else "🟢 正常"
        anemia_status = "無明顯貧血"
        if hb and hb < 12.0: anemia_status = f"🟡 小球性貧血" if mcv and mcv < 80 else f"🟡 大球性貧血" if mcv and mcv > 100 else "🟡 正球性貧血"
        na_status = "正常" if na and 135 <= na <= 145 else "異常" if na else "未提供"
        k_status = "🚨 危急值" if k and (k < 3.0 or k > 6.0) else "異常" if k and (k < 3.5 or k > 5.1) else "正常" if k else "未提供"
        bc_ratio = round(bun / cre, 1) if bun and cre else None
        renal_status = "正常"
        if bc_ratio and bc_ratio > 20: renal_status = f"🔴 腎前性氮血症 (Ratio={bc_ratio} > 20)"
        elif cre and cre > 1.3: renal_status = "🟡 腎功能損傷"
        ckd_status = "Stage 1 (≥90)" if egfr and egfr >= 90 else "Stage 2 (60-89)" if egfr and egfr >= 60 else "Stage 3a (45-59)" if egfr and egfr >= 45 else "Stage 3b (30-44)" if egfr and egfr >= 30 else "Stage 4 (15-29)" if egfr and egfr >= 15 else "Stage 5 (<15)" if egfr else "未提供"
        liver_status = "🚨 猛爆性肝損傷 (>1000)" if ast and alt and (ast > 1000 or alt > 1000) else "🟡 肝炎" if ast and alt and (ast > 100 or alt > 100) else "正常"
        
        corr_ca = round(ca + 0.8 * (4.0 - alb), 2) if ca and alb else None
        ca_display = corr_ca if corr_ca else ca
        ca_status = "🚨 危急值" if ca_display and (ca_display < 6.5 or ca_display > 13.0) else "異常" if ca_display and (ca_display < 8.5 or ca_display > 10.5) else "正常"
        mg_status = "異常" if mg and (mg < 1.5 or mg > 2.5) else "正常"
        bil_status = "異常" if tbil and tbil > 1.2 else "正常"

        # --- 全新加入：依據抽血報告的自動飲食防呆 ---
        diet_warning = "🟢 飲食無特殊禁忌"
        if (k and k > 5.1) or (egfr and egfr < 45):
            diet_warning = "⚠️ 飲食禁忌：嚴格限鉀、限磷，並依醫囑注意水份控制 (Renal Diet)。"
        elif glu and glu > 250:
            diet_warning = "⚠️ 飲食禁忌：糖尿病飲食 (DM Diet)，避免精緻糖及過量澱粉。"
        elif ast and ast > 500:
            diet_warning = "⚠️ 飲食禁忌：肝炎狀態，避免高脂、加工食品，若有腹水需嚴格限鈉。"

        st.markdown("### 🧫 血液常規 (CBC & DC)")
        c1, c2, c3, c4 = st.columns(4)
        if wbc: c1.metric("WBC", wbc); c2.metric("ANC", anc, anc_status.split(" ")[1] if anc < 1500 else "正常", delta_color="inverse" if anc < 1500 else "normal")
        if hb: c3.metric("Hb", hb, anemia_status.split(" ")[1] if hb < 12.0 else "正常", delta_color="inverse" if hb < 12.0 else "normal"); c4.metric("MCV", mcv)

        st.markdown("### 🧪 生化基礎與肝腎功能 (BCS)")
        b1, b2, b3, b4 = st.columns(4)
        if na: b1.metric("Na", na, na_status, delta_color="inverse" if na_status != "正常" else "normal")
        if k: b2.metric("K", k, k_status, delta_color="inverse" if k_status != "正常" else "normal")
        if cre: b3.metric("CRE", cre, "異常" if cre>1.3 else "正常", delta_color="inverse" if cre>1.3 else "normal")
        if egfr: b4.metric("eGFR", egfr, ckd_status.split(" ")[0], delta_color="inverse" if egfr<60 else "normal")

        st.markdown("### 🧪 進階電解質與肝膽指標 (Advanced BCS)")
        a1, a2, a3, a4 = st.columns(4)
        if tbil: a1.metric("T-Bil", tbil, bil_status.split(" ")[0], delta_color="inverse" if tbil > 1.2 else "normal")
        if alb: a2.metric("Albumin", alb, "偏低" if alb < 3.5 else "正常", delta_color="inverse" if alb < 3.5 else "normal")
        if ca_display: a3.metric("Ca (校正鈣)" if corr_ca else "Ca", ca_display, ca_status.split(" ")[0], delta_color="inverse" if ca_status != "正常" else "normal")
        if mg: a4.metric("Mg", mg, mg_status, delta_color="inverse" if mg_status != "正常" else "normal")
        
        if bc_ratio and bc_ratio > 20: st.error(f"**💧 體液與腎臟：** {renal_status}")
        if ast and (ast > 100 or alt > 100): st.warning(f"**🩸 肝臟功能：** {liver_status}")
        if corr_ca and corr_ca != ca: st.info(f"**🦴 鈣離子校正：** 因 Albumin 為 {alb}，測量鈣 {ca} 經校正後為 **{corr_ca}**。")
        
        st.code(f"""[抽血檢驗判讀]
1. 免疫：ANC {anc} / 貧血：Hb {hb} ({anemia_status})
2. 腎臟：BUN/CRE {bc_ratio} ({renal_status}) / CKD: {ckd_status.split(' ')[0]}
3. 肝膽：AST {ast} / ALT {alt} ({liver_status.split(' ')[0]})\n4. 電解質：Na {na} / K {k} / Ca(校正) {ca_display} / Mg {mg}
5. 飲食衛教：{diet_warning}""", language="text")

# ==========================================
# 模組 5：ADA 標準 DKA/HHS 動態導航系統
# ==========================================
elif page == "💧 DKA/HHS 動態導航 (ADA標準)":
    st.title("🚨 ADA 標準 DKA/HHS 動態導航系統")
    st.markdown("**基於美國糖尿病學會 (ADA) 高血糖危機處置指引，內建滲透壓與動態血鉀防護**")
    disease_type = st.radio("👉 請選擇病患的疾病型態：", ["DKA (糖尿病酮酸血症) - 轉換點 200", "HHS (高滲透壓高血糖狀態) - 轉換點 300"], horizontal=True)

    tab1, tab2 = st.tabs(["Phase 1: 初始評估與給藥 (Initial)", "Phase 2: 動態滴定與轉換 (Titration)"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            weight_p1 = st.number_input("病患體重 (kg)", min_value=30.0, max_value=200.0, value=60.0, step=1.0, key="w1")
            init_gluc = st.number_input("初始血糖 (mg/dL)", min_value=50, max_value=2000, value=450, step=10, key="g1")
            ph_val = st.number_input("動脈/靜脈 pH 值", min_value=6.0, max_value=7.5, value=7.1, step=0.01, key="ph1")
        with col2:
            init_k = st.number_input("初始血鉀 K+ (mEq/L)", min_value=1.0, max_value=10.0, value=4.0, step=0.1, key="k1")
            init_na = st.number_input("測量血鈉 Na+ (mEq/L)", min_value=100, max_value=200, value=135, step=1, key="na1")

        if st.button("計算 ADA 初始醫囑", type="primary", key="btn1"):
            st.divider()
            st.subheader("🧠 0. 有效血液滲透壓")
            eff_osmo = (2 * init_na) + (init_gluc / 18)
            st.markdown(f"有效滲透壓為：**{eff_osmo:.1f} mOsm/kg**")
            if eff_osmo > 320: st.error("🚨 **診斷提示：滲透壓 > 320 mOsm/kg！** (典型 HHS，前期需極度積極補充水分)")
            else: st.info("💡 滲透壓 ≤ 320 mOsm/kg。")

            st.subheader("💧 1. 初始液體復甦 (第一小時)")
            st.info("優先給予 **0.9% NaCl** 1000 - 1500 mL/hr 快速滴注。")

            st.subheader("🛑 2. 血鉀檢核 (Potassium Check)")
            if init_k < 3.3: st.error(f"**絕對禁忌：血鉀 {init_k} < 3.3 mEq/L！**\n\n**HOLD INSULIN (禁止啟動胰島素)！**\n請先補充 KCl，直到 K+ ≥ 3.3。")
            elif 3.3 <= init_k <= 5.3: st.success(f"**血鉀 {init_k} mEq/L (安全範圍)。**\n允許啟動 Insulin。於點滴中加入 **20-30 mEq KCl**。")
            else: st.warning(f"**血鉀 {init_k} mEq/L (偏高)。**\n允許啟動 Insulin。點滴**暫不加鉀**。")

            st.subheader("🧪 3. 校正血鈉與維持輸液 (第二小時起)")
            factor_used = 1.6 if init_gluc <= 400 else 2.4
            corr_na = init_na + factor_used * ((init_gluc - 100) / 100)
            st.markdown(f"校正血鈉為：**{corr_na:.1f} mEq/L**")
            if corr_na >= 135: st.warning("👉 維持點滴改掛 **0.45% NaCl** (250-500 mL/hr)。")
            else: st.success("👉 維持點滴續掛 **0.9% NaCl** (250-500 mL/hr)。")

            st.subheader("💉 4. 胰島素初始給藥")
            if init_k >= 3.3: st.info(f"**作法 A**：IV Bolus **{(weight_p1 * 0.1):.1f} U**，隨後 Pump **{(weight_p1 * 0.1):.1f} mL/hr**。\n* **作法 B**：無 Bolus，Pump **{(weight_p1 * 0.14):.1f} mL/hr**。")

            st.subheader("🩺 5. 酸鹼平衡 (Bicarbonate)")
            if ph_val < 6.9: st.error(f"**pH {ph_val} < 6.9：極度酸血症！**\n建議給予 100 mmol NaHCO3 滴注。")
            else: st.success(f"**pH {ph_val} ≥ 6.9**：不建議給予碳酸氫鈉。")

    with tab2:
        col3, col4 = st.columns(2)
        with col3:
            weight_p2 = st.number_input("病患體重 (kg)", min_value=30.0, max_value=200.0, value=60.0, step=1.0, key="w2")
            old_gluc = st.number_input("前次血糖 (mg/dL)", min_value=20, max_value=1500, value=300, step=10, key="g2_old")
        with col4:
            new_gluc = st.number_input("最新血糖 (mg/dL)", min_value=20, max_value=1500, value=250, step=10, key="g2_new")
            current_rate = st.number_input("目前 Pump 速率 (mL/hr)", min_value=0.0, max_value=50.0, value=6.0, step=0.5, key="r2")

        st.markdown("---")
        has_new_k = st.checkbox("有 4 小時內的最新血鉀 (K+) 報告", value=False)
        new_k = None
        if has_new_k: new_k = st.number_input("輸入最新血鉀 K+ (mEq/L)", min_value=1.0, max_value=10.0, value=4.0, step=0.1, key="k2")

        if st.button("計算 ADA 最新滴數", type="primary", key="btn2"):
            st.divider()
            if has_new_k and new_k < 3.3:
                st.error(f"🛑 **動態血鉀攔截：最新血鉀 {new_k} < 3.3 mEq/L！**\n\n**必須立刻關閉 Insulin Pump！**\n請先靜脈補充 KCl，待 K+ ≥ 3.3 後再啟動。")
                st.stop()
            elif has_new_k and new_k > 5.3: st.warning(f"⚠️ **最新血鉀 {new_k} > 5.3 mEq/L**：請確認已停止加入 KCl。")
            elif has_new_k: st.success(f"✅ **最新血鉀 {new_k} mEq/L (安全)**：確認點滴中持續加入 KCl。")

            st.markdown("---")
            target_threshold = 200 if "DKA" in disease_type else 300
            target_range = "150-200" if "DKA" in disease_type else "200-300"
            drop = old_gluc - new_gluc
            
            if new_gluc < 70:
                st.error("🆘 **嚴重低血糖 (< 70 mg/dL)！**\n立刻關閉 Insulin Pump！給予 D50W 推注，並改為 Q15min 密切監測。")
            elif new_gluc <= target_threshold:
                min_rate = max(0.5, weight_p2 * 0.02)
                half_rate = max(min_rate, current_rate / 2)
                st.error(f"🚨 **ADA 關鍵防護期**：{disease_type} 血糖已達 {new_gluc} mg/dL！\n必須**立刻**執行：")
                st.warning("1. **加糖**：維持點滴立即加入 5% 葡萄糖 (改為 **D5W + 0.45% NaCl**)。")
                st.warning(f"2. **降速**：建議直接將原速率減半為 **{half_rate:.1f} mL/hr**。")
                st.info(f"🎯 **後續 ADA 目標**：將血糖穩定鎖定在 **{target_range} mg/dL** 之間，直到酸中毒解除。")
            else:
                st.write(f"過去期間血糖降幅：**{drop:.0f} mg/dL**")
                if (new_gluc <= target_threshold + 50) and (drop > 75):
                    st.warning(f"⚠️ **邊界趨勢預警**：極可能即將跌破防護線 ({target_threshold})，請預先準備含糖輸液 (D5W)。")

                if drop < 50:
                    doubled_rate = current_rate * 2
                    if doubled_rate > 15.0: st.error(f"🛑 **滴數已達安全上限 ({doubled_rate:.1f} mL/hr)！**\n請強烈懷疑 **IV 管路漏針 (Infiltration)** 或阻塞！")
                    else: st.warning(f"📉 **降幅 < 50 mg/dL (降太慢)**：\n建議新滴數：**{doubled_rate:.1f} mL/hr**")
                elif 50 <= drop <= 75:
                    st.success(f"✨ **降幅 50-75 mg/dL (完美達標)**：\n🎯 **維持滴數：{current_rate:.1f} mL/hr**")
                else:
                    adjust = weight_p2 * 0.05
                    min_allowed = max(0.5, weight_p2 * 0.02)
                    new_rate = max(min_allowed, current_rate - adjust)
                    st.warning(f"📉 **降幅 > 75 mg/dL (降太快)**：\n建議適度調降 Pump 速率。\n👉 建議新滴數：**{new_rate:.1f} mL/hr**")

# ==========================================
# 全域頁尾
# ==========================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.85em;">
    <p><strong>© 2026 急診臨床決策輔助系統 (ER Clinical Decision Support)</strong></p>
    <p>💡 <b>System Design & Clinical Logic by：</b>花蓮慈濟醫學中心 急診護理師 吳智弘 (D-MAT / BLS Instructor)</p>
    <p>⚠️ <b>免責聲明：</b>本系統基於臨床實證醫學 (EBP) 開發，不可替代臨床醫師之專業診斷。</p>
</div>
""", unsafe_allow_html=True)
