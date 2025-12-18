import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PROFESSIONAL DESIGN ---
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
        border-radius: 8px; height: 45px; font-weight: 600; border: none; 
    }
    
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="select_all_btn"],
    div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"], 
    div.stButton > button[key="deselect_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }

    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px;
    }

    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }

    @media only screen and (max-width: 1024px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    try:
        if val is None or str(val).strip() == "": return ""
        return str(int(float(str(val).replace(',', '.'))))
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
        if col not in df.columns: 
            df[col] = "Nee" if col == "Uit voorraad" else ""

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
    save_df = save_df.astype(str)
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

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
            else: st.error("Fout wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
if "geselecteerd_ids" not in st.session_state:
    st.session_state.geselecteerd_ids = []

df = st.session_state.mijn_data

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Toevoegen"):
        nieuwe_data = pd.read_excel(uploaded_file)
        # ... (mapping logica blijft hetzelfde)
        st.rerun()

# --- KPI's ---
active_df = df[df["Uit voorraad"] == "Nee"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    aantal_num = pd.to_numeric(active_df["Aantal"], errors='coerce').fillna(0)
    st.metric("In Voorraad (stuks)", int(aantal_num.sum()))
with c3: 
    orders = active_df[active_df["Order"] != ""]["Order"].apply(lambda x: str(x).split('-')[0].strip())
    st.metric("Unieke Orders", orders.nunique())

# --- TABEL VOORBEREIDING (Voor filteren) ---
view_df = df.copy()
zoekterm = st.session_state.get("zoek_input", "")
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- ACTIEBALK LOGICA ---
aantal_geselecteerd = len(st.session_state.geselecteerd_ids)

if aantal_geselecteerd > 0:
    st.markdown('<div class="actie-container">', unsafe_allow_html=True)
    col_sel, col_loc = st.columns([1.5, 4.5], gap="large", vertical_alignment="bottom")
    with col_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Selectie wissen", key="deselect_btn", use_container_width=True):
            st.session_state.geselecteerd_ids = []
            st.rerun()
    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp: nieuwe_loc = st.text_input("Locatie", placeholder="Nieuwe locatie...", label_visibility="collapsed")
        with c_btn:
            if st.button("📍 Verplaats", key="bulk_update_btn", use_container_width=True) and nieuwe_loc:
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(st.session_state.geselecteerd_ids), "Locatie"] = nieuwe_loc
                st.session_state.geselecteerd_ids = []
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
            # Selecteer alleen de ID's die momenteel zichtbaar zijn door de zoekopdracht
            st.session_state.geselecteerd_ids = view_df["ID"].tolist()
            st.rerun()

st.write("") 

# UI Booleans en Styling
view_df["Selecteren"] = view_df["ID"].isin(st.session_state.geselecteerd_ids)
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

def highlight_stock(s):
    return ['background-color: #ff4b4b; color: white' if s["Uit voorraad_bool"] else '' for _ in s]

styled_view = view_df.style.apply(highlight_stock, axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Selecteren", width="small", default=False),
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Uit voorraad\nmelden", width="small", default=False),
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

# VERWERKING WIJZIGINGEN
if not edited_df.equals(view_df):
    # Update Selectie op basis van handmatig vinken in de tabel
    st.session_state.geselecteerd_ids = edited_df[edited_df["Selecteren"] == True]["ID"].tolist()
    
    # Update Uit voorraad tekst op basis van vinkje
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Update dataset en sla op
    st.session_state.mijn_data.update(edited_df[["ID", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]])
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
