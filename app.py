import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="collapsed")

# --- CSS: TABLET & UI OPTIMALISATIE ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* Grotere knoppen voor touch-bediening op tablets */
    div.stButton > button { 
        border-radius: 10px; 
        height: 55px; 
        font-weight: 600; 
        font-size: 18px !important;
        border: none; 
    }
    
    div.stButton > button[key="search_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }

    /* Betere weergave van metrics op kleine schermen */
    div[data-testid="stMetric"] {
        background-color: #ffffff; 
        border: 1px solid #e0e0e0; 
        padding: 20px; 
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }

    /* Checkbox schaling voor tablets */
    input[type=checkbox] { transform: scale(1.8); cursor: pointer; }

    /* Verberg standaard Streamlit elementen voor een schone app-look */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Forceer tabel lettergrootte voor leesbaarheid op tablets */
    [data-testid="stTable"] { font-size: 16px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_val(val, decimals=0):
    """Zet waarde om naar getal met specifiek aantal decimalen"""
    try:
        if val is None or str(val).strip() == "": return ""
        f_val = float(str(val).replace(',', '.'))
        if decimals == 0:
            return str(int(f_val))
        return f"{f_val:.{decimals}f}".replace('.', ',')
    except:
        return str(val)

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

    # Formattering bij inladen
    if "Uit voorraad" in df.columns:
        df["Uit voorraad"] = df["Uit voorraad"].astype(str).apply(
            lambda x: "Ja" if x.lower() in ["true", "ja", "1", "yes"] else "Nee"
        )

    # Breedte en Hoogte naar 1 decimaal, rest naar 0
    for col in ["Aantal", "Spouw"]:
        if col in df.columns: df[col] = df[col].apply(lambda x: clean_val(x, 0))
    for col in ["Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(lambda x: clean_val(x, 1))
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    if df.empty: return
    conn = get_connection()
    save_df = df.copy().astype(str)
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- AUTH SYSTEEM (Met refresh check) ---
# We checken of de 'auth' parameter in de URL staat
if "ingelogd" not in st.session_state:
    if st.query_params.get("auth") == "true":
        st.session_state.ingelogd = True
    else:
        st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br><h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Voer wachtwoord in...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.query_params["auth"] = "true" # Bewaar status in URL voor refresh
                st.rerun()
            else: st.error("Fout wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

df = st.session_state.mijn_data

# --- SIDEBAR (Excel Import) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Toevoegen", key="upload_btn"):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
            nieuwe_data["Uit voorraad"] = "Nee"
            for col in DATAKOLOMMEN:
                if col not in nieuwe_data.columns: nieuwe_data[col] = ""
            
            # Formatteer ook de import direct naar de juiste decimalen
            for col in ["Breedte", "Hoogte"]: nieuwe_data[col] = nieuwe_data[col].apply(lambda x: clean_val(x, 1))
            
            final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
        except Exception as e: st.error(f"Fout bij upload: {e}")
    
    if st.button("Uitloggen"):
        st.session_state.ingelogd = False
        st.query_params.clear()
        st.rerun()

# --- KPI's ---
active_df = df[df["Uit voorraad"] == "Nee"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Voorraad")
with c2: 
    aantal_num = pd.to_numeric(active_df["Aantal"], errors='coerce').fillna(0)
    st.metric("Totaal Stuks", int(aantal_num.sum()))
with c3: 
    orders = active_df[active_df["Order"] != ""]["Order"].apply(lambda x: str(x).split('-')[0].strip())
    st.metric("Open Orders", orders.nunique())

# --- ZOEKBALK (Extra groot voor tablet) ---
c_in, c_zo, c_wi = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
with c_in: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of locatie...", label_visibility="collapsed", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

st.write("") 

# --- TABEL ---
view_df = df.copy()
if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

# Omzetten naar booleans voor de checkbox-kolom
view_df["Uit voorraad_bool"] = view_df["Uit voorraad"] == "Ja"

def highlight_stock(s):
    return ['background-color: #ffcccc; color: black' if s["Uit voorraad_bool"] else '' for _ in s]

styled_view = view_df.style.apply(highlight_stock, axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br. (1 dec)", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg. (1 dec)", width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("Gereed", width="small", default=False),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "ID": None,
        "Uit voorraad": None 
    },
    disabled=["ID", "Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=800, # Hoger voor makkelijker scrollen op tablet
    key="editor"
)

# VERWERKING VAN DE KLIK
if not edited_df.equals(view_df):
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    st.session_state.mijn_data.update(edited_df[["ID", "Uit voorraad"]])
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
