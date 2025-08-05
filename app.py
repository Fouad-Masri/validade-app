from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

# === Configuração da aplicação Flask ===
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave-padrao")
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.permanent_session_lifetime = timedelta(minutes=15)

# === URL do banco de dados PostgreSQL (Render) ===
DATABASE_URL = "postgres://validade_user:DEAV3HTY1ss2NI2vdgojU8cur2fnEjxP@dpg-d28hpiqli9vc73am77bg-a.render.com:5432/validade_db"

# === Função para conectar ao banco ===
def get_db_connection():
    try:
        return psycopg2.connect(
            dsn=DATABASE_URL,
            sslmode='require',
            cursor_factory=psycopg2.extras.DictCursor
        )
    except Exception as e:
        print("Erro ao conectar ao banco:", e)
        raise

# === Inicializar banco com a tabela produtos ===
def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
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

# === Função utilitária para executar queries ===
def query_db(query, args=(), one=False, commit=False):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, args)
            if commit:
                conn.commit()
                return
            result = cur.fetchall()
            return result[0] if one else result

# === Rota para verificação de senha (uso via JS) ===
@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    data = request.get_json()
    senha = data.get("senha")
    return jsonify({"valido": senha == "operador456"})

# === Login ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == '1234':
            session['usuario'] = 'admin'
            return redirect(url_for('index'))
        return render_template('login.html', erro="Senha incorreta.")
    return render_template('login.html')

# === Logout ===
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# === Página principal ===
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
        if isinstance(venc, str):
            venc = datetime.strptime(venc, '%Y-%m-%d').date()
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

# === Cadastrar produto ===
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

# === Editar produto ===
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

# === Excluir produto ===
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

# === Iniciar aplicação ===
if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print("Erro ao inicializar o banco:", e)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
