import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }

    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; border: none; }
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="select_all_btn"],
    div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"], 
    div.stButton > button[key="deselect_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }

    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = "Nee" if col == "Uit voorraad" else ""

    if "Uit voorraad" in df.columns:
        df["Uit voorraad"] = df["Uit voorraad"].astype(str).apply(
            lambda x: "Ja" if x.lower() in ["true", "ja", "1", "yes"] else "Nee"
        )
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    if df.empty: return
    conn = get_connection()
    save_df = df.copy()
    if "Selecteren" in save_df.columns: save_df = save_df.drop(columns=["Selecteren"])
    if "Uit voorraad_bool" in save_df.columns: save_df = save_df.drop(columns=["Uit voorraad_bool"])
    
    try:
        conn.update(worksheet="Blad1", data=save_df.astype(str))
        st.cache_data.clear()
    except Exception as e: st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
if "geselecteerd_ids" not in st.session_state:
    st.session_state.geselecteerd_ids = set()

# --- KPI's ---
active_df = st.session_state.mijn_data[st.session_state.mijn_data["Uit voorraad"] == "Nee"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    st.metric("In Voorraad (stuks)", int(pd.to_numeric(active_df["Aantal"], errors='coerce').fillna(0).sum()))
with c3: 
    orders = active_df[active_df["Order"] != ""]["Order"].apply(lambda x: str(x).split('-')[0].strip())
    st.metric("Unieke Orders", orders.nunique())

# --- FILTERING ---
view_df = st.session_state.mijn_data.copy()
zoekterm = st.session_state.get("zoek_input", "")
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- ACTIEBALK ---
aantal_geselecteerd = len(st.session_state.geselecteerd_ids)

if aantal_geselecteerd > 0:
    st.markdown('<div class="actie-container">', unsafe_allow_html=True)
    col_sel, col_loc = st.columns([1.5, 4.5], gap="large", vertical_alignment="bottom")
    with col_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Wissen", key="deselect_btn", use_container_width=True):
            st.session_state.geselecteerd_ids = set()
            st.rerun()
    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp: nieuwe_loc = st.text_input("Locatie", placeholder="Nieuwe locatie...", label_visibility="collapsed")
        with c_btn:
            if st.button("📍 Verplaats", key="bulk_update_btn", use_container_width=True) and nieuwe_loc:
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(st.session_state.geselecteerd_ids), "Locatie"] = nieuwe_loc
                st.session_state.geselecteerd_ids = set()
                sla_data_op(st.session_state.mijn_data)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
else:
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    with c_in: st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_input")
    with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)
    with c_all:
        if st.button("✅ Alles Selecteren", key="select_all_btn", use_container_width=True):
            st.session_state.geselecteerd_ids = set(view_df["ID"].tolist())
            st.rerun()

# --- TABEL ---
# Bereid UI kolommen voor
view_df["Selecteren"] = view_df["ID"].apply(lambda x: x in st.session_state.geselecteerd_ids)
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

# Styling
styled_view = view_df.style.apply(lambda s: ['background-color: #ff4b4b; color: white' if s["Uit voorraad_bool"] else '' for _ in s], axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Selecteren", width="small"),
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad\nmelden", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "ID": None, "Uit voorraad": None
    },
    disabled=["ID"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- AFHANDELING WIJZIGINGEN ---
if not edited_df.equals(view_df):
    # Check wat er veranderd is
    # 1. Update de selectie-set (gebeurt razendsnel lokaal)
    nieuwe_selectie = set(edited_df[edited_df["Selecteren"] == True]["ID"].tolist())
    selectie_is_gewijzigd = nieuwe_selectie != st.session_state.geselecteerd_ids
    
    # 2. Update de data (Locatie, Uit voorraad, etc.)
    data_is_gewijzigd = not edited_df.drop(columns=["Selecteren"]).equals(view_df.drop(columns=["Selecteren"]))
    
    if selectie_is_gewijzigd:
        st.session_state.geselecteerd_ids = nieuwe_selectie
        st.rerun()
        
    if data_is_gewijzigd:
        # Vertaal bool terug naar tekst voor opslag
        edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
        # Update hoofd-dataset
        st.session_state.mijn_data.update(edited_df[["ID", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]])
        sla_data_op(st.session_state.mijn_data)
        st.rerun()
