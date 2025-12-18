import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Uit voorraad"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PROFESSIONAL DESIGN & RED HIGHLIGHT ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Styling voor de actie-container */
    .actie-container {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    div.stButton > button { 
        border-radius: 8px; 
        height: 45px; 
        font-weight: 600; 
        transition: all 0.2s ease-in-out;
    }
    
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="select_all_btn"],
    div.stButton > button[key="bulk_update_btn"] { 
        background-color: #0d6efd; color: white; 
    }

    /* Checkbox groter maken */
    input[type=checkbox] { transform: scale(1.4); cursor: pointer; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: 
            df[col] = "False" if col == "Uit voorraad" else ""
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteren" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteren"])
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteren", False)

df = st.session_state.mijn_data

# --- HEADER ---
st.title("🏭 Glas Voorraad")

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
c_in, c_zo, c_all = st.columns([6, 1, 2], gap="small", vertical_alignment="bottom")

with c_in:
    zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, afmeting of locatie...", label_visibility="collapsed", key="zoek_input")
with c_zo:
    st.button("🔍", key="search_btn", use_container_width=True)
with c_all:
    if st.button("✅ Alles Selecteren", key="select_all_btn", use_container_width=True):
        temp_view = df.copy()
        if zoekterm:
            mask = temp_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
            temp_view = temp_view[mask]
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(temp_view["ID"]), "Selecteren"] = True
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL WEERGAVE ---
view_df = df.copy()

# Zoekfilter toepassen
if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

# Data types corrigeren voor editor
view_df["Selecteren"] = view_df["Selecteren"].map({'True': True, 'False': False, True: True, False: False})
view_df["Uit voorraad"] = view_df["Uit voorraad"].map({'True': True, 'False': False, True: True, False: False})

# Functie voor rode rij-kleuring
def style_row(row):
    if row["Uit voorraad"] == True:
        return ['background-color: #ffcccc'] * len(row) # Lichtrood
    return [''] * len(row)

# Styling toepassen
styled_df = view_df.style.apply(style_row, axis=1)

edited_df = st.data_editor(
    styled_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Selecteren", width="medium"),
        "Uit voorraad": st.column_config.CheckboxColumn("Uit voorraad", width="medium"),
        "Locatie": st.column_config.TextColumn("Locatie"),
        "Aantal": st.column_config.TextColumn("Aant."),
        "Breedte": st.column_config.TextColumn("Br."),
        "Hoogte": st.column_config.TextColumn("Hg."),
        "Order": st.column_config.TextColumn("Order"),
        "ID": None
    },
    disabled=["ID"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# Wijzigingen direct opslaan
if not edited_df.equals(view_df):
    # Converteer terug naar string voor GSheets
    final_df = edited_df.copy()
    final_df["Uit voorraad"] = final_df["Uit voorraad"].astype(str)
    final_df["Selecteren"] = final_df["Selecteren"].astype(str)
    
    st.session_state.mijn_data.update(final_df)
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
