import streamlit as st
import pandas as pd
import uuid
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PRO DESIGN & ANTI-FLASH ---
st.markdown("""
    <style>
    /* Algemeen */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* Knoppen Styling */
    div.stButton > button { border-radius: 6px; height: 42px; font-weight: 600; border: none; transition: 0.2s; }
    
    /* Primaire Actie (Blauw) */
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="upload_btn"],
    div.stButton > button[key="bulk_update_btn"],
    div.stButton > button[key="select_all_btn"] { 
        background-color: #0d6efd; color: white; 
    }
    
    /* Secundair (Wit/Grijs) */
    div.stButton > button[key="clear_btn"],
    div.stButton > button[key="deselect_btn"] { 
        background-color: white; color: #495057; border: 1px solid #ced4da; 
    }
    
    /* Gevaar (Rood) */
    div.stButton > button[key="header_del_btn"], div.stButton > button[key="cancel_del_btn"] {
        background-color: #dc3545; color: white;
    }
    
    /* Succes (Groen) */
    div.stButton > button[key="real_del_btn"] {
        background-color: #198754; color: white;
    }

    /* Actiebalk Container */
    .actie-container {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }

    /* Checkbox vergroten */
    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }

    /* TABLET TWEAKS: Verberg sidebar op kleine schermen */
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

# --- STATUS BEPALING ---
try:
    geselecteerd_df = df[df["Selecteer"] == True]
    aantal_geselecteerd = len(geselecteerd_df)
except:
    aantal_geselecteerd = 0

# --- SLIMME BALK BOVENAAN ---
# Hier bepalen we wat we tonen: Zoekbalk OF Actie-menu
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

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
    # FASE 2: ACTIE MODUS (ER IS GESELECTEERD)
    
    # Toggle: Wat wil je zien?
    col_view, col_actions = st.columns([2, 5])
    
    with col_view:
        # Dit lost je vraag op: "Alleen die rijen zichtbaar blijven"
        filter_mode = st.radio("Toon:", ["Alles", f"Geselecteerd ({aantal_geselecteerd})"], 
                               horizontal=True, label_visibility="collapsed")

    with col_actions:
        # Layout: [Deselect] [Nieuwe Locatie] [Wijzig] [Verwijder]
        c_des, c_inp, c_upd, c_del = st.columns([1, 2, 1, 1], gap="small")
        
        with c_des:
             if st.button("❌ Wis", key="deselect_btn", help="Selectie wissen", use_container_width=True):
                 st.session_state.mijn_data["Selecteer"] = False
                 st.rerun()
        
        with c_inp:
            nieuwe_locatie = st.text_input("Nieuwe Locatie", placeholder="Naar locatie...", label_visibility="collapsed", key="bulk_loc_input")
            
        with c_upd:
            if st.button("✏️ Wijzig", key="bulk_update_btn", use_container_width=True):
                if nieuwe_locatie:
                    ids_te_wijzigen = geselecteerd_df["ID"].tolist()
                    masker = st.session_state.mijn_data["ID"].isin(ids_te_wijzigen)
                    st.session_state.mijn_data.loc[masker, "Locatie"] = nieuwe_locatie
                    st.session_state.mijn_data.loc[masker, "Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.session_state.success_msg = f"✅ {len(ids_te_wijzigen)} ruiten verplaatst naar '{nieuwe_locatie}'"
                    st.rerun()
                else:
                    st.toast("Vul eerst een locatie in", icon="⚠️")
        
        with c_del:
            if st.button("🗑️ Weg", key="header_del_btn", help="Verwijderen", use_container_width=True):
                st.session_state.ask_del = True
                st.rerun()

else:
    # FASE 1: ZOEK MODUS
    filter_mode = "Alles" # Standaard als niks geselecteerd is
    
    # Zoeken + Alles Selecteren
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 1.5], gap="small", vertical_alignment="bottom")
    
    with c_in:
        zoekterm = st.text_input("Zoek", placeholder="🔍 Typ order, maat of locatie...", label_visibility="collapsed", key="zoek_input")
    with c_zo:
        st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi:
        st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)
    with c_all:
        if st.button("✅ Alles Selecteren", key="select_all_btn", use_container_width=True):
            # We moeten weten wat 'alles' is (rekening houdend met zoekfilter)
            temp_view = df.copy()
            if zoekterm:
                mask = temp_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
                temp_view = temp_view[mask]
            
            visible_ids = temp_view["ID"].tolist()
            # Update sessie state
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(visible_ids), "Selecteer"] = True
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL LOGICA ---
view_df = df.copy()

# Filter logic
if "Geselecteerd" in str(filter_mode) and aantal_geselecteerd > 0:
    # Toon ALLEEN geselecteerd
    view_df = view_df[view_df["Selecteer"] == True]
else:
    # Toon zoekresultaten (of alles)
    if aantal_geselecteerd == 0 and st.session_state.get("zoek_input"):
        zoekterm = st.session_state.get("zoek_input")
        mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
        view_df = view_df[mask]

# De Editor
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

# --- ANTI-FLASH UPDATE SYNC ---
# We slaan NIET op naar cloud bij vinkjes zetten. Alleen naar geheugen.
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    # Let op: GEEN sla_data_op() hier! Dat is de fix voor het flitsen.
    # We slaan pas op als je op een actieknop klikt.
    st.rerun()
