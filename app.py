import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="header_revive_btn"] { background-color: #198754; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    try:
        if val is None or str(val).strip() == "": return ""
        return str(int(float(str(val).replace(',', '.').strip())))
    except: return str(val)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    if df.empty: return
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e: st.error(f"Fout: {e}")

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    ww = st.sidebar.text_input("Wachtwoord", type="password")
    if st.sidebar.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

# --- DATA ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# --- KPI's ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2:
    op_voorraad = df[df["Status"] != "UIT VOORRAAD"]["Aantal"].replace('', '0').astype(int).sum()
    st.metric("Op Voorraad", op_voorraad)
with c3:
    uniek = df[df["Status"] != "UIT VOORRAAD"]["Order"].nunique()
    st.metric("Orders", uniek)

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
geselecteerd = df[df["Selecteer"] == True]

if len(geselecteerd) > 0:
    col_a, col_b, col_c = st.columns([2, 2, 2])
    with col_a:
        if st.button(f"📦 Meld {len(geselecteerd)} stuks UIT voorraad (Rood)", key="header_del_btn", use_container_width=True):
            st.session_state.mijn_data.loc[st.session_state.mijn_data["Selecteer"] == True, "Status"] = "UIT VOORRAAD"
            st.session_state.mijn_data["Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
    with col_b:
        if st.button(f"🔙 Zet {len(geselecteerd)} stuks TERUG op voorraad", key="header_revive_btn", use_container_width=True):
            st.session_state.mijn_data.loc[st.session_state.mijn_data["Selecteer"] == True, "Status"] = ""
            st.session_state.mijn_data["Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
    with col_c:
        if st.button("❌ Selectie wissen", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
else:
    zoekterm = st.text_input("Zoeken", placeholder="Type om te zoeken...", key="zoek_input")
st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL WEERGAVE ---
view_df = df.copy()
if st.session_state.get("zoek_input"):
    z = st.session_state.zoek_input.lower()
    mask = view_df.astype(str).apply(lambda x: x.str.lower().contains(z)).any(axis=1)
    view_df = view_df[mask]

# Styling functie
def style_row(row):
    if row['Status'] == "UIT VOORRAAD":
        return ['background-color: #ffcccc; color: #900; font-weight: bold'] * len(row)
    return [''] * len(row)

# Editor
edited_df = st.data_editor(
    view_df.style.apply(style_row, axis=1),
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False),
        "ID": None,
        "Status": st.column_config.TextColumn("Status", disabled=True)
    },
    hide_index=True,
    use_container_width=True,
    height=600
)

# --- SYNC NA EDITS ---
# Gebruik .data om het originele dataframe uit de styler te halen voor de vergelijking
if not edited_df.data.equals(view_df):
    # Update de hoofddataset met de wijzigingen uit de editor (zoals checkboxes of locaties)
    for index, row in edited_df.data.iterrows():
        orig_idx = st.session_state.mijn_data.index[st.session_state.mijn_data['ID'] == row['ID']]
        if not orig_idx.empty:
            st.session_state.mijn_data.loc[orig_idx, "Selecteer"] = row["Selecteer"]
            st.session_state.mijn_data.loc[orig_idx, "Locatie"] = row["Locatie"]
    st.rerun()
