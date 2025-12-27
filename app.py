import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Order", "Uit voorraad", "Omschrijving", "Spouw"]
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- 2. DATA FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

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
            df[col] = "Nee" if col == "Uit voorraad" else ""
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_op(df):
    conn = get_connection()
    conn.update(worksheet="Blad1", data=df.astype(str))
    st.cache_data.clear()

# --- 3. AUTHENTICATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    st.title("🔒 Inloggen")
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.rerun()
    st.stop()

# --- 4. INITIALISATIE DATA ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

# --- 5. SIDEBAR (HET BULK-PANEL) ---
with st.sidebar:
    st.header("📦 Bulk Acties")
    st.info("1. Vink rijen aan in de tabel\n2. Kies hieronder de nieuwe locatie\n3. Klik op de knop")
    
    nieuwe_locatie_keuze = st.selectbox("Nieuwe Locatie", LOCATIE_OPTIES, key="bulk_loc_sb")
    
    # De bulk-knop
    if st.button("📍 VERPLAATS SELECTIE", use_container_width=True, type="primary"):
        # We halen de data op die op dat moment in de editor staat
        if "main_editor" in st.session_state:
            # We kijken welke rijen zijn aangepast/aangevinkt
            # De editor geeft ons de 'edited_df' terug in de session state
            pass # Logica wordt hieronder bij de editor verwerkt via de return waarde

    st.divider()
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"])
    # (Import logica weggelaten voor de focus op bulk bewerking, maar kan hieronder)

# --- 6. HOOFDSCHERM ---
st.title("🏭 Glas Voorraad")

# Zoekbalk
zoekterm = st.text_input("🔍 Zoeken", placeholder="Zoek op order, maat, etc...", key="zoek_input")

# Data voorbereiden voor weergave
df_view = st.session_state.mijn_data.copy()

if zoekterm:
    mask = df_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_view = df_view[mask]

# BELANGRIJK: Voeg de selectiekolom toe
df_view.insert(0, "Kies", False)
df_view["Uit voorraad_bool"] = df_view["Uit voorraad"] == "Ja"

# --- 7. DE TABEL (EDITOR) ---
# We vangen de output van de editor op in 'edited_df'
edited_df = st.data_editor(
    df_view,
    column_config={
        "Kies": st.column_config.CheckboxColumn("S", width="small"),
        "Locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES),
        "Uit voorraad_bool": st.column_config.CheckboxColumn("✅ Uit"),
        "ID": None, # Verberg ID voor de gebruiker
        "Uit voorraad": None
    },
    disabled=["Aantal", "Breedte", "Hoogte", "Order", "Omschrijving", "Spouw"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="main_editor"
)

# --- 8. LOGICA VOOR OPSLAAN ---

# Check of de bulk-knop (in de sidebar) is ingedrukt
# Omdat de knop een rerun triggert, moeten we kijken of we geselecteerde rijen hebben
geselecteerde_rijen = edited_df[edited_df["Kies"] == True]

if st.sidebar.button("📍 BEVESTIG VERPLAATSING", key="confirm_bulk"):
    if not geselecteerde_rijen.empty:
        ids_to_update = geselecteerde_rijen["ID"].tolist()
        
        # Update alleen de geselecteerde ID's in de bron-data
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids_to_update), "Locatie"] = nieuwe_locatie_keuze
        
        sla_op(st.session_state.mijn_data)
        st.success(f"✅ {len(ids_to_update)} rijen verplaatst naar {nieuwe_locatie_keuze}")
        st.rerun()
    else:
        st.sidebar.warning("Vink eerst rijen aan in de tabel!")

# Check voor normale wijzigingen (per rij locatie aanpassen of 'Uit voorraad' vinken)
elif not edited_df.drop(columns=["Kies"]).equals(df_view.drop(columns=["Kies"])):
    # Zet de checkbox terug naar tekst "Ja/Nee"
    edited_df["Uit voorraad"] = edited_df["Uit voorraad_bool"].apply(lambda x: "Ja" if x else "Nee")
    
    # Werk de hoofd-data bij
    for _, row in edited_df.iterrows():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == row["ID"], ["Locatie", "Uit voorraad"]] = [row["Locatie"], row["Uit voorraad"]]
    
    sla_op(st.session_state.mijn_data)
    st.rerun()
