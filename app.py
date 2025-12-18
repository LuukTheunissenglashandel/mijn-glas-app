import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Beheer")

WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Initialiseer session state
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "data" not in st.session_state: st.session_state.data = pd.DataFrame()

# --- 2. FUNCTIES ---
def laad_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
        # Zorg voor unieke IDs
        if "ID" not in df.columns:
            df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
        return df.fillna("").astype(str)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

def sla_op(df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Verwijder hulpkolommen voor opslaan
    save_df = df[[col for col in df.columns if col in (["ID"] + DATAKOLOMMEN)]]
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- 3. LOGIN ---
if not st.session_state.ingelogd:
    st.title("🔒 Glas Voorraad")
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.session_state.data = laad_data()
            st.rerun()
    st.stop()

# --- 4. DATA CONTROLE ---
if st.session_state.data.empty:
    st.session_state.data = laad_data()

# --- 5. INTERFACE ---
st.title("🏭 Glas Voorraad")

# Zoekbalk
zoekterm = st.text_input("🔍 Zoeken op order, maat of locatie", placeholder="Typ hier om te filteren...")

# Filteren van de dataset
df_display = st.session_state.data.copy()
if zoekterm:
    mask = df_display.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    df_display = df_display[mask]

# --- 6. DE TABEL MET DIRECTE ACTIEKNOP ---
# Hier gebruiken we de ButtonColumn. Dit is VEILIGER dan checkboxes.
st.write(f"Resultaten: {len(df_display)} ruiten gevonden.")

event = st.data_editor(
    df_display,
    column_config={
        "ID": None, # Verberg ID
        "Meld": st.column_config.ButtonColumn(
            "Actie",
            help="Meld deze ruit direct uit voorraad",
            default_value="Uit voorraad",
        ),
    },
    disabled=DATAKOLOMMEN, # Je kunt de data zelf niet per ongeluk wijzigen
    hide_index=True,
    use_container_width=True,
    key="voorraad_tabel"
)

# --- 7. VERWERK VERWIJDERING ---
# Als er op de knop in een rij is geklikt:
if event["last_clicked_column"] == "Meld":
    rij_index = event["last_clicked_row"]
    # Pak het unieke ID van de ruit in de GEFILTERDE lijst
    ruit_id = df_display.iloc[rij_index]["ID"]
    ruit_order = df_display.iloc[rij_index]["Order"]

    # Voer de verwijdering uit op de HOOFD-dataset
    nieuwe_data = st.session_state.data[st.session_state.data["ID"] != ruit_id]
    
    # Update sessie en Google Sheets
    st.session_state.data = nieuwe_data
    sla_op(nieuwe_data)
    
    st.toast(f"✅ Order {ruit_order} is uit voorraad gemeld.")
    st.rerun()

# --- 8. EXTRA OPTIES ---
with st.expander("➕ Nieuwe ruiten toevoegen (Excel)"):
    uploaded_file = st.file_uploader("Kies Excel bestand", type=["xlsx"])
    if uploaded_file and st.button("Uploaden"):
        nieuwe_data = pd.read_excel(uploaded_file).astype(str)
        nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
        # Alleen relevante kolommen behouden
        for col in DATAKOLOMMEN:
            if col not in nieuwe_data.columns: nieuwe_data[col] = ""
        
        updated_df = pd.concat([st.session_state.data, nieuwe_data], ignore_index=True)
        st.session_state.data = updated_df
        sla_op(updated_df)
        st.success("Data toegevoegd!")
        st.rerun()

if st.button("🔄 Ververs volledige lijst"):
    st.session_state.data = laad_data()
    st.rerun()
