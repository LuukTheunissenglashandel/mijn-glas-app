import streamlit as st
import pandas as pd
from supabase import create_client, Client
import base64
import os
from datetime import datetime
import pytz
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager

# =============================================================================
# 1. CONFIGURATIE & CACHING
# =============================================================================

st.set_page_config(layout="wide", page_title="Voorraad glas", page_icon="theunissen.webp")

# Constanten
WACHTWOORD = st.secrets["auth"]["password"]
LOCATIE_OPTIES = [
    "BK", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B9", "B10", 
    "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18", "B19", "B20", "W0",
    "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9", "W10"
]
ROWS_PER_PAGE = 25
AMSTERDAM_TZ = pytz.timezone("Europe/Amsterdam")

@dataclass
class AppState:
    ingelogd: bool = False
    mijn_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    bulk_loc: str = "BK"
    zoek_veld: str = ""
    current_page: int = 0
    loc_prefix: str = "B"
    success_msg: str = ""
    selected_ids: set = field(default_factory=set)
    undo_stack: List[Dict[str, Any]] = field(default_factory=list) 
    total_count: int = 0

@st.cache_data
def get_base64_logo(img_path: str) -> str:
    if os.path.exists(img_path):
        with open(img_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return ""

def render_styling():
    st.markdown(f"""
        <style>
        .block-container {{ padding-top: 1rem; padding-bottom: 5rem; }}
        #MainMenu, footer, header {{visibility: hidden;}}
        .header-left {{ display: flex; align-items: center; gap: 15px; height: 100%; }}
        .header-left img {{ width: 60px; height: auto; }}
        .header-left h1 {{ margin: 0; font-size: 1.8rem !important; font-weight: 700; }}
        div[data-testid="stTextInput"] > div, div[data-testid="stTextInput"] div[data-baseweb="input"] {{ height: 3.5em !important; }}
        div.stButton > button {{ border-radius: 8px; font-weight: 600; height: 3.5em !important; width: 100%; }}
        [data-testid="stVerticalBlock"] {{ gap: 0.4rem !important; }}
        </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 2. DATABASE & SERVICE LAAG
# =============================================================================

class GlasVoorraadRepository:
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
        self.table = "glas_voorraad"
    
    @contextmanager
    def _handle_errors(self, operation: str):
        try: yield
        except Exception as e:
            st.error(f"Database fout bij {operation}: {e}")
            raise
    
    def get_paged_data(self, zoekterm: str = "", page: int = 0, limit: int = 25) -> Tuple[List[Dict[str, Any]], int]:
        with self._handle_errors("ophalen data"):
            start, end = page * limit, (page * limit) + limit - 1
            query = self.client.table(self.table).select("*", count="exact")
            if zoekterm:
                search_filter = f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%"
                query = query.or_(search_filter)
            result = query.order("id").range(start, end).execute()
            return result.data, result.count

    def get_all_matching_ids(self, zoekterm: str = "") -> List[int]:
        query = self.client.table(self.table).select("id")
        if zoekterm:
            query = query.or_(f"order_nummer.ilike.%{zoekterm}%,omschrijving.ilike.%{zoekterm}%,locatie.ilike.%{zoekterm}%")
        result = query.execute()
        return [r['id'] for r in result.data]

    def get_sum_aantal_for_ids(self, ids: List[int]) -> int:
        if not ids: return 0
        result = self.client.table(self.table).select("aantal").in_("id", ids).execute()
        return sum(int(r['aantal'] or 0) for r in result.data)

    def insert_one(self, record: Dict[str, Any]):
        self.client.table(self.table).insert(record).execute()
    
    def bulk_update_location(self, ids: List[int], nieuwe_locatie: str):
        self.client.table(self.table).update({"locatie": nieuwe_locatie}).in_("id", ids).execute()
    
    def bulk_update_fields(self, updates: List[Dict[str, Any]]):
        self.client.table(self.table).upsert(updates).execute()
    
    def delete_many(self, ids: List[int]):
        self.client.table(self.table).delete().in_("id", ids).execute()

class VoorraadService:
    def __init__(self, repo: GlasVoorraadRepository):
        self.repo = repo

    def laad_data(self, zoekterm: str, page: int) -> Tuple[pd.DataFrame, int]:
        @st.cache_data(ttl=600)
        def _cached_fetch(zoek: str, p: int):
            return self.repo.get_paged_data(zoek, p, ROWS_PER_PAGE)
        
        data, count = _cached_fetch(zoekterm, page)
        kolommen = ["Selecteren", "locatie", "aantal", "breedte", "hoogte", "order_nummer", "omschrijving", "id"]
        if not data: return pd.DataFrame(columns=kolommen), 0
        df = pd.DataFrame(data)
        df["Selecteren"] = df["id"].apply(lambda x: x in st.session_state.app_state.selected_ids)
        for col in kolommen:
            if col not in df.columns: df[col] = None
        return df[kolommen], count

    def push_undo_state(self):
        full_data = self.repo.client.table("glas_voorraad").select("*").execute().data
        nu = datetime.now(AMSTERDAM_TZ).strftime("%d-%m-%Y %H:%M:%S")
        st.session_state.app_state.undo_stack.append({"data": full_data, "tijd": nu})
        if len(st.session_state.app_state.undo_stack) > 10: st.session_state.app_state.undo_stack.pop(0)

# =============================================================================
# 3. UI COMPONENTEN
# =============================================================================

def render_header(logo_b64: str):
    h1, h2 = st.columns([7, 2])
    with h1:
        st.markdown(f'<div class="header-left"><img src="data:image/webp;base64,{logo_b64}"><h1>Voorraad glas</h1></div>', unsafe_allow_html=True)
    with h2:
        if st.button("🚪 UITLOGGEN", key="logout_btn", use_container_width=True):
            st.session_state.clear()
            st.rerun()

@st.fragment
def render_main_interface(service: VoorraadService):
    state = st.session_state.app_state
    
    # 1. Zoeksectie met dynamische knop
    c1, c2 = st.columns([7, 2])
    zoek_val = c1.text_input("Zoeken", value=state.zoek_veld, placeholder="🔍 Zoek...", label_visibility="collapsed")
    
    if zoek_val != state.zoek_veld:
        state.zoek_veld = zoek_val
        state.current_page = 0
        st.rerun()
        
    if not state.zoek_veld:
        if c2.button("ZOEKEN", use_container_width=True, key="main_search"): st.rerun()
    else:
        if c2.button("WISSEN", use_container_width=True, key="main_clear"):
            state.zoek_veld = ""
            state.current_page = 0
            st.rerun()

    # 2. Data & Sommen
    state.mijn_data, state.total_count = service.laad_data(state.zoek_veld, state.current_page)
    
    # Lokale berekening van sommen voor snelheid
    curr_ids = set(state.mijn_data['id'].tolist())
    sel_on = state.selected_ids.intersection(curr_ids)
    sum_on = state.mijn_data[state.mijn_data['id'].isin(sel_on)]['aantal'].fillna(0).astype(int).sum()
    
    @st.cache_data(ttl=300)
    def get_off_page_sum(ids_tuple):
        if not ids_tuple: return 0
        return service.repo.get_sum_aantal_for_ids(list(ids_tuple))
    
    sel_off = state.selected_ids.difference(curr_ids)
    sum_off = get_off_page_sum(tuple(sorted(list(sel_off))))
    totaal_sel = sum_on + sum_off
    suffix = f" ({totaal_sel})" if totaal_sel > 0 else ""

    # 3. Tabel Acties
    act_cont = st.container()
    cs1, cs2 = st.columns([1, 1])
    if cs1.button(f"✅ ALLES SELECTEREN{suffix}", use_container_width=True):
        state.selected_ids.update(service.repo.get_all_matching_ids(state.zoek_veld)); st.rerun()
    if cs2.button(f"⬜ ALLES DESELECTEREN{suffix}", use_container_width=True):
        state.selected_ids.clear(); st.rerun()

    # 4. De Tabel
    def on_edit():
        if "main_editor" in st.session_state:
            edits = st.session_state.main_editor.get("edited_rows", {})
            for idx, changes in edits.items():
                if "Selecteren" in changes:
                    rid = state.mijn_data.iloc[int(idx)]["id"]
                    if changes["Selecteren"]: state.selected_ids.add(rid)
                    else: state.selected_ids.discard(rid)
    
    st.data_editor(
        state.mijn_data,
        column_config={
            "Selecteren": st.column_config.CheckboxColumn("Selecteer", width="small"),
            "id": None,
            "locatie": st.column_config.SelectboxColumn("📍 Loc", options=LOCATIE_OPTIES, width="small"),
            "aantal": st.column_config.NumberColumn("Aant.", width="small")
        },
        hide_index=True, use_container_width=True, key="main_editor", height=500, disabled=["id"],
        on_change=on_edit
    )

    # Database updates verwerken
    edits = st.session_state.main_editor.get("edited_rows", {})
    db_updates = []
    for idx, changes in edits.items():
        clean = {k: v for k, v in changes.items() if k != "Selecteren"}
        if clean: db_updates.append({"id": int(state.mijn_data.iloc[int(idx)]["id"]), **clean})
    
    if db_updates:
        service.push_undo_state(); service.repo.bulk_update_fields(db_updates)
        st.cache_data.clear(); st.rerun()

    # 5. Paginering
    num_p = max(1, (state.total_count - 1) // ROWS_PER_PAGE + 1)
    if num_p > 1:
        p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
        if p1.button("⬅️ VORIGE", disabled=state.current_page == 0, use_container_width=True):
            state.current_page -= 1; st.rerun()
        p2.markdown(f"<p style='text-align:center; margin:0;'>Pagina {state.current_page + 1} van {num_p}</p>", unsafe_allow_html=True)
        if p3.button("VOLGENDE ➡️", disabled=state.current_page == num_p - 1, use_container_width=True):
            state.current_page += 1; st.rerun()

    # 6. Bulk acties
    if state.selected_ids:
        with act_cont:
            b1, b2 = st.columns(2)
            if b1.button("❌ SLUIT" if state.show_location_grid else "📍 LOCATIE WIJZIGEN", use_container_width=True):
                state.show_location_grid = not state.show_location_grid; st.rerun()
            if b2.button(f"🗑️ MEEGENOMEN ({totaal_sel})", use_container_width=True):
                service.push_undo_state(); service.repo.delete_many(list(state.selected_ids))
                state.selected_ids.clear(); st.cache_data.clear(); st.rerun()
            
            if state.show_location_grid:
                st.divider()
                al1, al2, al3 = st.columns([2, 1, 1])
                if al1.button(f"🚀 VERPLAATS NAAR {state.bulk_loc}", type="primary", use_container_width=True):
                    service.push_undo_state(); service.repo.bulk_update_location(list(state.selected_ids), state.bulk_loc)
                    st.cache_data.clear(); state.show_location_grid = False; st.rerun()
                if al2.button("📍 Wijchen", use_container_width=True): state.loc_prefix = "W"; st.rerun()
                if al3.button("📍 Boxmeer", use_container_width=True): state.loc_prefix = "B"; st.rerun()
                
                locs = [l for l in LOCATIE_OPTIES if l.startswith(state.loc_prefix) or l == "BK"]
                cols = st.columns(5)
                for i, loc in enumerate(locs):
                    with cols[i % 5]:
                        if st.button(loc, key=f"lbtn_{loc}", use_container_width=True, type="primary" if state.bulk_loc == loc else "secondary"):
                            state.bulk_loc = loc; st.rerun()

# =============================================================================
# 4. MAIN EXECUTION
# =============================================================================

def main():
    if "app_state" not in st.session_state: 
        st.session_state.app_state = AppState(ingelogd=st.query_params.get("auth") == "true")
    state = st.session_state.app_state

    render_styling()
    logo_b64 = get_base64_logo("theunissen.webp")

    if not state.ingelogd:
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.header("Inloggen")
            pw = st.text_input("Wachtwoord", type="password")
            if st.button("Inloggen", use_container_width=True):
                if pw == WACHTWOORD:
                    state.ingelogd = True; st.query_params["auth"] = "true"; st.rerun()
                else: st.error("Wachtwoord onjuist")
        st.stop()
    
    repo = GlasVoorraadRepository(create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]))
    service = VoorraadService(repo)
    
    render_header(logo_b64)
    render_main_interface(service)

    # Footer
    st.divider()
    f1, f2 = st.columns([1, 1])
    with f1:
        st.subheader("➕ Nieuwe ruit toevoegen")
        if state.success_msg: st.success(state.success_msg); state.success_msg = ""
        with st.form("add_form", clear_on_submit=True):
            n_loc = st.selectbox("Locatie", options=LOCATIE_OPTIES)
            n_aant = st.number_input("Aantal", min_value=1, value=1)
            n_br = st.number_input("Breedte (mm)", min_value=0, value=0)
            n_ho = st.number_input("Hoogte (mm)", min_value=0, value=0)
            n_ord = st.text_input("Ordernummer")
            n_oms = st.text_input("Omschrijving")
            if st.form_submit_button("TOEVOEGEN", use_container_width=True):
                service.push_undo_state()
                repo.insert_one({"locatie": n_loc, "aantal": n_aant, "breedte": n_br if n_br > 0 else None, "hoogte": n_ho if n_ho > 0 else None, "order_nummer": n_ord.strip() or None, "omschrijving": n_oms.strip() or None})
                st.cache_data.clear(); state.success_msg = "Gelukt!"; st.rerun()

    with f2:
        st.subheader("📥 Bulk & Systeem")
        up = st.file_uploader("Bulk import Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")
        if up and st.button("🚀 IMPORT STARTEN", use_container_width=True):
            try:
                df = pd.read_excel(up)
                df.columns = [str(c).lower().strip().replace(' ', '_') for c in df.columns]
                if 'order' in df.columns: df = df.rename(columns={'order': 'order_nummer'})
                service.push_undo_state(); repo.bulk_update_fields(df.to_dict('records'))
                st.cache_data.clear(); st.rerun()
            except Exception as e: st.error(f"Fout: {e}")
        
        if st.button("🔄 DATA VOLLEDIG VERVERSEN", use_container_width=True):
            st.cache_data.clear(); st.rerun()
        if state.undo_stack:
            ls = state.undo_stack[-1]
            if st.button(f"⏪ TERUGZETTEN ({ls['tijd']})", use_container_width=True):
                service.repo.client.table("glas_voorraad").delete().neq("id", 0).execute()
                service.repo.client.table("glas_voorraad").insert([{k:v for k,v in r.items() if k != 'Selecteren'} for r in state.undo_stack.pop()['data']]).execute()
                st.cache_data.clear(); st.success("Hersteld!"); st.rerun()

if __name__ == "__main__": main()
