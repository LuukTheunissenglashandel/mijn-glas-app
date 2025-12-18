import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(layout="wide", page_title="Glas Voorraad")
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Initialisatie
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "mijn_data" not in st.session_state: st.session_state.mijn_data = pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

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
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    # Opslaan zonder Selecteer kolom (die is alleen voor de app)
    save_df = df.copy()
    if "Selecteer" in save_df.columns: 
        save_df = save_df.drop(columns=["Selecteer"])
    
    # Veiligheidscheck: Nooit een lege lijst opslaan als er daarvoor nog data was
    if save_df.empty and len(st.session_state.mijn_data) > 5:
        st.error("⚠️ FOUT: De app probeerde alles te wissen. Opslaan geblokkeerd.")
        return

    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

# ==========================================
# 3. LOGIN
# ==========================================
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

# ==========================================
# 4. DATA CHECK
# ==========================================
if "ID" not in st.session_state.mijn_data.columns:
    st.session_state.mijn_data = laad_data()

# We werken met een lokale kopie voor weergave
df = st.session_state.mijn_data.copy()

# ==========================================
# 5. SIDEBAR (IMPORT)
# ==========================================
with st.sidebar:
    st.header("Import")
    up = st.file_uploader("Excel", type=["xlsx"])
    if up and st.button("Toevoegen"):
        try:
            nieuwe = pd.read_excel(up)
            nieuwe.columns = [c.strip().capitalize() for c in nieuwe.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe = nieuwe.rename(columns=mapping)
            nieuwe["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe))]
            if "Locatie" not in nieuwe.columns: nieuwe["Locatie"] = ""
            for c in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                if c in nieuwe.columns: nieuwe[c] = nieuwe[c].apply(clean_int)
            for c in DATAKOLOMMEN:
                if c not in nieuwe.columns: nieuwe[c] = ""
            
            final = nieuwe[["ID"] + DATAKOLOMMEN].astype(str)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success("Toegevoegd!")
            time.sleep(1)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    if st.button("Herlaad Data"):
        st.session_state.mijn_data = laad_data()
        st.rerun()

# ==========================================
# 6. HOOFDSCHERM
# ==========================================
st.title("Glas Voorraad")

# A. Zoekbalk
zoekterm = st.text_input("Zoeken", placeholder="Typ hier...")

# B. Filteren (We maken een NIEUWE weergave, los van de hoofddata)
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# C. Voeg de checkbox kolom toe aan de WEERGAVE (standaard False)
# We dwingen hier af dat vinkjes ALTIJD uit staan als je zoekt/laadt.
view_df.insert(0, "Selecteer", False)

# D. De Tabel Editor
# We gebruiken een unieke key gebaseerd op de zoekterm. 
# Dit zorgt ervoor dat als je zoekt, de tabel volledig wordt ververst (vinkjes weg).
edited_df = st.data_editor(
    view_df,
    key=f"editor_{len(view_df)}_{zoekterm}", 
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "ID": None
    },
    disabled=["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"],
    hide_index=True,
    height=600,
    use_container_width=True
)

# ==========================================
# 7. VERWIJDER LOGICA (ALLEEN WAT JE ZIET)
# ==========================================

# We kijken nu ALLEEN naar 'edited_df'. Dat is de tabel die jij op je scherm hebt.
# Wat daar niet in staat (omdat het verborgen is), bestaat voor deze logica niet.
geselecteerde_regels = edited_df[edited_df["Selecteer"] == True]

if not geselecteerde_regels.empty:
    aantal = len(geselecteerde_regels)
    st.warning(f"Je hebt **{aantal}** regels geselecteerd.")
    
    if st.button(f"🗑️ Verwijder {aantal} regels definitief"):
        # 1. Haal de IDs op van de regels die JIJ hebt aangevinkt
        ids_weg = geselecteerde_regels["ID"].tolist()
        
        # 2. Verwijder deze IDs uit de hoofddatabase
        st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
        
        # 3. Opslaan
        sla_data_op(st.session_state.mijn_data)
        
        st.success("Regels verwijderd!")
        time.sleep(1)
        st.rerun()
