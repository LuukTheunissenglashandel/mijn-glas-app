import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. INSTELLINGEN & INITIALISATIE
# ==========================================
st.set_page_config(layout="wide", page_title="Glas Voorraad")

WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Zorg dat de app nooit crasht bij opstarten
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "mijn_data" not in st.session_state: st.session_state.mijn_data = pd.DataFrame(columns=["ID", "Selecteer"] + DATAKOLOMMEN)
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""

# ==========================================
# 2. FUNCTIES
# ==========================================
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
    """Haalt data op van Google Sheets"""
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: 
             return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    # Zorg dat ID en Selecteer kolommen bestaan
    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    # Maak alle data netjes
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
        
    result = df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)
    result["Selecteer"] = False
    return result

def sla_data_op(df):
    """Slaat data op naar Google Sheets"""
    conn = get_connection()
    # Maak kopie om op te slaan (zonder selectievakjes)
    save_df = df.copy()
    if "Selecteer" in save_df.columns: 
        save_df = save_df.drop(columns=["Selecteer"])
    
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

def reset_selecties():
    """CRUCIAAL: Zet alle vinkjes uit. Wordt aangeroepen bij zoeken."""
    if not st.session_state.mijn_data.empty:
        st.session_state.mijn_data["Selecteer"] = False

# ==========================================
# 3. LOGIN SCHERM
# ==========================================
if not st.session_state.ingelogd:
    st.markdown("<h2 style='text-align: center;'>🔒 Inloggen</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Start", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                with st.spinner("Data laden..."):
                    st.session_state.mijn_data = laad_data()
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# ==========================================
# 4. HOOFD PROGRAMMA
# ==========================================

# Data check (voor zekerheid)
if "ID" not in st.session_state.mijn_data.columns:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- SIDEBAR (Import) ---
with st.sidebar:
    st.header("Excel Import")
    uploaded_file = st.file_uploader("Kies Excel bestand", type=["xlsx"])
    if uploaded_file and st.button("Toevoegen"):
        try:
            nieuwe = pd.read_excel(uploaded_file)
            # Kolommen normaliseren
            nieuwe.columns = [c.strip().capitalize() for c in nieuwe.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe = nieuwe.rename(columns=mapping)
            
            # Nieuwe IDs en kolommen
            nieuwe["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe))]
            if "Locatie" not in nieuwe.columns: nieuwe["Locatie"] = ""
            for c in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                if c in nieuwe.columns: nieuwe[c] = nieuwe[c].apply(clean_int)
            for c in DATAKOLOMMEN:
                if c not in nieuwe.columns: nieuwe[c] = ""
            
            final = nieuwe[["ID"] + DATAKOLOMMEN].astype(str)
            final["Selecteer"] = False
            
            # Toevoegen aan bestaande data
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success(f"{len(final)} regels toegevoegd!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Fout: {e}")
    
    st.markdown("---")
    if st.button("Data verversen"):
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- HEADER & ZOEKEN ---
st.title("🏭 Glas Voorraad")

c_zoek, c_knop = st.columns([4, 1])
with c_zoek:
    # LET OP: on_change=reset_selecties zorgt dat oude vinkjes verdwijnen als je typt!
    zoekterm = st.text_input("Zoeken", placeholder="Typ order, maat of locatie...", key="zoek_input", on_change=reset_selecties)

# --- TABEL VOORBEREIDEN ---
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# Tel selecties
aantal_geselecteerd = len(df[df["Selecteer"] == True])

# --- VERWIJDER KNOP (Alleen zichtbaar als er iets geselecteerd is) ---
if aantal_geselecteerd > 0:
    st.warning(f"Je hebt **{aantal_geselecteerd}** regels geselecteerd.")
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(f"🗑️ Verwijder {aantal_geselecteerd} regels", type="primary"):
            # 1. Haal IDs op van wat aangevinkt staat
            ids_weg = df[df["Selecteer"] == True]["ID"].tolist()
            
            # 2. Filter de dataset (alles behouden wat NIET in de weg-lijst staat)
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            
            # 3. Opslaan naar Google Sheets
            sla_data_op(st.session_state.mijn_data)
            
            # 4. Opruimen
            st.session_state.zoek_input = "" # Zoekbalk leeg
            st.success("Regels verwijderd!")
            time.sleep(1)
            st.rerun()

# --- DE TABEL (EDITOR) ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "ID": None # Verberg ID kolom
    },
    disabled=["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"], # Alleen vinkjes aanpasbaar
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- SYNC: VINKJES OPSLAAN IN GEHEUGEN ---
# Als je iets aanvinkt in de gefilterde lijst, moet dit onthouden worden in de hoofdlijst
if not edited_df.equals(view_df):
    # Maak een lijstje van: Welk ID heeft Welke Status (True/False)
    wijzigingen = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    
    # Update de hoofd data
    st.session_state.mijn_data["Selecteer"] = st.session_state.mijn_data["ID"].map(wijzigingen).fillna(st.session_state.mijn_data["Selecteer"]).astype(bool)
    st.rerun()
