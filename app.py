import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import contextmanager

# =============================================================================
# 1. CONFIGURATIE & DATA CLASSES
# =============================================================================

st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

WACHTWOORD = st.secrets["auth"]["password"]
LOCATIE_OPTIES = [
    "HK", "H0", "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", 
    "H11", "H12", "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20"
]

@dataclass
class AppState:
    ingelogd: bool = False
    mijn_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    bulk_loc: str = "HK"
    zoek_veld: str = ""
    confirm_delete: bool = False
    show_location_grid: bool = False

# =============================================================================
# 2. DATABASE REPOSITORY LAAG
# =============================================================================

class GlasVoorraadRepository:
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        self.table = "glas_voorraad"
    
    @contextmanager
    def _handle_errors(self, operation: str):
        try:
            yield
        except Exception as e:
            st.error(f"Database fout bij {operation}: {e}")
            raise
    
    def get_all(self) -> Optional[List[Dict[str, Any]]]:
        with self._handle_errors("ophalen data"):
            result = self.client.table(self.table).select("*").order("id").execute()
            return result.data
    
    def insert_many(self, records: List[Dict[str, Any]]) -> bool:
        with self._handle_errors("toevoegen records"):
            self.client.table(self.table).insert(records).execute()
            return True
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str) -> bool:
        with self._handle_errors("locatie update"):
            self.client.table(self.table)\
                .update({"locatie": nieuwe_locatie})\
                .in_("id", ids)\
                .execute()
            return True
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]) -> bool:
        with self._handle_errors("velden update"):
            self.client.table(self.table).upsert(updates).execute()
            return True
    
    def delete_many(self, ids: List[int]) -> bool:
        with self._handle_errors("verwijderen"):
            self.client.table(self.table).delete().in_("id", ids).execute()
            return True

# =============================================================================
# 3. SERVICE LAAG
# =============================================================================

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo
    
    def laad_voorraad_df(self) -> pd.DataFrame:
        data = self.repo.get_all()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=["id", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"])
        df["Selecteren"] = False
        return df[["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]]
    
    def filter_voorraad(self, df: pd.DataFrame, zoekterm: str) -> pd.DataFrame:
        if df.empty or not zoekterm: return df
        zoek_kolommen = [col for col in df.columns if col not in ["Selecteren", "id"]]
        mask = df[zoek_kolommen].astype(str).apply(lambda x: x.str.contains(zoekterm, case=False, na=False)).any(axis=1)
        return df[mask]
    
    def verwerk_inline_edits(self, df: pd.DataFrame, edits: Dict[int, Dict[str, Any]]) -> bool:
        if not edits: return False
        batch_updates = []
        for row_idx, changes in edits.items():
            clean_changes = {k: v for k, v in changes.items() if k != "Selecteren"}
            if clean_changes:
                row_id = df.iloc[int(row_idx)]["id"]
                batch_updates.append({"id": row_id, **clean_changes})
        return self.repo.bulk_update_fields(batch_updates) if batch_updates else False

    def valideer_excel_import(self, df: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
        errors = []
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = df.rename(columns={"order": "order_nummer", "ordernummer": "order_nummer", "aantal_stuks": "aantal", "qty": "aantal", "glastype": "omschrijving", "type": "omschrijving"})
        required = {"locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"}
        missing = required - set(df.columns)
        if missing: return pd.DataFrame(), [f"❌ FOUT: Ontbrekende kolommen: {', '.join(missing)}"]
        for num_col in ["aantal", "breedte", "hoogte"]: df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
        df.loc[~df["locatie"].isin(LOCATIE_OPTIES), "locatie"] = "HK"
        df["uit_voorraad"] = "Nee"
        return df.dropna(subset=["order_nummer"]).fillna(""), errors

# =============================================================================
# 4. UI HELPER FUNCTIES
# =============================================================================

@st.cache_data
def get_base64_logo(img_path: str) -> str:
    if os.path.exists(img_path):
        with open(img_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return ""

def render_styling(logo_b64: str):
    st.markdown(f"""
        <style>
        .block-container {{ padding-top: 1rem; padding-bottom: 5rem; }}
        #MainMenu, footer, header {{visibility: hidden;}}
        .header-left {{ display: flex; align-items: center; gap: 15px; height: 100%; }}
        .header-left img {{ width: 60px; height: auto; }}
        .header-left h1 {{ margin: 0; font-size: 1.8rem !important; font-weight: 700; }}
        div[data-testid="stTextInput"] > div, div[data-testid="stTextInput"] div[data-baseweb="input"] {{ height: 3.5em !important; }}
        div.stButton > button {{ border-radius: 8px; font-weight: 600; height: 3.5em !important; width: 100%; }}
        div.stButton > button[key="logout_btn"] {{ background-color: #ff4b4b; color: white; }}
        .action-box {{ background-color: #f8f9fa; border-radius: 10px; padding: 15px; margin-bottom: 10px; border: 1px solid #dee2e6; }}
        </style>
    """, unsafe_allow_html=True)

def render_header(logo_b64: str):
    # Verhouding 7:2 zodat Logout knop even breed is als de actieknoppen beneden
    h1, h2 = st.columns([7, 2])
    with h1:
        st.markdown(f'<div class="header-left"><img src="data:image/webp;base64,{logo_b64}"><h1>Voorraad glas</h1></div>', unsafe_allow_html=True)
    with h2:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.session_state.app_state.ingelogd = False
            st.query_params.clear()
            st.rerun()

def update_zoekterm():
    st.session_state.app_state.zoek_veld = st.session_state.zoek_input

def render_zoekbalk():
    state = st.session_state.app_state
    # Als er gezocht wordt: [5, 2, 2] (totaal 9), als er niet gezocht wordt: [7, 2] (totaal 9)
    # Dit houdt de 'Zoeken' knop op een constante breedte van 2/9 van het scherm.
    if state.zoek_veld:
        c1, c2, c3 = st.columns([5, 2, 2])
    else:
        c1, c2 = st.columns([7, 2])
    
    zoekterm = c1.text_input("Zoeken", placeholder="🔍 Zoek op order, maat of type...", 
                            label_visibility="collapsed", key="zoek_input", 
                            value=state.zoek_veld, on_change=update_zoekterm)
    
    if c2.button("ZOEKEN", use_container_width=True):
        state.zoek_veld = zoekterm
        st.rerun()
        
    if state.zoek_veld:
        if c3.button("WISSEN", use_container_width=True):
            state.zoek_veld = ""
            st.rerun()
    return state.zoek_veld

def render_batch_acties(geselecteerd_df: pd.DataFrame, service: VoorraadService):
    if geselecteerd_df.empty: return
    ids_to_act = geselecteerd_df["id"].tolist()
    state = st.session_state.app_state
    st.markdown('<div class="action-box">', unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns(2)
    
    btn_text = "❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN"
    if btn_col1.button(btn_text, use_container_width=True):
        state.show_location_grid = not state.show_location_grid
        st.rerun()
    
    if not state.confirm_delete:
        if btn_col2.button("🗑️ MEEGENOMEN", use_container_width=True):
            state.confirm_delete = True
            st.rerun()
    else:
        with btn_col2:
            st.warning("Zeker?")
            cy, cn = st.columns(2)
            if cy.button("JA", use_container_width=True):
                service.repo.delete_many(ids_to_act)
                state.confirm_delete = False
                state.mijn_data = service.laad_voorraad_df()
                st.rerun()
            if cn.button("NEE", use_container_width=True):
                state.confirm_delete = False
                st.rerun()
    
    if state.show_location_grid:
        st.divider()
        if st.button(f"🚀 VERPLAATS NAAR {state.bulk_loc}", type="primary", use_container_width=True):
            service.repo.bulk_update_location(ids_to_act, state.bulk_loc)
            state.show_location_grid = False
            state.mijn_data = service.laad_voorraad_df()
            st.rerun()
        cols = st.columns(5)
        for i, loc in enumerate(LOCATIE_OPTIES):
            with cols[i % 5]:
                if st.button(loc, key=f"loc_btn_{loc}", use_container_width=True, type="primary" if state.bulk_loc == loc else "secondary"):
                    state.bulk_loc = loc
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def render_beheer_sectie(service: VoorraadService):
    st.divider()
    ex1, ex2 = st.columns(2)
    with ex1.expander("➕ Nieuwe Ruit"):
        with st.form("add_form", clear_on_submit=True):
            nieuwe_ruit = {"locatie": st.selectbox("Locatie", LOCATIE_OPTIES), "order_nummer": st.text_input("Ordernummer"), "aantal": st.number_input("Aantal", min_value=1, value=1), "breedte": st.number_input("Breedte", value=0), "hoogte": st.number_input("Hoogte", value=0), "omschrijving": st.text_input("Glas type"), "uit_voorraad": "Nee"}
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                service.repo.insert_many([nieuwe_ruit])
                st.session_state.app_state.mijn_data = service.laad_voorraad_df()
                st.rerun()
    with ex2.expander("📥 Excel Import"):
        uploaded_file = st.file_uploader("Excel bestand", type=["xlsx"])
        if uploaded_file and st.button("UPLOAD NU", use_container_width=True):
            df_upload = pd.read_excel(uploaded_file)
            df_normalized, errors = service.valideer_excel_import(df_upload)
            if not df_normalized.empty:
                service.repo.insert_many(df_normalized[["locatie", "aantal", "breedte", "hoogte", "order_nummer", "uit_voorraad", "omschrijving"]].to_dict(orient="records"))
                st.session_state.app_state.mijn_data = service.laad_voorraad_df()
                st.rerun()

# =============================================================================
# 5. INITIALISATIE & MAIN
# =============================================================================

@st.cache_resource
def init_supabase() -> Client: return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

def main():
    if "app_state" not in st.session_state: st.session_state.app_state = AppState(ingelogd=st.query_params.get("auth") == "true")
    state = st.session_state.app_state
    
    if not state.ingelogd:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.header("Inloggen")
            if st.text_input("Wachtwoord", type="password") == WACHTWOORD and st.button("Inloggen", use_container_width=True):
                state.ingelogd = True
                st.query_params["auth"] = "true"
                st.rerun()
        st.stop()
    
    service = VoorraadService(GlasVoorraadRepository(init_supabase()))
    logo_b64 = get_base64_logo("theunissen.webp")
    if state.mijn_data.empty: state.mijn_data = service.laad_voorraad_df()
    
    render_styling(logo_b64)
    render_header(logo_b64)
    zoekterm = render_zoekbalk()
    view_df = service.filter_voorraad(state.mijn_data.copy(), zoekterm)
    
    actie_houder = st.container()

    # --- SELECTIE BUTTONS ---
    col_sel1, col_sel2, _ = st.columns([2, 2, 5])
    if col_sel1.button("✅ ALLES SELECTEREN", use_container_width=True):
        state.mijn_data.loc[state.mijn_data["id"].isin(view_df["id"]), "Selecteren"] = True
        st.rerun()
    if col_sel2.button("⬜ ALLES DESELECTEREN", use_container_width=True):
        state.mijn_data.loc[state.mijn_data["id"].isin(view_df["id"]), "Selecteren"] = False
        st.rerun()
    
    edited_df = st.data_editor(view_df, column_config={"Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"), "id": None, "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"), "aantal": st.column_config.NumberColumn("Aant.", width="small")}, hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"])
    
    edits = st.session_state.main_editor.get("edited_rows", {})
    if edits and any(any(k != "Selecteren" for k in change.keys()) for change in edits.values()):
        if service.verwerk_inline_edits(view_df, edits):
            state.mijn_data = service.laad_voorraad_df()
            st.rerun()
    
    with actie_houder: render_batch_acties(edited_df[edited_df["Selecteren"]], service)
    render_beheer_sectie(service)
    
    if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
        st.cache_data.clear()
        state.mijn_data = service.laad_voorraad_df()
        st.rerun()

if __name__ == "__main__": main()
