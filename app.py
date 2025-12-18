import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- INITIALISATIE (VOORKOMT FLASH ERRORS) ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if "zoek_input" not in st.session_state: st.session_state.zoek_input = ""
if "success_msg" not in st.session_state: st.session_state.success_msg = ""

# --- CSS: DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    .actie-container { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }
    div.stButton > button { border-radius: 8px; height: 45px; font-weight: 600; border: none; }
    div.stButton > button[key="search_btn"], div.stButton > button[key="select_all_btn"], div.stButton > button[key="bulk_update_btn"] { background-color: #0d6efd; color: white; }
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

def clean_int(val):
    try:
        if val is None or str(val).strip() == "": return ""
        s_val = str(val).replace(',', '.').strip()
        return str(int(float(s_val)))
    except: return str(val)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except: return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    if "ID" not in df.columns: df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    if df.empty:
        st.warning("⚠️ Opslaan geannuleerd: De tabel is leeg!")
        return
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns: save_df = save_df.drop(columns=["Selecteer"])
    try:
        conn.update(worksheet="Blad1", data=save_df)
        st.cache_data.clear()
    except Exception as e: st.error(f"Fout bij opslaan: {e}")

def clear_search():
    st.session_state.zoek_input = ""

# --- AUTH ---
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else: st.error("Fout wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df_master = st.session_state.mijn_data

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"])
    if uploaded_file and st.button("📤 Toevoegen aan voorraad", key="upload_btn"):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
            mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
            if "Locatie" not in nieuwe_data.columns: nieuwe_data["Locatie"] = ""
            for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                if col in nieuwe_data.columns: nieuwe_data[col] = nieuwe_data[col].apply(clean_int)
            for c in DATAKOLOMMEN:
                if c not in nieuwe_data.columns: nieuwe_data[c] = ""
            final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
            final_upload.insert(0, "Selecteer", False)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success(f"✅ Toegevoegd!")
            time.sleep(1)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    if st.button("🔄 Data Herladen"):
        del st.session_state.mijn_data
        st.rerun()

# --- HEADER ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df_master["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: 
    try: n = df_master[df_master["Order"] != ""]["Order"].apply(lambda x: str(x).split('-')[0].strip()).nunique()
    except: n = 0
    st.metric("Unieke Orders", n)

if st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = ""

# --- ACTIEBALK ---
geselecteerd_df = df_master[df_master["Selecteer"] == True]
aantal_geselecteerd = len(geselecteerd_df)

st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    st.markdown(f"**⚠️ Weet je zeker dat je {aantal_geselecteerd} regels wilt verwijderen?**")
    cj, cn = st.columns([1, 1])
    with cj:
        if st.button("✅ JA, Melden", key="real_del_btn", use_container_width=True):
            ids_weg = geselecteerd_df["ID"].tolist()
            st.session_state.mijn_data = df_master[~df_master["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.zoek_input = ""
            st.session_state.success_msg = f"✅ Verwijderd!"
            st.rerun()
    with cn:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    cs, cl, co = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")
    with cs:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Wissen", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with cl:
        ci, cb = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with ci: nl = st.text_input("Nieuwe Locatie", placeholder="Naar...")
        with cb:
            if st.button("📍 Wijzig", key="bulk_update_btn", use_container_width=True):
                if nl:
                    st.session_state.mijn_data.loc[df_master["Selecteer"] == True, "Locatie"] = nl
                    st.session_state.mijn_data["Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.rerun()
    with co:
        if st.button("📦 Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    ci, cz, cw, ca = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    with ci: zoek = st.text_input("Zoeken", placeholder="Zoek...", key="zoek_input")
    with cz: st.button("🔍", key="search_btn")
    with cw: st.button("❌", key="clear_btn", on_click=clear_search)
    with ca:
        if st.button("✅ Alles Selecteren", key="select_all_btn"):
            mask = df_master.astype(str).apply(lambda x: x.str.contains(zoek, case=False)).any(axis=1) if zoek else [True]*len(df_master)
            st.session_state.mijn_data.loc[mask, "Selecteer"] = True
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- FILTER WEERGAVE ---
view_df = df_master.copy()
zoekterm = st.session_state.zoek_input
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- EDITOR ---
edited_df = st.data_editor(
    view_df,
    column_config={"ID": None, "Selecteer": st.column_config.CheckboxColumn("✅", width="small")},
    disabled=DATAKOLOMMEN,
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- DE VEILIGE SYNC (CRUCIAAL) ---
# In plaats van update() gebruiken we een ID-match om alleen de Selecteer-kolom te syncen
if not edited_df.equals(view_df):
    # Map de nieuwe Selecteer-waardes op basis van ID naar de master-data
    changes = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    for r_id, val in changes.items():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == r_id, "Selecteer"] = val
    st.rerun()
