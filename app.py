import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: DESIGN & OPTIMALISATIE ---
st.markdown("""
    <style>
    /* Algemeen */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Cards & Balken */
    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 8px;
    }
    .actie-balk {
        background-color: #f1f3f4; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd;
    }

    /* Knoppen Styling */
    div.stButton > button { border-radius: 6px; height: 42px; font-weight: 600; border: none; }
    
    /* Blauw (Acties) */
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="upload_btn"],
    div.stButton > button[key="bulk_update_btn"],
    div.stButton > button[key="select_all_btn"] { 
        background-color: #0d6efd; color: white; 
    }
    
    /* Wit/Rood (Wis/Annuleer/Deselecteer) */
    div.stButton > button[key="clear_btn"],
    div.stButton > button[key="cancel_del_btn"],
    div.stButton > button[key="deselect_btn"] { 
        background-color: white; color: #dc3545; border: 1px solid #dc3545; 
    }
    
    /* Rood (Verwijder) */
    div.stButton > button[key="header_del_btn"] {
        background-color: #dc3545; color: white;
    }
    
    /* Groen (Bevestig) */
    div.stButton > button[key="real_del_btn"] {
        background-color: #198754; color: white;
    }

    /* Checkbox vergroten */
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }

    /* VERBERG SIDEBAR OP TABLETS (< 1024px) */
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

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns: df[col] = df[col].apply(clean_int)
            
    return df[["ID"] + DATAKOLOMMEN].fillna("").astype(str)

def sla_data_op(df):
    conn = get_connection()
    save_df = df.copy()
    if "Selecteer" in save_df.columns:
        save_df = save_df.drop(columns=["Selecteer"])
    conn.update(worksheet="Blad1", data=save_df)
    st.cache_data.clear()

def clear_search():
    st.session_state.zoek_input = ""

def bereken_unieke_orders(df):
    try:
        orders = df[df["Order"] != ""]["Order"].astype(str)
        basis_orders = orders.apply(lambda x: x.split('-')[0].strip())
        return basis_orders.nunique()
    except:
        return 0

# --- AUTH ---
if "ingelogd" not in st.session_state: st.session_state.ingelogd = False
if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Inloggen</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", label_visibility="collapsed")
        if st.button("Starten", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data_van_cloud()
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# --- SIDEBAR (IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file:
        st.info("Bestand herkend!")
        if st.button("📤 Toevoegen", key="upload_btn"):
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
                st.success(f"✅ {len(final_upload)} regels toegevoegd!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")
    st.markdown("---")
    if st.button("🔄 Data Herladen"):
        del st.session_state.mijn_data
        st.rerun()

# --- HEADER & KPI's ---
c1, c2, c3 = st.columns([2, 1, 1])
with c1: st.title("🏭 Glas Voorraad")
with c2: 
    try: tot = df["Aantal"].replace('', '0').astype(int).sum()
    except: tot = 0
    st.metric("Totaal Ruiten", tot)
with c3: st.metric("Unieke Orders", bereken_unieke_orders(df))

# --- SUCCES MELDING ---
if 'success_msg' in st.session_state and st.session_state.success_msg:
    st.success(st.session_state.success_msg)
    st.session_state.success_msg = "" 

# --- ACTIEBALK LOGICA & WEERGAVE ---
st.markdown('<div class="actie-balk">', unsafe_allow_html=True)

try:
    geselecteerd_df = df[df["Selecteer"] == True]
    aantal_geselecteerd = len(geselecteerd_df)
except:
    aantal_geselecteerd = 0

if st.session_state.get('ask_del'):
    # FASE 3: BEVESTIGING
    st.markdown(f"**⚠️ Weet je zeker dat je {aantal_geselecteerd} regels wilt verwijderen?**")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Verwijderen", key="real_del_btn", use_container_width=True):
            ids_weg = geselecteerd_df["ID"].tolist()
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.success_msg = f"🗑️ {len(ids_weg)} regels verwijderd!"
            st.rerun()
    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    # FASE 2: BULK ACTIES
    # Layout: [Info + Deselect] [Verwijder] [Input] [Wijzig]
    c_info, c_del, c_input, c_update = st.columns([1.5, 1, 1.5, 1], gap="small", vertical_alignment="bottom")
    
    with c_info:
        col_inf_txt, col_inf_btn = st.columns([1, 1])
        with col_inf_txt:
            st.markdown(f"✅ **{aantal_geselecteerd}** geselecteerd")
        with col_inf_btn:
             if st.button("❌ Deselecteer", key="deselect_btn", use_container_width=True):
                 st.session_state.mijn_data["Selecteer"] = False
                 sla_data_op(st.session_state.mijn_data)
                 st.rerun()

    with c_del:
        if st.button("🗑️ Verwijder", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()
            
    with c_input:
        nieuwe_locatie = st.text_input("Nieuwe Locatie", placeholder="Bijv. Bok 12", label_visibility="collapsed", key="bulk_loc_input")
        
    with c_update:
        if st.button("✏️ Wijzig", key="bulk_update_btn", use_container_width=True):
            if nieuwe_locatie:
                ids_te_wijzigen = geselecteerd_df["ID"].tolist()
                masker = st.session_state.mijn_data["ID"].isin(ids_te_wijzigen)
                st.session_state.mijn_data.loc[masker, "Locatie"] = nieuwe_locatie
                st.session_state.mijn_data.loc[masker, "Selecteer"] = False # Auto deselect na wijziging
                sla_data_op(st.session_state.mijn_data)
                st.session_state.success_msg = f"✅ Locatie van {len(ids_te_wijzigen)} regels gewijzigd naar '{nieuwe_locatie}'!"
                st.rerun()
            else:
                st.warning("Vul eerst een locatie in.")

else:
    # FASE 1: ZOEKEN & SELECTEREN
    # Eerst berekenen we view_df om te weten wat 'alles' is
    temp_view_df = df.copy()
    temp_zoek = st.session_state.get("zoek_input", "")
    if temp_zoek:
        mask = temp_view_df.astype(str).apply(lambda x: x.str.contains(temp_zoek, case=False)).any(axis=1)
        temp_view_df = temp_view_df[mask]

    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 1.5], gap="small", vertical_alignment="bottom")
    
    with c_in:
        zoekterm = st.text_input("Zoek", placeholder="🔍 Typ order, maat of locatie...", label_visibility="collapsed", key="zoek_input")
    with c_zo:
        st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi:
        st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)
    with c_all:
        if st.button(f"✅ Alles ({len(temp_view_df)})", key="select_all_btn", help="Selecteer alle zichtbare regels", use_container_width=True):
            # Selecteer alle zichtbare ID's
            visible_ids = temp_view_df["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(visible_ids), "Selecteer"] = True
            sla_data_op(st.session_state.mijn_data)
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
view_df = df.copy() 
if aantal_geselecteerd == 0 and zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("✅", default=False, width="small"),
        "Locatie": st.column_config.TextColumn("Locatie", width="small"),
        "Aantal": st.column_config.TextColumn("Aant.", width="small"),
        "Breedte": st.column_config.TextColumn("Br.", width="small"),
        "Hoogte": st.column_config.TextColumn("Hg.", width="small"),
        "Spouw": st.column_config.TextColumn("Sp.", width="small"),
        "Omschrijving": st.column_config.TextColumn("Omschrijving", width="medium"),
        "Order": st.column_config.TextColumn("Order", width="medium"),
        "ID": None
    },
    disabled=["ID"],
    hide_index=True,
    use_container_width=True,
    height=700,
    key="editor"
)

# --- UPDATE SYNC ---
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)
    st.rerun()
