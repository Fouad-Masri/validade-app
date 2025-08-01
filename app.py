from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
import os
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

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

# Conexão com acesso por nome de coluna
def get_db_connection():
    conn = sqlite3.connect('validade.db')
    conn.row_factory = sqlite3.Row
    return conn

# Página inicial
@app.route('/')
def index():
    conn = get_db_connection()
    produtos_raw = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()

    hoje = datetime.today().date()
    produtos = []
    aviso = []

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

    return render_template('index.html', produtos=produtos, aviso=aviso)

# Cadastro
@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
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

