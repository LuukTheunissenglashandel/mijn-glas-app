import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & CSS ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad Beheer", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; }
    div[data-testid="stMetric"] { background-color: #f8f9fa; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    /* Grotere checkbox voor selectie */
    [data-testid="stDataFrameSelectionCheckbox"] { transform: scale(1.2); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCTIES ---
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
    
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    try:
        conn.update(worksheet="Blad1", data=df.astype(str))
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- 3. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else: st.error("Onjuist wachtwoord")
    st.stop()

# --- 4. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 5. SIDEBAR (EXCEL IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Toevoegen", use_container_width=True):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            # Basis mapping en opschonen
            nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
            nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
            for col in DATAKOLOMMEN:
                if col not in nieuwe_data.columns: nieuwe_data[col] = ""
            
            final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success("Excel succesvol toegevoegd!")
            st.rerun()
        except Exception as e: st.error(f"Import fout: {e}")

# --- 6. KPI DASHBOARD ---
df = st.session_state.mijn_data
active_df = df[df["Uit voorraad"] != "Ja"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Voorraad Overzicht")
with c2: 
    aantal_totaal = pd.to_numeric(active_df["Aantal"], errors='coerce').sum()
    st.metric("In Voorraad (stuks)", int(aantal_totaal))
with c3: 
    st.metric("Unieke Orders", active_df["Order"].nunique())

# --- 7. BULK ACTIES ---
with st.container(border=True):
    st.markdown("**🛠️ Bulk Bewerking** (Selecteer rijen in de tabel hieronder)")
    col_b1, col_b2, col_b3 = st.columns([3, 2, 2])
    bulk_locatie = col_b1.text_input("Nieuwe Locatie", placeholder="Bijv: Rek B-2", label_visibility="collapsed")
    
    if col_b2.button("📍 Locatie bijwerken", use_container_width=True):
        if "editor" in st.session_state and "selection" in st.session_state.editor:
            geselecteerde_indices = st.session_state.editor["selection"]["rows"]
            if geselecteerde_indices:
                selected_ids = st.session_state.current_view.iloc[geselecteerde_indices]["ID"].values
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(selected_ids), "Locatie"] = bulk_locatie
                sla_data_op(st.session_state.mijn_data)
                st.success(f"{len(selected_ids)} rijen verplaatst.")
                st.rerun()
            else: st.warning("Selecteer eerst rijen!")

    if col_b3.button("📦 Meld 'Uit Voorraad'", use_container_width=True):
        if "editor" in st.session_state and "selection" in st.session_state.editor:
            geselecteerde_indices = st.session_state.editor["selection"]["rows"]
            if geselecteerde_indices:
                selected_ids = st.session_state.current_view.iloc[geselecteerde_indices]["ID"].values
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(selected_ids), "Uit voorraad"] = "Ja"
                sla_data_op(st.session_state.mijn_data)
                st.rerun()

# --- 8. TABEL MET ZOEKFUNCTIE ---
zoekterm = st.text_input("🔍 Zoeken", placeholder="Zoek op order, afmeting of locatie...")
view_df = st.session_state.mijn_data.copy()

if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Cache de huidige weergave voor de bulk-selectie
st.session_state.current_view = view_df

edited_df = st.data_editor(
    view_df,
    column_config={
        "ID": None,
        "Locatie": st.column_config.TextColumn("Locatie", width="medium"),
        "Aantal": st.column_config.TextColumn("Aantal", width="small"),
        "Uit voorraad": st.column_config.SelectboxColumn("Op Voorraad?", options=["Nee", "Ja"], width="small"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
    key="editor",
    selection_mode="multi_row" # DIT ZORGT VOOR DE VINKJES
)

# Opslaan van individuele wijzigingen (inline editen)
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
