import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order", "Status"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: DESIGN & RESPONSIVENESS ---
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
    except:
        return str(val)

def laad_data_van_cloud():
    conn = get_connection()
    try:
        df = conn.read(worksheet="Blad1", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)
    except:
        return pd.DataFrame(columns=["ID"] + DATAKOLOMMEN)

    if "ID" not in df.columns:
        df["ID"] = [str(uuid.uuid4()) for _ in range(len(df))]
    
    for col in DATAKOLOMMEN:
        if col not in df.columns: df[col] = ""
    
    # Zorg dat Status altijd gevuld is
    if "Status" in df.columns:
        df["Status"] = df["Status"].fillna("In Voorraad").replace("", "In Voorraad")
    else:
        df["Status"] = "In Voorraad"

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df_to_save):
    conn = get_connection()
    save_df = df_to_save.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

def clear_search():
    st.session_state.zoek_input = ""

def bereken_unieke_orders(df):
    try:
        actieve_df = df[df["Status"] != "Uit Voorraad"]
        orders = actieve_df[actieve_df["Order"] != ""]["Order"].astype(str)
        basis_orders = orders.apply(lambda x: x.split('-')[0].strip())
        return basis_orders.nunique()
    except:
        return 0

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
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    if "Selecteer" not in st.session_state.mijn_data.columns:
        st.session_state.mijn_data.insert(0, "Selecteer", False)

# --- SIDEBAR ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_excel = st.file_uploader("Excel kiezen", type=["xlsx"], label_visibility="collapsed", key="u_excel")
    if uploaded_excel:
        if st.button("📤 Excel toevoegen", key="upload_excel_btn"):
            try:
                nieuwe_data = pd.read_excel(uploaded_excel)
                nieuwe_data.columns = [c.strip().capitalize() for c in nieuwe_data.columns]
                mapping = {"Pos": "Pos.", "Breedte": "Breedte", "Hoogte": "Hoogte", "Aantal": "Aantal", "Omschrijving": "Omschrijving", "Spouw": "Spouw", "Order": "Order"}
                nieuwe_data = nieuwe_data.rename(columns=mapping)
                
                nieuwe_data["ID"] = [str(uuid.uuid4()) for _ in range(len(nieuwe_data))]
                nieuwe_data["Status"] = "In Voorraad"
                if "Locatie" not in nieuwe_data.columns: nieuwe_data["Locatie"] = ""
                
                for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
                    if col in nieuwe_data.columns: nieuwe_data[col] = nieuwe_data[col].apply(clean_int)
                for c in DATAKOLOMMEN:
                    if c not in nieuwe_data.columns: nieuwe_data[c] = ""
                
                final_upload = nieuwe_data[["ID"] + DATAKOLOMMEN].astype(str)
                final_upload.insert(0, "Selecteer", False)
                
                st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_upload], ignore_index=True)
                sla_data_op(st.session_state.mijn_data)
                st.success(f"✅ {len(final_upload)} regels toegevoegd!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")

    st.markdown("---")
    if st.button("🔄 Data Herladen"):
        st.session_state.mijn_data = laad_data_van_cloud()
        st.session_state.mijn_data.insert(0, "Selecteer", False)
        st.rerun()

# --- KPI's ---
df = st.session_state.mijn_data
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: 
        actieve_voorraad = df[df["Status"] != "Uit Voorraad"]
        tot = actieve_voorraad["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("In Voorraad", tot)
with c3: st.metric("Unieke Orders", bereken_unieke_orders(df))

# --- ACTIES ---
geselecteerd_df = df[df["Selecteer"] == True]
aantal_geselecteerd = len(geselecteerd_df)

st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    st.markdown(f"**⚠️ Markeer {aantal_geselecteerd} regels als 'Uit Voorraad'?**")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Bevestig", key="real_del_btn", use_container_width=True):
            ids = geselecteerd_df["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Status"] = "Uit Voorraad"
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Selecteer"] = False
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.rerun()
    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    col_sel, col_loc, col_out = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")
    with col_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Wis selectie", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()
    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp: nieuwe_locatie = st.text_input("Nieuwe Locatie", placeholder="Locatie...", label_visibility="collapsed")
        with c_btn:
            if st.button("📍 Verplaats", key="bulk_update_btn", use_container_width=True):
                if nieuwe_locatie:
                    ids = geselecteerd_df["ID"].tolist()
                    st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Locatie"] = nieuwe_locatie
                    st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(ids), "Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.rerun()
    with col_out:
        if st.button("📦 Uit voorraad", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
else:
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    with c_in: zoekterm = st.text_input("Zoeken", placeholder="Zoek op order, maat, locatie...", label_visibility="collapsed", key="zoek_input")
    with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)
    with c_all:
        if st.button("✅ Selecteer alles", key="select_all_btn", use_container_width=True):
            temp_view = df.copy()
            if zoekterm:
                mask = temp_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
                temp_view = temp_view[mask]
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(temp_view["ID"]), "Selecteer"] = True
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
view_df = df.copy()
show_all = st.checkbox("Toon ook items 'Uit Voorraad' (Rood gemarkeerd)", value=False)

if not show_all:
    view_df = view_df[view_df["Status"] != "Uit Voorraad"]

if st.session_state.get("zoek_input"):
    z = st.session_state.zoek_input
    view_df = view_df[view_df.astype(str).apply(lambda x: x.str.contains(z, case=False)).any(axis=1)]

# Styling functie
def highlight_status(row):
    if row.Status == "Uit Voorraad":
        return ['background-color: #ffcccc; color: #990000; font-weight: bold'] * len(row)
    return [''] * len(row)

styled_view = view_df.style.apply(highlight_status, axis=1)

edited_df = st.data_editor(
    styled_view,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "Status": st.column_config.SelectboxColumn("Status", options=["In Voorraad", "Uit Voorraad"], width="small"),
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "ID": None
    },
    disabled=["ID"],
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# SYNC: Alleen wijzigingen doorvoeren op basis van ID om massa-updates te voorkomen
if not edited_df.equals(view_df):
    for idx, row in edited_df.iterrows():
        row_id = row["ID"]
        # Update alleen deze specifieke regel in de hoofddataset
        for col in DATAKOLOMMEN + ["Selecteer"]:
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"] == row_id, col] = row[col]
    
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
