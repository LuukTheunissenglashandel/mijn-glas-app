import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: ORIGINEEL DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; transition: all 0.2s; }
    div.stButton > button[key="search_btn"], div.stButton > button[key="select_all_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="save_btn"] { background-color: #198754; color: white; border: 2px solid #146c43; }
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        for col in DATAKOLOMMEN:
            if col not in df.columns: df[col] = ""
        return df[["ID"] + DATAKOLOMMEN].astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    ww = st.sidebar.text_input("Wachtwoord", type="password")
    if st.sidebar.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df_work = st.session_state.mijn_data.copy()

# --- KPI'S ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    actief = len(df_work[df_work["Status"] != "UIT VOORRAAD"])
    st.metric("Op Voorraad", actief)
with c3:
    orders = df_work[df_work["Status"] != "UIT VOORRAAD"]["Order"].nunique()
    st.metric("Orders", orders)

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c_in, c_zo, c_wi, c_del = st.columns([4, 1, 1, 2], gap="small", vertical_alignment="bottom")
with c_in: zoekterm = st.text_input("Zoeken", placeholder="Order, maat, locatie...", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: 
    if st.button("❌", key="clear_btn", use_container_width=True):
        st.session_state.zoek_input = ""
        st.rerun()
with c_del:
    if st.button("📦 Meld UIT VOORRAAD", key="header_del_btn", use_container_width=True):
        # We halen de IDs op die 'True' zijn in de huidige state
        if "main_editor" in st.session_state:
            # We kijken naar de rijen die zijn aangevinkt in de editor
            edited_rows = st.session_state.main_editor.get("edited_rows", {})
            for idx_str, changes in edited_rows.items():
                if changes.get("Selecteer") is True:
                    idx = int(idx_str)
                    st.session_state.mijn_data.iloc[idx, st.session_state.mijn_data.columns.get_loc("Status")] = "UIT VOORRAAD"
            sla_op(st.session_state.mijn_data)
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
if "Selecteer" not in df_work.columns:
    df_work.insert(0, "Selecteer", False)

if zoekterm:
    mask = df_work.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    display_df = df_work[mask]
else:
    display_df = df_work

def highlight(row):
    if row['Status'] == "UIT VOORRAAD":
        return ['background-color: #ffcccc; color: #b30000'] * len(row)
    return [''] * len(row)

# Gebruik een stabiele weergave zonder directe sync-loop
edited_output = st.data_editor(
    display_df.style.apply(highlight, axis=1),
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False),
        "ID": None,
        "Status": st.column_config.TextColumn("Status", disabled=True),
        "Locatie": st.column_config.TextColumn("Locatie"),
    },
    hide_index=True,
    use_container_width=True,
    height=600,
    key="main_editor"
)

# --- OPSLAAN KNOP ---
st.markdown("---")
if st.button("💾 Alle wijzigingen (locaties/vinkjes) opslaan", key="save_btn", use_container_width=True):
    # Synchroniseer de data uit de editor naar de session state
    new_data = edited_output.data
    # Update alleen de regels die in het display stonden
    st.session_state.mijn_data.update(new_data)
    sla_op(st.session_state.mijn_data)
    st.success("✅ Alles succesvol opgeslagen!")
    time.sleep(1)
    st.rerun()
