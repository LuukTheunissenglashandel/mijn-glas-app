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
    .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }
    #MainMenu, footer, header {visibility: hidden;}
    div.stButton > button { border-radius: 8px; font-weight: 600; height: 3em; }
    div[data-testid="column"] { padding: 1px !important; }
    [data-testid="stDataEditor"] input[type="checkbox"] { transform: scale(1.8); margin: 10px; cursor: pointer; }
    div.stButton > button[key^="delete_btn"], 
    div.stButton > button[key^="confirm_delete"],
    div.stButton > button[key="logout_btn"] { background-color: #ff4b4b; color: white; }
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
        ww = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if ww == WACHTWOORD:
                st.session_state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
            else: st.error("Onjuist wachtwoord")
    st.stop()

# --- 4. DATA LADEN ---
if 'mijn_data' not in st.session_state: 
    st.session_state.mijn_data = laad_data()
if 'bulk_loc' not in st.session_state:
    st.session_state.bulk_loc = "HK"

def reset_zoekopdracht():
    st.session_state.zoek_veld = ""

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
with c1: zoekterm = st.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of glastype...", label_visibility="collapsed", key="zoek_veld")
with c2: 
    if st.button("ZOEKEN", use_container_width=True): st.rerun()
with c3: st.button("WISSEN", use_container_width=True, on_click=reset_zoekopdracht)

view_df = st.session_state.mijn_data.copy()
if zoekterm:
    mask = view_df.drop(columns=["Selecteren"]).astype(str).apply(lambda x: x.str.contains(zoekterm, case=False)).any(axis=1)
    view_df = view_df[mask]

actie_placeholder = st.empty()

# --- 7. TABEL ---
# We tonen de tabel met een vaste key om onnodige resets te voorkomen
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

# --- 8. ACTIEBALK (Bovenaan bij selectie) ---
geselecteerd = edited_df[edited_df["Selecteren"] == True]
if not geselecteerd.empty:
    totaal_ruiten = int(geselecteerd["aantal"].sum())
    with actie_placeholder.container(border=True):
        st.markdown(f"### 📍 Actie voor {totaal_ruiten} ruiten ({len(geselecteerd)} regels)")
        
        # 1. De buttons bovenaan
        col_move, col_del = st.columns(2)
        with col_move:
            if st.button(f"🚀 VERPLAATS NAAR {st.session_state.bulk_loc}", type="primary", use_container_width=True):
                get_supabase().table("glas_voorraad").update({"locatie": st.session_state.bulk_loc}).in_("id", geselecteerd["id"].tolist()).execute()
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
        
        with col_del:
            if f"confirm_delete" not in st.session_state: st.session_state.confirm_delete = False
            if not st.session_state.confirm_delete:
                if st.button(f"🗑️ MEEGENOMEN / WISSEN", key="delete_btn", use_container_width=True):
                    st.session_state.confirm_delete = True; st.rerun()
            else:
                st.warning("Zeker weten?")
                c_yes, c_no = st.columns(2)
                if c_yes.button("JA, VERWIJDER", key="confirm_delete_yes", use_container_width=True):
                    get_supabase().table("glas_voorraad").delete().in_("id", geselecteerd["id"].tolist()).execute()
                    st.session_state.confirm_delete = False; st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
                if c_no.button("ANNULEER", use_container_width=True):
                    st.session_state.confirm_delete = False; st.rerun()

        st.write("---")
        
        # 2. Het grid onder de buttons
        st.write("Kies nieuwe locatie:")
        cols_per_row = 5
        rows = [LOCATIE_OPTIES[i:i + cols_per_row] for i in range(0, len(LOCATIE_OPTIES), cols_per_row)]
        for row in rows:
            grid_cols = st.columns(cols_per_row)
            for i, loc_naam in enumerate(row):
                is_selected = st.session_state.bulk_loc == loc_naam
                if grid_cols[i].button(loc_naam, key=f"grid_{loc_naam}", use_container_width=True, type="primary" if is_selected else "secondary"):
                    st.session_state.bulk_loc = loc_naam
                    st.rerun()

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
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                if n_order:
                    nieuwe_data = {"locatie": n_loc, "order_nummer": n_order, "aantal": n_aantal, "breedte": n_br, "hoogte": n_hg, "omschrijving": n_oms, "uit_voorraad": "Nee"}
                    get_supabase().table("glas_voorraad").insert(nieuwe_data).execute()
                    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

with exp_col2:
    with st.expander("📥 Excel Import"):
        uploaded_file = st.file_uploader("Kies Excel", type=["xlsx"], label_visibility="collapsed")
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
                st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")

if st.button("🔄 DATA VERVERSEN", use_container_width=True):
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()

# --- 10. OPSLAAN VAN TABEL WIJZIGINGEN (Geoptimaliseerd) ---
# We vergelijken alleen de inhoudskolommen om onnodige reruns bij selecteren te voorkomen
inhoud_cols = ["locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"]
if not edited_df[inhoud_cols].equals(view_df[inhoud_cols]):
    for i in range(len(edited_df)):
        id_val = edited_df.iloc[i]["id"]
        orig_row = st.session_state.mijn_data[st.session_state.mijn_data["id"] == id_val].iloc[0]
        curr_row = edited_df.iloc[i]
        
        # Check of er echt iets veranderd is in de inhoud van deze rij
        if not curr_row[inhoud_cols].equals(orig_row[inhoud_cols]):
            update_data = {col: curr_row[col] for col in inhoud_cols}
            # Zorg voor juiste types
            update_data["aantal"] = int(update_data["aantal"])
            update_data["breedte"] = int(update_data["breedte"])
            update_data["hoogte"] = int(update_data["hoogte"])
            
            get_supabase().table("glas_voorraad").update(update_data).eq("id", id_val).execute()
            
    st.cache_data.clear(); st.session_state.mijn_data = laad_data(); st.rerun()
