from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from urllib.parse import urlparse
from datetime import datetime, date
import os
import psycopg2
import psycopg2.extras
import sqlite3

app = Flask(__name__)
app.secret_key = 'sua-chave-super-secreta'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        result = urlparse(DATABASE_URL)
        return psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    else:
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
        if DATABASE_URL:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, args)
                if commit:
                    conn.commit()
                if query.strip().upper().startswith("SELECT"):
                    result = cur.fetchall()
                    return result[0] if (result and one) else result
        else:
            query = query.replace('%s', '?')
            cur = conn.cursor()
            cur.execute(query, args)
            if commit:
                conn.commit()
            if query.strip().upper().startswith("SELECT"):
                rows = cur.fetchall()
                rows_dict = [dict(row) for row in rows]
                return rows_dict[0] if (rows_dict and one) else rows_dict
    finally:
        conn.close()

@app.route("/")
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produtos_raw = query_db("SELECT * FROM produtos ORDER BY vencimento ASC")
    hoje = date.today()
    produtos = []
    aviso = []
    contagem_verde = contagem_amarelo = contagem_vermelho = 0

    for p in produtos_raw:
        venc = p['vencimento']
        if isinstance(venc, str):
            try:
                venc = datetime.strptime(venc, "%Y-%m-%d").date()
            except ValueError:
                venc = hoje  # trata erro de data inválida

        dias_restantes = (venc - hoje).days
        produto = dict(p)
        produto['vencimento'] = venc
        produto['dias_restantes'] = dias_restantes
        produto['foto_url'] = f"/static/uploads/{p['foto']}" if p.get('foto') else None
        produtos.append(produto)

        # ALERTAS
        if 0 <= dias_restantes <= 30:
            aviso.append(f"⚠️ Produto {p['descricao']} (cód: {p['codigo']}) vence em {dias_restantes} dias!")
        elif dias_restantes < 0:
            aviso.append(f"❌ Produto {p['descricao']} (cód: {p['codigo']}) está vencido!")

        # CONTAGEM POR COR
        if dias_restantes > 365:
            contagem_verde += 1
        elif 91 <= dias_restantes <= 365:
            contagem_amarelo += 1
        else:  # dias <= 90 (inclui vencidos)
            contagem_vermelho += 1

    return render_template("index.html",
                           produtos=produtos,
                           aviso=aviso,
                           contagem_verde=contagem_verde,
                           contagem_amarelo=contagem_amarelo,
                           contagem_vermelho=contagem_vermelho)

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        codigo = request.form.get("codigo")
        descricao = request.form.get("descricao")
        quantidade = request.form.get("quantidade", 0)
        lote = request.form.get("lote")
        vencimento = request.form.get("vencimento")
        foto = request.files.get("foto")

        filename = ""
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        query_db("""
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (codigo, descricao, quantidade, lote, vencimento, filename), commit=True)

        return redirect(url_for('index'))

    return render_template("cadastrar.html")

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db("SELECT * FROM produtos WHERE id = %s", (id,), one=True)
    if not produto:
        return "Produto não encontrado", 404

    if request.method == "POST":
        codigo = request.form.get("codigo")
        descricao = request.form.get("descricao")
        quantidade = request.form.get("quantidade")
        lote = request.form.get("lote")
        vencimento = request.form.get("vencimento")
        foto = request.files.get("foto")

        try:
            quantidade = int(quantidade)
        except:
            quantidade = 0

        try:
            vencimento = datetime.strptime(vencimento, "%Y-%m-%d").date()
        except:
            vencimento = None

        filename = produto['foto']
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            foto.save(foto_path)

        query_db("""
            UPDATE produtos SET codigo=%s, descricao=%s, quantidade=%s, lote=%s, vencimento=%s, foto=%s
            WHERE id=%s
        """, (codigo, descricao, quantidade, lote, vencimento, filename, id), commit=True)

        return redirect(url_for('index'))

    return render_template("editar.html", produto=produto)

@app.route("/confirmar_exclusao/<int:id>", methods=["GET", "POST"])
def confirmar_exclusao(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db("SELECT * FROM produtos WHERE id = %s", (id,), one=True)
    if not produto:
        return "Produto não encontrado", 404

    if request.method == "POST":
        query_db("DELETE FROM produtos WHERE id = %s", (id,), commit=True)
        return redirect(url_for('index'))

    return render_template("confirmar_exclusao.html", produto=produto)

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    data = request.get_json()
    return jsonify({"valido": data.get("senha") == "operador456"})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("senha") == "1234":
            session.clear()
            session["usuario"] = "admin"
            return redirect(url_for("index"))
        return render_template("login.html", erro="Senha incorreta.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
