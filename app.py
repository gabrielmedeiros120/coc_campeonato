import streamlit as st
import pandas as pd

# =====================
# Configuração inicial
# =====================
players = [
    "Necrod", "Mayara", "Cabo", "Cronos", "Ramos",
    "Diogo", "Senju", "Erick", "Magnata", "Vanahein"
]

# DataFrame inicial
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame({
        "Jogador": players,
        "Vitórias": 0,
        "Estrelas Ataque": 0,
        "Estrelas Defesa": 0,
        "Porc Ataque": 0.0,
        "Porc Defesa": 0.0,
        "Tempo Ataque": 0,
        "Tempo Defesa": 0
    })

df = st.session_state.df

# =====================
# Layout
# =====================
st.title("🏆 Liga do 13º – Temporada 1")
st.subheader("Tabela de Classificação")

# Ordenação por critérios de desempate
df_sorted = df.sort_values(
    by=[
        "Vitórias",
        "Estrelas Ataque",
        "Estrelas Defesa",
        "Porc Ataque",
        "Porc Defesa",
        "Tempo Ataque",
        "Tempo Defesa"
    ],
    ascending=[False, False, True, False, True, True, True]
)

st.dataframe(df_sorted, use_container_width=True)

# =====================
# Inserir resultados
# =====================
st.subheader("Adicionar Resultado de Duelo")

col1, col2 = st.columns(2)
with col1:
    player_a = st.selectbox("Jogador A", players)
    estrelas_a = st.number_input("Estrelas Ataque (A)", 0, 3, 0)
    porc_a = st.slider("Porcentagem Ataque (A)", 0, 100, 0)
    tempo_a = st.number_input("Tempo Ataque (A)", 0, 300, 0)

with col2:
    player_b = st.selectbox("Jogador B", players)
    estrelas_b = st.number_input("Estrelas Ataque (B)", 0, 3, 0)
    porc_b = st.slider("Porcentagem Ataque (B)", 0, 100, 0)
    tempo_b = st.number_input("Tempo Ataque (B)", 0, 300, 0)

if st.button("Registrar Resultado"):
    if player_a != player_b:
        # Vitórias
        vit_a, vit_b = (1,0) if estrelas_a > estrelas_b else (0,1) if estrelas_b > estrelas_a else (0,0)

        # Atualiza estatísticas
        for p, vit, est_atk, est_def, porc_atk, porc_def, tempo_atk, tempo_def in [
            (player_a, vit_a, estrelas_a, estrelas_b, porc_a, porc_b, tempo_a, tempo_b),
            (player_b, vit_b, estrelas_b, estrelas_a, porc_b, porc_a, tempo_b, tempo_a)
        ]:
            df.loc[df["Jogador"] == p, "Vitórias"] += vit
            df.loc[df["Jogador"] == p, "Estrelas Ataque"] += est_atk
            df.loc[df["Jogador"] == p, "Estrelas Defesa"] += est_def
            df.loc[df["Jogador"] == p, "Porc Ataque"] += porc_atk
            df.loc[df["Jogador"] == p, "Porc Defesa"] += porc_def
            df.loc[df["Jogador"] == p, "Tempo Ataque"] += tempo_atk
            df.loc[df["Jogador"] == p, "Tempo Defesa"] += tempo_def

        st.success("✅ Resultado registrado!")
    else:
        st.error("Jogador A e Jogador B não podem ser o mesmo.")

