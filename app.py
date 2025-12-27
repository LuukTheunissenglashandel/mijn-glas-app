import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

# --- 2. CSS (EXTREEM STRENG VOOR KLEUREN) ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    
    /* BASIS VOOR ALLE KNOPPEN */
    div.stButton > button {
        border-radius: 8px !important;
        height: 45px !important;
        font-weight: 700 !important;
        color: white !important;
        border: none !important;
        text-transform: uppercase;
    }

    /* Dwing witte tekst voor alle elementen in de knop */
    div.stButton > button p {
        color: white !important;
    }

    /* BLAUWE KNOP (Gebaseerd op de tekst 'VERPLAATS') */
    div.stButton > button:has(p:contains("VERPLAATS")) {
        background-color: #007bff !important;
    }
    
    /* RODE KNOP (Gebaseerd op de tekst 'WISSEN') */
    div.stButton > button:has(p:contains("WISSEN")) {
        background-color: #ff4b4b !important;
    }

    /* ZWARTE KNOPPEN (Inloggen, Verversen, Uploaden) */
    div.stButton > button:has(p:contains("INLOGGEN")),
    div.stButton > button:has(p:contains("VERVERSEN")),
    div.stButton > button:has(p:contains("UPLOADEN")) {
        background-color: #262730 !important;
    }

    /* Styling voor de actie-balk container */
    [data-testid="stExpander"] {
        border: none !important;
        background-color: #f8f9fa !important;
        border-radius: 10px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE VERBINDING ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# --- 4. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    client = get_supabase()
    res = client.table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    df["Selecteren"] = False
    return df

def update_bulk(ids, updates):
    client = get_supabase()
    client.table("glas_voorraad").update(updates).in_("id", ids).execute()
    st.cache_data.clear()

def verwijder_bulk(ids):
    client = get_supabase()
    client.table("glas_voorraad").delete().in_("id", ids).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    client = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    client.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()

# --- 5. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("INLOGGEN", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else: st.error("Onjuist wachtwoord")
    st.stop()

# --- 6. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()
df = st.session_state.mijn_data

# --- 7. SIDEBAR (IMPORT) ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("UPLOADEN", use_container_width=True):
        try:
            raw = pd.read_excel(uploaded_file)
            raw.columns = [str(c).strip().lower() for c in raw.columns]
            mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
            raw = raw.rename(columns=mapping)
            import_df = raw.dropna(subset=["order_nummer"])
            import_df["uit_voorraad"] = "Nee"
            for c in ["aantal", "breedte", "hoogte"]:
                import_df[c] = pd.to_numeric(import_df[c], errors='coerce').fillna(0).astype(int)
            voeg_data_toe(import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna(""))
            st.session_state.mijn_data = laad_data()
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    st.divider()
    if st.button("VERVERSEN", use_container_width=True):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 8. DASHBOARD HEADER ---
st.title("🏭 Glas Voorraad Dashboard")
active_df = df[df["uit_voorraad"] == "Nee"]
c1, c2 = st.columns(2)
with c1: st.metric("In Voorraad (stuks)", int(pd.to_numeric(active_df["aantal"], errors='coerce').sum()))
with c2: st.metric("Unieke Orders", active_df["order_nummer"].nunique() if not active_df.empty else 0)

# --- 9. ZOEKBALK & ACTIE BALK ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
actie_placeholder = st.empty()

view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 10. TABEL EDITOR ---
cols_order = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
view_df = view_df[cols_order]

edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Kies", width="small"),
        "id": None, 
        "locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aantal", disabled=True),
        "breedte": st.column_config.NumberColumn("Breedte", disabled=True),
        "hoogte": st.column_config.NumberColumn("Hoogte", disabled=True),
        "order_nummer": st.column_config.TextColumn("Order", disabled=True),
        "omschrijving": st.column_config.TextColumn("Omschrijving", width="large", disabled=True),
    },
    hide_index=True,
    use_container_width=True,
    height=500,
    key="editor"
)

# --- 11. ACTIE LOGICA (KNOPPEN BOVENAAN) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

if not geselecteerd.empty:
    with actie_placeholder:
        # Een schone container voor de knoppen
        with st.container():
            st.write(f"**{len(geselecteerd)} ruiten gekozen**")
            col_sel, col_btn1, col_btn2 = st.columns([2, 2.5, 2.5])
            with col_sel:
                nieuwe_loc = st.selectbox("Naar:", LOCATIE_OPTIES, key="bulk_loc", label_visibility="collapsed")
            with col_btn1:
                if st.button(f"📍 VERPLAATS NAAR {nieuwe_loc}", use_container_width=True):
                    update_bulk(geselecteerd["id"].tolist(), {"locatie": nieuwe_loc})
                    st.session_state.mijn_data = laad_data()
                    st.rerun()
            with col_btn2:
                if st.button(f"🗑️ WISSEN / MEEGENOMEN", use_container_width=True):
                    verwijder_bulk(geselecteerd["id"].tolist())
                    st.session_state.mijn_data = laad_data()
                    st.rerun()

# --- 12. INDIVIDUELE WIJZIGING ---
if not edited_df.drop(columns=["Selecteren"]).equals(view_df.drop(columns=["Selecteren"])):
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            get_supabase().table("glas_voorraad").update({"locatie": str(edited_df.iloc[i]["locatie"])}).eq("id", edited_df.iloc[i]["id"]).execute()
    st.cache_data.clear()
    st.session_state.mijn_data = laad_data()
    st.rerun()
