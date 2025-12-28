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
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    /* Algemene spacing */
    .block-container { padding-top: 1.5rem; padding-bottom: 7rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* TOETSENBORD ONDERDRUKKEN: Voorkomt dat toetsenbord opent bij selectboxes */
    div[data-baseweb="select"] input {
        inputmode: none !important;
    }
    [data-testid="stDataEditor"] input {
        inputmode: none !important;
    }

    /* TABLET OPTIMALISATIE: Grotere knoppen en inputs */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        height: 3.8em !important;
        font-size: 16px !important;
    }
    
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        height: 3.5rem !important;
    }

    /* ZWEVENDE ACTIEBALK ONDERAAN: Voor tabletgebruik */
    div.floating-bar {
        position: fixed;
        bottom: 20px;
        left: 2%;
        right: 2%;
        z-index: 999;
        background-color: #ffffff;
        border: 2px solid #007BFF;
        border-radius: 20px;
        box-shadow: 0 -5px 25px rgba(0,0,0,0.15);
        padding: 15px;
    }

    /* Grotere checkboxes in de tabel */
    [data-testid="stDataEditor"] input[type="checkbox"] {
        transform: scale(2);
        margin: 15px;
        cursor: pointer;
    }

    /* Kleur voor gevaar-knoppen */
    div.stButton > button[key^="delete_btn"], 
    div.stButton > button[key^="confirm_delete"],
    div.stButton > button[key="logout_btn"] {
        background-color: #ff4b4b;
        color: white;
    }
    
    /* Verwijder labels voor een cleanere look */
    .stSelectbox label, .stTextInput label { display:none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE & DATA FUNCTIES ---
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def laad_data():
    res = get_supabase().table("glas_voorraad").select("*").order("id").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        df = pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"])
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
                st.query_params["auth"] = "true"
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")
    st.stop()

# --- 4. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state: 
    st.session_state.mijn_data = laad_data()

def reset_zoekopdracht():
    st.session_state.zoek_veld = ""

# --- 5. HEADER ---
col_logo, col_titel, col_logout = st.columns([0.15, 0.65, 0.2])
with col_logo:
    st.image("theunissen.webp", use_container_width=True)
with col_titel:
    st.title("Voorraad glas")
with col_logout:
    if st.button("🚪 LOGOUT", key="logout_btn", use_container_width=True):
        st.session_state.ingelogd = False
        st.query_params.clear()
        st.rerun()

# --- 6. ZOEKBALK ---
c1, c2, c3 = st.columns([6, 1, 1])
with c1:
    zoekterm = st.text_input(
        "Zoeken", 
        placeholder="🔍 Zoek op order, maat of glastype...", 
        key="zoek_veld"
    )
with c2:
    if st.button("ZOEK", use_container_width=True): st.rerun()
with c3:
    st.button("✖", use_container_width=True, on_click=reset_zoekopdracht)

view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 7. TABEL ---
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Vink", width="small"),
        "id": None,
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        "breedte": st.column_config.NumberColumn("Br.", width="small"),
        "hoogte": st.column_config.NumberColumn("Hg.", width="small"),
        "order_nummer": st.column_config.TextColumn("Order"),
        "omschrijving": st.column_config.TextColumn("Glastype"),
    },
    hide_index=True, use_container_width=True, key="editor", height=550
)

# --- 8. ZWEVENDE ACTIEBALK (Verschijnt alleen bij selectie) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]
if not geselecteerd.empty:
    st.markdown('<div class="floating-bar">', unsafe_allow_html=True)
    col_info, col_sel, col_b1, col_b2 = st.columns([1, 1.5, 2.5, 2.5], vertical_alignment="center")
    
    with col_info: 
        st.markdown(f"**{len(geselecteerd)} items**")
    
    with col_sel: 
        nieuwe_loc = st.selectbox("Naar:", LOCATIE_OPTIES, key="bulk_loc")
    
    with col_b1:
        if st.button(f"📍 NAAR {nieuwe_loc}", type="primary", use_container_width=True):
            get_supabase().table("glas_voorraad").update({"locatie": nieuwe_loc}).in_("id", geselecteerd["id"].tolist()).execute()
            st.toast(f"✅ Verplaatst naar {nieuwe_loc}")
            st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
            
    with col_b2:
        if "confirm_delete" not in st.session_state: st.session_state.confirm_delete = False
        if not st.session_state.confirm_delete:
            if st.button(f"🗑️ MEEGENOMEN", key="delete_btn", use_container_width=True):
                st.session_state.confirm_delete = True; st.rerun()
        else:
            c_yes, c_no = st.columns(2)
            if c_yes.button("JA", key="confirm_delete_yes", use_container_width=True):
                get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
                st.toast("🗑️ Items verwijderd")
                st.session_state.confirm_delete = False; st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
            if c_no.button("NEE", use_container_width=True):
                st.session_state.confirm_delete = False; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 9. BEHEER SECTIE ---
st.divider()
st.subheader("⚙️ Beheer & Toevoegen")
exp_col1, exp_col2 = st.columns(2)

with exp_col1:
    with st.expander("➕ Nieuwe Ruit Toevoegen"):
        with st.form("handmatige_toevoeging", clear_on_submit=True):
            n_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            n_order = st.text_input("Ordernummer")
            n_aantal = st.number_input("Aantal", min_value=1, value=1)
            n_br = st.number_input("Breedte (mm)", min_value=0)
            n_hg = st.number_input("Hoogte (mm)", min_value=0)
            n_oms = st.text_input("Glastype")
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                if n_order:
                    nieuwe_data = {"locatie": n_loc, "order_nummer": n_order, "aantal": n_aantal, "breedte": n_br, "hoogte": n_hg, "omschrijving": n_oms, "uit_voorraad": "Nee"}
                    get_supabase().table("glas_voorraad").insert(nieuwe_data).execute()
                    st.toast("✅ Toegevoegd!")
                    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                else: st.error("Ordernummer verplicht!")

with exp_col2:
    with st.expander("📥 Excel Import"):
        uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"])
        if uploaded_file and st.button("UPLOADEN", use_container_width=True):
            try:
                raw = pd.read_excel(uploaded_file)
                raw.columns = [str(c).strip().lower() for c in raw.columns]
                mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
                raw = raw.rename(columns=mapping)
                import_df = raw.dropna(subset=["order_nummer"])
                import_df["uit_voorraad"] = "Nee"
                data_dict = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
                get_supabase().table("glas_voorraad").insert(data_dict).execute()
                st.toast("✅ Excel geïmporteerd!")
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")

if st.button("🔄 DATA VERVERSEN", use_container_width=True):
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 10. AUTO-SAVE WIJZIGINGEN ---
# Vergelijk bewerkte data met origineel om wijzigingen op te slaan
if not edited_df.drop(columns=["Selecteren"]).equals(view_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]):
    for i in range(len(edited_df)):
        orig_row = st.session_state.mijn_data[st.session_state.mijn_data["id"] == edited_df.iloc[i]["id"]].iloc[0]
        curr_row = edited_df.iloc[i]
        if not curr_row.drop("Selecteren").equals(orig_row[curr_row.drop("Selecteren").index]):
            update_data = {
                "locatie": str(curr_row["locatie"]), 
                "aantal": int(curr_row["aantal"]), 
                "breedte": int(curr_row["breedte"]), 
                "hoogte": int(curr_row["hoogte"]), 
                "omschrijving": str(curr_row["omschrijving"]), 
                "order_nummer": str(curr_row["order_nummer"])
            }
            get_supabase().table("glas_voorraad").update(update_data).eq("id", curr_row["id"]).execute()
    st.toast("💾 Wijzigingen opgeslagen")
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
