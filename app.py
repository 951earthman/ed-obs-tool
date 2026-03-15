import streamlit as st
import pandas as pd
from datetime import datetime
import os
import re

# --- 設定資料紀錄檔案名稱 ---
LOG_FILE = "assessment_log.csv"

# --- 側邊欄：管理員專區 ---
st.sidebar.title("🔒 管理員專區")
admin_password = st.sidebar.text_input("請輸入管理員密碼", type="password")

if admin_password == "alex":
    st.sidebar.success("✅ 登入成功")
    st.sidebar.markdown("### 🗂️ 系統使用紀錄")
    
    # 讀取並顯示紀錄檔
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        st.sidebar.dataframe(df) # 在側邊欄顯示表格
        
        # 提供下載按鈕
        csv = df.to_csv(index=False, encoding='utf-8-sig')
        st.sidebar.download_button(
            label="📥 下載完整紀錄 (CSV)",
            data=csv,
            file_name="ed_obs_log.csv",
            mime="text/csv"
        )
        
        # 提供清空紀錄按鈕
        if st.sidebar.button("🗑️ 清空所有紀錄"):
            os.remove(LOG_FILE)
            st.sidebar.warning("紀錄已清空，請重新整理網頁。")
    else:
        st.sidebar.info("目前尚無任何評估紀錄。")
elif admin_password != "":
    st.sidebar.error("❌ 密碼錯誤")


# --- 網頁主畫面 (給一般使用者) ---
st.title("🚨 急診留觀風險自動評估系統")
st.markdown("快速計算 MEWS、休克指數，並整合危險檢驗值 (K, Hs-TnI, CRP, Lactate)。")
st.divider() 

st.subheader("1. 臨床徵象與意識評估")
vitals_input = st.text_area("📋 請貼上生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)", height=100)
gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1)

st.subheader("2. 補充檢驗報告 (若無則留白)")
col1, col2 = st.columns(2)
with col1:
    k_input = st.text_input("➤ 鉀離子 (K) 數值：")
    crp_input = st.text_input("➤ CRP (發炎指標)：")
with col2:
    tni_input = st.text_input("➤ Hs-TnI 數值：")
    lactate_input = st.text_input("➤ Lactate (乳酸) 數值：")

st.divider()
# --- 學理依據與評分標準 (折疊面板) ---
with st.expander("📚 點此查看系統評分標準與學理依據 (Evidence-Based Practice)"):
    st.markdown("""
    ### 1. MEWS (Modified Early Warning Score) 早期預警分數
    * **臨床目的**：用於早期發現潛在的病情惡化，降低院內心跳停止 (IHCA) 的發生率。
    * **評估項目**：體溫、脈搏、呼吸、收縮壓、意識狀態 (GCS)。
    * **風險分層**：
        * **0 - 2 分**：穩定狀態，維持常規留觀 (綠區)。
        * **3 - 4 分**：中度風險，需增加 Vital signs 監測頻率 (黃區)。
        * **≥ 5 分**：高度惡化風險，需立即醫療介入或考慮收治 (紅區)。

    ### 2. 休克指數 (Shock Index, SI)
    * **計算公式**：`心率 (HR) / 收縮壓 (SBP)`
    * **學理依據**：急診常面臨**「隱性休克 (Occult Shock)」**的挑戰。當有效循環血量減少時，身體會先以心跳加快來代償，此時血壓可能仍看似正常。SI 能在血壓崩盤前，提早揪出潛在的血流動力學不穩定。
    * **判斷標準**：
        * **0.5 - 0.7**：正常範圍。
        * **> 0.8**：警戒邊緣，潛在發病率開始上升。
        * **≥ 1.0**：危險值，死亡率與需急救介入的機率大幅提升，直接列為高度風險 (紅區)。

    ### 3. 危險檢驗數值 (Critical Labs)
    留觀期間的動態抽血變化，往往是決定動向的鐵律：
    * **Lactate (乳酸) ≥ 4.0 mmol/L**：代表組織嚴重缺氧，為敗血性休克 (Septic Shock) 等重症的黃金指標，直接觸發紅區警告。
    * **Hs-TnI > 17.5 ng/L**：高敏感度心肌酵素異常，提示急性心肌損傷 (如 ACS)。
    * **K (鉀離子) < 3.0 或 > 6.0 mEq/L**：極端值極易引發致命性心律不整 (致命性 Tachycardia 或 Bradycardia)。
    """)
    
st.divider() # 在折疊面板下方再加一條分隔線，讓排版更乾淨

if st.button("🚀 開始評估並生成紀錄", type="primary"):
    if vitals_input.strip() == "":
        st.error("⚠️ 請先貼上生命徵象！")
    elif gcs_input is None:
        st.error("⚠️ 請輸入 GCS 意識分數！")
    else:
        total_score = 0
        temp = hr = rr = sbp = None 
        
        temp_match = re.search(r'體溫：([\d.]+)', vitals_input)
        if temp_match:
            temp = float(temp_match.group(1))
            total_score += (2 if temp < 35 or temp >= 38.5 else 1 if temp < 36 else 0)

        hr_match = re.search(r'脈搏：(\d+)', vitals_input)
        if hr_match:
            hr = int(hr_match.group(1))
            total_score += (3 if hr <= 40 or hr >= 130 else 2 if 111 <= hr <= 129 else 1 if 41 <= hr <= 50 or 101 <= hr <= 110 else 0)

        rr_match = re.search(r'呼吸：(\d+)', vitals_input)
        if rr_match:
            rr = int(rr_match.group(1))
            total_score += (3 if rr >= 30 else 2 if rr <= 8 or 21 <= rr <= 29 else 1 if 15 <= rr <= 20 else 0)

        sbp_match = re.search(r'血壓：(\d+)/', vitals_input)
        if sbp_match:
            sbp = int(sbp_match.group(1))
            total_score += (3 if sbp <= 70 else 2 if sbp <= 80 or sbp >= 200 else 1 if sbp <= 100 else 0)

        gcs_score = 0
        if gcs_input == 15: gcs_score = 0
        elif 13 <= gcs_input <= 14: gcs_score = 1
        elif 9 <= gcs_input <= 12: gcs_score = 2
        elif gcs_input <= 8: gcs_score = 3
        total_score += gcs_score

        shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

        lab_alert = False
        lab_records_list = []
        
        if k_input.strip() != "":
            k_val = float(k_input)
            if k_val < 3.0 or k_val > 6.0:
                lab_alert = True
            lab_records_list.append(f"K {k_val}")
                
        if tni_input.strip() != "":
            tni_val = float(tni_input)
            if tni_val > 17.5:
                lab_alert = True
            lab_records_list.append(f"TnI {tni_val}")

        if crp_input.strip() != "":
            lab_records_list.append(f"CRP {crp_input}")

        if lactate_input.strip() != "":
            lac_val = float(lactate_input)
            if lac_val >= 4.0:
                lab_alert = True 
            lab_records_list.append(f"Lac {lac_val}")

        risk_level = ""
        if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0):
            risk_level = "🔴 紅區"
            st.error(f"判定結果：{risk_level}") 
        elif total_score >= 3:
            risk_level = "🟡 黃區"
            st.warning(f"判定結果：{risk_level}") 
        else:
            risk_level = "🟢 綠區"
            st.success(f"判定結果：{risk_level}") 

        # --- 產生護理紀錄 (給使用者複製) ---
        st.subheader("📋 護理交班紀錄")
        nursing_note = f"[留觀風險自動評估紀錄]\nMEWS: {total_score}分 (GCS {gcs_input}), SI: {shock_index}\n風險: {risk_level}"
        st.code(nursing_note, language="text")

        # ==========================================
        # 隱藏的後台動作：將這筆資料寫入 CSV 檔案
        # ==========================================
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 準備要存進表格的一筆資料
        new_record = {
            "評估時間": current_time,
            "MEWS分數": total_score,
            "GCS": gcs_input,
            "休克指數": shock_index,
            "檢驗項目": " / ".join(lab_records_list) if lab_records_list else "無",
            "系統判定": risk_level
        }
        
        # 轉換成表格格式並儲存
        df_new = pd.DataFrame([new_record])
        if not os.path.exists(LOG_FILE):
            df_new.to_csv(LOG_FILE, index=False, encoding='utf-8-sig') # 第一次建立檔案
        else:
            df_new.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig') # 之後附加在原本檔案後面
st.caption("© 2026 [護理師 吳智弘] 開發設計. 版權所有。")
