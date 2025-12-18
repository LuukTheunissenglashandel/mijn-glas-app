import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PROFESSIONAL DESIGN ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    .actie-container {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    div.stButton > button { 
        border-radius: 8px; 
        height: 45px; 
        font-weight: 600; 
        border: none; 
        transition: all 0.2s ease-in-out;
    }
    
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="select_all_btn"],
    div.stButton > button[key="bulk_update_btn"] { 
        background-color: #0d6efd; color: white; 
    }

    div.stButton > button[key="clear_btn"],
    div.stButton > button[key="deselect_btn"], 
    div.stButton > button[key="cancel_del_btn"] { 
        background-color: #f8f9fa; color: #495057; border: 1px solid #dee2e6; 
    }
    
    div.stButton > button[key="header_del_btn"] {
        background-color: #dc3545; color: white;
    }
    
    div.stButton > button[key="real_del_btn"] {
        background-color: #198754; color: white;
    }

    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }

    @media only screen and (max-width: 1024px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
    }
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

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
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

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed", placeholder="Wachtwoord...")
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

if 'zoek_input' not in st.session_state: st.session_state.zoek_input = ""

# --- SIDEBAR IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
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
            
            final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
            final_upload.insert(0, "Selecteer", False)
            st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
            sla_data_op(st.session_state.mijn_data)
            st.success("✅ Toegevoegd!")
            time.sleep(1)
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    st.markdown("---")
    if st.button("🔄 Data Herladen"):
        st.session_state.mijn_data = laad_data_van_cloud()
        st.session_state.mijn_data.insert(0, "Selecteer", False)
        st.rerun()

# --- FILTER LOGICA ---
df_master = st.session_state.mijn_data
zoekterm = st.session_state.zoek_input
view_df = df_master.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- STATUS BEPALEN (Echt geselecteerd binnen view) ---
echt_geselecteerd = view_df[view_df["Selecteer"] == True]
aantal_geselecteerd = len(echt_geselecteerd)

# --- HEADER & KPI ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df_master["Aantal"].astype(float).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", int(tot))
with c3: 
    try: n = df_master[df_master["Order"] != ""]["Order"].nunique()
    except: n = 0
    st.metric("Unieke Orders", n)

# --- ACTIEBALK ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)
if st.session_state.get('ask_del'):
    st.warning(f"⚠️ Weet je zeker dat je **{aantal_geselecteerd}** regels wilt verwijderen?")
    c_ja, c_nee = st.columns([1, 1])
    with c_ja:
        if st.button("✅ JA, Melden", key="real_del_btn", use_container_width=True):
            ids_weg = echt_geselecteerd["ID"].tolist()
            st.session_state.mijn_data = df_master[~df_master["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.zoek_input = ""
            st.success("Verwijderd!")
            time.sleep(1)
            st.rerun()
    with c_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()
elif aantal_geselecteerd > 0:
    c_sel, c_loc, c_out = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")
    with c_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Wissen", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with c_loc:
        c_i, c_b = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_i: n_loc = st.text_input("Nieuwe Locatie", placeholder="Naar...")
        with c_b:
            if st.button("📍 Wijzig", key="bulk_update_btn", use_container_width=True):
                if n_loc:
                    st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(echt_geselecteerd["ID"]), "Locatie"] = n_loc
                    st.session_state.mijn_data["Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.rerun()
    with c_out:
        if st.button("📦 Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    with c_in: zoek = st.text_input("Zoeken", placeholder="Zoek...", value=st.session_state.zoek_input)
    with c_zo: 
        if st.button("🔍", key="search_btn"):
            st.session_state.zoek_input = zoek
            st.rerun()
    with c_wi:
        if st.button("❌", key="clear_btn"):
            st.session_state.zoek_input = ""
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with c_all:
        if st.button("✅ Alles Selecteren", key="select_all_btn"):
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(view_df["ID"]), "Selecteer"] = True
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", width="small"),
        "ID": None
    },
    disabled=DATAKOLOMMEN,
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- SYNC (Op ID basis om fouten te voorkomen) ---
if not edited_df.equals(view_df):
    changes = dict(zip(edited_df["ID"], edited_df["Selecteer"]))
    for r_id, val in changes.items():
        st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == r_id, "Selecteer"] = val
    st.rerun()
