from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import os
import psycopg2
import psycopg2.extras
import sqlite3
from urllib.parse import urlparse
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = 'sua-chave-secreta-aqui'  # Troque para uma chave secreta forte em produção
app.permanent_session_lifetime = timedelta(minutes=15)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        # PostgreSQL
        result = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=result.path[1:],  # remove a barra inicial "/"
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        return conn
    else:
        # SQLite
        conn = sqlite3.connect('validade.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db_connection()
    with conn:
        cur = conn.cursor()
        if DATABASE_URL:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS produtos (
                    id SERIAL PRIMARY KEY,
                    codigo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    quantidade INTEGER NOT NULL,
                    lote TEXT,
                    vencimento DATE NOT NULL,
                    foto TEXT
                )
            ''')
        else:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS produtos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    quantidade INTEGER NOT NULL,
                    lote TEXT,
                    vencimento TEXT NOT NULL,
                    foto TEXT
                )
            ''')
        cur.close()
    conn.close()

def query_db(query, args=(), one=False, commit=False):
    conn = get_db_connection()
    try:
        with conn:
            if DATABASE_URL:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    # Ajustar placeholders para PostgreSQL (%s)
                    cur.execute(query, args)
                    if commit:
                        conn.commit()
                    if query.strip().upper().startswith("SELECT"):
                        result = cur.fetchall()
                        return (result[0] if result else None) if one else result
            else:
                # SQLite usa ?
                query_sqlite = query.replace('%s', '?')
                cur = conn.cursor()
                cur.execute(query_sqlite, args)
                if commit:
                    conn.commit()
                if query_sqlite.strip().upper().startswith("SELECT"):
                    rows = cur.fetchall()
                    # Converte sqlite3.Row para dict para facilitar template
                    rows_dict = [dict(row) for row in rows]
                    cur.close()
                    return (rows_dict[0] if rows_dict else None) if one else rows_dict
                cur.close()
                return None
    finally:
        conn.close()

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    data = request.get_json()
    senha = data.get("senha")
    if senha == "operador456":
        return jsonify({"valido": True})
    else:
        return jsonify({"valido": False})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == '1234':
            session.clear()
            session.permanent = False
            session['usuario'] = 'admin'
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro='Senha incorreta.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produtos_raw = query_db('SELECT * FROM produtos ORDER BY vencimento ASC')

    hoje = datetime.today().date()
    produtos = []
    aviso = []
    contagem_verde = contagem_amarelo = contagem_vermelho = 0

    for p in produtos_raw:
        venc = p['vencimento']
        # Se local SQLite, converte string para date
        if not DATABASE_URL:
            venc = datetime.strptime(venc, '%Y-%m-%d').date()
        else:
            # No PostgreSQL, já é date
            venc = venc

        dias_restantes = (venc - hoje).days

        produto = dict(p)
        produto['vencimento'] = venc
        produto['dias_restantes'] = dias_restantes
        produtos.append(produto)

        if 0 <= dias_restantes <= 30:
            aviso.append(f"⚠️ Atenção! Produto {p['descricao']} (cód: {p['codigo']}) vence em {dias_restantes} dias!")
        elif dias_restantes < 0:
            aviso.append(f"❌ Produto {p['descricao']} (cód: {p['codigo']}) está vencido!")

        if dias_restantes >= 366:
            contagem_verde += 1
        elif 91 <= dias_restantes < 366:
            contagem_amarelo += 1
        else:
            contagem_vermelho += 1

    return render_template('index.html', produtos=produtos, aviso=aviso,
                           contagem_verde=contagem_verde,
                           contagem_amarelo=contagem_amarelo,
                           contagem_vermelho=contagem_vermelho)

@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        quantidade = request.form.get('quantidade', '0')
        lote = request.form.get('lote', '').strip()
        vencimento = request.form.get('vencimento')
        foto = request.files.get('foto')

        if not codigo or not descricao or not vencimento:
            return redirect(url_for('cadastrar'))

        filename = ''
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        query_db('''
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''' if DATABASE_URL else '''
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (codigo, descricao, int(quantidade), lote, vencimento, filename), commit=True)

        return redirect(url_for('index'))

    return render_template('cadastrar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s' if DATABASE_URL else 'SELECT * FROM produtos WHERE id = ?', (id,), one=True)

    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        quantidade = request.form.get('quantidade', '0')
        lote = request.form.get('lote', '').strip()
        vencimento = request.form.get('vencimento')
        foto = request.files.get('foto')

        filename = produto['foto']
        if foto and foto.filename != '':
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        query_db('''
            UPDATE produtos SET codigo=%s, descricao=%s, quantidade=%s, lote=%s, vencimento=%s, foto=%s WHERE id=%s
        ''' if DATABASE_URL else '''
            UPDATE produtos SET codigo=?, descricao=?, quantidade=?, lote=?, vencimento=?, foto=? WHERE id=?
        ''', (codigo, descricao, int(quantidade), lote, vencimento, filename, id), commit=True)

        return redirect(url_for('index'))

    return render_template('editar.html', produto=produto)

@app.route('/excluir/<int:id>', methods=['GET', 'POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s' if DATABASE_URL else 'SELECT * FROM produtos WHERE id = ?', (id,), one=True)

    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        query_db('DELETE FROM produtos WHERE id = %s' if DATABASE_URL else 'DELETE FROM produtos WHERE id = ?', (id,), commit=True)
        return redirect(url_for('index'))

    return render_template('confirmar_exclusao.html', produto=produto)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
