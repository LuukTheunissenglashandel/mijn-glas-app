import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. SETUP
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="Glas Voorraad")
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Sessie status initialiseren (voorkomt crashes)
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "mijn_data" not in st.session_state: st.session_state.mijn_data = pd.DataFrame()
if "bevestig_delete" not in st.session_state: st.session_state.bevestig_delete = False
if "ids_om_te_wissen" not in st.session_state: st.session_state.ids_om_te_wissen = []

# ---------------------------------------------------------
# 2. FUNCTIES
# ---------------------------------------------------------
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def clean_int(val):
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
        if df is None or df.empty: return pd.DataFrame(columns=["ID", "Selecteer"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID", "Selecteer"] + DATAKOLOMMEN)

    # Data schoonmaken
    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    
    df = df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)
    
    # CRUCIAAL: Zorg dat de Selecteer kolom altijd bestaat en False is bij laden
    df["Selecteer"] = False
    return df

def sla_data_op(df):
    conn = get_connection()
    # Maak kopie om Selecteer kolom niet mee te sturen naar Google Sheets
    export_df = df.copy()
    if "Selecteer" in export_df.columns:
        export_df = export_df.drop(columns=["Selecteer"])
    
    # VEILIGHEID: Als export leeg is, checken of dat wel de bedoeling is
    if export_df.empty:
        st.warning("⚠️ De lijst is leeg. Opslaan overgeslagen uit veiligheid.")
        return

    try:
        conn.update(worksheet="Blad1", data=export_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# ---------------------------------------------------------
# 3. LOGIN & DATA LADEN
# ---------------------------------------------------------
if not st.session_state.ingelogd:
    ww = st.text_input("Wachtwoord", type="password")
    if st.button("Login"):
        if ww == WACHTWOORD:
            st.session_state.ingelogd = True
            st.session_state.mijn_data = laad_data()
            st.rerun()
        else:
            st.error("Fout wachtwoord")
    st.stop()

# Als data leeg is (door refresh), opnieuw laden
if st.session_state.mijn_data.empty:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# ---------------------------------------------------------
# 4. DE APP
# ---------------------------------------------------------
st.title("Glas Voorraad Beheer")

# A. SIDEBAR IMPORT
with st.sidebar:
    st.header("Import")
    up = st.file_uploader("Excel", type=["xlsx"])
    if up and st.button("Importeer"):
        try:
            nieuwe = pd.read_excel(up)
            nieuwe.columns = [c.strip().capitalize() for c in nieuwe.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe = nieuwe.rename(columns=mapping)
            nieuwe["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe))]
            
            # Kolommen matchen
            for c in DATAKOLOMMEN:
                if c not in nieuwe.columns: nieuwe[c] = ""
            for c in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                if c in nieuwe.columns: nieuwe[c] = nieuwe[c].apply(clean_int)
            
            final = nieuwe[["ID"] + DATAKOLOMMEN].astype(str)
            final["Selecteer"] = False
            
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success("Geïmporteerd!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Fout: {e}")
    
    if st.button("Geforceerd Herladen"):
        st.session_state.mijn_data = laad_data()
        st.rerun()

# B. ZOEKEN
zoekterm = st.text_input("Zoeken (Order, maat, locatie)", "")

# C. FILTEREN (Alleen voor weergave!)
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# D. VERWIJDER PROCES (Stap voor Stap)
aantal_geselecteerd = len(df[df["Selecteer"] == True])

if aantal_geselecteerd > 0:
    st.info(f"Je hebt {aantal_geselecteerd} regels aangevinkt.")
    
    if st.button("🗑️ Verwijderen Controleren"):
        # We slaan de IDs op in session state zodat we ze niet kwijtraken bij een rerun
        st.session_state.ids_om_te_wissen = df[df["Selecteer"] == True]["ID"].tolist()
        st.session_state.bevestig_delete = True

if st.session_state.bevestig_delete:
    st.warning("⚠️ **Weet je het zeker?**")
    st.write("De volgende IDs worden definitief verwijderd:")
    # Laat even zien wat er weg gaat (check voor gebruiker)
    preview_weg = df[df["ID"].isin(st.session_state.ids_om_te_wissen)]
    st.dataframe(preview_weg[["Order", "Breedte", "Hoogte", "Locatie"]])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ JA, DEFINITIEF VERWIJDEREN"):
            # 1. Filteren
            oude_lengte = len(st.session_state.mijn_data)
            st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(st.session_state.ids_om_te_wissen)]
            nieuwe_lengte = len(st.session_state.mijn_data)
            
            # 2. Opslaan
            sla_data_op(st.session_state.mijn_data)
            
            # 3. Resetten
            st.session_state.bevestig_delete = False
            st.session_state.ids_om_te_wissen = []
            st.success(f"{oude_lengte - nieuwe_lengte} regels verwijderd!")
            time.sleep(1)
            st.rerun()
            
    with col2:
        if st.button("❌ Annuleren"):
            st.session_state.bevestig_delete = False
            st.session_state.ids_om_te_wissen = []
            st.rerun()

# E. DE TABEL
# Cruciaal: We gebruiken session_state.mijn_data direct voor sync
# Als je filtert, tonen we de gefilterde set, maar edits gaan naar de master data
edited_df = st.data_editor(
    view_df,
    key="data_editor",
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "ID": None
    },
    disabled=["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"],
    hide_index=True,
    height=600
)

# SYNC LOGICA: Vinkjes overnemen in de hoofdlijst
if not edited_df.equals(view_df):
    # Update de vinkjes in de hoofddatabase op basis van ID
    wijzigingen = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    st.session_state.mijn_data["Selecteer"] = st.session_state.mijn_data["ID"].map(wijzigingen).fillna(st.session_state.mijn_data["Selecteer"]).astype(bool)
    st.rerun()
