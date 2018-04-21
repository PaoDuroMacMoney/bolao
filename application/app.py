# coding: latin-1

import sys
import os

sys.path.append(os.path.abspath('../../bolao'))

import pymongo
from flask import Flask, flash
from flask import request
from flask import render_template, redirect, url_for, session
from operator import itemgetter
from bson import ObjectId

from application.db_config import get_db_client

from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from application.oauth import OAuthSignIn

client = get_db_client()

db = client.dev
tbl_jogo = db.jogo
tbl_selecao = db.selecao
tbl_usuario = db.usuario
tbl_bolao = db.bolao
tbl_aposta = db.aposta
tbl_palpite = db.palpite
tbl_pontuacao = db.pontuacao

app = Flask(__name__)
app.secret_key = "super secret key"
app.config.from_object(__name__)

SECRET_KEY = 'secret'

app.config['OAUTH_CREDENTIALS'] = {
    'facebook': {
        'id': '447729492345224',
        'secret': 'fd9016e1279fcc825736eb7c4ed3bd88'
    },
    'google': {
            'id': '760126712590-qaul287sj1bkqr46hubnmh9udvq3rrn6.apps.googleusercontent.com',
            'secret': 'RK0abVTO0Q5CZliyiuB-nQxM'
        }
}

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Voc� precisa estar logado para acessar esta p�gina!'
login_manager.init_app(app)

grupos = {}
todos_jogos = []

@login_manager.user_loader
def load_user(user_id):
    return Usuario(user_id)

@app.route('/')
def inicio():
    return intro()


@app.route('/novo_bolao', methods=['GET', 'POST'])
@login_required
def novo_bolao():
    if request.method == 'GET':
        return render_template('novo_bolao.html')
    else:
        if not valida_informacoes_bolao(request.form):
            return render_template('novo_bolao.html')
        cria_bolao(request.form)
        return lista_bolao()


@app.route('/intro')
def intro():
    return render_template('intro.html')


@app.route('/lista_bolao')
def lista_bolao():
    boloes = monta_dto_boloes()
    return render_template('lista_bolao.html', lista_boloes=boloes)


@app.route('/<bolao>/nova_aposta', methods=['GET', 'POST'])
@login_required
def nova_aposta(bolao):
    grupos = monta_dto_grupos()
    if request.method == 'GET':
        return render_template('aposta.html', grupos=grupos, bolao=bolao)
    else:
        id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
        nome_aposta = request.form['inputNome']
        if not aposta_ja_existe(nome_aposta, id_bolao):
            id_aposta = insere_aposta(nome_aposta, id_bolao)
            insere_palpites(id_aposta, request.form)
            insere_pontuacoes(id_aposta)
            return ranking(bolao)
        else:
            flash('J� existe uma aposta para este bol�o com o nome [{}]. Escolha outro.'.format(nome_aposta))
            return render_template('nova_aposta.html', bolao=bolao, grupos=grupos)


@app.route('/<bolao>/descricao_bolao')
def descricao(bolao):
    bolao_selecionado = tbl_bolao.find_one({'nome': bolao})
    responsavel = tbl_usuario.find_one({'_id': bolao_selecionado['usuario']})
    return render_template('descricao_bolao.html', bolao=bolao, bolao_selecionado=bolao_selecionado, responsavel=responsavel)


@app.route('/<bolao>/ranking')
def ranking(bolao):
    lista_apostas = monta_dto_apostas(bolao)
    return render_template('ranking.html', bolao=bolao, lista_apostas=lista_apostas)


@app.route('/<bolao>/admin')
@login_required
def admin(bolao):
    if usuario_criou_o_bolao(bolao):
        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisi��o inv�lida, apenas usu�rio que criou o bol�o pode acessar sua �rea de Admin')
        return lista_bolao()


@app.route('/valida_nome_bolao', methods=['POST'])
def valida_nome_bolao():
    nome_bolao = request.form['nome_bolao']
    return valida_nome_bolao_ja_existe(nome_bolao)


@app.route('/<bolao>/valida_nome_aposta', methods=['POST'])
def valida_nome_aposta(bolao):
    nome_aposta = request.form['nome_aposta']
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']

    if aposta_ja_existe(nome_aposta, id_bolao):
        return '''Aposta com nome <Strong>{0}</Strong> j� existe para este bol�o, escolha outro.'''.format(nome_aposta)
    else:
        return ''


@app.route('/<bolao>/toggle_pago', methods=['POST'])
@login_required
def toggle_pago(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
        nome_aposta = request.form['nome_aposta']
        aposta = tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao})
        novo_pago = not aposta['pago']

        tbl_aposta.update_one({'nome': nome_aposta,
                               'bolao': id_bolao},
                              {"$set": {"pago": novo_pago}})

        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisi��o inv�lida, apenas usu�rio que criou o bol�o pode acessar sua �rea de Admin')
        return lista_bolao()


@app.route('/pago', methods=['GET', 'POST'])
def grade():
    if request.method == 'POST':
        return 'Form posted.'


@app.route('/<bolao>/remover_aposta', methods=['POST'])
@login_required
def remover_aposta(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
        nome_aposta = request.form['nome_aposta']
        id_aposta = tbl_aposta.find_one({"nome": nome_aposta, 'bolao': id_bolao})['_id']
        tbl_aposta.remove(id_aposta)
        lista_apostas = monta_dto_apostas(bolao)
        return render_template('admin.html', bolao=bolao, lista_apostas=lista_apostas)
    else:
        flash('Requisi��o inv�lida, apenas usu�rio que criou o bol�o pode acessar sua �rea de Admin')
        return lista_bolao()


@app.route('/<bolao>/remover_bolao', methods=['POST'])
@login_required
def remover_bolao(bolao):
    if usuario_criou_o_bolao(bolao):
        id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
        tbl_bolao.remove(id_bolao)
        return redirect(url_for('lista_bolao'))
    else:
        flash('Requisi��o inv�lida, apenas usu�rio que criou o bol�o pode acessar sua �rea de Admin')
        return lista_bolao()


@app.route('/<bolao>/palpite/<nome_aposta>')
def palpite(bolao, nome_aposta):
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    aposta = tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao})
    monta_dto_grupos()
    palpites = monta_palpites(aposta)
    pontuacoes = monta_pontuacoes(aposta)
    lista_jogos_ordem_tela = []
    placares = monta_placares(lista_jogos_ordem_tela)

    return render_template('palpites.html', bolao=bolao, jogos=lista_jogos_ordem_tela, palpites=palpites,
                           pontuacoes=pontuacoes, placares=placares, nome_aposta=nome_aposta)



@app.route('/login', methods=['GET', 'POST'])
def login():
    next_uri = request.args.get('next')
    if next_uri is None:
        next_uri = url_for('lista_bolao')
    session['next'] = next_uri
    return render_template('login.html')


@app.route('/logout')
def logout():
    next_uri = request.args.get('next')
    if next_uri is None:
        next_uri = url_for('intro')
    logout_user()
    return redirect(next_uri)

@app.route('/callback/<provider>')
def oauth_callback(provider):
    next_uri = session.get('next')
    if not next_uri:
        next_uri = url_for('lista_bolao')
    if not current_user.is_anonymous:
        return redirect(next_uri)
    oauth = OAuthSignIn.get_provider(provider)
    nome, email, primeiro_nome, sobrenome, foto, sexo = oauth.callback()
    if nome is None:
        flash('Falha na autentica��o.')
        return redirect(url_for('login'))
    usuario = Usuario(email)
    if usuario.is_anonymous():
        tbl_usuario.insert_one({'nome': nome,
                                'email': email,
                                'primeiro_nome': primeiro_nome,
                                'sobrenome': sobrenome,
                                'foto': foto,
                                'sexo': sexo[0]})
        usuario = Usuario(email)
    login_user(usuario, remember=True)
    return redirect(next_uri)


@app.route('/authorize/<provider>')
def oauth_authorize(provider):
    print(session)
    next_uri = session.get('next')
    if not next_uri:
        next_uri = url_for('lista_bolao')
    if not current_user.is_anonymous:
        return redirect(next_uri)
    oauth = OAuthSignIn.get_provider(provider)
    return oauth.authorize()


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Erro no campo %s - %s" % (getattr(form, field).label.text, error))


def usuario_criou_o_bolao(nome_bolao):
    return tbl_bolao.find_one({'usuario': current_user.mongo_id, 'nome': nome_bolao}) is not None


def monta_placares(lista_jogos_ordem_tela):
    placares = {}
    lista_sem_resultados = []
    lista_com_resultados = []
    for jogo in todos_jogos:
        id_jogo = ObjectId(jogo['_id'])
        jogo_banco = tbl_jogo.find_one({'_id': id_jogo})
        lista = lista_sem_resultados if jogo_banco['gols_mandante'] is None else lista_com_resultados
        lista.append(jogo)
        gols_mandante = '-' if jogo_banco['gols_mandante'] is None else jogo_banco['gols_mandante']
        gols_visitante = '-' if jogo_banco['gols_visitante'] is None else jogo_banco['gols_visitante']
        placares[jogo['nome']] = '{} x {}'.format(gols_mandante, gols_visitante)

    lista_com_resultados.sort(key=itemgetter('date_time'), reverse=True)
    lista_sem_resultados.sort(key=itemgetter('date_time'), reverse=False)
    lista_com_resultados.extend(lista_sem_resultados)
    lista_jogos_ordem_tela.extend(lista_com_resultados)
    return placares


def monta_pontuacoes(aposta):
    pontuacoes = {}
    for jogo in todos_jogos:
        pontuacao_jogo = tbl_pontuacao.find_one({'aposta': aposta['_id'],
                                                 'jogo': jogo['_id']})
        pontuacoes[jogo['nome']] = pontuacao_jogo['pontos']
    return pontuacoes


def monta_palpites(aposta):
    palpites = {}
    for jogo in todos_jogos:
        palpite_jogo = tbl_palpite.find_one({'aposta': aposta['_id'],
                                             'jogo': jogo['_id']})
        palpites[jogo['nome']] = '{} x {}'.format(palpite_jogo['gols_mandante'], palpite_jogo['gols_visitante'])
    return palpites


def cria_bolao(form):
    tbl_bolao.insert_one({'nome': form['inputNome'],
                          'usuario': current_user.mongo_id,
                          'valor': int(form['inputValor']),
                          'premiacao': form['inputPremiacao'],
                          'descricao': form['inputDescricao']})


def valida_nome_bolao_ja_existe(nome_bolao):
    if tbl_bolao.find_one({'nome': nome_bolao}) is not None:
        return '''Nome [{0}] j� foi escolhido para um bol�o, escolha outro.'''.format(nome_bolao)
    else:
        return ''


def valida_campo_preenchido(valor_campo, nome_campo):
    if valor_campo == '':
        return '''Campo [{0}] � de preenchimento obrigat�rio.'''.format(nome_campo)
    else:
        return ''


def valida_campo_numerico(valor_campo):
    try:
        inteiro = int(valor_campo.strip())
        if inteiro < 0:
            return 'O campo Valor n�o pode ser negativo'
        return ''
    except ValueError:
        return 'O campo Valor precisa ser um n�mero'


def valida_senhas_iguais(senha1, senha2):
    if senha1 != senha2:
        return 'Senhas n�o conferem.'
    return ''


def valida_informacoes_bolao(form):
    algum_erro = False
    validacoes = [valida_nome_bolao_ja_existe(form['inputNome']),
                  valida_campo_preenchido(form['inputValor'], 'Valor'),
                  valida_campo_numerico(form['inputValor']),
                  valida_campo_preenchido(form['inputPremiacao'], 'Premia��o')]
    for erro in validacoes:
        if erro > '':
            algum_erro = True
            flash(erro)
    return not algum_erro


def totaliza_pontuacao(id_aposta, campo):
    total = 0
    for pontuacao in tbl_pontuacao.find({'aposta': id_aposta}):
        total = total + pontuacao[campo]
    return total


def monta_dto_apostas(bolao):
    lista_retorno = []
    id_bolao = tbl_bolao.find_one({'nome': bolao})['_id']
    for aposta in tbl_aposta.find({'bolao': id_bolao}):
        pontuacao_aposta = totaliza_pontuacao(aposta['_id'], 'pontos')
        placares_exatos_aposta = totaliza_pontuacao(aposta['_id'], 'placar_exato')
        vencedor_ou_empate_aposta = totaliza_pontuacao(aposta['_id'], 'vencedor_ou_empate')
        gols_de_um_time_aposta = totaliza_pontuacao(aposta['_id'], 'gols_de_um_time')
        usuario = tbl_usuario.find_one({'_id': aposta['usuario']})
        lista_retorno.append({"nome": aposta["nome"],
                              "pontuacao": pontuacao_aposta,
                              "placar_exato": placares_exatos_aposta,
                              "vencedor_ou_empate": vencedor_ou_empate_aposta,
                              "gols_de_um_time": gols_de_um_time_aposta,
                              "pago": aposta["pago"],
                              "foto": usuario['foto']})
    return sorted(lista_retorno, key=itemgetter('pontuacao', 'placar_exato', 'vencedor_ou_empate', 'gols_de_um_time'),
                  reverse=True)


def insere_aposta(nome, id_bolao):
    return tbl_aposta.insert_one({'nome': nome,
                                  'usuario': current_user.mongo_id,
                                  'bolao': id_bolao,
                                  'pago': False,
                                  }).inserted_id


def insere_pontuacoes(id_aposta):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        tbl_pontuacao.insert_one({'aposta': id_aposta,
                                  'jogo': id_jogo,
                                  'pontos': 0,
                                  'placar_exato': 0,
                                  'vencedor_ou_empate': 0,
                                  'gols_de_um_time': 0})


def insere_palpites(id_aposta, form):
    for jogo in todos_jogos:
        id_jogo = jogo["_id"]
        id_mandante_form = 'm{0}'.format(str(id_jogo))
        id_visitante_form = 'v{0}'.format(str(id_jogo))
        tbl_palpite.insert_one({'aposta': id_aposta,
                                'jogo': id_jogo,
                                'gols_mandante': int(form[id_mandante_form]),
                                'gols_visitante': int(form[id_visitante_form])})


def aposta_ja_existe(nome_aposta, id_bolao):
    return tbl_aposta.find_one({'nome': nome_aposta, 'bolao': id_bolao}) is not None


def monta_dto_jogo(jogo):
    mandante = tbl_selecao.find_one({'_id': jogo["mandante"]})
    visitante = tbl_selecao.find_one({'_id': jogo["visitante"]})
    return {"_id": jogo["_id"],
            "nome": jogo["nome"],
            "escudo_mandante": mandante["escudo"],
            "escudo_visitante": visitante["escudo"],
            "nome_mandante": mandante["nome"],
            "nome_visitante": visitante["nome"],
            "id_input_mandante": 'm{0}'.format(str(jogo["_id"])),
            "id_input_visitante": 'v{0}'.format(str(jogo["_id"])),
            "data": jogo["data"].strftime('%d/%m %H:%M'),
            "date_time": jogo["data"],
            "local": jogo["local"]}


def inclui_jogo_na_lista_rodadas(lista_rodadas, jogo):
    rodada_do_jogo = jogo["rodada"]

    existe_rodada_na_lista = False
    for rodada in lista_rodadas:
        if rodada["numero"] == rodada_do_jogo:
            existe_rodada_na_lista = True
            jogos = rodada["jogos"]
            break

    if not existe_rodada_na_lista:
        jogos = []
        lista_rodadas.append({"numero": rodada_do_jogo,
                              "nome": '{0}� Rodada'.format(rodada_do_jogo),
                              "jogos": jogos})
    dto_jogo = monta_dto_jogo(jogo)
    jogos.append(dto_jogo)
    todos_jogos.append(dto_jogo)


def monta_dto_boloes():
    dto_boloes = []
    for bolao in tbl_bolao.find():
        dto_boloes.append({'nome': bolao['nome']})
    return dto_boloes


def monta_dto_grupos():
    if not grupos:
        # for jogo in tbl_jogo.find({'grupo': 'Grupo A', 'rodada': 1}):  # para testar com menos jogos
        for jogo in tbl_jogo.find().sort(
                [("grupo", pymongo.ASCENDING), ("rodada", pymongo.ASCENDING), ("data", pymongo.ASCENDING)]):
            nome_grupo = jogo["grupo"]
            if nome_grupo not in grupos.keys():
                grupos[nome_grupo] = {"nome": nome_grupo,
                                      "rodadas": []}

            rodadas = grupos[nome_grupo]["rodadas"]
            inclui_jogo_na_lista_rodadas(rodadas, jogo)
    return [grupos[x] for x in sorted(grupos)]


class Usuario:
    def __init__(self, email):
        self.usuario_banco = tbl_usuario.find_one({'email': email})
        if self.usuario_banco is not None:
            self.email = str(self.usuario_banco['email'])
            self.nome = str(self.usuario_banco['nome'])
            self.foto = str(self.usuario_banco['foto'])
            self.primeiro_nome = str(self.usuario_banco['primeiro_nome'])
            self.sobrenome = str(self.usuario_banco['sobrenome'])
            self.sexo = str(self.usuario_banco['sexo'])
            self.mongo_id = self.usuario_banco['_id']

    def is_authenticated(self):
        return self.usuario_banco is not None

    def is_active(self):
        return self.usuario_banco is not None

    def is_anonymous(self):
        return self.usuario_banco is None

    def get_id(self):
        return self.email

    def eh_criador_do_bolao(self, nome_bolao):
        bolao = tbl_bolao.find_one({'nome': nome_bolao})
        return self.is_authenticated and self.mongo_id == bolao['usuario']
