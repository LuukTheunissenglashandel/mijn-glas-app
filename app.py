import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(
    layout="wide", 
    page_title="Voorraad glas",
    page_icon="theunissen.webp"
)

WACHTWOORD = "glas123"
# Dynamische lijst van 30+ locaties
LOCATIE_OPTIES = ["HK"] + [f"H{i}" for i in range(0, 31)]

st.markdown("""
    <style>
    /* Ruimte onderaan voor de zwevende balk */
    .block-container { padding-top: 1.5rem; padding-bottom: 15rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* ZWEVENDE ACTIEBALK ONDERAAN */
    div.floating-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 999;
        background-color: #ffffff;
        border-top: 3px solid #007BFF;
        box-shadow: 0 -10px 30px rgba(0,0,0,0.2);
        padding: 20px;
    }

    /* KNOP STYLING */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        height: 3em !important;
    }

    /* Grid knoppen (locaties) specifiek */
    div.stButton > button[key^="loc_"] {
        background-color: #f0f2f6;
        color: #31333F;
        border: 1px solid #d1d5db;
        margin-bottom: 2px;
    }
    
    /* Gevaar knop (verwijderen) */
    div.stButton > button[key="delete_btn"], div.stButton > button[key^="confirm_delete"] {
        background-color: #ff4b4b;
        color: white;
    }

    /* Checkbox vergroten voor tablet */
    [data-testid="stDataEditor"] input[type="checkbox"] {
        transform: scale(1.8);
        cursor: pointer;
    }

    /* Verberg labels */
    .stTextInput label, .stSelectbox label { display:none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE FUNCTIES ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def laad_data():
    res = get_supabase().table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"])
    df["Selecteren"] = False
    return df

# --- 3. AUTHENTICATIE ---
if "ingelogd" not in st.session_state:
    st.session_state.ingelogd = st.query_params.get("auth") == "true"

if not st.session_state.ingelogd:
    _, col2, _ = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>Voorraad glas</h2>", unsafe_allow_html=True)
        ww = st.text_input("Wachtwoord", type="password", placeholder="Wachtwoord...")
        if st.button("INLOGGEN", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True
                st.query_params["auth"] = "true"; st.rerun()
            else: st.error("Onjuist wachtwoord")
    st.stop()

if 'mijn_data' not in st.session_state: 
    st.session_state.mijn_data = laad_data()

# --- 4. HEADER & ZOEKFUNCTIE ---
c_logo, c_titel, c_logout = st.columns([0.15, 0.7, 0.15])
with c_logo: st.image("theunissen.webp", use_container_width=True)
with c_titel: st.title("Voorraad glas")
with c_logout: 
    if st.button("🚪 LOGUIT", use_container_width=True):
        st.session_state.ingelogd = False; st.query_params.clear(); st.rerun()

zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of glastype...", key="zoek_veld")

view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 5. TABEL (DATA EDITOR) ---
# Belangrijk: locatie is disabled om toetsenbord te voorkomen bij klikken
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Vink", width="small"),
        "id": None,
        "locatie": st.column_config.TextColumn("📍 Locatie", disabled=True), 
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        "breedte": st.column_config.NumberColumn("Br.", width="small"),
        "hoogte": st.column_config.NumberColumn("Hg.", width="small"),
        "order_nummer": st.column_config.TextColumn("Order"),
        "omschrijving": st.column_config.TextColumn("Glastype"),
    },
    hide_index=True, use_container_width=True, key="editor", height=500
)

# --- 6. DE NIEUWE ACTIEBALK (GRID-SYSTEEM) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

if not geselecteerd.empty:
    st.markdown('<div class="floating-bar">', unsafe_allow_html=True)
    
    col_info, col_grid = st.columns([1, 4])
    
    with col_info:
        st.subheader(f"💎 {len(geselecteerd)} items")
        if st.button("🗑️ WISSEN / MEE", key="delete_btn", use_container_width=True):
            get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
            st.toast("Verwijderd uit voorraad"); st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
        st.caption("Selecteer hieronder de nieuwe locatie om direct te verplaatsen:")

    with col_grid:
        # We maken een grid van 8 kolommen breed voor de locaties
        cols = st.columns(8)
        for i, loc in enumerate(LOCATIE_OPTIES):
            with cols[i % 8]:
                if st.button(loc, key=f"loc_{loc}", use_container_width=True):
                    get_supabase().table("glas_voorraad").update({"locatie": loc}).in_("id", geselecteerd["id"].tolist()).execute()
                    st.toast(f"✅ Verplaatst naar {loc}")
                    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                    
    st.markdown('</div>', unsafe_allow_html=True)

# --- 7. BEHEER & TOEVOEGEN ---
st.divider()
st.subheader("⚙️ Beheer")
ex1, ex2 = st.columns(2)

with ex1:
    with st.expander("➕ Nieuwe Ruit Toevoegen"):
        with st.form("handmatige_toevoeging", clear_on_submit=True):
            # Gebruik hier segmented_control (geen toetsenbord) als Streamlit versie het toelaat, 
            # anders een selectbox (met risico op toetsenbord, maar dit is slechts bij 1 item toevoegen)
            n_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            n_order = st.text_input("Ordernummer", placeholder="Ordernummer...")
            c_a, c_b, c_h = st.columns(3)
            n_aantal = c_a.number_input("Aantal", min_value=1, value=1)
            n_br = c_b.number_input("Breedte", min_value=0)
            n_hg = c_h.number_input("Hoogte", min_value=0)
            n_oms = st.text_input("Omschrijving / Glastype")
            
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                if n_order:
                    nieuwe_data = {"locatie": n_loc, "order_nummer": n_order, "aantal": n_aantal, "breedte": n_br, "hoogte": n_hg, "omschrijving": n_oms, "uit_voorraad": "Nee"}
                    get_supabase().table("glas_voorraad").insert(nieuwe_data).execute()
                    st.toast("✅ Toegevoegd"); st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                else: st.error("Ordernummer verplicht")

with ex2:
    with st.expander("📥 Excel Import"):
        up_file = st.file_uploader("Kies Excel", type=["xlsx"])
        if up_file and st.button("UPLOAD"):
            raw = pd.read_excel(up_file)
            # ... (import logica blijft hetzelfde als je origineel)
            st.toast("Excel verwerkt"); st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

if st.button("🔄 DATA VERVERSEN", use_container_width=True):
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
