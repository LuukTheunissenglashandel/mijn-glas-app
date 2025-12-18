import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS VOOR DE RODE REGELS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }
    /* Rood voor uit voorraad */
    div.stButton > button[key="status_red_btn"] { background-color: #dc3545; color: white; }
    /* Groen voor terugzetten */
    div.stButton > button[key="status_green_btn"] { background-color: #198754; color: white; }
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

def laad_data():
    conn = get_connection()
    df = conn.read(worksheet="Blad1", ttl=0)
    if df is None or df.empty:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    
    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    return df[["ID"] + DATAKOLOMMEN].astype(str)

def sla_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- INITIALISATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    ww = st.sidebar.text_input("Wachtwoord", type="password")
    if st.sidebar.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

if 'df' not in st.session_state:
    st.session_state.df = laad_data()

# --- FILTEREN & ZOEKEN ---
zoekterm = st.text_input("🔍 Zoeken (Order, Maat, Locatie)", placeholder="Typ om te filteren...")
display_df = st.session_state.df.copy()

if zoekterm:
    mask = display_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    display_df = display_df[mask]

# --- ACTIES ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([2, 2, 2])

# We gebruiken de data_editor om selecties te maken
with c1:
    if st.button("📦 Markeer als UIT VOORRAAD (Rood)", key="status_red_btn", use_container_width=True):
        # We halen de IDs op die in de editor zijn aangevinkt
        if "editor" in st.session_state and "edited_rows" in st.session_state.editor:
            # Voor een simpelere aanpak kijken we welke rijen veranderd zijn
            st.warning("Vink eerst de regels aan in de tabel hieronder.")

with c2:
    nieuwe_loc = st.text_input("Nieuwe Locatie", placeholder="Typ locatie...")
    if st.button("📍 Verplaatsen", use_container_width=True):
        st.info("Gebruik de tabel om gegevens direct aan te passen.")

st.markdown('</div>', unsafe_allow_html=True)

# --- DE TABEL ---
def color_red(row):
    if row['Status'] == "UIT VOORRAAD":
        return ['background-color: #ffcccc; color: #b30000; font-weight: bold'] * len(row)
    return [''] * len(row)

# We tonen de tabel met de mogelijkheid om direct 'Status' of 'Locatie' aan te passen
edited_df = st.data_editor(
    display_df.style.apply(color_red, axis=1),
    column_config={
        "ID": None,
        "Status": st.column_config.SelectboxColumn("Status", options=["", "UIT VOORRAAD"]),
        "Aantal": st.column_config.TextColumn("Aant."),
        "Breedte": st.column_config.TextColumn("Br."),
        "Hoogte": st.column_config.TextColumn("Hg."),
    },
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic",
    key="voorraad_editor"
)

# --- OPSLAAN KNOP ---
if st.button("💾 Alle wijzigingen opslaan naar Google Sheets", use_container_width=True, type="primary"):
    # Pak de data uit de editor (die de .style wrap heeft)
    final_df = edited_df.data
    # Update de hoofddataset
    st.session_state.df = final_df
    sla_op(final_df)
    st.success("✅ Opgeslagen in Google Sheets!")
    time.sleep(1)
    st.rerun()

with st.sidebar:
    if st.button("🔄 Vernieuwen"):
        del st.session_state.df
        st.rerun()
