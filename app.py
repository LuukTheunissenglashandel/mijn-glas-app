import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- INITIALISATIE (ANTI-FLASH) ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""
if "success_msg" not in st.session_state: st.session_state.success_msg = ""

# --- CSS: HET MOOIE DESIGN IS TERUG ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    .actie-container {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px;
        border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px;
    }

    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; border: none; }
    div.stButton > button[key="search_btn"], div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
    div.stButton > button[key="clear_btn"], div.stButton > button[key="deselect_btn"], div.stButton > button[key="cancel_del_btn"] { background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; }
    div.stButton > button[key="header_del_btn"] { background-color: #dc3545; color: white; }
    div.stButton > button[key="real_del_btn"] { background-color: #198754; color: white; }

    div[data-testid="stMetric"] { background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; }
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
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
    if df.empty: return
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

def reset_selectie_bij_zoeken():
    """Wist alle vinkjes zodra de zoekterm verandert om spook-selecties te voorkomen."""
    if "mijn_data" in st.session_state:
        st.session_state.mijn_data["Selecteer"] = False

def clear_search():
    st.session_state.zoek_input = ""
    reset_selectie_bij_zoeken()

# --- AUTH ---
if not st.session_state.ingelogd:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

# --- FILTER LOGICA ---
zoekterm = st.session_state.zoek_input
view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- BEVEILIGING: TELLEN VAN ZICHTBARE SELECTIE ---
echt_geselecteerd = view_df[view_df["Selecteer"] == True]
aantal_echt = len(echt_geselecteerd)

# --- HEADER ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = st.session_state.mijn_data["Aantal"].astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: 
    try: n = st.session_state.mijn_data[st.session_state.mijn_data["Order"] != ""]["Order"].nunique()
    except: n = 0
    st.metric("Unieke Orders", n)

if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = ""

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    st.warning(f"⚠️ Weet je zeker dat je **{aantal_echt}** geselecteerde ruiten wilt verwijderen?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ JA, Verwijderen", key="real_del_btn", use_container_width=True):
            ids_weg = echt_geselecteerd["ID"].tolist()
            st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.mijn_data["Selecteer"] = False
            st.session_state.zoek_input = ""
            st.session_state.success_msg = f"✅ {len(ids_weg)} ruiten verwijderd."
            st.rerun()
    with c2:
        if st.button("❌ Annuleren", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_echt > 0:
    c1, c2, c3 = st.columns([1.5, 3, 1.5], vertical_alignment="bottom")
    with c1: st.markdown(f"**{aantal_echt}** geselecteerd")
    with c2:
        nl = st.text_input("Nieuwe Locatie", placeholder="Locatie...")
        if st.button("📍 Verplaatsen", key="bulk_update_btn"):
            ids = echt_geselecteerd["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_state.mijn_data["ID"].isin(ids), "Locatie"] = nl
            st.session_state.mijn_data["Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.rerun()
    with c3:
        if st.button("🗑️ Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    c1, c2, c3 = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
    with c1: st.text_input("Zoeken", key="zoek_input", on_change=reset_selectie_bij_zoeken, placeholder="Zoek ruit...")
    with c2: st.button("🔍", key="search_btn", use_container_width=True)
    with c3: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

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

# --- SYNC ---
if not edited_df.equals(view_df):
    changes = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    for r_id, val in changes.items():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == r_id, "Selecteer"] = val
    st.rerun()

# --- SIDEBAR IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    up = st.file_uploader("Bestand", type=["xlsx"], label_visibility="collapsed")
    if up and st.button("Uploaden"):
        new = pd.read_excel(up).astype(str)
        new["ID"] = [str(uuid.uuid4()) for _ in range(len(new))]
        for c in DATAKOLOMMEN: 
            if c not in new.columns: new[c] = ""
        final = new[["ID"] + DATAKOLOMMEN]
        final.insert(0, "Selecteer", False)
        st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final], ignore_index=True)
        sla_data_op(st.session_state.mijn_data)
        st.success("Data toegevoegd")
        st.rerun()
