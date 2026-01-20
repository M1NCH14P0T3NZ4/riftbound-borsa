import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Riftbound Borsa AI", 
    page_icon="📈", 
    layout="wide"
)

# Nascondi menu Streamlit
st.markdown("""<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>""", unsafe_allow_html=True)

# --- CONNESSIONE SUPABASE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(URL, KEY)
except Exception as e:
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

# --- INTERFACCIA ---
try:
    df_cards = get_cards_list()
except:
    st.error("Impossibile connettersi a Supabase. Controlla le chiavi API.")
    st.stop()

st.sidebar.title("📊 Analisi Mercato")
st.sidebar.divider()

card_list = sorted(df_cards['display_name'].unique())
selected_display = st.sidebar.selectbox("Seleziona Carta:", card_list)
selected_lang = st.sidebar.radio("Mercato:", ["EN", "CN"])

if st.sidebar.button("🔄 Aggiorna Database"):
    st.cache_data.clear()
    st.rerun()

# Recupero info carta
card_info = df_cards[df_cards['display_name'] == selected_display].iloc[0]
card_id = card_info['card_id']

# --- LAYOUT PRINCIPALE ---
st.title(f"📊 Borsa: {selected_display}")
st.caption("Confronto Prezzo Istantaneo vs Media Mobile (SMA 7gg)")
st.divider()

col_img, col_chart = st.columns([1, 2.5])

# Recupero Storico
df_history = get_card_history(card_id)

with col_img:
    st.image(card_info['image_url'], use_container_width=True)
    st.subheader("📝 Info")
    st.write(f"**Rarità:** {card_info['rarity']} | **Set:** {card_info['set_code']}")
    
    # LOGICA SEGNALE IA
    if not df_history.empty:
        df_lang = df_history[df_history['language'] == selected_lang]
        if not df_lang.empty:
            last_p = float(df_lang.iloc[-1]['price_low'])
            last_t = float(df_lang.iloc[-1]['price_trend'])
            
            st.subheader("🤖 Segnale IA")
            if last_p > last_t * 1.15:
                st.warning(f"⚠️ **SOPRAVALUTATA**\nIl prezzo è del {round(((last_p/last_t)-1)*100)}% sopra la media.")
            elif last_p < last_t * 0.85:
                st.success(f"🔥 **OCCASIONE**\nIl prezzo è del {round((1-(last_p/last_t))*100)}% sotto la media.")
            else:
                st.info("⚖️ **STABILE**\nPrezzo in linea con il trend.")

with col_chart:
    if not df_history.empty:
        df_plot = df_history[df_history['language'] == selected_lang].copy()
        
        if not df_plot.empty:
            # --- FIX VALUERROR: Riprogrammazione Melt ---
            # Selezioniamo solo le colonne necessarie
            temp_df = df_plot[['recorded_at', 'price_low', 'price_trend']].copy()
            
            # Trasformiamo in formato 'lungo' per Plotly
            df_melted = temp_df.melt(
                id_vars=['recorded_at'],
                value_vars=['price_low', 'price_trend'],
                var_name='Legenda',
                value_name='Prezzo'
            )
            
            # Rinominazione valori per la legenda
            df_melted['Legenda'] = df_melted['Legenda'].map({
                'price_low': 'Prezzo di Mercato',
                'price_trend': 'Trend (Media 7gg)'
            })

            # GRAFICO
            fig = px.line(
                df_melted, 
                x="recorded_at", 
                y="Prezzo", 
                color="Legenda",
                markers=True, 
                template="plotly_dark",
                color_discrete_map={
                    'Prezzo di Mercato': "#00CC96", 
                    'Trend (Media 7gg)': "#FFA15A"
                }
            )
            
            fig.update_layout(
                hovermode="x unified",
                xaxis_title=None,
                yaxis_title="Prezzo (€)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Metrica Veloce
            st.metric(
                label=f"Ultimo Rilevamento ({selected_lang})", 
                value=f"{df_plot.iloc[-1]['price_low']} €", 
                delta=f"{round(float(df_plot.iloc[-1]['price_low']) - float(df_plot.iloc[-1]['price_trend']), 2)} € vs Media"
            )
        else:
            st.warning(f"Nessun dato per il mercato {selected_lang}.")
    else:
        st.info("Nessuno storico prezzi trovato per questa carta.")

# Tabella in fondo
if not df_history.empty:
    with st.expander("📄 Visualizza Storico Dati"):
        st.dataframe(df_history.sort_values('recorded_at', ascending=False), use_container_width=True, hide_index=True)

st.divider()
st.caption("Riftbound Borsa AI v3.1 | Powered by Supabase & CardTrader")
