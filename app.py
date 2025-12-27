import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & UITGEBREIDE STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Dashboard", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; color: white; border: none; }
    
    /* RODE KNOP: Meegenomen / Verwijderen */
    div.stButton > button[key^="bulk_delete"] {
        background-color: #ff4b4b;
    }
    div.stButton > button[key^="bulk_delete"]:hover {
        background-color: #ff3333;
    }

    /* BLAUWE KNOP: Locatie aanpassen */
    div.stButton > button[key^="bulk_update_loc"] {
        background-color: #007bff;
    }
    div.stButton > button[key^="bulk_update_loc"]:hover {
        background-color: #0056b3;
    }
    
    /* Styling voor de actie-container */
    .action-bar {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #dee2e6;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE VERBINDING ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# --- 3. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    client = get_supabase()
    res = client.table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
    df["Selecteren"] = False
    return df

def update_bulk_locatie(row_ids, nieuwe_locatie):
    client = get_supabase()
    client.table("glas_voorraad").update({"locatie": nieuwe_locatie}).in_("id", row_ids).execute()
    st.cache_data.clear()

def verwijder_bulk(row_ids):
    client = get_supabase()
    client.table("glas_voorraad").delete().in_("id", row_ids).execute()
    st.cache_data.clear()

def update_rij_enkel(row_id, updates):
    client = get_supabase()
    client.table("glas_voorraad").update(updates).eq("id", row_id).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    client = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    client.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()

# --- 4. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = False

if not st.session_state.ingelogd:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 Glas Voorraad</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Fout wachtwoord")
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 6. SIDEBAR: IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Upload naar Database", use_container_width=True):
        try:
            raw_data = pd.read_excel(uploaded_file)
            raw_data.columns = [str(c).strip().lower() for c in raw_data.columns]
            mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
            raw_data = raw_data.rename(columns=mapping)
            
            import_df = raw_data.dropna(subset=["order_nummer"])
            import_df["uit_voorraad"] = "Nee"
            for c in ["aantal", "breedte", "hoogte"]:
                import_df[c] = pd.to_numeric(import_df[c], errors='coerce').fillna(0).astype(int)
            
            final_upload = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("")
            voeg_data_toe(final_upload)
            st.success("✅ Toegevoegd!")
            st.session_state.mijn_data = laad_data()
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")
    
    st.divider()
    if st.button("🔄 Verversen", use_container_width=True):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 7. KPI'S ---
st.title("🏭 Glas Voorraad Dashboard")
active_df = df[df["uit_voorraad"] == "Nee"]
k1, k2 = st.columns(2)
with k1:
    totaal = pd.to_numeric(active_df["aantal"], errors='coerce').sum()
    st.metric("In Voorraad (stuks)", int(totaal) if not pd.isna(totaal) else 0)
with k2:
    st.metric("Unieke Orders", active_df["order_nummer"].nunique() if not active_df.empty else 0)

# --- 8. ZOEKBALK & ACTIE CONTAINER ---
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed")
actie_container = st.empty()

view_df = df.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 9. DATA EDITOR ---
cols_order = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
view_df = view_df[cols_order]

edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Kies", width="small", default=False),
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

# --- 10. DYNAMISCHE BULK ACTIES ---
geselecteerde_rijen = edited_df[edited_df["Selecteren"] == True]

if not geselecteerde_rijen.empty:
    with actie_container:
        st.markdown('<div class="action-bar">', unsafe_allow_html=True)
        col_loc, col_btn_loc, col_btn_del = st.columns([3, 3, 3])
        
        with col_loc:
            nieuwe_loc = st.selectbox("Nieuwe locatie voor selectie:", LOCATIE_OPTIES, key="bulk_loc_val")
        
        with col_btn_loc:
            if st.button(f"📍 Verplaats {len(geselecteerde_rijen)} stuks", key="bulk_update_loc", use_container_width=True):
                ids = geselecteerde_rijen["id"].tolist()
                update_bulk_locatie(ids, nieuwe_loc)
                st.session_state.mijn_data = laad_data()
                st.rerun()
                
        with col_btn_del:
            if st.button(f"🗑️ {len(geselecteerde_rijen)} stuks Meegenomen", key="bulk_delete", use_container_width=True):
                ids = geselecteerde_rijen["id"].tolist()
                verwijder_bulk(ids)
                st.session_state.mijn_data = laad_data()
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 11. INDIVIDUELE WIJZIGINGEN OPSLAAN ---
if not edited_df.drop(columns=["Selecteren"]).equals(view_df.drop(columns=["Selecteren"])):
    for i in range(len(edited_df)):
        if not edited_df.iloc[i].drop("Selecteren").equals(view_df.iloc[i].drop("Selecteren")):
            update_rij_enkel(edited_df.iloc[i]["id"], {"locatie": str(edited_df.iloc[i]["locatie"])})
    st.session_state.mijn_data = laad_data()
    st.rerun()
