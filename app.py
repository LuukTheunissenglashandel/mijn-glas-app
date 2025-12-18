import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- INITIALISATIE ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""
if "success_msg" not in st.session_state: st.session_state.success_msg = ""

# --- CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    .actie-container { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px; border-radius: 12px; margin-bottom: 20px; }
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; }
    div.stButton > button[key="search_btn"], div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="real_del_btn"] { background-color: #198754; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCTIES ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df.fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

# --- AUTH ---
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen"):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

# --- FILTER LOGICA ---
zoekterm = st.session_state.zoek_input
view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- BEPALEN WAT ÉCHT GESELECTEERD IS (ZICHTBAAR + AANGEVINKT) ---
# Dit is de cruciale beveiligingslaag
echt_geselecteerd = view_df[view_df["Selecteer"] == True]
aantal_echt = len(echt_geselecteerd)

# --- HEADER ---
st.title("🏭 Glas Voorraad")
if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = ""

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    st.warning(f"⚠️ Bezig met verwijderen: Er zijn **{aantal_echt}** regels zichtbaar geselecteerd.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ JA, Verwijder deze", key="real_del_btn"):
            ids_weg = echt_geselecteerd["ID"].tolist()
            st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.mijn_data["Selecteer"] = False
            st.session_state.zoek_input = ""
            st.session_state.success_msg = f"✅ {len(ids_weg)} ruiten verwijderd."
            st.rerun()
    with c2:
        if st.button("❌ Annuleer"):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_echt > 0:
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1: st.write(f"**{aantal_echt}** ruiten geselecteerd")
    with c2:
        nl = st.text_input("Nieuwe Locatie", key="loc_input")
        if st.button("📍 Verplaatsen"):
            ids = echt_geselecteerd["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Locatie"] = nl
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
    with c3:
        if st.button("🗑️ Uit voorraad", key="header_del_btn"):
            st.session_state.ask_del = True
            st.rerun()
else:
    c1, c2, c3 = st.columns([5, 1, 1])
    with c1: st.text_input("Zoeken", key="zoek_input", placeholder="Filter lijst...")
    with c2: st.button("🔍", key="search_btn")
    with c3: 
        if st.button("❌"):
            st.session_state.zoek_input = ""
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
edited_df = st.data_editor(
    view_df,
    column_config={"ID": None, "Selecteer": st.column_config.CheckboxColumn("✅", width="small")},
    disabled=DATAKOLOMMEN,
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- SYNC (ID-SPECIFIEK) ---
if not edited_df.equals(view_df):
    changes = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    for r_id, val in changes.items():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == r_id, "Selecteer"] = val
    st.rerun()
