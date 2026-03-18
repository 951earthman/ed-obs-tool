import streamlit as st
import pandas as pd
import re
from datetime import datetime
import os

# ==========================================
# 系統設定與全域變數
# ==========================================
st.set_page_config(page_title="急診臨床決策輔助系統", page_icon="🚨", layout="wide")

# ==========================================
# 🔒 全域密碼防護網 (專利保護機制)
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def check_password():
    # 👉 這裡的 "tzuchi2026" 就是你的全域密碼，請自行修改成你想要的密碼！
    if st.session_state["global_pwd"] == "asd55660":
        st.session_state["authenticated"] = True
    else:
        st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    # 這是被擋在門外的人會看到的畫面
    st.title("🔒 系統已上鎖 (智財保護與封測中)")
    st.warning("⚠️ 本系統目前進入專利申請與封閉測試階段。未經授權之人員請勿登入或側錄。")
    st.text_input("🔑 請輸入全域通行密碼解鎖系統：", type="password", key="global_pwd", on_change=check_password)
    
    if st.session_state.get("global_pwd") and not st.session_state["authenticated"]:
        st.error("❌ 密碼錯誤，請重新輸入！")
        
    st.stop()  # 🛑 這行是靈魂！密碼沒過，後方的所有醫療邏輯與 UI 絕對不會被渲染出來！

# ==========================================
# 系統往下繼續執行 (密碼正確才會走到這裡)
# ==========================================
LOG_FILE = "assessment_log.csv"
FEEDBACK_FILE = "feedback_log.csv"
SYSTEM_VERSION = "v17.1"
LAST_UPDATE = "2026-03"
NEXT_REVIEW = "2027-01 (配合 ADA 最新指引發布)"
# ==========================================
# 核心解析神經中樞
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
# 側邊欄 (Sidebar)
# ==========================================
st.sidebar.title("🏥 急診超級瑞士刀")
page = st.sidebar.radio("請選擇功能模組：", [
    "📝 留觀風險評估 (交班)", 
    "📈 生命徵象趨勢 (查房)",
    "🩸 ABG 血液氣體判讀",
    "💉 血液檢驗報告 (CBC+BCS)",
    "💧 DKA/HHS 動態導航 (ADA標準)",
    "📖 參考文獻與系統更新",
    "💬 系統意見反饋"
])

st.sidebar.divider()
st.sidebar.subheader("🔗 實用快速連結")
st.sidebar.markdown("💊 [**院內藥物查詢系統**](https://hldrug.tzuchi.com.tw/tchw/IphqryChinese/DesktopModules/WesternMedicine/Pill_Search.aspx?Hospital=HL)", unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.subheader("📚 臨床機轉小寶典 (EBP)")
search_query = st.sidebar.text_input("🔍 搜尋 (例: 敗血症, 酮體, 鉀)", "").strip().lower()

ebp_dict = {
    "Sepsis 敗血症黃金一小時 (Hour-1 Bundle)": "SSC 2021 指引：當 MAP < 65 或 Lactate ≥ 4.0，須於 3 小時內給予 30 mL/kg 輸液(首選 LR/平衡液)。未達標則啟動 Levophed 維持 MAP ≥ 65。給抗生素前須完成兩套 Blood Culture。",
    "預警分數 (MEWS/PEWS) 與休克指數": "MEWS ≥ 5 分 或 SI ≥ 1.0 代表高度休克風險。PEWS 整合兒童行為、膚色與呼吸費力程度提供早期預警。",
    "高危輸液 (IV Pump) 與假性穩定": "依賴升壓劑維持血壓即代表重度心血管衰竭，無視當下血壓直接列為紅區。",
    "鈣離子校正 (Corrected Ca) 與鎂離子 (Mg)": "Albumin < 4.0 會導致假性低血鈣，校正公式：Ca + 0.8×(4.0-Alb)。Mg < 1.5 易引發致命心律不整 (TdP) 及頑固性低血鉀。",
    "肝功能與黃疸 (AST/ALT/Bil)": "AST/ALT > 100 提示實質性肝炎；> 1000 強烈提示猛爆性肝炎或缺血性肝炎 (Shock Liver)。",
    "腎臟功能與 BUN/CRE 比例": "BUN/CRE > 20 提示腎前性氮血症 (Prerenal Azotemia)，常見於嚴重脫水或 GI Bleeding。",
    "DKA 為什麼會變酸？ (機轉)": "【絕對缺乏胰島素】當體內沒有胰島素時，細胞開始瘋狂分解脂肪。脂肪分解的副產物就是「酮體 (Ketones)」造成酸中毒。打 Insulin 是為了關閉酮體工廠！",
    "HHS 為什麼會極度脫水？ (機轉)": "【相對缺乏胰島素】微量胰島素足以阻止脂肪分解(無酮體)，但超高血糖會從腎臟引發「滲透壓性利尿」，把水分大量排光。HHS 前期大量灌注 N/S 比打 Insulin 更重要！",
    "致命陷阱：血鉀的捉迷藏 (K+ Shift)": "嚴重酸血症時身體會把 K+ 趕出細胞到血液中，抽血正常或偏高其實是「假象」！打了 Insulin 瞬間把 K+ 掃回細胞內會引發致命性低血鉀。",
    "為什麼會有假性低血鈉？ (校正公式)": "血管極高葡萄糖產生巨大滲透壓，把水分吸進血管稀釋血鈉。必須用 1.6 或 2.4 的常數去「還原」真實血鈉。",
    "防護期：預防腦水腫 (Cerebral Edema)": "高血糖時腦細胞內有滲透壓物質。若 Insulin 把血糖降得太快，水分會瘋狂灌進腦細胞引發腦水腫。所以必須提早踩煞車加 D5W。"
}

found = False
for title, content in ebp_dict.items():
    if search_query == "" or search_query in title.lower() or search_query in content.lower():
        found = True
        with st.sidebar.expander(title, expanded=(search_query != "")):
            st.write(content)

st.sidebar.divider()
st.sidebar.subheader("🔒 管理員後台")
admin_password = st.sidebar.text_input("輸入密碼解鎖", type="password")
if admin_password == "alex":
    st.sidebar.success("✅ 身分驗證成功")
    tab_log, tab_fb = st.sidebar.tabs(["📝 評估紀錄", "💬 意見反饋"])
    with tab_log:
        if os.path.exists(LOG_FILE):
            df_log = pd.read_csv(LOG_FILE)
            st.download_button("📥 下載紀錄", data=df_log.to_csv(index=False, encoding='utf-8-sig'), file_name="ed_obs_log.csv", mime="text/csv", use_container_width=True)
            if st.button("🗑️ 清空紀錄", use_container_width=True): os.remove(LOG_FILE); st.rerun()
    with tab_fb:
        if os.path.exists(FEEDBACK_FILE):
            df_fb = pd.read_csv(FEEDBACK_FILE)
            st.download_button("📥 下載反饋", data=df_fb.to_csv(index=False, encoding='utf-8-sig'), file_name="ed_feedback_log.csv", mime="text/csv", use_container_width=True)
            if st.button("🗑️ 清空反饋", use_container_width=True): os.remove(FEEDBACK_FILE); st.rerun()

# ==========================================
# 模組 1：留觀單次評估 (含隱形 Sepsis 防護網)
# ==========================================
if page == "📝 留觀風險評估 (交班)":
    st.title("🚨 急診留觀風險自動評估與交班")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS標準)", "👶 兒科 (PEWS標準)"], horizontal=True)
    with col_t2:
        # 為了計算 Sepsis 30mL/kg 輸液量，加入體重欄位
        weight_input = st.number_input("⚖️ 病患體重 (kg, 供急救輸液運算)", min_value=10.0, max_value=200.0, value=60.0, step=1.0)

    vitals_input = st.text_area("📋 1. 請貼上單次生命徵象 (含收縮壓/舒張壓)：", height=100, placeholder="體溫：36.5\n脈搏：110\n呼吸：22\n血壓：85/50...")
    
    total_score = 0
    if patient_type == "🧑 成人 (MEWS標準)":
        gcs_input = st.number_input("🧠 意識狀態 (GCS 分數) ⚠️必填", min_value=3, max_value=15, value=None, step=1)
        log_score_name = "MEWS"
    else:
        gcs_input = 15 
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
                                  ["🧠 癲癇/TIA", "🫀 暈厥/胸痛", "🩸 疑似 GI Bleeding", "🫁 嚴重氣喘/COPD", "☠️ 嚴重低血糖/酒精戒斷", "🦠 疑似嚴重感染/敗血症 (Sepsis)"])

    st.subheader("🧪 4. 補充檢驗報告")
    col1, col2 = st.columns(2)
    with col1: k_input, crp_input = st.text_input("➤ K："), st.text_input("➤ CRP：")
    with col2: tni_input, lactate_input = st.text_input("➤ Hs-TnI："), st.text_input("➤ Lactate：")

    if st.button("🚀 開始評估並生成紀錄", type="primary"):
        if vitals_input.strip() == "": st.error("⚠️ 請先貼上生命徵象！")
        elif patient_type == "🧑 成人 (MEWS標準)" and gcs_input is None: st.error("⚠️ 請輸入 GCS 意識分數！")
        else:
            temp = hr = rr = sbp = dbp = None 
            if re.search(r'體溫：([\d.]+)', vitals_input): temp = float(re.search(r'體溫：([\d.]+)', vitals_input).group(1))
            if re.search(r'脈搏：(\d+)', vitals_input): hr = int(re.search(r'脈搏：(\d+)', vitals_input).group(1))
            if re.search(r'呼吸：(\d+)', vitals_input): rr = int(re.search(r'呼吸：(\d+)', vitals_input).group(1))
            
            # 升級：同時抓取收縮壓 (sbp) 與舒張壓 (dbp) 來算 MAP
            bp_match = re.search(r'血壓：(\d+)/(\d+)', vitals_input)
            if bp_match: 
                sbp = int(bp_match.group(1))
                dbp = int(bp_match.group(2))

            # 計算 MAP
            map_val = round((sbp + 2 * dbp) / 3, 1) if (sbp and dbp) else None

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
            lac_val = None
            if lactate_input.strip():
                lac_val = float(lactate_input)
                if lac_val >= 4.0: lab_alert = True
                lab_records_list.append(f"Lac {lac_val}")
                
            if k_input.strip() and (float(k_input) < 3.0 or float(k_input) > 6.0): lab_alert = True; lab_records_list.append(f"K {k_input}")
            elif k_input.strip(): lab_records_list.append(f"K {k_input}")
            if tni_input.strip() and float(tni_input) > 17.5: lab_alert = True; lab_records_list.append(f"TnI {tni_input}")
            elif tni_input.strip(): lab_records_list.append(f"TnI {tni_input}")
            if crp_input.strip() and float(crp_input) >= 10.0: lab_alert = True; lab_records_list.append(f"CRP {crp_input}(≥10)")
            elif crp_input.strip(): lab_records_list.append(f"CRP {crp_input}")
            
            lab_record_text = " / ".join(lab_records_list) if lab_records_list else "無異常"

            has_vasopressor = any("Levophed" in p or "easydopamine" in p for p in iv_pumps)
            has_vasodilator = any("Isoket" in p or "Perdipine" in p for p in iv_pumps)
            pump_record_text = " / ".join(iv_pumps) if iv_pumps else "無"
            
            has_high_risk_cc = len(high_risk_cc) > 0
            cc_record_text = " / ".join(high_risk_cc) if has_high_risk_cc else "無"

            diet_warning = "🟢 飲食建議：普通飲食 (Normal Diet) 或依醫囑。"
            if gcs_input is not None and gcs_input <= 12: diet_warning = "🛑 飲食建議：絕對 NPO (禁食)！意識不清預防吸入性肺炎。"
            elif has_high_risk_cc and any("GI Bleeding" in cc for cc in high_risk_cc): diet_warning = "🛑 飲食建議：絕對 NPO (禁食)！保留內視鏡空腹時間。"
            elif has_high_risk_cc and any("氣喘" in cc or "癲癇" in cc for cc in high_risk_cc): diet_warning = "⚠️ 飲食建議：暫時 NPO 或視情況給予流質。"

            # 判斷總結
            if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0) or has_vasopressor:
                risk_level, disposition = "🔴 紅區", "具高度惡化休克風險，建議收治或轉急救區。"
                st.error(f"判定：{risk_level}")
            elif total_score >= 3 or has_vasodilator or has_high_risk_cc:
                risk_level, disposition = "🟡 黃區", "潛在突發惡化風險，請落實密切監測並縮短 Vital signs 頻率。"
                st.warning(f"判定：{risk_level}")
            else:
                risk_level, disposition = "🟢 綠區", "生命徵象穩定，持續常規留觀。"
                st.success(f"判定：{risk_level}")

            # ==========================================
            # 🩸 隱形式 Sepsis 黃金一小時警報系統
            # ==========================================
            sepsis_triggered = False
            if (lac_val and lac_val >= 4.0) or (map_val and map_val < 65):
                sepsis_triggered = True
                fluid_goal = int(weight_input * 30)
                st.error(f"""### 🚨 [Sepsis 敗血症黃金一小時警報]
觸發條件：發現 MAP < 65 ({map_val}) 或 Lactate ≥ 4.0 ({lac_val})。

**【SSC 2021 敗血症處置建議 (Hour-1 Bundle)】：**
1. 💧 **目標輸液量**：體重 {weight_input} kg × 30 mL/kg = **{fluid_goal} mL** (建議於 3 小時內給予平衡性晶體輸液如 LR/Plasma-Lyte)。
2. 🫀 **血壓標的**：若輸液後 MAP 仍 < 65 mmHg，請準備啟動 **Norepinephrine (Levophed)**。
3. 🩸 **血液培養**：請於給予抗生素「前」完成 Blood Culture (兩套)。
4. 💊 **抗生素**：盡速給予廣效性抗生素 (Broad-spectrum IV antibiotics)。
5. 🧪 **乳酸追蹤**：若初始 Lactate > 2.0，請於 2-4 小時內重驗。""")

            st.code(f"""[留觀風險自動評估紀錄]
1. 對象：{patient_type}
2. 生理：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}/{dbp} (MAP: {map_val})
3. 預警：{score_display} / SI {shock_index}
4. 輸液/風險：{pump_record_text} / {cc_record_text}
5. 檢驗：{lab_record_text}
6. 判定/處置：{risk_level} - {disposition}
7. 飲食動向：{diet_warning}
{"8. Sepsis Bundle: 已達標高風險條件，建議啟動 30mL/kg 輸液與 1-Hour Bundle 流程。" if sepsis_triggered else ""}""", language="text")

            new_record = pd.DataFrame([{
                "評估時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "類別": log_score_name, "分數": total_score, "休克指數": shock_index,
                "高危主訴": "有" if has_high_risk_cc else "無", "檢驗項目": lab_record_text, "系統判定": risk_level
            }])
            if not os.path.exists(LOG_FILE): new_record.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
            else: new_record.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

# ==========================================
# 模組 2-7 保留不動 (趨勢/ABG/CBC/DKA/更新/反饋)
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
            anc_status = "🔴 重度 (<500)" if anc < 500 else "🟡 中度 (<1000)" if anc < 1000 else "🟡 輕度 (<1500)" if anc < 1500 else "🟢 正常"
        anemia_status = "無明顯貧血"
        if hb and hb < 12.0: anemia_status = f"🟡 小球性貧血" if mcv and mcv < 80 else f"🟡 大球性貧血" if mcv and mcv > 100 else "🟡 正球性貧血"
        na_status = "正常" if na and 135 <= na <= 145 else "異常" if na else "未提供"
        k_status = "🚨 危急值" if k and (k < 3.0 or k > 6.0) else "異常" if k and (k < 3.5 or k > 5.1) else "正常" if k else "未提供"
        bc_ratio = round(bun / cre, 1) if bun and cre else None
        renal_status = "正常"
        if bc_ratio and bc_ratio > 20: renal_status = f"🔴 腎前性氮血症"
        elif cre and cre > 1.3: renal_status = "🟡 腎功能損傷"
        ckd_status = "Stage 1 (≥90)" if egfr and egfr >= 90 else "Stage 2 (60-89)" if egfr and egfr >= 60 else "Stage 3a (45-59)" if egfr and egfr >= 45 else "Stage 3b (30-44)" if egfr and egfr >= 30 else "Stage 4 (15-29)" if egfr and egfr >= 15 else "Stage 5 (<15)" if egfr else "未提供"
        liver_status = "🚨 猛爆性肝損傷" if ast and alt and (ast > 1000 or alt > 1000) else "🟡 肝炎" if ast and alt and (ast > 100 or alt > 100) else "正常"
        
        corr_ca = round(ca + 0.8 * (4.0 - alb), 2) if ca and alb else None
        ca_display = corr_ca if corr_ca else ca
        ca_status = "🚨 危急值" if ca_display and (ca_display < 6.5 or ca_display > 13.0) else "異常" if ca_display and (ca_display < 8.5 or ca_display > 10.5) else "正常"
        mg_status = "異常" if mg and (mg < 1.5 or mg > 2.5) else "正常"

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
        if tbil: a1.metric("T-Bil", tbil)
        if alb: a2.metric("Albumin", alb)
        if ca_display: a3.metric("Ca (校正鈣)" if corr_ca else "Ca", ca_display, ca_status.split(" ")[0], delta_color="inverse" if ca_status != "正常" else "normal")
        if mg: a4.metric("Mg", mg, mg_status, delta_color="inverse" if mg_status != "正常" else "normal")
        
        if bc_ratio and bc_ratio > 20: st.error(f"**💧 體液與腎臟：** {renal_status}")
        if ast and (ast > 100 or alt > 100): st.warning(f"**🩸 肝臟功能：** {liver_status}")
        
        st.code(f"[抽血檢驗判讀]\n1. 免疫：ANC {anc} / 貧血：Hb {hb} ({anemia_status})\n2. 腎臟：BUN/CRE {bc_ratio} / CKD: {ckd_status.split(' ')[0]}\n3. 肝膽：AST {ast} / ALT {alt}\n4. 電解質：Na {na} / K {k} / Ca(校正) {ca_display} / Mg {mg}", language="text")

elif page == "💧 DKA/HHS 動態導航 (ADA標準)":
    st.title("🚨 ADA 標準 DKA/HHS 動態導航系統")
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
            eff_osmo = (2 * init_na) + (init_gluc / 18)
            if eff_osmo > 320: st.error(f"🚨 **滲透壓 > 320 mOsm/kg！** (典型 HHS，需積極補水)")
            
            st.info("💧 **初始液體**：優先給予 **0.9% NaCl** 1000 - 1500 mL/hr。")

            if init_k < 3.3: st.error(f"🛑 **絕對禁忌：血鉀 {init_k} < 3.3 mEq/L！**\n**HOLD INSULIN！** 請先補充 KCl。")
            elif 3.3 <= init_k <= 5.3: st.success(f"✅ **血鉀 {init_k} mEq/L**：允許啟動 Insulin。點滴加入 20-30 mEq KCl。")
            else: st.warning(f"⚠️ **血鉀 {init_k} mEq/L (偏高)**：允許啟動 Insulin。點滴暫不加鉀。")

            factor_used = 1.6 if init_gluc <= 400 else 2.4
            corr_na = init_na + factor_used * ((init_gluc - 100) / 100)
            if corr_na >= 135: st.warning("👉 維持點滴改掛 **0.45% NaCl** (250-500 mL/hr)。")
            else: st.success("👉 維持點滴續掛 **0.9% NaCl** (250-500 mL/hr)。")

            st.info(f"💉 **胰島素**：Pump 設定 **{(weight_p1 * 0.1):.1f} mL/hr**。")
            if ph_val < 6.9: st.error(f"🔴 **pH {ph_val} < 6.9**：建議給予 100 mmol NaHCO3。")

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
                st.error(f"🛑 **血鉀 {new_k} < 3.3 mEq/L！必須立刻關閉 Insulin Pump！**")
                st.stop()

            target_threshold = 200 if "DKA" in disease_type else 300
            drop = old_gluc - new_gluc
            
            if new_gluc < 70:
                st.error("🆘 **嚴重低血糖 (< 70 mg/dL)！立刻關閉 Insulin Pump！** 給予 D50W 推注。")
            elif new_gluc <= target_threshold:
                min_rate = max(0.5, weight_p2 * 0.02)
                half_rate = max(min_rate, current_rate / 2)
                st.error(f"🚨 **ADA 防護期**：血糖已達 {new_gluc} mg/dL！\n1. 點滴加入 5% 葡萄糖 (D5W+0.45%S)。\n2. 降速至 **{half_rate:.1f} mL/hr**。")
            else:
                if drop < 50:
                    doubled_rate = current_rate * 2
                    if doubled_rate > 15.0: st.error(f"🛑 **滴數已達上限 ({doubled_rate:.1f} mL/hr)！** 懷疑漏針或阻塞！")
                    else: st.warning(f"📉 **降幅 < 50 mg/dL**：建議新滴數 **{doubled_rate:.1f} mL/hr**")
                elif 50 <= drop <= 75:
                    st.success(f"✨ **降幅 50-75 mg/dL (完美達標)**：維持滴數 **{current_rate:.1f} mL/hr**")
                else:
                    adjust = weight_p2 * 0.05
                    new_rate = max(max(0.5, weight_p2 * 0.02), current_rate - adjust)
                    st.warning(f"📉 **降幅 > 75 mg/dL (降太快)**：建議新滴數 **{new_rate:.1f} mL/hr**")

elif page == "📖 參考文獻與系統更新":
    st.title("📖 參考文獻與系統版本紀錄")
    st.markdown("為確保臨床安全與決策品質，本系統之評估邏輯皆基於最新版國際醫學實證指引 (EBP) 建立。")
    st.info(f"🔄 **當前系統版本**：{SYSTEM_VERSION} (最後更新：{LAST_UPDATE})\n\n📅 **預計下次全系統學理審查**：{NEXT_REVIEW}")
    st.divider()
    st.subheader("📚 核心評估邏輯文獻來源")
    st.markdown("""
    | 臨床決策模組 | 國際指引 / 實證出處 |
    | :--- | :--- |
    | **Sepsis 敗血症黃金一小時** | Surviving Sepsis Campaign (SSC) 2021 Guidelines. |
    | **MEWS / PEWS 早期預警分數** | Royal College of Physicians (RCP), *National Early Warning Score (NEWS)*。 |
    | **DKA / HHS 動態導航系統** | American Diabetes Association (ADA). *Standards of Medical Care in Diabetes*. |
    | **CKD (慢性腎臟病) 分級** | KDIGO 2024 Clinical Practice Guideline. |
    | **急診留觀室 (EDOU) 高危主訴** | American College of Emergency Physicians (ACEP). |
    | **血鈉校正公式 (Hillier)** | Hillier TA, et al. *Hyponatremia: evaluating the correction factor for hyperglycemia.* |
    """)
    st.divider()
    st.subheader("📝 系統維護日誌 (Changelog)")
    st.markdown("""
    * **[v17.1] 2026-03**：於留觀評估中新增「隱形式 Sepsis 黃金一小時警報」，輸入 MAP 與 Lactate 達危險值自動觸發。
    * **[v17.0] 2026-03**：新增意見反饋區，升級雙層管理員後台。
    * **[v16.0] 2026-03**：新增 EBP 參考文獻與系統更新宣告。
    """)

elif page == "💬 系統意見反饋":
    st.title("💬 系統意見反饋與優化建議")
    st.markdown("本系統為花蓮慈濟急診專屬開發，您的每一個回饋都是系統進化的養分！")
    with st.form("feedback_form", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1: fb_name = st.text_input("您的稱呼 (可選填)：", placeholder="例：白班學妹")
        with col_f2: fb_type = st.selectbox("反饋類型：", ["🐞 系統錯誤 (Bug)", "💡 功能許願 (Feature Request)", "📚 學理邏輯建議 (EBP)", "🎨 介面操作不順手", "其他"])
        fb_content = st.text_area("請描述您的建議或遇到的問題 ⚠️必填：", height=150)
        if st.form_submit_button("🚀 送出反饋", type="primary", use_container_width=True):
            if fb_content.strip() == "": st.error("⚠️ 請填寫反饋內容喔！")
            else:
                new_fb = pd.DataFrame([{"時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "稱呼": fb_name if fb_name.strip() != "" else "匿名", "類型": fb_type, "內容": fb_content}])
                if not os.path.exists(FEEDBACK_FILE): new_fb.to_csv(FEEDBACK_FILE, index=False, encoding='utf-8-sig')
                else: new_fb.to_csv(FEEDBACK_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')
                st.success("✅ 感謝您的反饋！")

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
