import streamlit as st
import pandas as pd
import re
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
                bp_idx = i
                break
                
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
                            clean_bp_idx = i
                            break
                            
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
# 側邊欄導覽 (Sidebar Navigation)
# ==========================================
st.sidebar.title("🏥 急診超級瑞士刀")
page = st.sidebar.radio("請選擇功能模組：", [
    "📝 留觀風險評估 (交班)", 
    "📈 生命徵象趨勢 (查房)",
    "🩸 ABG 血液氣體判讀",
    "🧫 CBC/DC 血液常規判讀", 
    "🧪 生化檢驗 (BCS) 判讀", 
    "🔒 系統管理員後台"
])
st.sidebar.divider()
st.sidebar.caption("臨床實證醫學輔助系統 v10.0")

# ==========================================
# 模組 1：留觀單次評估與交班
# ==========================================
if page == "📝 留觀風險評估 (交班)":
    st.title("🚨 急診留觀風險自動評估與交班")
    with st.expander("📚 點此查看系統評分標準與學理依據 (EBP)"):
        st.markdown("""
        ### 1. 預警分數 (MEWS/PEWS) 與休克指數 (SI)
        * **MEWS ≥ 5 分** 或 **SI ≥ 1.0**：高度休克與惡化風險，列為紅區。
        ### 2. 高危險連續輸液 (IV Pump) & 潛在不穩定主訴
        * 依賴升壓劑直列紅區。癲癇、消化道出血等極易突發惡化，強制列「黃區」。
        ### 3. 危險檢驗數值 (Critical Labs)
        * **Lactate ≥ 4.0** / **CRP ≥ 10.0** / **K < 3.0 或 > 6.0** (紅區)。
        """)
    st.divider()

    patient_type = st.radio("👥 請選擇病患評估類別：", ["🧑 成人 (MEWS標準)", "👶 兒科 (PEWS標準)"], horizontal=True)
    vitals_input = st.text_area("📋 1. 請貼上單次生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)：", height=100)
    
    total_score = 0
    if patient_type == "🧑 成人 (MEWS標準)":
        gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1)
        log_score_name = "MEWS"
    else:
        st.info("💡 兒科病患優先依據下方『臨床表徵』進行 PEWS 風險計分。")
        age_group = st.selectbox("👶 選擇病童年齡區間：", ["0-3個月", "4-11個月", "1-4歲", "5-11歲", "12歲以上"])
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1: pews_behavior = st.radio("行為狀態", ["正常(0分)", "焦躁/嗜睡(1分)", "對痛無反應(2分)"])
        with col_p2: pews_cv = st.radio("心血管/膚色", ["粉紅/充填<2秒(0分)", "蒼白/充填2-3秒(1分)", "發紺/大理石斑/充填>3秒(2分)"])
        with col_p3: pews_resp = st.radio("呼吸狀態", ["正常且無費力(0分)", "呼吸急促/需給氧(1分)", "胸凹/呻吟/SPO2<90%(2分)"])
        log_score_name = "PEWS"

    st.subheader("💉 2. 高危險連續輸液 (IV Pump)")
    iv_pumps = st.multiselect("➤ 病患是否使用以下滴注藥物？", ["Levophed", "easydopamine", "Isoket", "Perdipine", "其他降壓或強心"])

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

            lab_alert = False
            lab_records_list = []
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

            if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0) or has_vasopressor:
                risk_level, disposition = "🔴 紅區", "具高度惡化或休克風險，建議收治或轉急救區。"
                st.error(f"判定：{risk_level}")
            elif total_score >= 3 or has_vasodilator or has_high_risk_cc:
                risk_level, disposition = "🟡 黃區", "潛在突發惡化風險，請落實防跌、密切監測意識/出血，縮短 Vital signs 頻率。"
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
6. 判定/處置：{risk_level} - {disposition}""", language="text")

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
# 模組 4：CBC/DC 血液常規判讀
# ==========================================
elif page == "🧫 CBC/DC 血液常規判讀":
    st.title("🧫 CBC & DC 血液常規快速判讀")
    cbc_input = st.text_area("📋 請貼上 HIS 系統的 CBC & DC 報告：", height=200)
    if st.button("🔬 解析 CBC/DC 報告", type="primary") and cbc_input.strip() != "":
        wbc = float(re.search(r'WBC\s+([\d.]+)', cbc_input, re.IGNORECASE).group(1)) if re.search(r'WBC\s+([\d.]+)', cbc_input, re.IGNORECASE) else None
        hb = float(re.search(r'Hb\s+([\d.]+)', cbc_input, re.IGNORECASE).group(1)) if re.search(r'Hb\s+([\d.]+)', cbc_input, re.IGNORECASE) else None
        mcv = float(re.search(r'MCV\s+([\d.]+)', cbc_input, re.IGNORECASE).group(1)) if re.search(r'MCV\s+([\d.]+)', cbc_input, re.IGNORECASE) else None
        n_band = float(re.search(r'N\.?band\.?\s+([\d.]+)', cbc_input, re.IGNORECASE).group(1)) if re.search(r'N\.?band\.?\s+([\d.]+)', cbc_input, re.IGNORECASE) else 0.0
        n_seg = float(re.search(r'N\.?seg\.?\s+([\d.]+)', cbc_input, re.IGNORECASE).group(1)) if re.search(r'N\.?seg\.?\s+([\d.]+)', cbc_input, re.IGNORECASE) else 0.0
        
        if wbc:
            anc = round(wbc * 1000 * ((n_band + n_seg) / 100), 1)
            anc_status = "🔴 重度低下 (<500)" if anc < 500 else "🟡 中度低下 (<1000)" if anc < 1000 else "🟡 輕度低下 (<1500)" if anc < 1500 else "🟢 正常"
            anemia_status = "無明顯貧血"
            if hb and hb < 12.0:
                if mcv: anemia_status = f"🟡 小球性貧血 (MCV={mcv})" if mcv < 80 else f"🟡 大球性貧血 (MCV={mcv})" if mcv > 100 else f"🟡 正球性貧血 (MCV={mcv})"
                else: anemia_status = "🟡 貧血"
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("WBC", f"{wbc}")
            col_b.metric("Seg + Band", f"{round(n_seg + n_band, 1)} %")
            col_c.metric("ANC", anc, anc_status.split(" ")[1], delta_color="inverse" if anc < 1500 else "normal")
            if hb: col_d.metric("Hb", hb, anemia_status.split(" ")[1] if hb < 12.0 else "正常", delta_color="inverse" if hb < 12.0 else "normal")
            st.code(f"[CBC 判讀] WBC {wbc} / Hb {hb} / MCV {mcv}\nANC: {anc} ({anc_status.split(' ')[0]})\n貧血: {anemia_status}", language="text")

# ==========================================
# 模組 5：生化檢驗 (BCS) 判讀 (含 CKD 分級)
# ==========================================
elif page == "🧪 生化檢驗 (BCS) 判讀":
    st.title("🧪 生化檢驗 (BCS) 快速判讀")
    
    # --- 加入全新的 EBP 學理依據面板 ---
    with st.expander("📚 點此查看 BCS 判讀學理依據與 KDIGO CKD 分級標準 (EBP)"):
        st.markdown("""
        ### 1. 腎臟與體液狀態 (BUN/CRE Ratio)
        * **BUN/CRE > 20**：腎前性氮血症 (Prerenal Azotemia)。急診常見於**嚴重脫水**、**休克**，或**急性腸胃道出血 (UGIB)** (因血液在腸道被消化吸收，導致 BUN 異常飆高)。
        * **CRE 升高且 Ratio < 15**：偏向腎因性 (Renal) 損傷，如急性腎小管壞死 (ATN)。

        ### 2. 慢性腎臟病 (CKD) 分級 (依據 KDIGO 指引)
        急診給予顯影劑 (CT with Contrast) 或調整抗生素劑量時，高度依賴 eGFR 分級：
        * **Stage 1**：eGFR ≥ 90 (正常或高濾過率)
        * **Stage 2**：eGFR 60 - 89 (輕度下降)
        * **Stage 3a**：eGFR 45 - 59 (輕中度下降)
        * **Stage 3b**：eGFR 30 - 44 (中重度下降)
        * **Stage 4**：eGFR 15 - 29 (重度下降，準備透析)
        * **Stage 5**：eGFR < 15 (末期腎臟病 ESRD)

        ### 3. 肝炎與猛爆性肝損傷 (Liver Injury)
        * **AST/ALT > 100 U/L**：實質性肝炎 (病毒性、藥物性或酒精性)。
        * **AST/ALT > 1000 U/L**：強烈提示猛爆性肝炎、缺血性肝炎 (Shock Liver) 或嚴重 Acetaminophen (普拿疼) 中毒。
        """)
    st.divider()

    bcs_input = st.text_area("📋 請貼上 HIS 系統的生化報告 (包含 Na, K, BUN, CRE, AST, ALT, eGFR...)：", height=250)
    
    if st.button("🔬 解析 BCS 報告", type="primary"):
        if bcs_input.strip() == "":
            st.error("⚠️ 請先貼上生化報告！")
        else:
            na, k, glu, bun, cre, egfr, ast, alt = None, None, None, None, None, None, None, None
            
            if re.search(r'Na\s+([\d.]+)', bcs_input, re.IGNORECASE): na = float(re.search(r'Na\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            if re.search(r'K\s+([\d.]+)', bcs_input, re.IGNORECASE): k = float(re.search(r'K\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            if re.search(r'GLU\s+([\d.]+)', bcs_input, re.IGNORECASE): glu = float(re.search(r'GLU\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            if re.search(r'BUN\s+([\d.]+)', bcs_input, re.IGNORECASE): bun = float(re.search(r'BUN\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            
            cre_matches = re.findall(r'CRE\s+([\d.]+)', bcs_input, re.IGNORECASE)
            if cre_matches: cre = float(cre_matches[0])
            
            if re.search(r'eGFR[^\n\d]*([\d.]+)', bcs_input, re.IGNORECASE): egfr = float(re.search(r'eGFR[^\n\d]*([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            if re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', bcs_input, re.IGNORECASE): ast = float(re.search(r'AST\s*\(?GOT\)?\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))
            if re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', bcs_input, re.IGNORECASE): alt = float(re.search(r'ALT\s*\(?GPT\)?\s+([\d.]+)', bcs_input, re.IGNORECASE).group(1))

            findings = []
            
            # 1. 電解質
            na_status, k_status = "正常", "正常"
            na_color, k_color = "normal", "normal"
            if na:
                if na < 135: na_status = "📉 低血鈉"; na_color = "inverse"
                elif na > 145: na_status = "📈 高血鈉"; na_color = "inverse"
            if k:
                if k < 3.0 or k > 6.0: k_status = "🚨 危急值"; k_color = "inverse"
                elif k < 3.5: k_status = "📉 低血鉀"; k_color = "inverse"
                elif k > 5.1: k_status = "📈 高血鉀"; k_color = "inverse"
                
            # 2. 腎功能與 BUN/CRE 比例
            renal_status = "正常"
            bc_ratio = None
            if bun and cre:
                bc_ratio = round(bun / cre, 1)
                if cre > 1.3:
                    if bc_ratio > 20:
                        renal_status = f"🔴 腎前性氮血症 (Ratio={bc_ratio} > 20)，強烈提示脫水或 GI Bleeding"
                        findings.append("⚠️ BUN/CRE Ratio > 20: 疑似脫水或出血")
                    else:
                        renal_status = "🟡 腎功能損傷 (AKI / CKD)"
                        findings.append("⚠️ CRE 升高: 腎功能異常")
                else:
                    if bc_ratio > 20: renal_status = f"🟡 BUN 偏高 (Ratio={bc_ratio})，請注意水份攝取或潛在出血"
            
            # 3. KDIGO CKD 分級判斷
            ckd_status = "未提供"
            if egfr:
                if egfr >= 90: ckd_status = "Stage 1 (≥90, 正常)"
                elif egfr >= 60: ckd_status = "Stage 2 (60-89, 輕度下降)"
                elif egfr >= 45: ckd_status = "Stage 3a (45-59, 輕中度下降)"
                elif egfr >= 30: ckd_status = "Stage 3b (30-44, 中重度下降)"
                elif egfr >= 15: ckd_status = "Stage 4 (15-29, 重度下降)"
                else: ckd_status = "Stage 5 (<15, 末期腎臟病 ESRD)"

            # 4. 肝功能
            liver_status = "正常"
            if ast and alt:
                if ast > 1000 or alt > 1000:
                    liver_status = "🚨 猛爆性/缺血性肝損傷 (AST/ALT > 1000)"
                    findings.append("🚨 嚴重肝功能受損")
                elif ast > 100 or alt > 100:
                    liver_status = "🟡 肝炎 / 肝功能異常"
                    findings.append("⚠️ AST/ALT 升高")
                    
            # 5. 血糖
            glu_status = "正常"
            if glu:
                if glu < 70: glu_status = "🚨 低血糖"; findings.append("🚨 低血糖風險")
                elif glu > 200: glu_status = "📈 高血糖"

            # 畫面呈現
            st.markdown("### 📊 關鍵數值儀表板")
            c1, c2, c3, c4 = st.columns(4)
            if na: c1.metric("Na (鈉)", na, na_status, delta_color=na_color)
            if k: c2.metric("K (鉀)", k, k_status, delta_color=k_color)
            if glu: c3.metric("GLU (血糖)", glu, glu_status, delta_color="inverse" if glu<70 or glu>200 else "normal")
            if cre: c4.metric("CRE (肌酸酐)", cre, "異常" if cre>1.3 else "正常", delta_color="inverse" if cre>1.3 else "normal")
            
            c5, c6, c7, c8 = st.columns(4)
            if bun: c5.metric("BUN", bun)
            if egfr: c6.metric("eGFR", egfr, ckd_status.split(" ")[0], delta_color="inverse" if egfr<60 else "normal")
            if ast: c7.metric("AST", ast, "異常" if ast>40 else "正常", delta_color="inverse" if ast>40 else "normal")
            if alt: c8.metric("ALT", alt, "異常" if alt>50 else "正常", delta_color="inverse" if alt>50 else "normal")

            st.markdown("### 🔬 綜合病生理判讀")
            if bc_ratio and bc_ratio > 20: st.error(f"**💧 體液與腎臟：** {renal_status} / **CKD 分級：** {ckd_status}")
            else: st.info(f"**💧 體液與腎臟：** {renal_status} / **CKD 分級：** {ckd_status}")
            
            if ast and (ast > 100 or alt > 100): st.warning(f"**🩸 肝臟功能：** {liver_status}")
            else: st.info(f"**🩸 肝臟功能：** {liver_status}")
            
            summary = " / ".join(findings) if findings else "生化檢驗無重大異常或危險值"
            
            st.subheader("📋 護理交班紀錄")
            st.code(f"""[生化 (BCS) 快速判讀紀錄]
1. 腎臟與體液：BUN {bun} / CRE {cre} (Ratio: {bc_ratio})
2. CKD 腎病分級：eGFR {egfr} ➔ {ckd_status}
3. 肝臟酵素：AST {ast} / ALT {alt}
4. 關鍵電解質：Na {na} / K {k}
5. 血糖值：GLU {glu}
6. 綜合警示：{summary}""", language="text")

# ==========================================
# 模組 6：管理員後台
# ==========================================
elif page == "🔒 系統管理員後台":
    st.title("🔒 系統品管與稽核後台")
    admin_password = st.text_input("🔑 請輸入管理員密碼", type="password")
    if admin_password == "alex":
        st.success("✅ 登入成功")
        if os.path.exists(LOG_FILE):
            st.dataframe(pd.read_csv(LOG_FILE), use_container_width=True)
            if st.button("🗑️ 清空所有紀錄"): os.remove(LOG_FILE); st.rerun()

# ==========================================
# 全域頁尾
# ==========================================
st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("""
<div style="text-align: center; color: gray; font-size: 0.85em;">
    <p><strong>© 2026 急診臨床決策輔助系統 (ER Clinical Decision Support)</strong></p>
    <p>💡 <b>System Design & Clinical Logic by：</b>花蓮慈濟醫學中心 急診護理師 [吳智弘] (D-MAT / BLS Instructor)</p>
    <p>⚠️ <b>免責聲明：</b>本系統基於臨床實證醫學 (EBP) 開發，不可替代臨床醫師之專業診斷。</p>
</div>
""", unsafe_allow_html=True)
