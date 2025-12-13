import streamlit as st
import pandas as pd
import uuid
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="collapsed")

# --- CSS: MODERN DESIGN & TABLET OPTIMALISATIE ---
st.markdown("""
    <style>
    /* 1. Algemene Layout */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 5rem;
        max_width: 100%;
    }
    
    /* Verberg standaard Streamlit elementen */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* 2. Dashboard Cards (Statistieken) */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* 3. Zoekbalk Container */
    .zoek-container {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border: 1px solid #eee;
    }

    /* 4. Knoppen Styling */
    /* Primaire Actie (Zoeken, Uploaden, Ja) */
    div.stButton > button[key="search_btn"], 
    div.stButton > button[key="real_del_btn"],
    div.stButton > button[key="upload_btn"] { 
        background-color: #0056b3; /* Professioneel Blauw */
        color: white; 
        border-radius: 6px; 
        height: 45px; 
        width: 100%; 
        border: none;
        font-weight: 500;
        transition: all 0.2s;
    }
    div.stButton > button[key="search_btn"]:hover { background-color: #004494; }

    /* Secundaire Actie (Wissen, Nee) */
    div.stButton > button[key="clear_btn"],
    div.stButton > button[key="cancel_del_btn"] { 
        background-color: #ffffff; 
        color: #dc3545; 
        border: 1px solid #dc3545; 
        border-radius: 6px; 
        height: 45px; 
        width: 100%;
        font-weight: 500;
    }
    div.stButton > button[key="clear_btn"]:hover { background-color: #fff5f5; }

    /* Verwijder knop (onderaan) */
    div.stButton > button[key="main_delete_btn"] {
        background-color: #dc3545;
        color: white;
        border-radius: 6px;
        height: 48px;
        width: 100%;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(220, 53, 69, 0.3);
    }

    /* 5. Tabel & Tablet Optimalisatie */
    /* Vinkjes groter maken voor touch */
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }
    
    /* Tabel tekst iets groter en luchtiger */
    [data-testid="stDataFrameResizable"] {
        font-size: 16px;
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

# --- AUTH ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("### 🔒 Glas Voorraad Systeem")
        ww = st.text_input("Voer wachtwoord in", type="password")
        if st.button("Inloggen"):
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

# 2. Sidebar (Import)
with st.sidebar:
    st.markdown("### 📥 Excel Import")
    uploaded_file = st.file_uploader("Sleep bestand hierheen", type=["xlsx"])
    if uploaded_file:
        st.write("---")
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
                st.success("Succesvol geüpload!")
                st.rerun()
            except Exception as e:
                st.error(f"Fout: {e}")

# 3. HEADER & STATISTIEKEN (KPI's)
c_title, c_stats1, c_stats2 = st.columns([2, 1, 1])
with c_title:
    st.title("🏭 Glas Voorraad")
with c_stats1:
    # Bereken totaal aantal (som van kolom Aantal, veilig geconverteerd)
    try:
        totaal_glas = df["Aantal"].replace('', '0').astype(int).sum()
    except:
        totaal_glas = 0
    st.metric("Totaal Ruiten", f"{totaal_glas} stuks")
with c_stats2:
    st.metric("Unieke Orders", len(df["Order"].unique()))

st.write("") # Witregel

# 4. ZOEKBALK IN 'CARD' STIJL
with st.container():
    # Dit maakt een visueel kader om het zoekgedeelte
    st.markdown('<div class="zoek-container">', unsafe_allow_html=True)
    col_input, col_zoek, col_wis = st.columns([5, 1, 1], gap="small", vertical_alignment="bottom")

    with col_input:
        zoekterm = st.text_input("Zoeken", placeholder="🔍 Typ ordernummer, maat of locatie...", label_visibility="visible", key="zoek_input")

    with col_zoek:
        st.button("Zoeken", key="search_btn")

    with col_wis:
        st.button("Wis", on_click=clear_search, key="clear_btn")
    
    st.markdown('</div>', unsafe_allow_html=True)

# Filter logic
view_df = df.copy()
if zoekterm:
    mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# 5. TABEL (MODERN & RESPONSIVE)
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteer": st.column_config.CheckboxColumn("🗑️", default=False, width="small"),
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
    use_container_width=False, # Zorgt dat horizontaal scrollen werkt op tablet
    key="editor"
)

# 6. OPSLAAN & VERWIJDEREN
if not edited_df.drop(columns=["Selecteer"]).equals(df.loc[edited_df.index].drop(columns=["Selecteer"])):
    st.session_state.mijn_data.update(edited_df)
    sla_data_op(st.session_state.mijn_data)

try:
    geselecteerd = edited_df[edited_df["Selecteer"] == True]
except:
    geselecteerd = []

# Verwijder knop onderaan (zwevend of vast)
if len(geselecteerd) > 0:
    st.write("")
    col_del_L, col_del_R = st.columns([3, 1])
    with col_del_R:
        if st.button(f"🗑️ Verwijder {len(geselecteerd)} regels", type="primary", key="main_delete_btn"):
            st.session_state.ask_del = True
            
    if st.session_state.get('ask_del'):
        st.warning("Weet je zeker dat je deze regels wilt verwijderen?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ JA, Verwijderen", key="real_del_btn"):
                ids_weg = geselecteerd["ID"].tolist()
                st.session_state.mijn_data = st.session_state.mijn_data[~st.session_state.mijn_data["ID"].isin(ids_weg)]
                sla_data_op(st.session_state.mijn_data)
                st.session_state.ask_del = False
                st.rerun()
        with c2:
            if st.button("❌ ANNULEER", key="cancel_del_btn"):
                st.session_state.ask_del = False
                st.rerun()
