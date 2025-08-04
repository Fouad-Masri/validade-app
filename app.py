from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import os
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = 'sua-chave-secreta-aqui'
app.permanent_session_lifetime = timedelta(minutes=15)

# URL do banco de dados do Render com SSL
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port,
        sslmode='require',
        cursor_factory=psycopg2.extras.DictCursor
    )

def init_db():
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
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
            conn.commit()
    finally:
        conn.close()

def query_db(query, args=(), one=False, commit=False):
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(query, args)
            if commit:
                conn.commit()
            if query.strip().upper().startswith("SELECT"):
                results = cur.fetchall()
                return results[0] if one else results
    finally:
        conn.close()

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    data = request.get_json()
    senha = data.get("senha")
    return jsonify({"valido": senha == "operador456"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == '1234':
            session['usuario'] = 'admin'
            return redirect(url_for('index'))
        return render_template('login.html', erro="Senha incorreta.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produtos = query_db("SELECT * FROM produtos ORDER BY vencimento ASC")
    hoje = datetime.today().date()
    aviso = []
    verde = amarelo = vermelho = 0

    for p in produtos:
        venc = p['vencimento']
        dias_restantes = (venc - hoje).days
        p['dias_restantes'] = dias_restantes
        if 0 <= dias_restantes <= 30:
            aviso.append(f"⚠️ {p['descricao']} (cód: {p['codigo']}) vence em {dias_restantes} dias!")
        elif dias_restantes < 0:
            aviso.append(f"❌ {p['descricao']} (cód: {p['codigo']}) está vencido!")

        if dias_restantes >= 366:
            verde += 1
        elif 91 <= dias_restantes < 366:
            amarelo += 1
        else:
            vermelho += 1

    return render_template('index.html', produtos=produtos, aviso=aviso,
                           contagem_verde=verde,
                           contagem_amarelo=amarelo,
                           contagem_vermelho=vermelho)

@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        codigo = request.form['codigo'].strip()
        descricao = request.form['descricao'].strip()
        quantidade = int(request.form['quantidade'])
        lote = request.form['lote'].strip()
        vencimento = request.form['vencimento']
        foto = request.files.get('foto')

        filename = ''
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        query_db('''
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (codigo, descricao, quantidade, lote, vencimento, filename), commit=True)

        return redirect(url_for('index'))

    return render_template('cadastrar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s', (id,), one=True)
    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        codigo = request.form['codigo'].strip()
        descricao = request.form['descricao'].strip()
        quantidade = int(request.form['quantidade'])
        lote = request.form['lote'].strip()
        vencimento = request.form['vencimento']
        foto = request.files.get('foto')

        filename = produto['foto']
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        query_db('''
            UPDATE produtos SET codigo=%s, descricao=%s, quantidade=%s, lote=%s,
            vencimento=%s, foto=%s WHERE id=%s
        ''', (codigo, descricao, quantidade, lote, vencimento, filename, id), commit=True)

        return redirect(url_for('index'))

    return render_template('editar.html', produto=produto)

@app.route('/excluir/<int:id>', methods=['GET', 'POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s', (id,), one=True)
    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        query_db('DELETE FROM produtos WHERE id = %s', (id,), commit=True)
        return redirect(url_for('index'))

    return render_template('confirmar_exclusao.html', produto=produto)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
