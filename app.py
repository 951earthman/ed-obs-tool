import streamlit as st

# 1. 從 Streamlit Cloud 的 Secrets 讀取預設密碼
# 請確保您在 Streamlit 網頁後台的 Secrets 設定了 PASSWORD = "你的密碼"
CORRECT_PASSWORD = st.secrets["PASSWORD"]

def check_password():
    """驗證密碼，若成功則回傳 True"""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    # 如果已經驗證過，直接回傳 True
    if st.session_state["password_correct"]:
        return True

    # 顯示密碼輸入框
    st.title("🏥 急診臨床決策支援系統")
    st.subheader("請輸入單位驗證碼以繼續")
    
    user_input = st.text_input("密碼", type="password")
    
    if st.button("登入"):
        if user_input == CORRECT_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun() # 重新整理頁面以進入主程式
        else:
            st.error("❌ 密碼錯誤，請洽詢單位負責人")
            
    return False
# --- 網頁標題與說明 ---
st.title("🚨 急診留觀風險自動評估系統")
st.markdown("快速計算 MEWS、休克指數，並整合危險檢驗值 (K, Hs-TnI, CRP, Lactate)，自動生成護理交班紀錄。")
st.divider() 

# --- 第一區塊：輸入生命徵象與意識狀態 ---
st.subheader("1. 臨床徵象與意識評估")
vitals_input = st.text_area("📋 請貼上生命徵象 (例如：體溫：36.0 ℃；脈搏：85 次...)", height=100)

# 強制輸入 GCS，預設為空值 (None)，強迫使用者一定要填寫
gcs_input = st.number_input("🧠 意識狀態 (GCS 分數, 3-15) ⚠️必填", min_value=3, max_value=15, value=None, step=1, placeholder="請輸入 3 到 15 的整數")

# --- 第二區塊：輸入檢驗報告 (選填) ---
st.subheader("2. 補充檢驗報告 (若無則留白)")
# 把畫面分成左右兩半，放四個輸入框
col1, col2 = st.columns(2)

with col1:
    k_input = st.text_input("➤ 鉀離子 (K) 數值：", placeholder="例如：2.5")
    crp_input = st.text_input("➤ CRP (發炎指標)：", placeholder="例如：1.5")
with col2:
    tni_input = st.text_input("➤ Hs-TnI 數值：", placeholder="例如：18.2")
    lactate_input = st.text_input("➤ Lactate (乳酸) 數值：", placeholder="例如：2.1")

st.divider()

# --- 按下按鈕後開始運算 ---
if st.button("🚀 開始評估並生成紀錄", type="primary"):
    # 防呆機制：檢查是否都有填寫
    if vitals_input.strip() == "":
        st.error("⚠️ 請先貼上生命徵象！")
    elif gcs_input is None:
        st.error("⚠️ 請輸入 GCS 意識分數！")
    else:
        total_score = 0
        temp = hr = rr = sbp = None 
        
        # 1. 計算 Vital Signs 分數
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

        # 2. 計算 GCS 分數並加入 MEWS 總分
        gcs_score = 0
        if gcs_input == 15:
            gcs_score = 0
        elif 13 <= gcs_input <= 14:
            gcs_score = 1
        elif 9 <= gcs_input <= 12:
            gcs_score = 2
        elif gcs_input <= 8:
            gcs_score = 3
        total_score += gcs_score

        # 計算休克指數
        shock_index = round(hr / sbp, 2) if (hr and sbp and sbp > 0) else "無法計算"

        # 3. 處理檢驗報告邏輯
        lab_alert = False
        lab_records_list = []
        
        if k_input.strip() != "":
            k_val = float(k_input)
            if k_val < 3.0 or k_val > 6.0:
                lab_alert = True
                lab_records_list.append(f"鉀離子 {k_val} mEq/L (Critical)")
            else:
                lab_records_list.append(f"鉀離子 {k_val} mEq/L")
                
        if tni_input.strip() != "":
            tni_val = float(tni_input)
            if tni_val > 17.5:
                lab_alert = True
                lab_records_list.append(f"Hs-TnI {tni_val} (異常 > 17.5)")
            else:
                lab_records_list.append(f"Hs-TnI {tni_val} (正常)")

        if crp_input.strip() != "":
            crp_val = float(crp_input)
            if crp_val > 1.0: # 可依院內標準調整，此處抓大於 1.0 為偏高
                lab_records_list.append(f"CRP {crp_val} (偏高)")
            else:
                lab_records_list.append(f"CRP {crp_val} (正常)")

        if lactate_input.strip() != "":
            lac_val = float(lactate_input)
            if lac_val >= 2.2:
                lab_alert = True # 乳酸 >= 4.0 直接視為危急值觸發紅區
                lab_records_list.append(f"Lactate {lac_val} (Critical >= 4.0)")
            elif lac_val > 2.0:
                lab_records_list.append(f"Lactate {lac_val} (異常 > 2.0)")
            else:
                lab_records_list.append(f"Lactate {lac_val} (正常)")

        if len(lab_records_list) > 0:
            lab_record_text = " / ".join(lab_records_list)
        else:
            lab_record_text = "無特殊異常或未驗"

        # 4. 判斷風險等級
        risk_level = ""
        disposition = ""
        if total_score >= 5 or lab_alert or (isinstance(shock_index, float) and shock_index > 1.0):
            risk_level = "🔴 高度風險 (紅區)"
            disposition = "on monitor 並通知醫師評估處置，建議收治ICU或轉急救區。"
            st.error(f"判定結果：{risk_level}") 
        elif total_score >= 3:
            risk_level = "🟡 中度風險 (黃區)"
            disposition = "需密切觀察，增加 Vital signs 監測頻率Q2H-Q4H。"
            st.warning(f"判定結果：{risk_level}") 
        else:
            risk_level = "🟢 穩定狀態 (綠區)"
            disposition = "生命徵象穩定，持續常規留觀。"
            st.success(f"判定結果：{risk_level}") 

        # --- 產生護理紀錄 ---
        st.subheader("📋 護理交班紀錄 (請直接複製)")
        nursing_note = f"""[留觀風險自動評估紀錄]
1. 當下生理數值：體溫 {temp}℃, 脈搏 {hr}次/分, 呼吸 {rr}次/分, 血壓 {sbp}mmHg
2. 預警指標運算：MEWS 總分 {total_score} 分 (含 GCS {gcs_input} 分) / 休克指數 (SI) {shock_index}
3. 關鍵檢驗數值：{lab_record_text}
4. 系統判定風險：{risk_level}
5. 建議動向處置：{disposition}"""
        
        st.code(nursing_note, language="text")
st.caption("© 2026 [護理師 吳智弘] 開發設計. 版權所有。")
