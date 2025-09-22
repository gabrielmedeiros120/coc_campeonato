import streamlit as st
import sqlite3
import pandas as pd

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

def adicionar_jogador(conn, nome):
    try:
        conn.execute("INSERT INTO jogadores (nome) VALUES (?)", (nome,))
        conn.commit()
    except:
        pass

def registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2):
    conn.execute("""INSERT INTO rodadas 
                    (rodada, jogador1, jogador2, estrelas_j1, estrelas_j2, porc_j1, porc_j2, tempo_j1, tempo_j2) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                 (rodada, j1, j2, e1, e2, p1, p2, t1, t2))
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

menu = st.sidebar.radio("Navegação", ["Classificação", "Rodadas", "Cadastrar Resultados", "Gerenciar Jogadores"])

# ---------------------------
# CLASSIFICAÇÃO
# ---------------------------
if menu == "Classificação":
    st.subheader("📊 Tabela de Classificação")

    df = get_jogadores(conn)

    if not df.empty:
        df["Posição"] = df["vitorias"].rank(method="dense", ascending=False).astype(int)
        df = df.sort_values(by=["vitorias", "estrelas_ataque", "estrelas_defesa", "porc_ataque", "porc_defesa", "tempo_ataque"], 
                            ascending=[False, False, True, False, True, True])
        st.dataframe(df[["Posição", "nome", "vitorias", "estrelas_ataque", "estrelas_defesa", "porc_ataque", "porc_defesa", "tempo_ataque", "tempo_defesa"]],
                     use_container_width=True)

# ---------------------------
# RODADAS
# ---------------------------
elif menu == "Rodadas":
    st.subheader("📅 Rodadas")

    rodadas = get_rodadas(conn)
    if rodadas.empty:
        st.info("Nenhum confronto registrado ainda.")
    else:
        st.dataframe(rodadas, use_container_width=True)

# ---------------------------
# CADASTRAR RESULTADOS
# ---------------------------
elif menu == "Cadastrar Resultados":
    st.subheader("✍️ Registrar Resultado")

    jogadores = [row[0] for row in conn.execute("SELECT nome FROM jogadores").fetchall()]

    rodada = st.number_input("Rodada", min_value=1, step=1)
    j1 = st.selectbox("Jogador 1", jogadores)
    j2 = st.selectbox("Jogador 2", [j for j in jogadores if j != j1])

    e1 = st.number_input("Estrelas Jogador 1", 0, 3, step=1)
    e2 = st.number_input("Estrelas Jogador 2", 0, 3, step=1)
    p1 = st.number_input("Porcentagem Jogador 1", 0.0, 100.0, step=0.1)
    p2 = st.number_input("Porcentagem Jogador 2", 0.0, 100.0, step=0.1)
    t1 = st.number_input("Tempo Jogador 1 (segundos)", 0.0, 300.0, step=1.0)
    t2 = st.number_input("Tempo Jogador 2 (segundos)", 0.0, 300.0, step=1.0)

    if st.button("Salvar Resultado"):
        registrar_resultado(conn, rodada, j1, j2, e1, e2, p1, p2, t1, t2)
        st.success("Resultado registrado com sucesso ✅")

# ---------------------------
# GERENCIAR JOGADORES
# ---------------------------
elif menu == "Gerenciar Jogadores":
    st.subheader("👥 Jogadores")

    nome = st.text_input("Adicionar jogador")
    if st.button("Adicionar"):
        adicionar_jogador(conn, nome)
        st.success(f"Jogador {nome} adicionado ✅")

    df = get_jogadores(conn)
    if not df.empty:
        st.dataframe(df, use_container_width=True)
