import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Riftbound Borsa", page_icon="📈", layout="wide")

# Nascondi menu Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except:
    st.error("Configura i Secrets su Streamlit Cloud.")
    st.stop()

# --- CARICAMENTO DATI ---
@st.cache_data(ttl=600)
def get_cards_list():
    res = supabase.table("cards").select("*").execute()
    df = pd.DataFrame(res.data)
    df['display_name'] = df.apply(lambda r: f"{r['name']} (✨ Showcase)" if r.get('is_showcase') else r['name'], axis=1)
    return df

def get_card_history(card_id):
    res = supabase.table("card_prices").select("*").eq("card_id", card_id).order("recorded_at", desc=False).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['recorded_at'] = pd.to_datetime(df['recorded_at'])
    return df

@st.cache_data(ttl=3600)
def get_global_market_data():
    """Recupera gli ultimi 1000 record per calcolare le statistiche globali"""
    res = supabase.table("card_prices").select("*").order("recorded_at", desc=True).limit(1000).execute()
    return pd.DataFrame(res.data)

# --- AVVIO APP ---
df_cards = get_cards_list()

# --- SIDEBAR ---
st.sidebar.title("📊 Navigazione")
selected_set = st.sidebar.selectbox("Set:", ["Tutti"] + sorted(list(df_cards['set_code'].unique())))
filtered_cards = df_cards if selected_set == "Tutti" else df_cards[df_cards['set_code'] == selected_set]

selected_display = st.sidebar.selectbox("Cerca Carta:", sorted(filtered_cards['display_name'].unique()))
selected_langs = st.sidebar.multiselect("Lingue:", ["EN", "CN"], default=["EN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta selezionata
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']
df_history = get_card_history(card_id)

# --- LAYOUT PRINCIPALE CON TABS ---
st.title("💹 Riftbound Market Intelligence")

tab1, tab2, tab3 = st.tabs(["🔍 Dettaglio Carta", "🌍 Mercato Globale", "🎒 La mia Collezione"])

# --- TAB 1: DETTAGLIO CARTA (La tua parte funzionante) ---
with tab1:
    col_img, col_chart = st.columns([1, 2.5])
    with col_img:
        st.image(card_info['image_url'], width='stretch')
        st.subheader("📝 Info")
        st.write(f"**Rarità:** {card_info['rarity']} | **Dominio:** {card_info['domain']}")
        if card_info['ability']:
            with st.expander("Vedi Abilità"):
                st.write(card_info['ability'])
    
    with col_chart:
        if not df_history.empty:
            plot_df = df_history[df_history['language'].isin(selected_langs)]
            if not plot_df.empty:
                # Calcolo Variazione 24h per la singola carta
                last_p = float(plot_df.iloc[-1]['price_low'])
                delta_val = 0
                if len(plot_df) > 1:
                    prev_p = float(plot_df.iloc[-2]['price_low'])
                    delta_val = last_p - prev_p
                
                st.metric("Ultimo Prezzo Rilevato", f"{last_p} €", delta=f"{round(delta_val, 2)} €")

                fig = px.line(plot_df, x="recorded_at", y="price_low", color="language",
                             markers=True, template="plotly_dark",
                             color_discrete_map={"EN": "#00CC96", "CN": "#EF553B"})
                fig.update_layout(hovermode="x unified", xaxis_title=None)
                st.plotly_chart(fig, width='stretch')
                
                with st.expander("📄 Storico Rilevazioni"):
                    st.dataframe(plot_df.sort_values('recorded_at', ascending=False), width='stretch')
            else:
                st.warning("Seleziona una lingua.")
        else:
            st.error("Dati non trovati.")

# --- TAB 2: MERCATO GLOBALE (Nuova!) ---
with tab2:
    st.header("📈 Analisi Trend")
    df_global = get_global_market_data()
    
    if not df_global.empty:
        # Esempio: Mostriamo le 5 carte più costose del momento
        st.subheader("💎 Le 5 carte più preziose (EN)")
        # Prende l'ultimo prezzo per ogni carta
        latest = df_global[df_global['language'] == 'EN'].sort_values('recorded_at').groupby('card_id').last().reset_index()
        top_5 = pd.merge(latest, df_cards[['card_id', 'name']], on='card_id').sort_values('price_low', ascending=False).head(5)
        
        cols = st.columns(5)
        for i, (_, row) in enumerate(top_5.iterrows()):
            cols[i].metric(row['name'], f"{row['price_low']} €")
        
        st.divider()
        st.info("💡 Prossimamente: Qui appariranno i Gainers e Losers basati sul Machine Learning.")

# --- TAB 3: LA MIA COLLEZIONE (Nuova!) ---
with tab3:
    st.header("🎒 Gestione Raccoglitore")
    st.write("Quante copie possiedi di questa carta?")
    
    # Un semplice simulatore (per ora non salva su DB, lo faremo col login)
    qty = st.number_input("Quantità posseduta", min_value=0, value=0, step=1)
    purchase_p = st.number_input("Prezzo di acquisto (€)", min_value=0.0, value=0.0)
    
    if qty > 0 and not df_history.empty:
        current_p = float(df_history.iloc[-1]['price_low'])
        total_val = qty * current_p
        profit = (current_p - purchase_p) * qty
        
        c1, c2 = st.columns(2)
        c1.metric("Valore Attuale", f"{round(total_val, 2)} €")
        c2.metric("Profitto/Perdita", f"{round(profit, 2)} €", delta=f"{round(profit, 2)} €")
        
    st.warning("🔒 La funzione di salvataggio permanente della collezione richiede l'integrazione del login.")

st.divider()
st.caption("Riftbound Borsa v3.0 | Dati aggiornati via GitHub Actions")
