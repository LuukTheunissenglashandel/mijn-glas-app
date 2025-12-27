import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE & ORIGINELE UI CSS ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    div.stButton > button { 
        border-radius: 8px; height: 45px; font-weight: 600; border: none; 
    }
    div.stButton > button[key="search_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }

    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px;
    }

    /* Checkbox groter voor makkelijker klikken */
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
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
    # Zorg dat we geen tijdelijke hulpkolommen opslaan
    save_df = df[[col for col in df.columns if col in (["ID"] + DATAKOLOMMEN)]].astype(str)
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- 3. AUTHENTICATIE ---
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

# --- 4. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- 5. KPI'S (Jouw originele logica) ---
df = st.session_state.mijn_data
active_df = df[df["Uit voorraad"] == "Nee"]
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    aantal_num = pd.to_numeric(active_df["Aantal"], errors='coerce').fillna(0)
    st.metric("In Voorraad (stuks)", int(aantal_num.sum()))
with c3: 
    st.metric("Unieke Orders", active_df["Order"].nunique())

# --- 6. BULK ACTIE BALK (Nieuw & Slim) ---
st.markdown("### 🛠️ Bulk Bewerking")
with st.container():
    bc1, bc2, bc3 = st.columns([4, 2, 2])
    nieuwe_loc = bc1.text_input("Nieuwe locatie invullen...", key="bulk_loc_input", label_visibility="collapsed")
    
    if bc2.button("📍 Locatie Wijzigen", use_container_width=True, type="primary"):
        # We kijken welke rijen in de editor zijn aangevinkt
        if "editor" in st.session_state and "edited_rows" in st.session_state.editor:
            # Haal de ID's op van rijen waar 'Select' op True is gezet
            changes = st.session_state.editor["edited_rows"]
            selected_ids = []
            for idx, val in changes.items():
                if val.get("Select"):
                    row_id = st.session_state.current_view.iloc[int(idx)]["ID"]
                    selected_ids.append(row_id)
            
            if selected_ids and nieuwe_loc:
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(selected_ids), "Locatie"] = nieuwe_loc
                sla_data_op(st.session_state.mijn_data)
                st.success(f"Locatie bijgewerkt voor {len(selected_ids)} rijen!")
                st.rerun()
            else:
                st.warning("Selecteer eerst rijen in de tabel en vul een locatie in.")

    if bc3.button("📦 Uit voorraad", use_container_width=True):
        if "editor" in st.session_state and "edited_rows" in st.session_state.editor:
            changes = st.session_state.editor["edited_rows"]
            selected_ids = [st.session_state.current_view.iloc[int(idx)]["ID"] for idx, val in changes.items() if val.get("Select")]
            if selected_ids:
                st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(selected_ids), "Uit voorraad"] = "Ja"
                sla_data_op(st.session_state.mijn_data)
                st.rerun()

# --- 7. ZOEKBALK (Jouw originele design) ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, afmeting...", label_visibility="collapsed")

# --- 8. DE TABEL ---
view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Voeg een tijdelijke selectiekolom toe (wordt NIET opgeslagen in Sheets)
view_df.insert(0, "Select", False)
st.session_state.current_view = view_df

edited_df = st.data_editor(
    view_df,
    column_config={
        "Select": st.column_config.CheckboxColumn("Kies", help="Selecteer voor bulk actie", default=False),
        "ID": None,
        "Locatie": st.column_config.TextColumn("Locatie", width="medium"),
        "Aantal": st.column_config.TextColumn("Aantal", width="small"),
        "Uit voorraad": st.column_config.SelectboxColumn("Status", options=["Nee", "Ja"], width="small"),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
    key="editor"
)

# Individuele wijzigingen (bijv. status veranderen in de tabel) opslaan
if not edited_df.equals(view_df):
    # Alleen opslaan als er meer is veranderd dan alleen de 'Select' vinkjes
    # We checken of de inhoudelijke data is gewijzigd
    if not edited_df.drop(columns="Select").equals(view_df.drop(columns="Select")):
        st.session_state.mijn_data.update(edited_df.drop(columns="Select"))
        sla_data_op(st.session_state.mijn_data)
        st.rerun()
