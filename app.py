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
    # Veiligheidscheck: blokkeer als lijst plots leeg is terwijl hij vol was
    if df.empty and len(st.session_state.mijn_data) > 5:
        st.error("⚠️ FOUT: De app probeerde alles te wissen. Opslaan geblokkeerd.")
        return

    try:
        conn.update(worksheet="Blad1", data=df)
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

# Werk met een kopie voor weergave
df = st.session_state.mijn_data.copy()

# ==========================================
# 5. IMPORT (SIDEBAR)
# ==========================================
with st.sidebar:
    st.header("Excel Import")
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
    
    st.markdown("---")
    if st.button("Herlaad Data"):
        st.session_state.mijn_data = laad_data()
        st.rerun()

# ==========================================
# 6. HOOFDSCHERM
# ==========================================
st.title("🏭 Glas Voorraad")

# A. ZOEKEN
zoekterm = st.text_input("Zoeken", placeholder="Typ order, maat, locatie...")

# B. FILTEREN
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# C. TABEL TONEN (ZONDER VINKJES - PUUR KIJKEN)
st.dataframe(
    view_df.drop(columns=["ID"]), 
    hide_index=True, 
    use_container_width=True,
    height=400
)

# D. VERWIJDER MODULE (FOUTLOOS)
st.markdown("---")
st.subheader("🗑️ Verwijderen")

# Maak een leesbare lijst van de gevonden regels
# We maken een dictionary: "Order A - 100x100 (Locatie B)" -> ID
keuze_lijst = {}
for index, row in view_df.iterrows():
    # Dit is de tekst die je in de dropdown ziet
    label = f"Order: {row['Order']} | Maat: {row['Breedte']}x{row['Hoogte']} | Loc: {row['Locatie']} | ({row['Omschrijving']})"
    keuze_lijst[label] = row["ID"]

# De Dropdown / Multiselect
if not view_df.empty:
    geselecteerde_labels = st.multiselect(
        "Selecteer hieronder de regels die je wilt verwijderen:",
        options=list(keuze_lijst.keys())
    )

    if geselecteerde_labels:
        aantal = len(geselecteerde_labels)
        st.warning(f"Je staat op het punt **{aantal}** regel(s) definitief te verwijderen.")
        
        if st.button(f"JA, Verwijder {aantal} regels", type="primary"):
            # 1. Zoek de IDs bij de labels
            ids_om_te_wissen = [keuze_lijst[label] for label in geselecteerde_labels]
            
            # 2. Verwijder uit hoofddatabase
            st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_om_te_wissen)]
            
            # 3. Opslaan
            sla_data_op(st.session_state.mijn_data)
            
            st.success("Verwijderd!")
            time.sleep(1)
            st.rerun()
else:
    st.info("Geen ruiten gevonden met deze zoekterm.")
