import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad Pro", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    div.stButton > button { border-radius: 8px; height: 50px; font-weight: 600; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SECRETS CHECK (LEUGENDETECTOR) ---
if "supabase" not in st.secrets:
    st.error("❌ Configuratie-fout: Het blok [supabase] ontbreekt in je Secrets.")
    st.stop()

# --- 3. DATABASE VERBINDING ---
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

# --- 4. DATA FUNCTIES ---
@st.cache_data(ttl=60)
def laad_data():
    try:
        client = get_supabase()
        res = client.table("glas_voorraad").select("*").order("id").execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Fout bij laden: {e}")
        return pd.DataFrame()

def update_rij(row_id, updates):
    client = get_supabase()
    client.table("glas_voorraad").update(updates).eq("id", row_id).execute()
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
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🏭 Glas Voorraad Login</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Voer wachtwoord in...")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- 6. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 7. SIDEBAR: ROBUUSTE EXCEL IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    
    if uploaded_file and st.button("📤 Upload naar Database", use_container_width=True):
        try:
            raw_data = pd.read_excel(uploaded_file)
            
            # Kolomnamen opschonen (geen spaties, kleine letters)
            raw_data.columns = [str(c).strip().lower() for c in raw_data.columns]
            
            # Slimme mapping van Excel-namen naar Database-namen
            mapping = {
                "locatie": "locatie", "loc": "locatie", "plek": "locatie",
                "aantal": "aantal", "stuks": "aantal", "aant": "aantal",
                "breedte": "breedte", "br": "breedte", "breedte(mm)": "breedte",
                "hoogte": "hoogte", "hg": "hoogte", "hoogte(mm)": "hoogte",
                "order": "order_nummer", "order_nummer": "order_nummer", "ordernr": "order_nummer", "project": "order_nummer",
                "omschrijving": "omschrijving", "omschrijving/type": "omschrijving", "soort": "omschrijving"
            }
            
            raw_data = raw_data.rename(columns=mapping)
            
            # Verplichte kolommen checken
            vereist = ["locatie", "aantal", "breedte", "hoogte", "order_nummer"]
            missing = [c for c in vereist if c not in raw_data.columns]
            
            if missing:
                st.error(f"❌ Kolommen niet gevonden: {', '.join(missing)}")
                st.info("Zorg dat de koppen in Excel duidelijk zijn (bijv. 'Breedte', 'Hoogte', etc.)")
            else:
                # Data schoonmaken
                if "omschrijving" not in raw_data.columns: raw_data["omschrijving"] = ""
                raw_data["uit_voorraad"] = "Nee"
                
                # Alleen rijen met een order_nummer houden
                import_df = raw_data.dropna(subset=["order_nummer"])
                
                # Numerieke waarden forceren
                for c in ["aantal", "breedte", "hoogte"]:
                    import_df[c] = pd.to_numeric(import_df[c], errors='coerce').fillna(0).astype(int)
                
                # Definitieve selectie
                final_upload = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("")
                
                voeg_data_toe(final_upload)
                st.success(f"✅ {len(final_upload)} rijen toegevoegd!")
                st.session_state.mijn_data = laad_data()
                st.rerun()
        except Exception as e:
            st.error(f"Fout bij verwerking: {e}")

    st.divider()
    if st.button("🔄 Ververs Systeem", use_container_width=True):
        st.cache_data.clear()
        st.session_state.mijn_data = laad_data()
        st.rerun()

# --- 8. DASHBOARD KPI'S ---
st.title("🏗️ Glas Voorraad Systeem")

if not df.empty:
    active_df = df[df["uit_voorraad"] == "Nee"]
    k1, k2, k3 = st.columns(3)
    with k1:
        totaal = pd.to_numeric(active_df["aantal"], errors='coerce').sum()
        st.metric("Totaal in Voorraad", f"{int(totaal)} stuks")
    with k2:
        st.metric("Lopende Orders", active_df["order_nummer"].nunique())
    with k3:
        st.metric("Vrije Locaties", len(LOCATIE_OPTIES) - active_df["locatie"].nunique())

    # --- 9. ZOEKFUNCTIE ---
    zoekterm = st.text_input("🔍 Snel Zoeken", placeholder="Zoek op order, maat, locatie of glas-type...")
    view_df = df.copy()
    if zoekterm:
        mask = view_df.astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
        view_df = view_df[mask]

    # --- 10. DATA EDITOR ---
    # Alleen 'locatie' en 'uit_voorraad' zijn bewerkbaar
    edited_df = st.data_editor(
        view_df,
        column_config={
            "id": None,
            "uit_voorraad": st.column_config.SelectboxColumn("Status", options=["Ja", "Nee"], width="medium", help="Vink 'Ja' als het uit voorraad is"),
            "locatie": st.column_config.SelectboxColumn("📍 Locatie", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", disabled=True),
            "breedte": st.column_config.NumberColumn("Br. (mm)", disabled=True),
            "hoogte": st.column_config.NumberColumn("Hg. (mm)", disabled=True),
            "order_nummer": st.column_config.TextColumn("Order Nummer", disabled=True),
            "omschrijving": st.column_config.TextColumn("Type Glas", width="large", disabled=True),
            "created_at": None
        },
        hide_index=True,
        use_container_width=True,
        height=600,
        key="editor"
    )

    # --- 11. OPSLAAN ---
    if not edited_df.equals(view_df):
        for i in range(len(edited_df)):
            if not edited_df.iloc[i].equals(view_df.iloc[i]):
                row = edited_df.iloc[i]
                updates = {
                    "locatie": str(row["locatie"]),
                    "uit_voorraad": str(row["uit_voorraad"])
                }
                update_rij(row["id"], updates)
        
        st.session_state.mijn_data = laad_data()
        st.rerun()
else:
    st.info("De database is momenteel leeg. Gebruik de importfunctie in de sidebar om data toe te voegen.")
