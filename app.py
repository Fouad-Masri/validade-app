from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from werkzeug.utils import secure_filename
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import cloudinary
import cloudinary.uploader

# === Configuração da aplicação Flask ===
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave-padrao")

# === Configuração do Cloudinary ===
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# === Banco de dados PostgreSQL ===
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("A variável de ambiente DATABASE_URL não está definida.")

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

def query_db(query, args=(), one=False, commit=False):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, args)
            if commit:
                conn.commit()
                return
            result = cur.fetchall()
            return result[0] if one else result

# === Rotas ===

@app.route("/verificar_senha", methods=["POST"])
def verificar_senha():
    data = request.get_json()
    senha = data.get("senha")
    return jsonify({"valido": senha == "operador456"})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == 'admin123':
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

    produtos_raw = query_db("SELECT * FROM produtos ORDER BY vencimento ASC")
    produtos = []
    hoje = datetime.today().date()
    aviso = []
    verde = amarelo = vermelho = 0

    for p in produtos_raw:
        p_dict = dict(p)
        venc = p_dict.get('vencimento')
        if isinstance(venc, str):
            try:
                venc = datetime.strptime(venc, '%Y-%m-%d').date()
            except:
                venc = hoje
        elif venc is None:
            venc = hoje

        dias_restantes = (venc - hoje).days
        p_dict['dias_restantes'] = dias_restantes
        produtos.append(p_dict)

        if 0 <= dias_restantes <= 30:
            aviso.append(f"⚠️ {p_dict['descricao']} (cód: {p_dict['codigo']}) vence em {dias_restantes} dias!")
        elif dias_restantes < 0:
            aviso.append(f"❌ {p_dict['descricao']} (cód: {p_dict['codigo']}) está vencido!")

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

        foto_url = ''
        try:
            if foto and foto.filename:
                upload_result = cloudinary.uploader.upload(foto)
                foto_url = upload_result.get("secure_url", "")
        except Exception as e:
            print("Erro no upload da foto:", e)

        query_db('''
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (codigo, descricao, quantidade, lote, vencimento, foto_url), commit=True)

        return redirect(url_for('index'))

    return render_template('cadastrar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s', (id,), one=True)
    if not produto:
        abort(404, description="Produto não encontrado")

    if request.method == 'POST':
        try:
            codigo = request.form['codigo'].strip()
            descricao = request.form['descricao'].strip()
            quantidade = int(request.form['quantidade'])
            lote = request.form['lote'].strip()
            vencimento = request.form['vencimento']
            foto = request.files.get('foto')

            foto_url = produto['foto']
            if foto and foto.filename:
                upload_result = cloudinary.uploader.upload(foto)
                foto_url = upload_result.get("secure_url", foto_url)

            query_db('''
                UPDATE produtos SET codigo=%s, descricao=%s, quantidade=%s, lote=%s,
                vencimento=%s, foto=%s WHERE id=%s
            ''', (codigo, descricao, quantidade, lote, vencimento, foto_url, id), commit=True)

            return redirect(url_for('index'))

        except Exception as e:
            print(f"Erro ao editar produto ID {id}: {e}")
            return render_template('editar.html', produto=produto, erro="Erro ao salvar alterações.")

    return render_template('editar.html', produto=produto)

@app.route('/excluir/<int:id>', methods=['GET', 'POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    produto = query_db('SELECT * FROM produtos WHERE id = %s', (id,), one=True)
    if not produto:
        abort(404, description="Produto não encontrado")

    if request.method == 'POST':
        query_db('DELETE FROM produtos WHERE id = %s', (id,), commit=True)
        return redirect(url_for('index'))

    return render_template('confirmar_exclusao.html', produto=produto)

if __name__ == '__main__':
    try:
        init_db()
    except Exception as e:
        print("Erro ao inicializar o banco:", e)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
