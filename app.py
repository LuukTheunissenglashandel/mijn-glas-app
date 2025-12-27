import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS (Aangepast voor bulk actie bar) ---
st.markdown("""
    <style>
    .stSelection { background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin-bottom: 10px; }
    input[type=checkbox] { transform: scale(1.2); }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES (Bestaand) ---
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
    
    # Opschonen en types fixen
    df = df.fillna("")
    if "Uit voorraad" in df.columns:
        df["Uit voorraad"] = df["Uit voorraad"].astype(str).apply(
            lambda x: "Ja" if x.lower() in ["true", "ja", "1", "yes"] else "Nee"
        )
    return df[["ID"] + DATAKOLOMMEN].astype(str)

def sla_data_op(df):
    conn = get_connection()
    try:
        conn.update(worksheet="Blad1", data=df.astype(str))
        st.cache_data.clear()
        st.success("Data succesvol opgeslagen!")
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# --- AUTH & INITIALISATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    # (Wachtwoord sectie blijft hetzelfde als jouw origineel)
    ww = st.sidebar.text_input("Wachtwoord", type="password")
    if st.sidebar.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()

# --- BULK ACTIES SECTIE ---
st.title("🏭 Glas Voorraad Management")

# We maken een container voor de bulk acties boven de tabel
with st.expander("🛠️ Bulk Acties (Selecteer eerst rijen in de tabel hieronder)", expanded=True):
    col_bulk1, col_bulk2 = st.columns([2, 1])
    nieuwe_locatie = col_bulk1.text_input("Nieuwe Locatie voor selectie", placeholder="Bijv: Rek A-1")
    
    if col_bulk2.button("📍 Locatie Nu Wijzigen", use_container_width=True):
        # Check of er rijen zijn geselecteerd via de editor state
        if "editor" in st.session_state and "selection" in st.session_state.editor:
            selected_rows = st.session_state.editor["selection"]["rows"]
            
            if not selected_rows:
                st.warning("Selecteer eerst rijen met de vinkjes links in de tabel.")
            elif not nieuwe_locatie:
                st.warning("Vul een nieuwe locatie in.")
            else:
                # 1. Haal de huidige getoonde tabel op (rekening houdend met zoekfilters)
                current_view = st.session_state.filtered_df
                
                # 2. Haal de ID's op van de geselecteerde rijen in de huidige weergave
                selected_ids = current_view.iloc[selected_rows]["ID"].tolist()
                
                # 3. Update alleen deze ID's in de hoofd-dataset
                st.session_state.mijn_data.loc[
                    st.session_state.mijn_data["ID"].isin(selected_ids), "Locatie"
                ] = nieuwe_locatie
                
                # 4. Opslaan en herladen
                sla_data_op(st.session_state.mijn_data)
                st.rerun()

# --- ZOEKBALK & FILTERING ---
zoekterm = st.text_input("🔍 Zoeken", placeholder="Type om te filteren...", label_visibility="collapsed")
view_df = st.session_state.mijn_data.copy()

if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Sla de gefilterde df op in session_state zodat de bulk-functie erbij kan
st.session_state.filtered_df = view_df

# --- DE TABEL (Met Selectievakjes) ---
st.info("Gebruik de vakjes helemaal links om rijen te selecteren voor bulk-wijzigingen.")

edited_df = st.data_editor(
    view_df,
    column_config={
        "ID": None,
        "Locatie": st.column_config.TextColumn("Locatie ✨", width="medium"),
        "Uit voorraad": st.column_config.SelectboxColumn("Status", options=["Nee", "Ja"]),
    },
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor",
    # DIT IS DE KEY VOOR DE SELECTIEVAKJES:
    selection_mode="multi_row" 
)

# Losse rij-bewerkingen opslaan (als iemand direct in de tabel typt)
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
