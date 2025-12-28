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
# Dynamische lijst van locaties
LOCATIE_OPTIES = ["HK"] + [f"H{i}" for i in range(0, 31)]

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* DASHBOARD GRID STYLING */
    .location-header {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }

    /* TOETSENBORD BLOKKEREN */
    /* Forceer inputmode none op alle selectboxes en data editor inputs */
    div[data-baseweb="select"] input, [data-testid="stDataEditor"] input {
        inputmode: none !important;
    }

    /* KNOP STYLING */
    div.stButton > button {
        border-radius: 8px;
        font-weight: 600;
        height: 2.8em !important;
        font-size: 14px !important;
    }

    /* Specifieke styling voor de locatie-knoppen in de grid */
    div.stButton > button[key^="grid_loc_"] {
        background-color: #ffffff;
        border: 1px solid #007BFF;
        color: #007BFF;
        transition: 0.2s;
    }
    
    div.stButton > button[key^="grid_loc_"]:hover {
        background-color: #007BFF;
        color: white;
    }

    /* Rode knoppen */
    div.stButton > button[key="logout_btn"], div.stButton > button[key="delete_btn"] {
        background-color: #ff4b4b;
        color: white;
    }

    /* Grotere checkboxes voor tablet */
    [data-testid="stDataEditor"] input[type="checkbox"] {
        transform: scale(1.6);
        cursor: pointer;
    }

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

# --- 4. HEADER ---
c_logo, c_titel, c_logout = st.columns([0.1, 0.75, 0.15])
with c_logo: st.image("theunissen.webp", use_container_width=True)
with c_titel: st.title("Voorraad glas")
with c_logout: 
    if st.button("🚪 LOGUIT", key="logout_btn", use_container_width=True):
        st.session_state.ingelogd = False; st.query_params.clear(); st.rerun()

# --- 5. LOCATION GRID (BOVENAAN) ---
# Deze container wordt alleen actief als er items geselecteerd zijn
st.markdown("### 📍 Snel Verplaatsen")
view_df = st.session_state.mijn_data.copy()

# Filter/Zoekbalk voor de tabel (nu direct onder de grid titel)
zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of glastype...", key="zoek_veld", label_visibility="collapsed")
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# De eigenlijke Grid
with st.container(border=True):
    st.write("Klik op een locatie om geselecteerde ruiten direct te verplaatsen:")
    # We gebruiken 8 kolommen voor een compacte weergave op tablet/desktop
    n_cols = 8
    grid_cols = st.columns(n_cols)
    
    for i, loc in enumerate(LOCATIE_OPTIES):
        with grid_cols[i % n_cols]:
            if st.button(loc, key=f"grid_loc_{loc}", use_container_width=True):
                # Check of er iets geselecteerd is in de editor state
                if "editor" in st.session_state and "edited_rows" in st.session_state.editor:
                    # In een data_editor is selectie vaak een checkbox kolom
                    # We halen de geselecteerde IDs op uit de huidige weergave
                    pass # Logica wordt hieronder afgehandeld via de edited_df

# --- 6. TABEL (DATA EDITOR) ---
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Vink", width="small"),
        "id": None,
        "locatie": st.column_config.TextColumn("📍 Loc", disabled=True), # Voorkomt toetsenbord
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        "breedte": st.column_config.NumberColumn("Br.", width="small"),
        "hoogte": st.column_config.NumberColumn("Hg.", width="small"),
    },
    hide_index=True, use_container_width=True, key="editor", height=450
)

# --- 7. ACTIE AFHANDELING (GEKOPPELD AAN GRID) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

# Als er op een grid-knop is gedrukt (we checken de query params of session state)
# In Streamlit is de makkelijkste manier om de grid-knoppen de actie direct te laten uitvoeren:
for loc in LOCATIE_OPTIES:
    if st.session_state.get(f"grid_loc_{loc}"):
        if not geselecteerd.empty:
            get_supabase().table("glas_voorraad").update({"locatie": loc}).in_("id", geselecteerd["id"].tolist()).execute()
            st.toast(f"✅ {len(geselecteerd)} items naar {loc} verplaatst")
            st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
        else:
            st.warning("Selecteer eerst ruiten in de tabel hieronder!")

# --- 8. EXTRA ACTIES (WIS) ---
if not geselecteerd.empty:
    if st.button(f"🗑️ MEEGENOMEN ({len(geselecteerd)} stuks wissen)", key="delete_btn", use_container_width=True):
        get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
        st.toast("Items verwijderd")
        st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 9. BEHEER SECTIE ---
st.divider()
ex1, ex2 = st.columns(2)
with ex1:
    with st.expander("➕ Nieuwe Ruit Toevoegen"):
        with st.form("add_form", clear_on_submit=True):
            n_loc = st.selectbox("Locatie", LOCATIE_OPTIES) # Voor toevoegen is 1x dropdown ok
            n_order = st.text_input("Ordernummer")
            c1, c2 = st.columns(2)
            n_br = c1.number_input("Breedte")
            n_hg = c2.number_input("Hoogte")
            if st.form_submit_button("OPSLAAN", use_container_width=True):
                get_supabase().table("glas_voorraad").insert({"locatie": n_loc, "order_nummer": n_order, "breedte": n_br, "hoogte": n_hg, "uit_voorraad": "Nee"}).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

if st.button("🔄 DATA VERVERSEN", use_container_width=True):
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
