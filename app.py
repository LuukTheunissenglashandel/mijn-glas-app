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
    """Centrale state management voor de applicatie"""
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
    """
    Database access laag - alle Supabase interacties gebeuren hier.
    Dit maakt de code testbaar en scheidt data logica van UI.
    """
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        self.table = "glas_voorraad"
    
    @contextmanager
    def _handle_errors(self, operation: str):
        """Consistente error handling voor alle database operaties"""
        try:
            yield
        except Exception as e:
            st.error(f"Database fout bij {operation}: {e}")
            raise
    
    def get_all(self) -> Optional[List[Dict[str, Any]]]:
        """Haal alle voorraad op, gesorteerd op ID"""
        with self._handle_errors("ophalen data"):
            result = self.client.table(self.table).select("*").order("id").execute()
            return result.data
    
    def insert_many(self, records: List[Dict[str, Any]]) -> bool:
        """Voeg meerdere records toe in één keer"""
        with self._handle_errors("toevoegen records"):
            self.client.table(self.table).insert(records).execute()
            return True
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str) -> bool:
        """Update locatie voor meerdere items tegelijk"""
        with self._handle_errors("locatie update"):
            self.client.table(self.table)\
                .update({"locatie": nieuwe_locatie})\
                .in_("id", ids)\
                .execute()
            return True
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]) -> bool:
        """
        Update meerdere rijen in één batch met upsert.
        Elk dict moet een 'id' key hebben plus de te wijzigen velden.
        """
        with self._handle_errors("velden update"):
            self.client.table(self.table).upsert(updates).execute()
            return True
    
    def delete_many(self, ids: List[int]) -> bool:
        """Verwijder meerdere items tegelijk"""
        with self._handle_errors("verwijderen"):
            self.client.table(self.table).delete().in_("id", ids).execute()
            return True


# =============================================================================
# 3. SERVICE LAAG - BUSINESS LOGICA
# =============================================================================

class VoorraadService:
    """
    Business logica laag - bevat alle bewerkingen op de data.
    Scheidt UI van database en maakt logica herbruikbaar.
    """
    
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo
    
    def laad_voorraad_df(self) -> pd.DataFrame:
        """
        Laad data van database en converteer naar DataFrame.
        Voegt automatisch 'Selecteren' kolom toe voor UI.
        """
        data = self.repo.get_all()
        
        if not data:
            # Lege DataFrame met correcte structuur
            df = pd.DataFrame(columns=[
                "id", "locatie", "aantal", "breedte", "hoogte", 
                "order_nummer", "omschrijving"
            ])
        else:
            df = pd.DataFrame(data)
        
        # Voeg selectie kolom toe voor UI (altijd eerste kolom)
        df["Selecteren"] = False
        
        # Juiste kolomvolgorde
        return df[[
            "Selecteren", "locatie", "aantal", "breedte", "hoogte", 
            "order_nummer", "omschrijving", "id"
        ]]
    
    def filter_voorraad(self, df: pd.DataFrame, zoekterm: str) -> pd.DataFrame:
        """
        Filter dataframe op zoekterm (case-insensitive).
        Zoekt in alle kolommen behalve 'Selecteren' en 'id'.
        """
        if df.empty or not zoekterm:
            return df
        
        # Kolommen waar we in zoeken (niet Selecteren en id)
        zoek_kolommen = [
            col for col in df.columns 
            if col not in ["Selecteren", "id"]
        ]
        
        # Zoek in alle kolommen, gebruik na=False om NaN te negeren
        mask = df[zoek_kolommen].astype(str).apply(
            lambda x: x.str.contains(zoekterm, case=False, na=False)
        ).any(axis=1)
        
        return df[mask]
    
    def verwerk_inline_edits(self, df: pd.DataFrame, edits: Dict[int, Dict[str, Any]]) -> bool:
        """
        Verwerk inline edits uit data_editor in één batch.
        Returns True als er daadwerkelijk wijzigingen waren.
        """
        if not edits:
            return False
        
        # Verzamel alle updates in batch formaat
        batch_updates = []
        
        for row_idx, changes in edits.items():
            # Filter 'Selecteren' veld eruit (is alleen voor UI)
            clean_changes = {
                k: v for k, v in changes.items() 
                if k != "Selecteren"
            }
            
            if clean_changes:
                # Haal row ID op uit originele DataFrame
                row_id = df.iloc[int(row_idx)]["id"]
                
                # Voeg ID toe aan changes voor upsert
                update_record = {"id": row_id, **clean_changes}
                batch_updates.append(update_record)
        
        # Voer batch update uit (1 database call ipv N calls!)
        if batch_updates:
            return self.repo.bulk_update_fields(batch_updates)
        
        return False
    
    def valideer_excel_import(self, df: pd.DataFrame) -> tuple[pd.DataFrame, List[str]]:
        """
        Valideer en normaliseer Excel import.
        Returns: (genormaliseerde df, lijst met waarschuwingen/fouten)
        """
        errors = []
        
        # Normaliseer kolomnamen
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Map veelvoorkomende aliassen naar correcte namen
        column_mapping = {
            "order": "order_nummer",
            "ordernummer": "order_nummer",
            "aantal_stuks": "aantal",
            "qty": "aantal",
            "glastype": "omschrijving",
            "type": "omschrijving"
        }
        df = df.rename(columns=column_mapping)
        
        # Check verplichte kolommen
        required = {"locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving"}
        missing = required - set(df.columns)
        if missing:
            errors.append(f"❌ FOUT: Ontbrekende kolommen: {', '.join(missing)}")
            return pd.DataFrame(), errors
        
        # Converteer numerieke velden
        for num_col in ["aantal", "breedte", "hoogte"]:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")
        
        # Valideer locaties
        invalid_locs = set(df["locatie"]) - set(LOCATIE_OPTIES)
        if invalid_locs:
            errors.append(f"⚠️ Waarschuwing: Ongeldige locaties gevonden: {', '.join(map(str, invalid_locs))}")
            # Vervang ongeldige locaties door default
            df.loc[df["locatie"].isin(invalid_locs), "locatie"] = "HK"
        
        # Verwijder rijen zonder kritieke data
        initial_count = len(df)
        df = df.dropna(subset=["order_nummer"])
        removed = initial_count - len(df)
        if removed > 0:
            errors.append(f"⚠️ {removed} rij(en) verwijderd wegens ontbrekende ordernummer")
        
        # Voeg default 'uit_voorraad' veld toe
        df["uit_voorraad"] = "Nee"
        
        # Vul overige NaN waarden met empty string
        df = df.fillna("")
        
        return df, errors


# =============================================================================
# 4. UI HELPER FUNCTIES
# =============================================================================

@st.cache_data
def get_base64_logo(img_path: str) -> str:
    """Cache logo als base64 om herhaald inlezen te voorkomen"""
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


def render_styling(logo_b64: str):
    """Render alle CSS styling - gescheiden van logica"""
    st.markdown(f"""
        <style>
        .block-container {{ 
            padding-top: 1rem; 
            padding-bottom: 5rem;
        }}
        
        #MainMenu, footer, header {{visibility: hidden;}}

        /* Verbetering scroll-gedrag: voorkomt scroll-trap in tabel */
        [data-testid="stDataEditor"] {{
            overscroll-behavior: auto !important;
            touch-action: pan-y !important;
        }}

        /* Mobiele aanpassingen voor tabelhoogte en header */
        @media (max-width: 768px) {{
            [data-testid="stDataEditor"] {{
                max-height: 400px !important;
            }}
            .header-left img {{ width: 35px; }}
            .header-left h1 {{ font-size: 1.1rem !important; }}
        }}

        /* Header styling */
        .header-left {{
            display: flex;
            align-items: center;
            gap: 15px;
            height: 100%;
        }}
        .header-left img {{ width: 60px; height: auto; flex-shrink: 0; }}
        .header-left h1 {{ margin: 0; font-size: 1.8rem !important; font-weight: 700; white-space: nowrap; }}

        /* Exacte hoogte uitlijning voor zoekveld en buttons */
        div[data-testid="stTextInput"] > div {{
            height: 3.5em !important;
        }}
        div[data-testid="stTextInput"] div[data-baseweb="input"] {{
            height: 3.5em !important;
        }}
        div.stButton > button {{ 
            border-radius: 8px; 
            font-weight: 600; 
            height: 3.5em !important; 
            width: 100%;
            white-space: nowrap;
        }}
        
        div.stButton > button[key="logout_btn"] {{
            background-color: #ff4b4b;
            color: white;
        }}

        .action-box {{ background-color: #f8f9fa; border-radius: 10px; padding: 10px 15px; margin-bottom: 10px; border: 1px solid #dee2e6; }}
        </style>
    """, unsafe_allow_html=True)


def render_header(logo_b64: str):
    """Render header met logo en uitlog knop"""
    h1, h2, h3 = st.columns([5, 1.5, 2])
    
    with h1:
        st.markdown(f"""
            <div class="header-left">
                <img src="data:image/webp;base64,{logo_b64}">
                <h1>Voorraad glas</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with h3:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.session_state.app_state.ingelogd = False
            st.query_params.clear()
            st.rerun()


def update_zoekterm():
    """Callback functie voor zoekterm update (wordt getriggerd bij Enter)"""
    st.session_state.app_state.zoek_veld = st.session_state.zoek_input


def render_zoekbalk():
    """Render zoekbalk met zoek en wis knoppen"""
    c1, c2, c3 = st.columns([5, 1.5, 2])
    
    # Text input met on_change voor Enter functionaliteit
    zoekterm = c1.text_input(
        "Zoeken", 
        placeholder="🔍 Zoek op order, maat of type...", 
        label_visibility="collapsed", 
        key="zoek_input",
        value=st.session_state.app_state.zoek_veld,
        on_change=update_zoekterm  # Enter triggert nu zoeken!
    )
    
    if c2.button("ZOEKEN", use_container_width=True):
        st.session_state.app_state.zoek_veld = zoekterm
    
    if st.session_state.app_state.zoek_veld:
        if c3.button("WISSEN", use_container_width=True):
            st.session_state.app_state.zoek_veld = ""
            st.rerun()
    
    return st.session_state.app_state.zoek_veld


def render_batch_acties(geselecteerd_df: pd.DataFrame, service: VoorraadService):
    """
    Render batch actie knoppen (locatie wijzigen, verwijderen).
    Alleen zichtbaar als er items geselecteerd zijn.
    """
    if geselecteerd_df.empty:
        return
    
    ids_to_act = geselecteerd_df["id"].tolist()
    state = st.session_state.app_state
    
    st.markdown('<div class="action-box">', unsafe_allow_html=True)
    
    btn_col1, btn_col2 = st.columns(2)
    
    # Locatie wijzigen toggle
    btn_text = "❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN"
    if btn_col1.button(btn_text, use_container_width=True):
        state.show_location_grid = not state.show_location_grid
    
    # Verwijder knop met bevestiging
    if not state.confirm_delete:
        if btn_col2.button("🗑️ MEEGENOMEN", key="delete_btn", use_container_width=True):
            state.confirm_delete = True
    else:
        with btn_col2:
            st.warning("Zeker?")
            cy, cn = st.columns(2)
            
            if cy.button("JA", key="confirm_delete_yes", use_container_width=True):
                service.repo.delete_many(ids_to_act)
                state.confirm_delete = False
                state.mijn_data = service.laad_voorraad_df()
                st.rerun()
            
            if cn.button("NEE", use_container_width=True):
                state.confirm_delete = False
    
    # Locatie grid (uitklapbaar)
    if state.show_location_grid:
        st.divider()
        
        if st.button(
            f"🚀 VERPLAATS NAAR {state.bulk_loc}", 
            type="primary", 
            use_container_width=True
        ):
            service.repo.bulk_update_location(ids_to_act, state.bulk_loc)
            state.show_location_grid = False
            state.mijn_data = service.laad_voorraad_df()
            st.rerun()
        
        # Grid met locatie knoppen (5 kolommen)
        cols = st.columns(5)
        for i, loc in enumerate(LOCATIE_OPTIES):
            button_type = "primary" if state.bulk_loc == loc else "secondary"
            if cols[i % 5].button(
                loc, 
                key=f"g_{loc}", 
                use_container_width=True, 
                type=button_type
            ):
                state.bulk_loc = loc
                # Geen rerun - Streamlit update automatisch
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_beheer_sectie(service: VoorraadService):
    """Render beheer sectie met 'nieuwe ruit' en Excel import"""
    st.divider()
    
    ex1, ex2 = st.columns(2)
    
    # Nieuwe ruit toevoegen
    with ex1.expander("➕ Nieuwe Ruit"):
        with st.form("add_form", clear_on_submit=True):
            nieuwe_ruit = {
                "locatie": st.selectbox("Locatie", LOCATIE_OPTIES),
                "order_nummer": st.text_input("Ordernummer"),
                "aantal": st.number_input("Aantal", min_value=1, value=1),
                "breedte": st.number_input("Breedte", value=0),
                "hoogte": st.number_input("Hoogte", value=0),
                "omschrijving": st.text_input("Glas type"),
                "uit_voorraad": "Nee"
            }
            
            if st.form_submit_button("VOEG TOE", use_container_width=True):
                service.repo.insert_many([nieuwe_ruit])
                st.session_state.app_state.mijn_data = service.laad_voorraad_df()
                st.rerun()
    
    # Excel import
    with ex2.expander("📥 Excel Import"):
        uploaded_file = st.file_uploader("Excel bestand", type=["xlsx"])
        
        if uploaded_file and st.button("UPLOAD NU", use_container_width=True):
            try:
                # Lees Excel
                df_upload = pd.read_excel(uploaded_file)
                
                # Valideer en normaliseer
                df_normalized, errors = service.valideer_excel_import(df_upload)
                
                # Toon eventuele waarschuwingen
                for error in errors:
                    if "FOUT" in error:
                        st.error(error)
                    else:
                        st.warning(error)
                
                # Upload als validatie OK is
                if not df_normalized.empty:
                    # Selecteer juiste kolommen en converteer naar dict
                    upload_records = df_normalized[[
                        "locatie", "aantal", "breedte", "hoogte", 
                        "order_nummer", "uit_voorraad", "omschrijving"
                    ]].to_dict(orient="records")
                    
                    service.repo.insert_many(upload_records)
                    st.success(f"✅ {len(upload_records)} rijen succesvol geüpload!")
                    st.session_state.app_state.mijn_data = service.laad_voorraad_df()
                    st.rerun()
                
            except Exception as e:
                st.error(f"Fout bij verwerken Excel: {e}")


# =============================================================================
# 5. INITIALISATIE & SUPABASE CONNECTION
# =============================================================================

@st.cache_resource
def init_supabase() -> Client:
    """Cached Supabase client - wordt maar 1x aangemaakt"""
    return create_client(
        st.secrets["supabase"]["url"], 
        st.secrets["supabase"]["key"]
    )


def init_app_state():
    """Initialiseer app state als die nog niet bestaat"""
    if "app_state" not in st.session_state:
        # Check of er een auth query param is
        is_authenticated = st.query_params.get("auth") == "true"
        st.session_state.app_state = AppState(ingelogd=is_authenticated)


# =============================================================================
# 6. AUTHENTICATIE
# =============================================================================

def render_login_scherm():
    """Render login scherm"""
    _, col, _ = st.columns([1, 2, 1])
    
    with col:
        st.header("Inloggen")
        wachtwoord_input = st.text_input("Wachtwoord", type="password")
        
        if st.button("Inloggen", use_container_width=True):
            if wachtwoord_input == WACHTWOORD:
                st.session_state.app_state.ingelogd = True
                st.query_params["auth"] = "true"
                st.rerun()
            else:
                st.error("Wachtwoord onjuist")


# =============================================================================
# 7. MAIN APPLICATION
# =============================================================================

def main():
    """Hoofdapplicatie - orkestreert alle componenten"""
    
    # Initialisatie
    init_app_state()
    state = st.session_state.app_state
    
    # Login check
    if not state.ingelogd:
        render_login_scherm()
        st.stop()
    
    # Setup
    supabase = init_supabase()
    repo = GlasVoorraadRepository(supabase)
    service = VoorraadService(repo)
    logo_b64 = get_base64_logo("theunissen.webp")
    
    # Laad data (eerste keer of na refresh)
    if state.mijn_data.empty:
        state.mijn_data = service.laad_voorraad_df()
    
    # Render UI
    render_styling(logo_b64)
    render_header(logo_b64)
    
    # Zoekbalk
    zoekterm = render_zoekbalk()
    
    # Filter data
    view_df = service.filter_voorraad(state.mijn_data.copy(), zoekterm)
    
    # Batch acties placeholder (moet voor data_editor voor juiste volgorde)
    actie_houder = st.container()
    
    # Data editor
    edited_df = st.data_editor(
        view_df,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,  # Verberg ID kolom
            "locatie": st.column_config.SelectboxColumn(
                "📍 Loc", 
                options=LOCATIE_OPTIES, 
                width="small"
            ),
            "aantal": st.column_config.NumberColumn("Aant.", width="small"),
        },
        hide_index=True,
        use_container_width=True,
        key="main_editor",
        height=500
    )
    
    # Verwerk inline edits (gebeurt automatisch bij wijzigingen)
    edits = st.session_state.main_editor.get("edited_rows", {})
    if edits:
        # Batch update - 1 database call ipv N calls!
        if service.verwerk_inline_edits(view_df, edits):
            state.mijn_data = service.laad_voorraad_df()
            st.rerun()
    
    # Render batch acties (in placeholder van eerder)
    geselecteerd_df = edited_df[edited_df["Selecteren"]]
    with actie_houder:
        render_batch_acties(geselecteerd_df, service)
    
    # Beheer sectie
    render_beheer_sectie(service)
    
    # Data refresh knop
    if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
        st.cache_data.clear()
        state.mijn_data = service.laad_voorraad_df()
        st.rerun()


# =============================================================================
# 8. RUN APPLICATION
# =============================================================================

if __name__ == "__main__":
    main()
