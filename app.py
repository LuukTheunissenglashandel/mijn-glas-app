import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
# Status toegevoegd aan kolommen
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: HET ORIGINELE PROFESSIONELE DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

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
        border: none; 
        transition: all 0.2s ease-in-out;
    }
    
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="select_all_btn"],
    div.stButton > button[key="bulk_update_btn"] { 
        background-color: #0d6efd; color: white; 
    }

    div.stButton > button[key="clear_btn"],
    div.stButton > button[key="deselect_btn"], 
    div.stButton > button[key="cancel_del_btn"] { 
        background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; 
    }
    
    div.stButton > button[key="header_del_btn"] {
        background-color: #dc3545; color: white;
    }
    
    div.stButton > button[key="real_del_btn"] {
        background-color: #198754; color: white;
    }

    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
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
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# --- KPI'S ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df[df["Status"] != "UIT VOORRAAD"]["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("Op Voorraad", tot)
with c3: 
    uniek = df[df["Status"] != "UIT VOORRAAD"]["Order"].nunique()
    st.metric("Orders", uniek)

# --- ACTIEBALK CONTAINER (HERSTELD) ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

geselecteerd_df = df[df["Selecteer"] == "True"] if isinstance(df["Selecteer"].iloc[0], str) else df[df["Selecteer"] == True]
aantal_geselecteerd = len(geselecteerd_df)

if st.session_state.get('ask_del'):
    st.markdown(f"**⚠️ Markeer {aantal_geselecteerd} regels als 'UIT VOORRAAD' (rood)?**")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Markeren", key="real_del_btn", use_container_width=True):
            ids = geselecteerd_df["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Status"] = "UIT VOORRAAD"
            st.session_state.mijn_data["Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.rerun()
    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    col_sel, col_loc, col_out = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")
    with col_sel:
        if st.button("❌ Selectie wissen", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp: nieuwe_locatie = st.text_input("Nieuwe Locatie", placeholder="Naar locatie...")
        with c_btn:
            if st.button("📍 Wijzig", key="bulk_update_btn", use_container_width=True):
                ids = geselecteerd_df["ID"].tolist()
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Locatie"] = nieuwe_locatie
                st.session_state.mijn_data["Selecteer"] = False
                sla_data_op(st.session_state.mijn_data)
                st.rerun()
    with col_out:
        if st.button("📦 Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    with c_in: zoekterm = st.text_input("Zoeken", placeholder="Order, locatie...", key="zoek_input")
    with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi: st.button("❌", key="clear_btn", on_click=lambda: st.session_state.update({"zoek_input": ""}), use_container_width=True)
    with c_all:
        if st.button("✅ Alles Selecteren", key="select_all_btn", use_container_width=True):
            view_df = df.copy()
            if st.session_state.zoek_input:
                mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
                view_df = view_df[mask]
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(view_df["ID"]), "Selecteer"] = True
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL MET DE RODE STYLING ---
view_df = st.session_state.mijn_data.copy()
if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

def highlight_rows(row):
    if row['Status'] == "UIT VOORRAAD":
        return ['background-color: #ffcccc; color: #b30000; font-weight: bold'] * len(row)
    return [''] * len(row)

edited_df = st.data_editor(
    view_df.style.apply(highlight_rows, axis=1),
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "ID": None,
        "Status": st.column_config.TextColumn("Status", disabled=True),
    },
    hide_index=True,
    use_container_width=True,
    height=700,
    key="main_editor"
)

# Sync edits (checkboxes / handmatige wijzigingen)
if not edited_df.data.equals(view_df):
    st.session_state.mijn_data.update(edited_df.data)
    st.rerun()
