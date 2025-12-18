import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS (Jouw vertrouwde stijl + rood-styling) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    div.stButton > button[key="meld_btn"] { background-color: #dc3545; color: white; border: none; }
    div.stButton > button[key="save_btn"] { background-color: #0d6efd; color: white; font-weight: bold; }
    input[type=checkbox] { transform: scale(1.5); }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_connection()
    df = conn.read(worksheet="Blad1", ttl=0)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Selecteer", "ID"] + DATAKOLOMMEN)
    
    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    # Zorg dat alle kolommen bestaan
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    
    df["Selecteer"] = False
    return df[["Selecteer", "ID"] + DATAKOLOMMEN].astype(str)

def sla_op(df):
    conn = get_connection()
    # Verwijder Selecteer kolom voor opslag
    save_df = df.drop(columns=["Selecteer"]) if "Selecteer" in df.columns else df
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- AUTH ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- KPI'S ---
df = st.session_state.mijn_data
c1, c2 = st.columns(2)
with c1:
    actief = len(df[df["Status"] != "UIT VOORRAAD"])
    st.metric("Ruiten op voorraad", actief)
with c2:
    st.info("Selecteer regels en gebruik de knoppen om ze aan te passen.")

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
col_a, col_b, col_c = st.columns([3, 2, 2])

with col_a:
    zoekterm = st.text_input("🔍 Zoeken", placeholder="Ordernummer, locatie...")

with col_b:
    if st.button("📦 Markeer geselecteerd als UIT VOORRAAD", key="meld_btn", use_container_width=True):
        # Update de status van alle aangevinkte rijen
        st.session_state.mijn_data.loc[st.session_state.mijn_data["Selecteer"] == "True", "Status"] = "UIT VOORRAAD"
        st.session_state.mijn_data["Selecteer"] = "False"
        sla_op(st.session_state.mijn_data)
        st.success("Opgeslagen!")
        time.sleep(1)
        st.rerun()

with col_c:
    if st.button("💾 Wijzigingen opslaan", key="save_btn", use_container_width=True):
        sla_op(st.session_state.mijn_data)
        st.success("Alles gesynchroniseerd!")
        time.sleep(1)
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
view_df = st.session_state.mijn_data.copy()

if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Rode kleur functie
def highlight_red(row):
    if row['Status'] == "UIT VOORRAAD":
        return ['background-color: #ffcccc'] * len(row)
    return [''] * len(row)

edited_df = st.data_editor(
    view_df.style.apply(highlight_red, axis=1),
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("Kies"),
        "ID": None,
        "Status": st.column_config.TextColumn("Status", disabled=True),
    },
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# Sync editor terug naar session_state
if not edited_df.data.equals(view_df):
    # Alleen de kolommen 'Selecteer' en 'Locatie' etc syncen
    st.session_state.mijn_data.update(edited_df.data)
