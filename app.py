import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. INSTELLINGEN
# ==========================================
st.set_page_config(layout="wide", page_title="Glas Voorraad")
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

# Initialisatie (voorkom crashes)
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
        
    result = df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)
    result["Selecteer"] = False
    return result

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Fout bij opslaan: {e}")

def reset_selecties():
    """Zet alle vinkjes uit."""
    if not st.session_state.mijn_data.empty:
        st.session_state.mijn_data["Selecteer"] = False

# ==========================================
# 3. LOGIN
# ==========================================
if not st.session_state.ingelogd:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        with st.form("login"):
            ww = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Start", use_container_width=True):
                if ww == WACHTWOORD:
                    st.session_state.ingelogd = True
                    with st.spinner("Laden..."):
                        st.session_state.mijn_data = laad_data()
                    st.rerun()
                else:
                    st.error("Fout")
    st.stop()

# ==========================================
# 4. HOOFDSCHERM
# ==========================================
# Data check
if "ID" not in st.session_state.mijn_data.columns:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- SIDEBAR ---
with st.sidebar:
    st.header("Excel Import")
    uploaded = st.file_uploader("Kies Excel", type=["xlsx"])
    if uploaded and st.button("Toevoegen"):
        try:
            nieuwe = pd.read_excel(uploaded)
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
            final["Selecteer"] = False
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success("Toegevoegd!")
            time.sleep(1)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    st.markdown("---")
    if st.button("Reset Vinkjes & Reload"):
        reset_selecties()
        st.rerun()

# --- ZOEKEN ---
st.title("🏭 Glas Voorraad")
# on_change=reset_selecties zorgt dat vinkjes weggaan als je typt
zoekterm = st.text_input("Zoeken", placeholder="Typ order, maat...", key="zoek_input", on_change=reset_selecties)

# --- FILTER LOGICA ---
# 1. Maak eerst de gefilterde view
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# 2. CRUCIAAL: Tel ALLEEN vinkjes die in de view_df (zichtbare lijst) staan!
#    De oude code telde 'df' (alles), deze code telt 'view_df' (wat je ziet).
zichtbare_selectie = view_df[view_df["Selecteer"] == True]
aantal_geselecteerd = len(zichtbare_selectie)

# --- KNOPPEN ---
if aantal_geselecteerd > 0:
    st.info(f"**{aantal_geselecteerd}** regels geselecteerd in deze zoekopdracht.")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button(f"🗑️ Verwijder {aantal_geselecteerd}", type="primary"):
            # A. Pak alleen de IDs van de ZICHTBARE selectie
            ids_weg = zichtbare_selectie["ID"].tolist()
            
            # B. Verwijder die uit de grote database
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            
            # C. Opslaan & Reset
            sla_data_op(st.session_state.mijn_data)
            st.session_state.zoek_input = ""
            st.success("Verwijderd!")
            time.sleep(1)
            st.rerun()

# --- EDITOR ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "ID": None
    },
    disabled=["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- SYNC ---
if not edited_df.equals(view_df):
    # Update de vinkjes in de hoofddatabase
    wijzigingen = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    st.session_state.mijn_data["Selecteer"] = st.session_state.mijn_data["ID"].map(wijzigingen).fillna(st.session_state.mijn_data["Selecteer"]).astype(bool)
    st.rerun()
