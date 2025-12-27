import streamlit as st
import pandas as pd
from supabase import create_client, Client

# --- 1. VERBINDING (De officiële manier) ---
@st.cache_resource # Zorgt dat de verbinding hergebruikt wordt
def get_supabase() -> Client:
    # We halen de gegevens uit [connections.supabase] of [supabase]
    # Voor de veiligheid checken we beide plekken
    if "connections" in st.secrets and "supabase" in st.secrets["connections"]:
        url = st.secrets["connections"]["supabase"]["url"]
        key = st.secrets["connections"]["supabase"]["key"]
    else:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    
    return create_client(url, key)

# --- 2. DATA FUNCTIES ---
def laad_data():
    supabase = get_supabase()
    # Let op: .execute() aan het einde is belangrijk
    res = supabase.table("glas_voorraad").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def update_rij(row_id, updates):
    supabase = get_supabase()
    supabase.table("glas_voorraad").update(updates).eq("id", row_id).execute()
    st.cache_data.clear()

def voeg_data_toe(df_nieuw):
    supabase = get_supabase()
    data_dict = df_nieuw.to_dict(orient="records")
    supabase.table("glas_voorraad").insert(data_dict).execute()
    st.cache_data.clear()
