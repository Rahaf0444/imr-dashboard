import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import time
import base64
from pathlib import Path

st.set_page_config(page_title="Scale Formation Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.8rem;
        padding-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Dashboard for Detecting the Possibility of Scale Formation Using I-MR Control Charts")

# ------------------------------------------------
# Fixed control limits
# ------------------------------------------------
limits = {
    50: {
        "pH": {
            "I_CL": 10.3808,
            "I_UCL": 11.3823,
            "I_LCL": 9.3793,
            "MR_CL": 0.3766,
            "MR_UCL": 1.2302,
            "MR_LCL": 0
        },
        "EDTA Concentration (%)": {
            "I_CL": 12.3231,
            "I_UCL": 17.3929,
            "I_LCL": 7.2533,
            "MR_CL": 1.9062,
            "MR_UCL": 6.2277,
            "MR_LCL": 0
        }
    },
    80: {
        "pH": {
            "I_CL": 10.4137,
            "I_UCL": 11.4753,
            "I_LCL": 9.3521,
            "MR_CL": 0.3992,
            "MR_UCL": 1.3041,
            "MR_LCL": 0
        },
        "EDTA Concentration (%)": {
            "I_CL": 12.8367,
            "I_UCL": 18.2125,
            "I_LCL": 7.4610,
            "MR_CL": 1.9792,
            "MR_UCL": 6.4659,
            "MR_LCL": 0
        }
    }
}

# ------------------------------------------------
# Session state
# ------------------------------------------------
defaults = {
    "manual_data": [],
    "current_idx": 0,
    "is_running": False,
    "is_paused": False,
    "last_alarm_row": None,
    "last_temp": None,
    "last_mode": None
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ------------------------------------------------
# Helpers
# ------------------------------------------------
def reset_monitoring():
    st.session_state.current_idx = 0
    st.session_state.is_running = False
    st.session_state.is_paused = False
    st.session_state.last_alarm_row = None

def play_alarm_sound(audio_file="alarm.mp3"):
    audio_path = Path(audio_file)
    if audio_path.exists():
        audio_bytes = audio_path.read_bytes()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
        <audio autoplay>
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)

def draw_control_chart(x, y, ucl, cl, lcl, title, ylabel, out_mask):
    fig, ax = plt.subplots(figsize=(4.8, 2.0))

    ax.axhspan(lcl, ucl, alpha=0.12, color="#4A90E2")
    ax.plot(x, y, marker="o", linewidth=1.4, markersize=3.5, color="#1f77b4")
    ax.axhline(ucl, color="#F4A261", linewidth=1.4)
    ax.axhline(cl, color="#1D4ED8", linewidth=1.6)
    ax.axhline(lcl, color="#F4A261", linewidth=1.4)

    if out_mask.any():
        ax.scatter(
            x[out_mask],
            y[out_mask],
            s=40,
            facecolors="white",
            edgecolors="red",
            linewidths=1.4,
            zorder=5
        )

    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.set_xlabel("Row", fontsize=7)
    ax.set_ylabel(ylabel, fontsize=7)
    ax.tick_params(axis="both", labelsize=7)
    ax.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()
    return fig

def classify_alert(latest_row, ph_limits, edta_limits):
    ph_i = bool(latest_row["pH_I_Out"])
    edta_i = bool(latest_row["EDTA_I_Out"])
    ph_mr = bool(latest_row["pH_MR_Out"])
    edta_mr = bool(latest_row["EDTA_MR_Out"])

    ph_low = latest_row["pH"] < ph_limits["I_LCL"]
    edta_low = latest_row["EDTA Concentration (%)"] < edta_limits["I_LCL"]

    if ph_i and edta_i:
        if ph_low and edta_low and (ph_mr or edta_mr):
            return "CRITICAL", "Both pH and EDTA are below their lower control limits, with instability indicated by MR."
        if ph_low and edta_low:
            return "CRITICAL", "Both pH and EDTA are below their lower control limits."
        if ph_mr or edta_mr:
            return "CRITICAL", "Both pH and EDTA are out of control, and process instability is present."
        return "CRITICAL", "Both pH and EDTA are out of control."

    if ph_i or edta_i or ph_mr or edta_mr:
        if ph_i or edta_i:
            return "WARNING", "A primary chemical indicator is out of control."
        return "WARNING", "Process instability detected from MR chart behavior."

    return "NORMAL", "System is within control limits."

def diagnostic_answers(latest_row, ph_limits, edta_limits, temp):
    q0 = "Yes" if temp == 80 else "No"
    q1 = "Yes" if latest_row["pH_I_Out"] else "No"
    q2 = "Yes" if latest_row["EDTA Concentration (%)"] < edta_limits["I_LCL"] else "No"
    q3 = "Yes" if latest_row["EDTA Concentration (%)"] <= 0 else "No"
    q4 = "Yes" if (latest_row["pH_MR_Out"] or latest_row["EDTA_MR_Out"]) else "No"

    q5 = "Manual check"
    q6 = "Manual check"
    q7 = "Manual check"
    q8 = "Manual check"
    q9 = "Manual check"

    if q1 == "Yes" and q2 == "Yes" and q4 == "Yes":
        interpretation = "High scale formation risk due to abnormal pH, low EDTA concentration, and unstable process behavior."
    elif q1 == "Yes" and q2 == "Yes":
        interpretation = "High scale formation risk due to simultaneous pH deviation and insufficient inhibitor concentration."
    elif q2 == "Yes":
        interpretation = "Scale formation risk is likely related to insufficient EDTA concentration."
    elif q1 == "Yes":
        interpretation = "Scale formation risk is likely related to abnormal pH conditions."
    elif q4 == "Yes":
        interpretation = "The process is unstable; sudden variation may contribute to scale formation."
    else:
        interpretation = "No strong root-cause indication from the monitored variables."

    auto_df = pd.DataFrame({
        "No.": [0, 1, 2, 3, 4],
        "Question": [
            "Temp too high?",
            "pH too high/low?",
            "EDTA too low?",
            "No inhibitor added?",
            "MR instability?"
        ],
        "Answer": [q0, q1, q2, q3, q4]
    })

    manual_df = pd.DataFrame({
        "No.": [5, 6, 7, 8, 9],
        "Question": [
            "High Ca/Mg ions?",
            "Long residence time?",
            "Pressure change?",
            "Incompatible chemicals?",
            "Poor circulation?"
        ],
        "Answer": [q5, q6, q7, q8, q9]
    })

    return auto_df, manual_df, interpretation

def load_input_df(mode, screenshot_mode):
    if mode == "Upload CSV":
        uploaded_file = st.file_uploader("Upload one CSV file", type=["csv"])
        if uploaded_file is None:
            return None

        uploaded_df = pd.read_csv(uploaded_file)
        uploaded_df.columns = uploaded_df.columns.str.strip()

        possible_ph_cols = ["pH", "pH after mixing", "PH", "ph"]
        possible_edta_cols = [
            "EDTA Concentration (%)",
            "EDTA Concentration",
            "EDTA",
            "edta",
            "EDTA concentration (%)"
        ]

        ph_col = next((col for col in possible_ph_cols if col in uploaded_df.columns), None)
        edta_col = next((col for col in possible_edta_cols if col in uploaded_df.columns), None)

        if ph_col is None or edta_col is None:
            st.error("Could not find matching pH and EDTA columns in your CSV.")
            st.write("Detected columns:", list(uploaded_df.columns))
            return None

        df_local = uploaded_df[[ph_col, edta_col]].copy()
        df_local.columns = ["pH", "EDTA Concentration (%)"]

        if not screenshot_mode:
            st.success(f"Using columns: {ph_col} and {edta_col}")

        return df_local

    c1, c2 = st.columns(2)
    manual_ph = c1.number_input("Enter pH value", value=10.00, step=0.01, format="%.2f")
    manual_edta = c2.number_input("Enter EDTA Concentration (%)", value=10.00, step=0.10, format="%.2f")

    c3, c4 = st.columns(2)
    add_manual = c3.button("Add Observation")
    clear_manual = c4.button("Clear Manual Observations")

    if add_manual:
        st.session_state.manual_data.append({
            "pH": manual_ph,
            "EDTA Concentration (%)": manual_edta
        })

    if clear_manual:
        st.session_state.manual_data = []
        reset_monitoring()

    if len(st.session_state.manual_data) > 0:
        df_local = pd.DataFrame(st.session_state.manual_data)
        if not screenshot_mode:
            st.dataframe(df_local, use_container_width=True)
        return df_local

    st.info("No manual observations added yet.")
    return None

# ------------------------------------------------
# Controls
# ------------------------------------------------
top1, top2, top3, top4 = st.columns([1, 1, 1, 1])
with top1:
    temp = st.selectbox("Temperature (°C)", [50, 80])
with top2:
    speed = st.slider("Speed", 0.1, 2.0, 0.5, 0.1)
with top3:
    mode = st.radio("Input Mode", ["Upload CSV", "Manual observation input"])
with top4:
    screenshot_mode = st.checkbox("Screenshot Mode", value=True)

if st.session_state.last_temp != temp or st.session_state.last_mode != mode:
    reset_monitoring()
    st.session_state.last_temp = temp
    st.session_state.last_mode = mode

ph_limits = limits[temp]["pH"]
edta_limits = limits[temp]["EDTA Concentration (%)"]

df = load_input_df(mode, screenshot_mode)

# ------------------------------------------------
# Monitoring
# ------------------------------------------------
if df is not None and len(df) >= 2:
    header_left, header_mid, header_right = st.columns([2, 1, 1])

    with header_left:
        st.markdown("## Monitoring and Decision Support")
    with header_mid:
        st.metric("Temperature", f"{temp}°C")
    with header_right:
        current_row_display = st.session_state.current_idx if st.session_state.current_idx > 0 else len(df)
        st.metric("Current Row", current_row_display)

    b1, b2, b3, b4 = st.columns(4)

    if b1.button("Start"):
        st.session_state.is_running = True
        st.session_state.is_paused = False
        if st.session_state.current_idx == 0:
            st.session_state.current_idx = 1

    if b2.button("Pause"):
        st.session_state.is_paused = True

    if b3.button("Resume"):
        if st.session_state.current_idx < len(df):
            st.session_state.is_running = True
            st.session_state.is_paused = False
            if st.session_state.current_idx == 0:
                st.session_state.current_idx = 1

    if b4.button("Reset"):
        reset_monitoring()

    shown_count = st.session_state.current_idx
    preview_mode = shown_count == 0

    if preview_mode:
        running_df = df.copy()
    else:
        running_df = df.iloc[:shown_count].copy()

    left_col, right_col = st.columns(2)

    with right_col:
        st.markdown(
            """
            <div style="background-color:#0f172a; padding:10px; border-radius:8px;">
            <h2 style="color:white; font-size:22px; text-align:center; margin:0;">
            Alerts, Diagnostics, and Decisions
            </h2>
            </div>
            """,
            unsafe_allow_html=True
        )
        alert_placeholder = st.empty()
        diagnostic_title_placeholder = st.empty()
        diagnostic_auto_title_placeholder = st.empty()
        diagnostic_auto_table_placeholder = st.empty()
        diagnostic_manual_title_placeholder = st.empty()
        diagnostic_manual_table_placeholder = st.empty()
        diagnostic_interpretation_placeholder = st.empty()
        critical_summary_title_placeholder = st.empty()
        critical_summary_table_placeholder = st.empty()

    if len(running_df) > 0:
        running_df["Row"] = range(1, len(running_df) + 1)
        running_df["pH_MR"] = running_df["pH"].diff().abs()
        running_df["EDTA_MR"] = running_df["EDTA Concentration (%)"].diff().abs()

        running_df["pH_I_Out"] = (
            (running_df["pH"] > ph_limits["I_UCL"]) |
            (running_df["pH"] < ph_limits["I_LCL"])
        )
        running_df["pH_MR_Out"] = running_df["pH_MR"] > ph_limits["MR_UCL"]

        running_df["EDTA_I_Out"] = (
            (running_df["EDTA Concentration (%)"] > edta_limits["I_UCL"]) |
            (running_df["EDTA Concentration (%)"] < edta_limits["I_LCL"])
        )
        running_df["EDTA_MR_Out"] = running_df["EDTA_MR"] > edta_limits["MR_UCL"]

        running_df["Critical_Alert"] = running_df["pH_I_Out"] & running_df["EDTA_I_Out"]

        latest_row = running_df.iloc[-1]
        alert_level, alert_reason = classify_alert(latest_row, ph_limits, edta_limits)

        if preview_mode:
            alert_placeholder.markdown(
                """
                <div style="background-color:#1e3a8a; color:white; padding:10px; border-radius:8px; font-size:18px; font-weight:bold; text-align:center;">
                Preview mode
                </div>
                """,
                unsafe_allow_html=True
            )
            diagnostic_title_placeholder.empty()
            diagnostic_auto_title_placeholder.empty()
            diagnostic_auto_table_placeholder.empty()
            diagnostic_manual_title_placeholder.empty()
            diagnostic_manual_table_placeholder.empty()
            diagnostic_interpretation_placeholder.empty()

        elif alert_level == "CRITICAL":
            alert_placeholder.markdown(
                f"""
                <div style="background-color:#7f1d1d; color:white; padding:10px; border-radius:8px; font-size:22px; font-weight:bold; text-align:center;">
                🚨 CRITICAL ALERT<br>
                Temp: {temp}°C | Row: {int(latest_row['Row'])}
                </div>
                """,
                unsafe_allow_html=True
            )

            auto_df, manual_df, interpretation = diagnostic_answers(
                latest_row, ph_limits, edta_limits, temp
            )

            diagnostic_title_placeholder.markdown(
                "<h3 style='font-size:19px;'>Post-Alert Diagnostic Questions</h3>",
                unsafe_allow_html=True
            )
            diagnostic_auto_title_placeholder.markdown(
                "<div style='font-size:16px; font-weight:bold;'>Automatically Answered by Dashboard</div>",
                unsafe_allow_html=True
            )
            diagnostic_auto_table_placeholder.dataframe(auto_df, use_container_width=True)
            diagnostic_manual_title_placeholder.markdown(
                "<div style='font-size:16px; font-weight:bold;'>Requires Manual PETE / Operator Check</div>",
                unsafe_allow_html=True
            )
            diagnostic_manual_table_placeholder.dataframe(manual_df, use_container_width=True)
            diagnostic_interpretation_placeholder.markdown(
                f"""
                <div style="background-color:#111827; color:white; padding:10px; border-radius:6px; font-size:16px; font-weight:bold;">
                Interpretation:<br>{interpretation}
                </div>
                """,
                unsafe_allow_html=True
            )

            current_row = int(latest_row["Row"])
            if st.session_state.get("last_alarm_row") != current_row:
                play_alarm_sound("alarm.mp3")
                st.session_state.last_alarm_row = current_row

        elif alert_level == "WARNING":
            alert_placeholder.markdown(
                f"""
                <div style="background-color:#92400e; color:white; padding:10px; border-radius:8px; font-size:20px; font-weight:bold; text-align:center;">
                ⚠️ WARNING<br>
                Temp: {temp}°C | Row: {int(latest_row['Row'])}
                </div>
                """,
                unsafe_allow_html=True
            )

            auto_df, manual_df, interpretation = diagnostic_answers(
                latest_row, ph_limits, edta_limits, temp
            )

            diagnostic_title_placeholder.markdown(
                "<h3 style='font-size:19px;'>Post-Alert Diagnostic Questions</h3>",
                unsafe_allow_html=True
            )
            diagnostic_auto_title_placeholder.markdown(
                "<div style='font-size:16px; font-weight:bold;'>Automatically Answered by Dashboard</div>",
                unsafe_allow_html=True
            )
            diagnostic_auto_table_placeholder.dataframe(auto_df, use_container_width=True)
            diagnostic_manual_title_placeholder.markdown(
                "<div style='font-size:16px; font-weight:bold;'>Requires Manual PETE / Operator Check</div>",
                unsafe_allow_html=True
            )
            diagnostic_manual_table_placeholder.dataframe(manual_df, use_container_width=True)
            diagnostic_interpretation_placeholder.markdown(
                f"""
                <div style="background-color:#111827; color:white; padding:10px; border-radius:6px; font-size:16px; font-weight:bold;">
                Interpretation:<br>{interpretation}
                </div>
                """,
                unsafe_allow_html=True
            )

        else:
            alert_placeholder.markdown(
                f"""
                <div style="background-color:#065f46; color:white; padding:10px; border-radius:8px; font-size:18px; font-weight:bold; text-align:center;">
                ✅ NORMAL<br>
                Temp: {temp}°C | Row: {int(latest_row['Row'])}
                </div>
                """,
                unsafe_allow_html=True
            )
            diagnostic_title_placeholder.empty()
            diagnostic_auto_title_placeholder.empty()
            diagnostic_auto_table_placeholder.empty()
            diagnostic_manual_title_placeholder.empty()
            diagnostic_manual_table_placeholder.empty()
            diagnostic_interpretation_placeholder.empty()

        with left_col:
            st.markdown("## Monitoring")

            st.pyplot(
                draw_control_chart(
                    running_df["Row"],
                    running_df["pH"],
                    ph_limits["I_UCL"],
                    ph_limits["I_CL"],
                    ph_limits["I_LCL"],
                    f"pH I Chart at {temp}°C",
                    "pH",
                    running_df["pH_I_Out"]
                ),
                clear_figure=True
            )

            st.pyplot(
                draw_control_chart(
                    running_df["Row"],
                    running_df["EDTA Concentration (%)"],
                    edta_limits["I_UCL"],
                    edta_limits["I_CL"],
                    edta_limits["I_LCL"],
                    f"EDTA I Chart at {temp}°C",
                    "EDTA %",
                    running_df["EDTA_I_Out"]
                ),
                clear_figure=True
            )

            st.pyplot(
                draw_control_chart(
                    running_df["Row"],
                    running_df["pH_MR"].fillna(0),
                    ph_limits["MR_UCL"],
                    ph_limits["MR_CL"],
                    ph_limits["MR_LCL"],
                    f"pH MR Chart at {temp}°C",
                    "MR",
                    running_df["pH_MR_Out"].fillna(False)
                ),
                clear_figure=True
            )

            st.pyplot(
                draw_control_chart(
                    running_df["Row"],
                    running_df["EDTA_MR"].fillna(0),
                    edta_limits["MR_UCL"],
                    edta_limits["MR_CL"],
                    edta_limits["MR_LCL"],
                    f"EDTA MR Chart at {temp}°C",
                    "MR",
                    running_df["EDTA_MR_Out"].fillna(False)
                ),
                clear_figure=True
            )

        critical_rows = running_df[running_df["Critical_Alert"]][[
            "Row",
            "pH",
            "EDTA Concentration (%)",
            "pH_I_Out",
            "EDTA_I_Out",
            "pH_MR_Out",
            "EDTA_MR_Out"
        ]].copy()

        critical_summary_title_placeholder.markdown(
            "<h3 style='font-size:19px; color:#dc2626;'>Critical Alert Summary</h3>",
            unsafe_allow_html=True
        )
        if critical_rows.empty:
            critical_summary_table_placeholder.info("No critical alerts detected.")
        else:
            if screenshot_mode:
                critical_summary_table_placeholder.dataframe(critical_rows.tail(5), use_container_width=True)
            else:
                critical_summary_table_placeholder.dataframe(critical_rows, use_container_width=True)

    else:
        with right_col:
            st.info("Provide at least 2 observations.")

    if st.session_state.is_running and not st.session_state.is_paused and not preview_mode:
        if st.session_state.current_idx < len(df):
            time.sleep(speed)
            st.session_state.current_idx += 1
            st.rerun()
        else:
            st.session_state.is_running = False
            st.session_state.is_paused = False

else:
    st.info("Provide at least 2 observations using CSV upload or manual observation input.")