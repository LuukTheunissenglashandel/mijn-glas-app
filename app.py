import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PRO DESIGN ---
st.markdown("""
    <style>
    /* 1. Algemene Layout */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max_width: 100%;
    }
    
    /* Verberg standaard elementen */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* 2. Dashboard Cards */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }

    /* 3. Actiebalk */
    .actie-balk {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
    }

    /* 4. Knoppen Styling */
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="upload_btn"] { 
        background-color: #0d6efd; 
        color: white; 
        border: none;
        border-radius: 6px;
        height: 42px;
    }
    
    div.stButton > button[key="clear_btn"] { 
        background-color: #ffffff; 
        color: #6c757d; 
        border: 1px solid #ced4da;
        border-radius: 6px; 
        height: 42px; 
    }

    div.stButton > button[key="header_del_btn"],
    div.stButton > button[key="cancel_del_btn"] {
        background-color: #dc3545;
        color: white;
        border: none;
        border-radius: 6px;
        height: 42px;
        font-weight: 600;
    }

    div.stButton > button[key="real_del_btn"] {
        background-color: #198754;
        color: white;
        border: none;
        border-radius: 6px;
        height: 42px;
        font-weight: 600;
    }

    /* 5. Tabel Optimalisatie */
    input[type=checkbox] { transform: scale(1.4); cursor: pointer; }
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

def laad_data():
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
        if col not in df.columns:
            df[col] = ""

    for col in ["Aantal", "Spouw", "Breedte", "Hoogte"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_int)
            
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
    """
    Logica: 252464-1 en 252464-2 zijn 1 order.
    We splitsen op het streepje '-' en pakken het eerste deel.
    """
    try:
        # Filter lege orders eruit
        orders = df[df["Order"] != ""]["Order"].astype(str)
        # Pak alles voor het streepje
        basis_orders = orders.apply(lambda x: x.split('-')[0].strip())
        return basis_orders.nunique()
    except:
        return 0

# --- AUTH ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

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
                st.error("Ongeldig wachtwoord")
    st.stop()

# --- MAIN APP ---

# 1. Data Laden
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()
    if "Selecteer" not in st.session_state.mijn_data.columns:
        st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# 2. SIDEBAR (IMPORT ONLY - CLEAN)
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies .xlsx bestand", type=["xlsx"], label_visibility="collapsed")
    
    if uploaded_file:
        st.info("Bestand gereed")
        if st.button("📤 Upload naar Cloud", key="upload_btn"):
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
                huidig_uit_cloud = laad_data()
                totaal = pd.concat([huidig_uit_cloud, final_upload], ignore_index=True)
                sla_data_op(totaal)
                del st.session_state.mijn_data
                st.success("Geüpload!")
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")
    st.markdown("---")
    if st.button("🔄 Ververs Data"):
        del st.session_state.mijn_data
        st.rerun()

# 3. DASHBOARD HEADER
col_head1, col_head2, col_head3 = st.columns([2, 1, 1])
with col_head1:
    st.title("🏭 Glas Voorraad")
with col_head2:
    try:
        total_aantal = df["Aantal"].replace('', '0').astype(int).sum()
    except:
        total_aantal = 0
    st.metric("Totaal Ruiten", total_aantal)
with col_head3:
    # Aangepaste logica voor unieke orders (252464-1 en 252464-2 = 1 order)
    unieke_orders = bereken_unieke_orders(df)
    st.metric("Unieke Orders", unieke_orders)

# 4. ACTIEBALK
st.markdown('<div class="actie-balk">', unsafe_allow_html=True)

try:
    geselecteerd = df[df["Selecteer"] == True]
    aantal_geselecteerd = len(geselecteerd)
except:
    aantal_geselecteerd = 0

if aantal_geselecteerd > 0:
    # MODUS: VERWIJDEREN
    c_info, c_del = st.columns([3, 1], vertical_alignment="center")
    with c_info:
        st.markdown(f"**{aantal_geselecteerd}** regel(s) geselecteerd")
    with c_del:
        if st.button(f"🗑️ Verwijder ({aantal_geselecteerd})", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True

else:
    # MODUS: ZOEKEN
    c_input, c_btn_zoek, c_btn_wis = st.columns([6, 1, 1], gap="small", vertical_alignment="bottom")
    
    with c_input:
        zoekterm = st.text_input("Zoeken", placeholder="🔍 Typ order, maat, locatie...", label_visibility="collapsed", key="zoek_input")
    with c_btn_zoek:
        st.button("🔍", key="search_btn", help="Zoeken", use_container_width=True)
    with c_btn_wis:
        st.button("❌", key="clear_btn", on_click=clear_search, help="Zoekopdracht wissen", use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# Filter Data
view_df = df.copy()
if aantal_geselecteerd == 0 and zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# 5. TABEL
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
    num_rows="fixed",
    height=700, 
    use_container_width=True, 
    key="editor"
)

# 6. OPSLAAN & DIALOOG
if not edited_df.drop(columns=["Selecteer"]).equals(df.loc[edited_df.index].drop(columns=["Selecteer"])):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)

if st.session_state.get('ask_del'):
    st.info("⚠️ Weet je zeker dat je deze regels wilt verwijderen?")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("JA, Verwijderen", key="real_del_btn", use_container_width=True):
            ids_weg = geselecteerd["ID"].tolist()
            st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.rerun()
    with col_nee:
        if st.button("NEE, Annuleren", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()
