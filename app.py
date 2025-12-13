import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
# Let op: 'Selecteer' voegen we later toe voor de vinkjes
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad")

# --- CSS: Layout & Kleuren ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* Gekleurde knoppen */
    div.stButton > button[key="real_del_btn"] { background-color: #28a745; color: white; border-radius: 5px; height: 50px; width: 100%; }
    div.stButton > button[key="cancel_del_btn"] { background-color: #dc3545; color: white; border-radius: 5px; height: 50px; width: 100%; }
    
    /* Zorg dat de tabel goed scrollt op mobiel */
    [data-testid="stDataFrameResizable"] { width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
    """Zorgt dat waarden altijd hele cijfers zijn"""
    try:
        if val is None or str(val).strip() == "": return ""
        s_val = str(val).replace(',', '.').strip()
        return str(int(float(s_val)))
    except:
        return str(val)

def laad_data():
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
            df[col] = ""

    for col in ["Aantal", "Spouw"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
            
    # Zorg dat we strings hebben (geen rekenfouten)
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    """Slaat data op ZONDER de vinkjes-kolom"""
    conn = get_connection()
    # We filteren de 'Selecteer' kolom eruit voordat we naar Google sturen
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- AUTH ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.header("🔒 Inloggen")
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Starten"):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- MAIN APP ---
st.title("🏭 Glas Voorraad")

# 1. Data Laden
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()
    # Voeg vinkjes-kolom toe in het geheugen (niet in Google)
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# 2. Sidebar (Import)
with st.sidebar:
    st.header("📥 Import")
    uploaded_file = st.file_uploader("Excel bestand (.xlsx)", type=["xlsx"])
    if uploaded_file:
        if st.button("Bevestig Upload"):
            try:
                nieuwe_data = pd.read_excel(uploaded_file)
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe_data = nieuwe_data.rename(columns=mapping)
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                if "Locatie" not in nieuwe_data.columns: nieuwe_data["Locatie"] = ""

                for col in ["Aantal", "Spouw"]:
                    if col in nieuwe_data.columns: nieuwe_data[col] = nieuwe_data[col].apply(clean_int)

                for c in DATAKOLOMMEN:
                    if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                
                final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
                # Voeg samen en herlaad
                huidig_uit_cloud = laad_data()
                totaal = pd.concat([huidig_uit_cloud, final_upload], ignore_index=True)
                sla_data_op(totaal)
                st.session_state.mijn_data = None # Forceer herladen
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")

# 3. Zoekbalk & Knoppen
col_search, col_buttons = st.columns([3, 1])
with col_search:
    zoekterm = st.text_input("🔍", placeholder="Zoek op order, afmeting...", label_visibility="collapsed")
btn_place = col_buttons.empty()

# Filter logic voor zoeken
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# 4. DE TABEL (Nieuw: st.data_editor)
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn(
            "🗑️",
            help="Vink aan om te verwijderen",
            default=False,
            width="small"
        ),
        "Locatie": st.column_config.TextColumn("Locatie", width="medium"),
        "Aantal": st.column_config.TextColumn("Aantal", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="large"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "ID": None # Verberg ID
    },
    disabled=["ID"], # ID mag je niet aanpassen
    hide_index=True,
    num_rows="fixed", # Geen lege regels onderaan toevoegen
    height=600,
    key="editor"
)

# 5. Opslaan Logica (Automatisch bij wijziging)
# We checken of er inhoudelijke wijzigingen zijn (niet de vinkjes)
if not edited_df.drop(columns=["Selecteer"]).equals(df.loc[edited_df.index].drop(columns=["Selecteer"])):
    # Update de hoofdbron met de edits
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)

# 6. Verwijder Logica
geselecteerd = edited_df[edited_df["Selecteer"] == True]

if len(geselecteerd) > 0:
    with btn_place.container():
        if st.button(f"🗑️ Verwijder ({len(geselecteerd)})", type="primary"):
            st.session_state.ask_del = True
            
        if st.session_state.get('ask_del'):
            st.warning("Definitief verwijderen?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("JA", key="real_del_btn"):
                    ids_weg = geselecteerd["ID"].tolist()
                    # Filter uit de sessie data
                    st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
                    sla_data_op(st.session_state.mijn_data)
                    st.session_state.ask_del = False
                    st.rerun()
            with c2:
                if st.button("NEE", key="cancel_del_btn"):
                    st.session_state.ask_del = False
                    st.rerun()
