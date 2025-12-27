import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]

st.set_page_config(layout="wide", page_title="Glas Voorraad Pro", initial_sidebar_state="collapsed")

# --- VERBETERDE CSS VOOR TABLETS ---
st.markdown("""
    <style>
    /* Maak alles ruimer voor touch */
    .stButton > button {
        height: 3rem;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    /* KPI kaarten moderner */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border: none;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }

    /* Verberg irritante UI elementen op tablets */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Grotere letters voor leesbaarheid in de fabriek */
    .stMarkdown p { font-size: 1.1rem; }
    
    /* Optimalisatie voor data editor touch */
    [data-testid="stDataEditor"] div {
        font-size: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CORE FUNCTIES ---
@st.cache_resource
def get_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data():
    conn = get_conn()
    try:
        # ttl=0 zorgt dat we altijd verse data trekken bij een refresh
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        
        # Basis opschonen
        df = df.fillna("")
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        
        # Consistentie check voor 'Uit voorraad'
        if "Uit voorraad" in df.columns:
            df["Uit voorraad"] = df["Uit voorraad"].apply(lambda x: "Ja" if str(x).lower() in ["ja", "true", "1"] else "Nee")
        
        return df.astype(str)
    except Exception as e:
        st.error(f"Verbindingsfout: {e}")
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = get_conn()
    try:
        conn.update(worksheet="Blad1", data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Opslaan mislukt: {e}")
        return False

# --- AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    _, col, _ = st.columns([1,2,1])
    with col:
        st.title("🔐 Glasbeheer")
        pw = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True) or (pw == WACHTWOORD and pw != ""):
            if pw == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- UI LAYOUT ---
st.title("🏭 Glas Voorraad")

# Tabs voor betere organisatie op klein scherm
tab1, tab2, tab3 = st.tabs(["📦 Actuele Voorraad", "✅ Verwerkt", "📥 Import & Beheer"])

with tab1:
    # KPI's bovenaan de voorraad
    actief_mask = st.session_state.mijn_data["Uit voorraad"] == "Nee"
    actieve_data = st.session_state.mijn_data[actief_mask]
    
    k1, k2 = st.columns(2)
    k1.metric("Items in rek", len(actieve_data))
    k2.metric("Totaal glas", pd.to_numeric(actieve_data["Aantal"], errors='coerce').sum())

    # Zoeken
    zoek = st.text_input("🔍 Zoek op order, locatie of maat...", key="search_main")
    
    display_df = actieve_data.copy()
    if zoek:
        mask = display_df.astype(str).apply(lambda x: x.str.contains(zoek, case=False)).any(axis=1)
        display_df = display_df[mask]

    # De Editor
    # We voegen een tijdelijke bool kolom toe voor de checkbox
    display_df["Gereed"] = False 

    edited_view = st.data_editor(
        display_df,
        column_config={
            "ID": None,
            "Gereed": st.column_config.CheckboxColumn("Afmelden", help="Vink aan om uit voorraad te halen", default=False),
            "Uit voorraad": None,
            "Aantal": st.column_config.TextColumn("Stuks", width="small"),
            "Breedte": st.column_config.TextColumn("Br.", width="small"),
            "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        },
        disabled=["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
        hide_index=True,
        use_container_width=True,
        height=500,
        key="editor_actief"
    )

    # Verwerking: Alleen opslaan als er daadwerkelijk iets is aangevinkt
    if not edited_view[edited_view["Gereed"] == True].empty:
        ids_te_verwijderen = edited_view[edited_view["Gereed"] == True]["ID"].tolist()
        
        with st.spinner("Bijwerken..."):
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids_te_verwijderen), "Uit voorraad"] = "Ja"
            if sla_op(st.session_state.mijn_data):
                st.toast("Voorraad bijgewerkt!", icon="✅")
                st.rerun()

with tab2:
    verwerkt_data = st.session_state.mijn_data[st.session_state.mijn_data["Uit voorraad"] == "Ja"]
    st.dataframe(verwerkt_data.drop(columns=["ID"]), use_container_width=True)
    if st.button("🔄 Vernieuw Data"):
        st.session_state.mijn_data = laad_data()
        st.rerun()

with tab3:
    st.subheader("Excel Import")
    up = st.file_uploader("Upload .xlsx bestand", type=["xlsx"])
    if up:
        if st.button("Gegevens Toevoegen"):
            try:
                nieuw = pd.read_excel(up)
                # ... hier jouw bestaande mapping logica ...
                st.success("Import succesvol! (Nog niet opgeslagen in deze demo)")
            except Exception as e:
                st.error(f"Fout: {e}")
