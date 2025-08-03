from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = 'sua-chave-secreta-aqui'
app.permanent_session_lifetime = timedelta(minutes=15)

# Criação do banco
def init_db():
    conn = sqlite3.connect('validade.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            descricao TEXT,
            quantidade INTEGER,
            lote TEXT,
            vencimento DATE,
            foto TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Conexão
def get_db_connection():
    conn = sqlite3.connect('validade.db')
    conn.row_factory = sqlite3.Row
    return conn

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == '1234':
            session.clear()
            session.permanent = False  # a sessão expira ao fechar o navegador
            session['usuario'] = 'admin'
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro='Senha incorreta.')
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Página inicial com contagem por categoria
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    produtos_raw = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()

    hoje = datetime.today().date()
    produtos = []
    aviso = []

    contagem_verde = 0
    contagem_amarelo = 0
    contagem_vermelho = 0

    for p in produtos_raw:
        venc = datetime.strptime(p['vencimento'], '%Y-%m-%d').date()
        dias_restantes = (venc - hoje).days

        produto = {
            'id': p['id'],
            'codigo': p['codigo'],
            'descricao': p['descricao'],
            'quantidade': p['quantidade'],
            'lote': p['lote'],
            'vencimento': venc,
            'foto': p['foto'],
            'dias_restantes': dias_restantes
        }
        produtos.append(produto)

        if 0 <= dias_restantes <= 30:
            aviso.append(f"⚠️ Atenção! Produto {p['descricao']} (cód: {p['codigo']}) vence em {dias_restantes} dias!")

        # Contagem das categorias
        if dias_restantes >= 366:
            contagem_verde += 1
        elif 91 <= dias_restantes < 366:
            contagem_amarelo += 1
        else:
            contagem_vermelho += 1

    return render_template('index.html', 
                           produtos=produtos, 
                           aviso=aviso,
                           contagem_verde=contagem_verde,
                           contagem_amarelo=contagem_amarelo,
                           contagem_vermelho=contagem_vermelho)

# Cadastro
@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        codigo = request.form['codigo']
        descricao = request.form['descricao']
        quantidade = request.form['quantidade']
        lote = request.form['lote']
        vencimento = request.form['vencimento']

        foto = request.files['foto']
        filename = ''
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO produtos (codigo, descricao, quantidade, lote, vencimento, foto)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (codigo, descricao, quantidade, lote, vencimento, filename))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('cadastrar.html')

# Editar produto
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()

    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        codigo = request.form['codigo']
        descricao = request.form['descricao']
        quantidade = request.form['quantidade']
        lote = request.form['lote']
        vencimento = request.form['vencimento']

        foto = request.files['foto']
        filename = produto['foto']
        if foto and foto.filename:
            filename = secure_filename(foto.filename)
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn.execute('''
            UPDATE produtos
            SET codigo = ?, descricao = ?, quantidade = ?, lote = ?, vencimento = ?, foto = ?
            WHERE id = ?
        ''', (codigo, descricao, quantidade, lote, vencimento, filename, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('editar.html', produto=produto)

# Excluir produto
@app.route('/excluir/<int:id>', methods=['GET', 'POST'])
def excluir(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()

    if not produto:
        return 'Produto não encontrado', 404

    if request.method == 'POST':
        conn.execute('DELETE FROM produtos WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('confirmar_exclusao.html', produto=produto)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
