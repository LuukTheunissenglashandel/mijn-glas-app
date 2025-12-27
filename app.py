import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & ORIGINELE STYLING ---
st.set_page_config(layout="wide", page_title="Glas Voorraad", initial_sidebar_state="expanded")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden !important;}

    div.stButton > button { 
        border-radius: 8px; height: 50px; font-weight: 600; 
    }
    
    /* Gekleurde knop voor 'Meegenomen' */
    div.stButton > button[key="meegenomen_btn"] {
        background-color: #2e7d32;
        color: white;
        border: none;
    }

    input[type=checkbox] { transform: scale(1.5); cursor: pointer; }

    @media only screen and (max-width: 1024px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
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
@st.cache_data(ttl=0)
def laad_data():
    try:
        client = get_supabase()
        res = client.table("glas_voorraad").select("*").order("id").execute()
        df = pd.DataFrame(res.data)
        if df.empty:
            return pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
        return df
    except:
        return pd.DataFrame()

def update_bulk(ids, nieuwe_status):
    client = get_supabase()
    # Update meerdere rijen tegelijk naar Ja of Nee
    for rid in ids:
        client.table("glas_voorraad").update({"uit_voorraad": nieuwe_status}).eq("id", rid).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    client = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    client.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()

def clear_search():
    st.session_state.zoek_input = ""

# --- 4. AUTHENTICATIE ---
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
                st.error("Fout wachtwoord")
    st.stop()

# --- 5. DATA LADEN ---
if 'mijn_data' not in st.session_state:
    st.session_state.mijn_data = laad_data()

df = st.session_state.mijn_data

# --- 6. SIDEBAR: IMPORT ---
with st.sidebar:
    st.subheader("📥 Excel Import")
    uploaded_file = st.file_uploader("Bestand kiezen", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file and st.button("📤 Toevoegen"):
        try:
            nieuwe_data = pd.read_excel(uploaded_file)
            mapping = {"Locatie": "locatie", "Aantal": "aantal", "Breedte": "breedte", "Hoogte": "hoogte", "Order": "order_nummer", "Omschrijving": "omschrijving"}
            nieuwe_data = nieuwe_data.rename(columns=mapping)
            nieuwe_data["uit_voorraad"] = "Nee"
            final_upload = nieuwe_data[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("")
            voeg_data_toe(final_upload)
            st.session_state.mijn_data = laad_data()
            st.rerun()
        except Exception as e: st.error(f"Fout: {e}")

# --- 7. DASHBOARD HEADER & KPI'S ---
st.title("🏭 Glas Voorraad")
active_df = df[df["uit_voorraad"] == "Nee"]
kpi1, kpi2 = st.columns([1, 1])
with kpi1: 
    aantal_num = pd.to_numeric(active_df["aantal"], errors='coerce').fillna(0)
    st.metric("In Voorraad (stuks)", int(aantal_num.sum()))
with kpi2: 
    st.metric("Unieke Orders", active_df["order_nummer"].nunique() if not active_df.empty else 0)

# --- 8. ZOEKFUNCTIE ---
c_in, c_zo, c_wi = st.columns([7, 1, 1], gap="small", vertical_alignment="bottom")
with c_in: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of omschrijving...", label_visibility="collapsed", key="zoek_input")
with c_zo: st.button("🔍", key="search_btn", use_container_width=True)
with c_wi: st.button("❌", key="clear_btn", on_click=clear_search, use_container_width=True)

# --- 9. DE 'MEEGENOMEN' KNOP ONDER DE ZOEKBALK ---
st.write("") 
view_df = df.copy()

if st.session_state.get("zoek_input"):
    mask = view_df.astype(str).apply(lambda x: x.str.contains(st.session_state.zoek_input, case=False)).any(axis=1)
    view_df = view_df[mask]

# Maak checkboxes klaar
view_df["Selectie"] = False
# Volgorde herstellen
volgorde = ["Selectie", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id", "uit_voorraad"]
view_df = view_df[volgorde]

# De knop onder de zoekbalk
col_btn, col_spacer = st.columns([3, 7])
with col_btn:
    btn_label = "✅ Geselecteerde ruiten op MEEGENOMEN zetten"
    meegenomen_klik = st.button(btn_label, key="meegenomen_btn", use_container_width=True)

# --- 10. TABEL EDITOR ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selectie": st.column_config.CheckboxColumn("Kies", width="small"),
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.TextColumn("Aant.", width="small", disabled=True),
        "breedte": st.column_config.TextColumn("Br.", width="small", disabled=True),
        "hoogte": st.column_config.TextColumn("Hg.", width="small", disabled=True),
        "order_nummer": st.column_config.TextColumn("Order", width="medium", disabled=True),
        "omschrijving": st.column_config.TextColumn("Omschrijving", width="large", disabled=True),
        "id": None,
        "uit_voorraad": None
    },
    hide_index=True,
    use_container_width=True,
    height=600,
    key="editor"
)

# --- 11. VERWERK KNOP LOGICA ---
if meegenomen_klik:
    # Zoek alle rijen die zijn aangevinkt
    geselecteerde_ids = edited_df[edited_df["Selectie"] == True]["id"].tolist()
    
    if geselecteerde_ids:
        update_bulk(geselecteerde_ids, "Ja")
        st.success(f"✅ {len(geselecteerde_ids)} ruiten verwerkt!")
        st.session_state.mijn_data = laad_data()
        st.rerun()
    else:
        st.warning("Vink eerst minimaal één ruit aan in de kolom 'Kies'.")

# Check of de locatie handmatig is aangepast (zonder de knop)
if not edited_df["locatie"].equals(view_df["locatie"]):
    for i in range(len(edited_df)):
        if edited_df.iloc[i]["locatie"] != view_df.iloc[i]["locatie"]:
            row = edited_df.iloc[i]
            client = get_supabase()
            client.table("glas_voorraad").update({"locatie": str(row["locatie"])}).eq("id", row["id"]).execute()
    st.cache_data.clear()
    st.session_state.mijn_data = laad_data()
    st.rerun()
