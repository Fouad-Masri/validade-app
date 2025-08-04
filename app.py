from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessions'

# Conexão com PostgreSQL no Render
DATABASE_URL = os.environ.get("DATABASE_URL") or "postgresql://validade_user:senhaforte123@dpg-xxxx.render.com:5432/validade_db"
conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cursor = conn.cursor()

# Inicializa as tabelas, se não existirem
def inicializar_banco():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            senha TEXT NOT NULL
        );
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id SERIAL PRIMARY KEY,
            codigo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            lote TEXT NOT NULL,
            vencimento DATE NOT NULL
        );
    ''')
    conn.commit()

    # Cria o usuário admin se não existir
    cursor.execute("SELECT * FROM usuarios WHERE nome = %s", ('admin',))
    if not cursor.fetchone():
        senha_criptografada = generate_password_hash('admin123')
        cursor.execute("INSERT INTO usuarios (nome, senha) VALUES (%s, %s)", ('admin', senha_criptografada))
        conn.commit()

inicializar_banco()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome']
        senha = request.form['senha']
        cursor.execute("SELECT * FROM usuarios WHERE nome = %s", (nome,))
        usuario = cursor.fetchone()
        if usuario and check_password_hash(usuario['senha'], senha):
            session['usuario'] = nome
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha incorretos", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/index')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM produtos ORDER BY vencimento ASC")
    produtos = cursor.fetchall()

    hoje = datetime.today().date()
    vencendo_em_30_dias = [p for p in produtos if (p['vencimento'] - hoje).days <= 30]

    return render_template('index.html', produtos=produtos, vencendo_em_30_dias=vencendo_em_30_dias, usuario=session['usuario'])

@app.route('/cadastrar_produto', methods=['GET', 'POST'])
def cadastrar_produto():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        codigo = request.form['codigo']
        descricao = request.form['descricao']
        quantidade = int(request.form['quantidade'])
        lote = request.form['lote']
        vencimento = request.form['vencimento']

        cursor.execute("""
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento)
            VALUES (%s, %s, %s, %s, %s)
        """, (codigo, descricao, quantidade, lote, vencimento))
        conn.commit()
        return redirect(url_for('index'))

    return render_template('cadastrar_produto.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM produtos WHERE id = %s", (id,))
    produto = cursor.fetchone()

    if request.method == 'POST':
        descricao = request.form['descricao']
        quantidade = int(request.form['quantidade'])
        lote = request.form['lote']
        vencimento = request.form['vencimento']

        cursor.execute("""
            UPDATE produtos SET descricao = %s, quantidade = %s, lote = %s, vencimento = %s WHERE id = %s
        """, (descricao, quantidade, lote, vencimento, id))
        conn.commit()
        return redirect(url_for('index'))

    return render_template('editar.html', produto=produto)

@app.route('/excluir/<int:id>', methods=['GET', 'POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM produtos WHERE id = %s", (id,))
    produto = cursor.fetchone()

    if request.method == 'POST':
        cursor.execute("DELETE FROM produtos WHERE id = %s", (id,))
        conn.commit()
        return redirect(url_for('index'))

    return render_template('confirmar_exclusao.html', produto=produto)

if __name__ == '__main__':
    app.run(debug=True)
