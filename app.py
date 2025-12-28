import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURATIE & STYLING ---
st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

WACHTWOORD = "glas123"
LOCATIE_OPTIES = ["HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7","H8", "H9", "H10", "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"]

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Actiebox styling */
    .action-box {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border: 2px solid #007bff;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    
    /* Knoppen en Zoekveld op exact 3.5em hoogte */
    div.stButton > button { 
        border-radius: 8px; 
        font-weight: 600; 
        height: 3.5em !important; 
    }
    
    /* Zoekveld hoogte aanpassen */
    div[data-testid="stTextInput"] > div > div > input {
        height: 3.5em !important;
    }

    /* Grotere checkboxen voor tablet */
    [data-testid="stDataEditor"] input[type="checkbox"] { 
        transform: scale(1.8); 
        margin: 10px; 
        cursor: pointer; 
    }
    
    /* Kleuren */
    div.stButton > button[key^="delete_btn"] { background-color: #ff4b4b; color: white; border: none; }
    div.stButton > button[key="logout_btn"] { background-color: #ff4b4b; color: white; height: 2.5em !important; }
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
    return df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]

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

# --- 4. DATA LADEN ---
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
with c1: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of type...", label_visibility="collapsed", key="zoek_veld")
with c2: 
    if st.button("ZOEKEN", use_container_width=True): st.rerun()
with c3: 
    if st.button("WISSEN", use_container_width=True):
        st.session_state.zoek_veld = ""; st.rerun()

view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

# --- 7. PLACEHOLDER VOOR ACTIES ---
# Deze plek reserveren we boven de tabel
actie_houder = st.empty()

# --- 8. TABEL ---
edited_df = st.data_editor(
    view_df,
    column_config={
        "Selecteren": st.column_config.CheckboxColumn("Vink aan", width="small"),
        "id": None,
        "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
        "aantal": st.column_config.NumberColumn("Aant.", width="small"),
    },
    hide_index=True, use_container_width=True, key="main_editor", height=500
)

# --- 9. LOGICA VOOR ACTIEBOX (Vullen van de placeholder) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]

if not geselecteerd.empty:
    totaal_ruiten = int(geselecteerd["aantal"].sum())
    with actie_houder.container():
        st.markdown(f'<div class="action-box"><h3>📍 Acties voor {totaal_ruiten} ruiten</h3>', unsafe_allow_html=True)
        
        col_btn_move, col_btn_del = st.columns(2)
        with col_btn_move:
            if st.button(f"🚀 VERPLAATS NAAR {st.session_state.bulk_loc}", type="primary", use_container_width=True):
                ids = geselecteerd["id"].tolist()
                get_supabase().table("glas_voorraad").update({"locatie": st.session_state.bulk_loc}).in_("id", ids).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()
                
        with col_btn_del:
            if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="delete_btn", use_container_width=True):
                ids = geselecteerd["id"].tolist()
                get_supabase().table("glas_voorraad").delete().in_("id", ids).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()

        st.write("**Kies nieuwe doellocatie:**")
        # Grid voor locaties (5 per rij)
        for i in range(0, len(LOCATIE_OPTIES), 5):
            row_options = LOCATIE_OPTIES[i:i+5]
            grid_cols = st.columns(5)
            for idx, loc_naam in enumerate(row_options):
                is_active = st.session_state.bulk_loc == loc_naam
                if grid_cols[idx].button(loc_naam, key=f"grid_{loc_naam}", use_container_width=True, 
                                       type="primary" if is_active else "secondary"):
                    st.session_state.bulk_loc = loc_naam
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- 10. OPSLAAN VAN HANDMATIGE EDITS ---
if "main_editor" in st.session_state:
    edits = st.session_state["main_editor"].get("edited_rows", {})
    if edits:
        updates_made = False
        for row_idx, changes in edits.items():
            inhoud_wijziging = {k: v for k, v in changes.items() if k != "Selecteren"}
            if inhoud_wijziging:
                row_id = view_df.iloc[int(row_idx)]["id"]
                get_supabase().table("glas_voorraad").update(inhoud_wijziging).eq("id", row_id).execute()
                updates_made = True
        if updates_made:
            st.session_state.mijn_data = laad_data(); st.rerun()

# --- 11. BEHEER SECTIE (Onderaan) ---
st.divider()
st.subheader("⚙️ Beheer & Toevoegen")
exp_col1, exp_col2 = st.columns(2)

with exp_col1:
    with st.expander("➕ Nieuwe Ruit Handmatig"):
        with st.form("add_form", clear_on_submit=True):
            f_loc = st.selectbox("Locatie", LOCATIE_OPTIES)
            f_ord = st.text_input("Ordernummer")
            f_aan = st.number_input("Aantal", min_value=1, value=1)
            f_br = st.number_input("Breedte", value=0)
            f_hg = st.number_input("Hoogte", value=0)
            f_oms = st.text_input("Glastype")
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                get_supabase().table("glas_voorraad").insert({"locatie": f_loc, "order_nummer": f_ord, "aantal": f_aan, "breedte": f_br, "hoogte": f_hg, "omschrijving": f_oms, "uit_voorraad": "Nee"}).execute()
                st.session_state.mijn_data = laad_data(); st.rerun()

with exp_col2:
    with st.expander("📥 Excel Import"):
        uploaded_file = st.file_uploader("Kies Excel bestand", type=["xlsx"])
        if uploaded_file and st.button("UPLOAD NU", use_container_width=True):
            try:
                raw = pd.read_excel(uploaded_file)
                raw.columns = [str(c).strip().lower() for c in raw.columns]
                mapping = {"locatie": "locatie", "aantal": "aantal", "breedte": "breedte", "hoogte": "hoogte", "order": "order_nummer", "omschrijving": "omschrijving"}
                raw = raw.rename(columns=mapping)
                import_df = raw.dropna(subset=["order_nummer"])
                import_df["uit_voorraad"] = "Nee"
                data_dict = import_df[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].fillna("").to_dict(orient="records")
                get_supabase().table("glas_voorraad").insert(data_dict).execute()
                st.success("Import succesvol!"); st.session_state.mijn_data = laad_data(); st.rerun()
            except Exception as e: st.error(f"Fout bij import: {e}")

if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
    st.session_state.mijn_data = laad_data(); st.rerun()
