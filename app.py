import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE ---
st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    div.stButton > button { border-radius: 8px; font-weight: 600; height: 3em; }
    [data-testid="stDataEditor"] input[type="checkbox"] { transform: scale(1.8); margin: 10px; cursor: pointer; }
    div.stButton > button[key^="delete_btn"], div.stButton > button[key="logout_btn"] { background-color: #ff4b4b; color: white; }
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
        st.header("Voorraad glas")
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
    st.stop()

# --- 4. DATA INITIALISATIE ---
if 'mijn_data' not in st.session_state: 
    st.session_state.mijn_data = laad_data()
if 'bulk_loc' not in st.session_state:
    st.session_state.bulk_loc = "HK"

# --- 5. HEADER ---
col_logo, col_titel, col_logout = st.columns([0.1, 0.75, 0.15])
with col_logo: st.image("theunissen.webp", use_container_width=True)
with col_titel: st.title("Voorraad glas")
with col_logout:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
        st.session_state.ingelogd = False; st.query_params.clear(); st.rerun()

# --- 6. ZOEKFUNCTIE ---
c1, c2, c3 = st.columns([6, 1, 1])
with c1: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek...", label_visibility="collapsed", key="zoek_veld")
with c2: 
    if st.button("ZOEKEN", use_container_width=True): st.rerun()
with c3: 
    if st.button("WISSEN", use_container_width=True):
        st.session_state.zoek_veld = ""; st.rerun()

view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 7. TABEL ---
edited_df = st.data_editor(
    view_df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]],
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
        "id": None,
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
    },
    hide_index=True, use_container_width=True, key="main_editor", height=400
)

# --- 8. ACTIEBALK (Verschijnt alleen bij selectie) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]
if not geselecteerd.empty:
    totaal_ruiten = int(geselecteerd["aantal"].sum())
    with st.container(border=True):
        st.markdown(f"### 📍 Actie voor {totaal_ruiten} ruiten")
        
        # Buttons bovenaan
        cb1, cb2 = st.columns(2)
        with cb1:
            if st.button(f"🚀 VERPLAATS NAAR {st.session_state.bulk_loc}", type="primary", use_container_width=True):
                get_supabase().table("glas_voorraad").update({"locatie": st.session_state.bulk_loc}).in_("id", geselecteerd["id"].tolist()).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()
        with cb2:
            if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="delete_btn", use_container_width=True):
                get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()

        # Grid onderaan
        st.write("Kies nieuwe locatie:")
        cols_per_row = 5
        for i in range(0, len(LOCATIE_OPTIES), cols_per_row):
            row_options = LOCATIE_OPTIES[i:i+cols_per_row]
            grid_cols = st.columns(cols_per_row)
            for idx, loc_naam in enumerate(row_options):
                if grid_cols[idx].button(loc_naam, key=f"grid_{loc_naam}", use_container_width=True, 
                                       type="primary" if st.session_state.bulk_loc == loc_naam else "secondary"):
                    st.session_state.bulk_loc = loc_naam
                    st.rerun()

# --- 9. BEHEER & OPSLAAN LOGICA ---
# Deze sectie kijkt specifiek of er cellen zijn aangepast (GEEN checkboxen)
if "main_editor" in st.session_state:
    edits = st.session_state["main_editor"].get("edited_rows", {})
    if edits:
        updates_made = False
        for row_idx, changes in edits.items():
            # Check of de verandering iets anders is dan de 'Selecteren' kolom
            inhoud_wijziging = {k: v for k, v in changes.items() if k != "Selecteren"}
            if inhoud_wijziging:
                row_id = view_df.iloc[row_idx]["id"]
                get_supabase().table("glas_voorraad").update(inhoud_wijziging).eq("id", row_id).execute()
                updates_made = True
        
        if updates_made:
            st.session_state.mijn_data = laad_data()
            st.rerun()

st.divider()
exp1, exp2 = st.columns(2)
with exp1:
    with st.expander("➕ Nieuwe Ruit Toevoegen"):
        with st.form("add_form", clear_on_submit=True):
            f_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            f_ord = st.text_input("Ordernummer")
            f_aan = st.number_input("Aantal", min_value=1, value=1)
            f_br = st.number_input("Breedte", value=0)
            f_hg = st.number_input("Hoogte", value=0)
            f_oms = st.text_input("Glastype")
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                get_supabase().table("glas_voorraad").insert({"locatie": f_loc, "order_nummer": f_ord, "aantal": f_aan, "breedte": f_br, "hoogte": f_hg, "omschrijving": f_oms}).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()

with exp2:
    if st.button("🔄 DATA VERVERSEN", use_container_width=True):
        st.session_state.mijn_data = laad_data(); st.rerun()
