import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Errore: Secrets non configurati correttamente.")
    st.stop()

# --- CARICAMENTO CARTE ---
@st.cache_data(ttl=600)
def get_cards():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    # Creiamo il nome per il menu
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

# --- CARICAMENTO PREZZI (Solo per la carta scelta) ---
def get_history(cid):
    # Usiamo 'ilike' invece di 'eq' per ignorare maiuscole/minuscole (più sicuro)
    res = supabase.table("card_prices").select("*").ilike("card_id", cid).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
        # Ordiniamo per data qui in Python, che è più affidabile
        df = df.sort_values('recorded_at')
    return df

# --- INTERFACCIA ---
df_cards = get_cards()

st.sidebar.title("🔍 Navigazione")
selected_display = st.sidebar.selectbox("Scegli carta:", sorted(df_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN", "CN"])

if st.sidebar.button("🔄 Forza Ricaricamento"):
    st.cache_data.clear()
    st.rerun()

# Dati della carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# Recupero storico
df_prices = get_history(card_id)

# --- VISUALIZZAZIONE ---
st.title(f"📊 Borsa: {selected_display}")
st.divider()

col1, col2 = st.columns([1, 2])

with col1:
    # Immagine e Specs (Uso use_container_width=True, ignora pure i warning del terminale)
    st.image(card_info['image_url'], use_container_width=True)
    st.markdown(f"**ID:** `{card_id}` | **Rarità:** {card_info['rarity']}")
    if card_info['ability']:
        st.info(card_info['ability'])

with col2:
    if not df_prices.empty:
        # Applichiamo il filtro lingua
        plot_df = df_prices[df_prices['language'].isin(selected_langs)]
        
        if not plot_df.empty:
            # Grafico
            fig = px.line(
                plot_df, x="recorded_at", y="price_low", color="language",
                markers=True, template="plotly_dark",
                color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"},
                labels={"recorded_at": "Data", "price_low": "Prezzo (€)"}
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tabella
            with st.expander("📄 Vedi record completi"):
                st.dataframe(plot_df.sort_values('recorded_at', ascending=False), use_container_width=True)
        else:
            st.warning("Seleziona una lingua per vedere i dati.")
    else:
        st.error(f"⚠️ Nessun prezzo trovato per {card_id} nel database.")
        # Debug per te:
        st.write("Controlla se l'ID in 'card_prices' è identico a quello in 'cards'.")

st.divider()
st.caption("Riftbound Dashboard")
