import streamlit as st
import pandas as pd
import uuid
import time
import re
import pdfplumber
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATIE ---
WACHTWOORD = "glas123"
DATAKOLOMMEN = ["Locatie", "Aantal", "Breedte", "Hoogte", "Omschrijving", "Spouw", "Order"]

st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

# --- CSS: PROFESSIONAL DESIGN ---
st.markdown("""
    <style>
    /* 1. Algemene Layout */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    /* 2. Actie Container */
    .actie-container {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }

    /* 3. Knoppen Styling */
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

    /* KPI Cards */
    div[data-testid="stMetric"] {
        background-color: #fff; border: 1px solid #eee; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }

    /* Checkbox vergroten */
    input[type=checkbox] { transform: scale(1.6); cursor: pointer; }

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
        # Vervang komma door punt en rond af
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

# --- SLIMME PDF PARSER (MET LOCATIE FIX) ---
def parse_racklisten_pdf(uploaded_file):
    data = []
    
    # pdfplumber openen
    with pdfplumber.open(uploaded_file) as pdf:
        
        # Dit houdt de locatie bij terwijl we door het bestand "lezen"
        # We beginnen leeg
        huidige_locatie_nummer = ""
        
        for page in pdf.pages:
            # layout=True zorgt dat we regel voor regel van boven naar beneden lezen
            # Dit is cruciaal om eerst de header (Gestell) te zien en dan pas de regels
            text = page.extract_text(layout=True, x_tolerance=2)
            
            if not text: continue
            
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                # STAP 1: Check of deze regel een Gestell nummer bevat
                # We zoeken naar "Gestell" gevolgd door cijfers
                if "Gestell" in line:
                    # Regex om het nummer te vinden. Bijv: "Gestell: 0000203762-"
                    gestell_match = re.search(r"Gestell.*(\d{4,})", line)
                    if gestell_match:
                        volledig_nummer = gestell_match.group(1)
                        # We pakken de LAATSTE 4 cijfers
                        huidige_locatie_nummer = volledig_nummer[-4:]
                    continue # Ga naar de volgende regel, dit is geen glas-data

                # STAP 2: Check of deze regel glas-data is
                # We zoeken naar het patroon: Order/Pos Aantal Breedte Hoogte
                # Bijv: "1398617/4 2 1382 1524" of "1398617/21 1 996 * 741"
                
                # Regex uitleg:
                # (\d+/\d+)   -> Order/Pos (123/4)
                # \s+(\d+)    -> Spatie + Aantal (2)
                # \s+(\d{3,4}) -> Spatie + Breedte (3 of 4 cijfers)
                # \s*[\*x]?\s* -> Spatie, optioneel * of x, spatie
                # (\d{3,4})   -> Hoogte (3 of 4 cijfers)
                match = re.search(r"(\d+/\d+)\s+(\d+)\s+(\d{3,4})\s*[\*x]?\s*(\d{3,4})", line)
                
                if match:
                    # We hebben een match!
                    order_pos = match.group(1)
                    aantal = match.group(2)
                    breedte = match.group(3)
                    hoogte = match.group(4)
                    
                    # Probeer de omschrijving te pakken (alles achter de hoogte)
                    omschrijving = ""
                    try:
                        # Split op de hoogte en pak wat er achter staat
                        parts = line.split(str(hoogte))
                        if len(parts) > 1:
                            omschrijving = parts[-1].strip()
                            # Veel regels beginnen met "0 " of "0.0" na de maten, die halen we weg
                            if omschrijving.startswith("0 ") or omschrijving.startswith("0.0"):
                                omschrijving = omschrijving.replace("0 ", "", 1).replace("0.0", "", 1).strip()
                    except:
                        pass

                    # Voeg toe aan de lijst MET de huidige locatie
                    data.append({
                        "Locatie": huidige_locatie_nummer, # Hier gebruiken we de gevonden Gestell code
                        "Order": order_pos,
                        "Aantal": aantal,
                        "Breedte": breedte,
                        "Hoogte": hoogte,
                        "Omschrijving": omschrijving,
                        "Spouw": "" 
                    })
                    
    return pd.DataFrame(data)

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
    st.session_state.mijn_data.insert(0, "Selecteer", False)

df = st.session_state.mijn_data

# --- SIDEBAR (IMPORT) - ALLEEN DESKTOP ---
with st.sidebar:
    # 1. EXCEL IMPORT
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

    # 2. PDF IMPORT
    st.subheader("📄 PDF Rackliste Import")
    uploaded_pdf = st.file_uploader("PDF kiezen", type=["pdf"], label_visibility="collapsed", key="u_pdf")
    if uploaded_pdf:
        if st.button("📤 PDF verwerken & toevoegen", key="upload_pdf_btn"):
            try:
                pdf_data = parse_racklisten_pdf(uploaded_pdf)
                if not pdf_data.empty:
                    # Data gereedmaken
                    pdf_data["ID"] = [str(uuid.uuid4()) for _ in range(len(pdf_data))]
                    
                    # Ontbrekende kolommen vullen
                    for c in DATAKOLOMMEN:
                        if c not in pdf_data.columns: pdf_data[c] = ""
                    
                    # Netjes maken (integers van floats maken)
                    for col in ["Aantal", "Breedte", "Hoogte"]:
                        pdf_data[col] = pdf_data[col].apply(clean_int)
                        
                    final_pdf = pdf_data[["ID"] + DATAKOLOMMEN].astype(str)
                    final_pdf.insert(0, "Selecteer", False)
                    
                    st.session_state.mijn_data = pd.concat([st.session_state.mijn_data, final_pdf], ignore_index=True)
                    sla_data_op(st.session_state.mijn_data)
                    st.success(f"✅ {len(final_pdf)} ruiten uit PDF toegevoegd!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Geen bruikbare data gevonden. Controleer of de PDF leesbare tekst bevat.")
            except Exception as e:
                st.error(f"Fout bij PDF verwerking: {e}")

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

# --- STATUS ---
try:
    geselecteerd_df = df[df["Selecteer"] == True]
    aantal_geselecteerd = len(geselecteerd_df)
except:
    aantal_geselecteerd = 0

# --- ACTIEBALK CONTAINER ---
st.markdown('<div class="actie-container">', unsafe_allow_html=True)

if st.session_state.get('ask_del'):
    st.markdown(f"**⚠️ Weet je zeker dat je {aantal_geselecteerd} regels uit voorraad wilt melden?**")
    col_ja, col_nee = st.columns([1, 1])
    with col_ja:
        if st.button("✅ JA, Melden", key="real_del_btn", use_container_width=True):
            ids_weg = geselecteerd_df["ID"].tolist()
            st.session_state.mijn_data = df[~df["ID"].isin(ids_weg)]
            sla_data_op(st.session_state.mijn_data)
            st.session_state.ask_del = False
            st.session_state.success_msg = f"✅ {len(ids_weg)} regels uit voorraad gemeld!"
            st.rerun()
    with col_nee:
        if st.button("❌ ANNULEER", key="cancel_del_btn", use_container_width=True):
            st.session_state.ask_del = False
            st.rerun()

elif aantal_geselecteerd > 0:
    col_sel, col_loc, col_out = st.columns([1.5, 3, 1.5], gap="large", vertical_alignment="bottom")

    with col_sel:
        st.markdown(f"**{aantal_geselecteerd}** geselecteerd")
        if st.button("❌ Selectie wissen", key="deselect_btn", use_container_width=True):
            st.session_state.mijn_data["Selecteer"] = False
            st.rerun()

    with col_loc:
        c_inp, c_btn = st.columns([2, 1], gap="small", vertical_alignment="bottom")
        with c_inp:
            nieuwe_locatie = st.text_input("Nieuwe Locatie", placeholder="Naar locatie...", label_visibility="visible")
        with c_btn:
            if st.button("📍 Wijzig locatie", key="bulk_update_btn", use_container_width=True):
                if nieuwe_locatie:
                    ids_te_wijzigen = geselecteerd_df["ID"].tolist()
                    masker = st.session_state.mijn_data["ID"].isin(ids_te_wijzigen)
                    st.session_state.mijn_data.loc[masker, "Locatie"] = nieuwe_locatie
                    st.session_state.mijn_data.loc[masker, "Selecteer"] = False
                    sla_data_op(st.session_state.mijn_data)
                    st.session_state.success_msg = f"📍 {len(ids_te_wijzigen)} ruiten verplaatst naar '{nieuwe_locatie}'"
                    st.rerun()
                else:
                    st.toast("Vul eerst een locatie in", icon="⚠️")

    with col_out:
        st.write("") 
        if st.button("📦 Uit voorraad melden", key="header_del_btn", use_container_width=True):
            st.session_state.ask_del = True
            st.rerun()

else:
    c_in, c_zo, c_wi, c_all = st.columns([5, 1, 1, 2], gap="small", vertical_alignment="bottom")
    
    with c_in:
        zoekterm = st.text_input("Zoeken", placeholder="🔍 Order, afmeting, locatie...", label_visibility="visible", key="zoek_input")
    with c_zo:
        st.button("🔍", key="search_btn", use_container_width=True)
    with c_wi:
        st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)
    with c_all:
        if st.button("✅ Alles Selecteren", key="select_all_btn", use_container_width=True):
            temp_view = df.copy()
            if zoekterm:
                mask = temp_view.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
                temp_view = temp_view[mask]
            
            visible_ids = temp_view["ID"].tolist()
            st.session_state.mijn_data.loc[st.session_state.mijn_data["ID"].isin(visible_ids), "Selecteer"] = True
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)

# --- TABEL ---
view_df = df.copy()

if aantal_geselecteerd > 0:
    st.caption("Weergave opties:")
    filter_mode = st.radio("Toon:", ["Alles", f"Alleen Selectie ({aantal_geselecteerd})"], 
                           horizontal=True, label_visibility="collapsed")
    if "Alleen Selectie" in filter_mode:
        view_df = view_df[view_df["Selecteer"] == True]
    elif st.session_state.get("zoek_input"):
         zoekterm = st.session_state.get("zoek_input")
         mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
         view_df = view_df[mask]
else:
    if st.session_state.get("zoek_input"):
        zoekterm = st.session_state.get("zoek_input")
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

# --- ANTI-FLASH SYNC ---
if not edited_df.equals(view_df):
    st.session_state.mijn_data.update(edited_df)
    st.rerun()
