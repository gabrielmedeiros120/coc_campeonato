import streamlit as st
import sqlite3
import pandas as pd
import random

# ---------------------------
# CONFIGURAÇÃO INICIAL
# ---------------------------
players = [
    "Necrod", "Mayara", "Cabo", "Cronos", "Ramos",
    "Diogo", "Senju", "Erick", "Magnata", "Vanahein"
]

# ---------------------------
# BANCO DE DADOS
# ---------------------------
def init_db():
    conn = sqlite3.connect("liga.db")
    c = conn.cursor()

    # Tabela de jogadores
    c.execute('''CREATE TABLE IF NOT EXISTS jogadores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT UNIQUE,
                    vitorias INTEGER DEFAULT 0,
                    estrelas_ataque INTEGER DEFAULT 0,
                    estrelas_defesa INTEGER DEFAULT 0,
                    porc_ataque REAL DEFAULT 0,
                    porc_defesa REAL DEFAULT 0,
                    tempo_ataque REAL DEFAULT 0,
                    tempo_defesa REAL DEFAULT 0
                )''')

    # Tabela de rodadas
    c.execute('''CREATE TABLE IF NOT EXISTS rodadas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rodada INTEGER,
                    jogador1 TEXT,
                    jogador2 TEXT,
                    estrelas_j1 INTEGER,
                    estrelas_j2 INTEGER,
                    porc_j1 REAL,
                    porc_j2 REAL,
                    tempo_j1 REAL,
                    tempo_j2 REAL
                )''')

    conn.commit()
    return conn

# ---------------------------
# FUNÇÕES AUXILIARES
# ---------------------------
def get_jogadores(conn):
    return pd.read_sql("SELECT * FROM jogadores", conn)

def get_rodadas(conn):
    return pd.read_sql("SELECT * FROM rodadas", conn)

def inicializar_jogadores(conn):
    for nome in players:
        try:
            conn.execute("INSERT INTO jogadores (nome) VALUES (?)", (nome,))
        except:
            pass
    conn.commit()

def gerar_rodadas(conn):
    # Se já tiver rodadas cadastradas, não gera de novo
    existentes = pd.read_sql("SELECT COUNT(*) as qtd FROM rodadas", conn).iloc[0]["qtd"]
    if existentes > 0:
        return
    
    # Algoritmo round-robin
    n = len(players)
    lista = players.copy()
    if n % 2 != 0:
        lista.append("BYE")
        n += 1
    
    rodadas = []
    for i in range(n - 1):
        pares = []
        for j in range(n // 2):
            p1 = lista[j]
            p2 = lista[n - 1 - j]
            if p1 != "BYE" and p2 != "BYE":
                pares.append((p1, p2))
        rodadas.append(pares)
        lista.insert(1, lista.pop())
    
    # Inserir no banco
    for r, jogos in enumerate(rodadas, start=1):
        for j1, j2 in jogos:
            conn.execute("""INSERT INTO rodadas 
                            (rodada, jogador1, jogador2, estrelas_j1, estrelas_j2, porc_j1, porc_j2, tempo_j1, tempo_j2)
                            VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0)""",
                         (r, j1, j2))
    conn.commit()

def registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2):
    conn.execute("""UPDATE rodadas SET 
                        estrelas_j1=?, estrelas_j2=?, 
                        porc_j1=?, porc_j2=?, 
                        tempo_j1=?, tempo_j2=?
                    WHERE rodada=? AND jogador1=? AND jogador2=?""",
                 (e1, e2, p1, p2, t1, t2, rodada, j1, j2))
    conn.commit()
    atualizar_classificacao(conn, j1, j2, e1, e2, p1, p2, t1, t2)

def atualizar_classificacao(conn, j1, j2, e1, e2, p1, p2, t1, t2):
    # vitórias
    if e1 > e2:
        conn.execute("UPDATE jogadores SET vitorias = vitorias + 1 WHERE nome = ?", (j1,))
    elif e2 > e1:
        conn.execute("UPDATE jogadores SET vitorias = vitorias + 1 WHERE nome = ?", (j2,))

    # estrelas ataque
    conn.execute("UPDATE jogadores SET estrelas_ataque = estrelas_ataque + ? WHERE nome = ?", (e1, j1))
    conn.execute("UPDATE jogadores SET estrelas_ataque = estrelas_ataque + ? WHERE nome = ?", (e2, j2))

    # estrelas defesa
    conn.execute("UPDATE jogadores SET estrelas_defesa = estrelas_defesa + ? WHERE nome = ?", (e2, j1))
    conn.execute("UPDATE jogadores SET estrelas_defesa = estrelas_defesa + ? WHERE nome = ?", (e1, j2))

    # porcentagem
    conn.execute("UPDATE jogadores SET porc_ataque = porc_ataque + ?, porc_defesa = porc_defesa + ? WHERE nome = ?", (p1, p2, j1))
    conn.execute("UPDATE jogadores SET porc_ataque = porc_ataque + ?, porc_defesa = porc_defesa + ? WHERE nome = ?", (p2, p1, j2))

    # tempo
    conn.execute("UPDATE jogadores SET tempo_ataque = tempo_ataque + ?, tempo_defesa = tempo_defesa + ? WHERE nome = ?", (t1, t2, j1))
    conn.execute("UPDATE jogadores SET tempo_ataque = tempo_ataque + ?, tempo_defesa = tempo_defesa + ? WHERE nome = ?", (t2, t1, j2))

    conn.commit()

# ---------------------------
# APP STREAMLIT
# ---------------------------
st.set_page_config(page_title="Liga do 13°", layout="wide")
st.title("🏆 Liga do 13° – Temporada 1")

conn = init_db()
inicializar_jogadores(conn)
gerar_rodadas(conn)

menu = st.sidebar.radio("Navegação", ["Classificação", "Rodadas", "Cadastrar Resultados"])

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
if menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")

    df = get_jogadores(conn)
    if not df.empty:
        # Ordenação com todos os critérios de desempate
        df = df.sort_values(
            by=[
                "vitorias",          # mais vitórias primeiro
                "estrelas_ataque",   # mais estrelas ataque
                "estrelas_defesa",   # menos estrelas sofridas
                "porc_ataque",       # maior % ataque
                "porc_defesa",       # menor % defesa sofrida
                "tempo_ataque",      # menor tempo ataque
                "tempo_defesa"       # menor tempo defesa
            ],
            ascending=[
                False,   # vitórias desc
                False,   # estrelas ataque desc
                True,    # estrelas defesa asc
                False,   # % ataque desc
                True,    # % defesa asc
                True,    # tempo ataque asc
                True     # tempo defesa asc
            ]
        ).reset_index(drop=True)

        # Adiciona posição
        df.insert(0, "Posição", range(1, len(df) + 1))

        st.dataframe(
            df[[
                "Posição", "nome", "vitorias", "estrelas_ataque", "estrelas_defesa",
                "porc_ataque", "porc_defesa", "tempo_ataque", "tempo_defesa"
            ]],
            use_container_width=True
        )
# ---------------------------
# RODADAS
# ---------------------------
elif menu == "Rodadas":
    st.subheader("📅 Rodadas")
    rodadas = get_rodadas(conn)
    if rodadas.empty:
        st.info("Nenhum confronto registrado ainda.")
    else:
        for r in sorted(rodadas["rodada"].unique()):
            st.markdown(f"### Rodada {r}")
            st.dataframe(rodadas[rodadas["rodada"] == r][["jogador1", "jogador2", "estrelas_j1", "estrelas_j2"]],
                         use_container_width=True)

# ---------------------------
# CADASTRAR RESULTADOS
# ---------------------------
elif menu == "Cadastrar Resultados":
    st.subheader("✍️ Registrar Resultado")

    rodadas = get_rodadas(conn)
    rodada = st.selectbox("Rodada", sorted(rodadas["rodada"].unique()))
    jogos = rodadas[rodadas["rodada"] == rodada][["jogador1", "jogador2"]].values.tolist()

    jogo = st.selectbox("Confronto", [f"{j1} vs {j2}" for j1, j2 in jogos])
    j1, j2 = jogo.split(" vs ")

    e1 = st.number_input(f"⭐ Estrelas {j1}", 0, 3, step=1)
    e2 = st.number_input(f"⭐ Estrelas {j2}", 0, 3, step=1)
    p1 = st.number_input(f"% Ataque {j1}", 0.0, 100.0, step=0.1)
    p2 = st.number_input(f"% Ataque {j2}", 0.0, 100.0, step=0.1)
    t1 = st.number_input(f"⏱️ Tempo {j1} (segundos)", 0.0, 300.0, step=1.0)
    t2 = st.number_input(f"⏱️ Tempo {j2} (segundos)", 0.0, 300.0, step=1.0)

    if st.button("Salvar Resultado"):
        registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2)
        st.success("Resultado registrado com sucesso ✅")
