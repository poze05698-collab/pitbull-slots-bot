import telebot
from telebot import apihelper
from telebot.handler_backends import CancelUpdate, ContinueHandling
import logging
import time as _time
import socket
import threading

apihelper.ENABLE_MIDDLEWARE = True

# Telegram pode ficar alguns segundos lento sem que o processo esteja travado.
# Limites explícitos evitam que poucos usuários ocupem todas as threads.
apihelper.CONNECT_TIMEOUT = 10
apihelper.READ_TIMEOUT = 25


# =====================================================
# PROTEÇÃO GLOBAL DE ERROS DO TELEGRAM
# =====================================================
# Erros de rede da hospedagem (por exemplo, "Network is unreachable")
# não são erros do código do bot. O handler abaixo permite que o polling
# continue sem derrubar o processo.
_ultimo_log_rede = 0.0


def _erro_de_rede_temporario(exception):
    texto = str(exception).lower()

    marcadores = (
        "network is unreachable",
        "connection aborted",
        "connection reset",
        "connection refused",
        "connection timed out",
        "connect timeout",
        "read timeout",
        "max retries exceeded",
        "temporary failure in name resolution",
        "name or service not known",
        "failed to establish a new connection",
        "remote end closed connection",
        "broken pipe",
    )

    if any(m in texto for m in marcadores):
        return True

    if isinstance(exception, (ConnectionError, TimeoutError, socket.timeout)):
        return True

    if isinstance(exception, OSError) and getattr(exception, "errno", None) in (101, 110, 111, 113):
        return True

    return False


class TratadorDeExcecoes(telebot.ExceptionHandler):
    def handle(self, exception):
        global _ultimo_log_rede

        if _erro_de_rede_temporario(exception):
            agora = _time.time()

            # Evita inundar o log quando a Discloud ficar sem rede.
            if agora - _ultimo_log_rede >= 60:
                print(
                    "⚠️ Telegram temporariamente indisponível/rede da hospedagem. "
                    "O bot continuará tentando automaticamente."
                )
                _ultimo_log_rede = agora

            return True

        # Erros reais do código continuam sendo registrados para correção.
        try:
            print(f"❌ ERRO DE HANDLER: {type(exception).__name__}: {exception}")
            registrar_erro("handler", exception)
        except Exception:
            pass

        # False deixa o TeleBot tratar o erro normalmente, sem esconder bugs.
        return False

from config import TOKEN

# LINK OFICIAL DO GRUPO USADO PELO BOTAO ENTRAR NO GRUPO
GRUPO_LINK_BOTAO = "https://t.me/PITBULLPRIME1"

from telebot import types

from teclado import menu_principal

from usuario import (
    registrar as registrar_usuario,
    cadastrar_usuario
)

from tickets import registrar as registrar_tickets
from gamificacao import registrar as registrar_gamificacao, registrar_atividade
from avancado import registrar as registrar_avancado
from manutencao import registrar as registrar_manutencao, registrar_erro, preparar as preparar_manutencao
from premium import registrar as registrar_premium, preparar_premium
from painel_extra import registrar as registrar_painel_extra
from vip import registrar as registrar_vip, preparar_vip, beneficios_vip, cfg as vip_cfg, vip_ativo
from codigos import registrar as registrar_codigos, preparar_codigos

from saques import registrar as registrar_saques

from admin import registrar as registrar_admin
from admin_cargos import registrar as registrar_admin_cargos, menu_admin_por_cargo

from database import conn, cursor

from config import GRUPO_ID, GRUPO_OBRIGATORIO
from indicacoes import (
    registrar_indicacao,
    confirmar_entrada_grupo,
    aprovar_indicacao_automatica,
    buscar_dono_convite,
    buscar_por_indicado
)
# ==========================================
# BOT
# ==========================================

bot = telebot.TeleBot(
    TOKEN,
    parse_mode="HTML",
    exception_handler=TratadorDeExcecoes(),
    suppress_middleware_excepions=True,
    threaded=True,
    # 4 workers eram insuficientes: uma chamada lenta ao Telegram podia
    # bloquear o atendimento dos demais usuários.
    num_threads=24
)

# =====================================================
# LIMPEZA PROFISSIONAL DAS MENSAGENS DE TELA
# =====================================================
_MENSAGENS_TELA = {}
_MENSAGENS_TELA_LOCK = threading.RLock()
_MAX_MENSAGENS_TELA_POR_CHAT = 30

_send_message_original = bot.send_message

def _send_message_rastreado(chat_id, text, *args, **kwargs):
    resultado = _send_message_original(chat_id, text, *args, **kwargs)
    try:
        if isinstance(chat_id, int) and chat_id > 0 and resultado is not None:
            with _MENSAGENS_TELA_LOCK:
                lista = _MENSAGENS_TELA.setdefault(chat_id, [])
                lista.append(resultado.message_id)
                if len(lista) > _MAX_MENSAGENS_TELA_POR_CHAT:
                    del lista[:-_MAX_MENSAGENS_TELA_POR_CHAT]
    except Exception:
        pass
    return resultado

bot.send_message = _send_message_rastreado

def _limpar_mensagens_usuario(chat_id):
    if not isinstance(chat_id, int) or chat_id <= 0:
        return
    with _MENSAGENS_TELA_LOCK:
        ids = list(_MENSAGENS_TELA.pop(chat_id, []))
    for message_id in ids:
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass

_BOTOES_LIMPEZA_TELA = {
    "👤 Perfil", "💰 Saldo", "🔗 Meu Link", "👥 Minhas Indicações",
    "💳 PIX", "💸 Solicitar Saque", "🎫 Suporte", "📜 Histórico",
    "🔔 Notificações", "🏆 Ranking", "🏅 Meu Nível", "🎯 Missões",
    "👥 Equipe", "🏅 Conquistas", "🔥 Sequência", "🛡️ Confiança",
    "🎁 Evento", "💎 VIP", "🎟️ Código Promocional", "🪙 Moedas",
    "🎰 Roleta", "🎁 Caixa Surpresa", "🏪 Loja", "🎫 Raspadinha",
    "🤝 Parceiros", "⚔️ Clã", "📖 Regras", "ℹ️ Informações", "⬅️ Menu"
}

@bot.middleware_handler(update_types=["message"])
def limpar_tela_antes_de_nova_funcao(bot_instance, update):
    try:
        chat = getattr(update, "chat", None)
        texto = getattr(update, "text", "") or ""
        if chat and getattr(chat, "type", None) == "private" and texto in _BOTOES_LIMPEZA_TELA:
            _limpar_mensagens_usuario(chat.id)
    except Exception as erro:
        print(f"ERRO AO LIMPAR MENSAGENS DE TELA: {erro}")

# =====================================================
# BLOQUEIO GLOBAL DE MANUTENÇÃO
# =====================================================
# A manutenção é tratada por handlers prioritários registrados antes
# dos módulos. Assim cada atualização é interrompida antes de chegar
# às funções do usuário, sem depender de middleware.

# =====================================================
# BLOQUEIO GLOBAL POR ENTRADA NO GRUPO
# =====================================================
# Usuários comuns só podem usar as funções do bot depois que
# o Telegram confirmar que estão dentro do grupo obrigatório.
# /start e o botão "Já entrei no grupo" continuam liberados para
# que o usuário consiga entrar e fazer a verificação.
_grupo_cache = {}
_GRUPO_CACHE_TTL = 10.0

def usuario_esta_no_grupo(usuario_id):
    agora = _time.time()
    cache = _grupo_cache.get(usuario_id)
    if cache and agora - cache[0] < _GRUPO_CACHE_TTL:
        return cache[1]

    try:
        membro = bot.get_chat_member(GRUPO_ID, usuario_id)
        status = getattr(membro, "status", "left")

        if status in ("creator", "administrator", "member"):
            dentro = True
        elif status == "restricted":
            dentro = bool(getattr(membro, "is_member", False))
        else:
            dentro = False

        _grupo_cache[usuario_id] = (agora, dentro)
        return dentro
    except Exception as erro:
        # Não liberamos funções quando a verificação falha.
        # Assim o requisito de entrada no grupo nunca é contornado.
        print(f"ERRO AO VERIFICAR MEMBRO DO GRUPO {usuario_id}: {erro}")
        return False


def enviar_bloqueio_grupo(bot_instance, chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👥 ENTRAR NO GRUPO", url=GRUPO_LINK_BOTAO))
    markup.add(types.InlineKeyboardButton("✅ JÁ ENTREI — VERIFICAR", callback_data="confirmar_grupo"))

    bot_instance.send_message(
        chat_id,
        "🚫 <b>ACESSO BLOQUEADO</b>\n\n"
        "Para usar as funções do bot, você precisa estar dentro do nosso grupo oficial.\n\n"
        "1️⃣ Entre no grupo\n"
        "2️⃣ Volte aqui\n"
        "3️⃣ Clique em <b>✅ JÁ ENTREI — VERIFICAR</b>\n\n"
        "⚠️ Enquanto você não estiver no grupo, os recursos do bot permanecerão bloqueados.",
        reply_markup=markup,
        parse_mode="HTML"
    )


@bot.middleware_handler(update_types=["message", "callback_query"])
def bloquear_sem_grupo(bot_instance, update):
    try:
        from utils import eh_admin

        # Permite desativar a exigência pelo config.py sem alterar o middleware.
        if not GRUPO_OBRIGATORIO:
            return

        usuario = getattr(update, "from_user", None)
        usuario_id = getattr(usuario, "id", None)
        if not usuario_id or eh_admin(usuario_id):
            return

        # Se a manutenção estiver ativa, deixe o handler prioritário de
        # manutenção bloquear a atualização. Isso evita que esta trava
        # mostre a mensagem de grupo antes da mensagem de manutenção.
        from manutencao import esta_em_manutencao
        if esta_em_manutencao():
            return

        # /start é permitido para mostrar o convite/verificação.
        texto = getattr(update, "text", "") or ""
        if texto.startswith("/start"):
            return

        # O callback de confirmação é permitido para verificar a entrada.
        if getattr(update, "data", None) == "confirmar_grupo":
            return

        # Eventos enviados pelo próprio grupo não devem passar por esta trava.
        chat = getattr(update, "chat", None)
        if chat and getattr(chat, "id", None) == GRUPO_ID:
            return

        if usuario_esta_no_grupo(usuario_id):
            return

        if getattr(update, "data", None) is not None:
            try:
                bot_instance.answer_callback_query(
                    update.id,
                    "🚫 Entre no grupo para liberar o bot.",
                    show_alert=True
                )
            except Exception:
                pass
            return CancelUpdate()

        if chat:
            enviar_bloqueio_grupo(bot_instance, chat.id)
        return CancelUpdate()

    except Exception as erro:
        print(f"ERRO NO MIDDLEWARE DE GRUPO: {erro}")
        # Falha na verificação = acesso bloqueado para usuário comum.
        try:
            if getattr(update, "data", None) is not None:
                return CancelUpdate()
            chat = getattr(update, "chat", None)
            if chat:
                enviar_bloqueio_grupo(bot_instance, chat.id)
                return CancelUpdate()
        except Exception:
            pass
        return CancelUpdate()

# =====================================================
# CONTROLE DE CARGOS DOS ADMINISTRADORES
# =====================================================
# O Master continua com acesso total. Outros admins recebem apenas as
# funções permitidas pelo cargo. O bloqueio acontece antes dos handlers.
_ADMIN_ACOES = {
    "🎁 Indicações": "indicacoes", "💸 Saques": "saques", "💰 Adicionar Saldo": "saldo",
    "👥 Usuários": "usuarios", "🏆 Ranking": "ranking", "📢 Anunciar": "anuncio",
    "📊 Dashboard": "dashboard", "📊 Estatísticas": "dashboard", "🧠 Gamificação": "gamificacao",
    "🔥 Evento": "evento", "💎 Configurar VIP": "vip", "🛠️ Manutenção": "manutencao",
    "🎫 Tickets": "tickets", "🎟️ Códigos": "codigos", "🤝 Parceiros": "parceiros",
    "🚫 Banimentos": "banimentos", "⚙️ Configurações": "configuracoes"
}
_ADMIN_CALLBACKS = {
    "aprovar_indicacao:": "indicacoes", "rejeitar_indicacao:": "indicacoes",
    "aprovar_saque:": "saques", "rejeitar_saque:": "saques",
    "usuario_ban:": "banimentos", "usuario_unban:": "banimentos",
    "usuario_atualizar:": "usuarios", "config_": "configuracoes",
    "admin_maint_": "manutencao", "anuncio_": "anuncio"
}

@bot.middleware_handler(update_types=["message", "callback_query"])
def bloquear_acoes_sem_cargo(bot_instance, update):
    try:
        from utils import cargo_admin, tem_permissao_admin
        user=getattr(update,"from_user",None); uid=getattr(user,"id",None)
        if not uid or cargo_admin(uid) is None or cargo_admin(uid) == "master": return
        permissao=None
        texto=getattr(update,"text","") or ""
        data=getattr(update,"data","") or ""
        if texto in _ADMIN_ACOES: permissao=_ADMIN_ACOES[texto]
        elif texto.startswith("/"):
            cmd=texto.split()[0].lower()
            permissao={"/ban":"banimentos","/unban":"banimentos","/evento":"evento","/evento_off":"evento","/campanha":"gamificacao","/campanhas":"gamificacao","/economia":"gamificacao","/parceiro":"parceiros","/parceiro_off":"parceiros","/backup":"dashboard","/relatorio":"dashboard","/erros":"manutencao","/manutencao":"manutencao","/criarlink":"indicacoes","/codigo":"codigos","/raspadinha":"gamificacao","/raspadinha_valores":"gamificacao"}.get(cmd)
        else:
            for prefix,perm in _ADMIN_CALLBACKS.items():
                if data.startswith(prefix): permissao=perm; break
        if permissao and not tem_permissao_admin(uid, permissao):
            if data:
                try: bot_instance.answer_callback_query(update.id,"🚫 Seu cargo não possui esta permissão.",show_alert=True)
                except Exception: pass
                return CancelUpdate()
            chat=getattr(update,"chat",None)
            if chat: bot_instance.send_message(chat.id,"🚫 <b>Acesso restrito ao seu cargo.</b>",parse_mode="HTML")
            return CancelUpdate()
    except Exception as erro:
        print(f"ERRO NO CONTROLE DE CARGOS: {erro}")

# =====================================================
# HANDLERS PRIORITÁRIOS DE MANUTENÇÃO
# =====================================================
# Registrados antes dos módulos do bot. Para usuários comuns, quando
# a manutenção está ativa, o update é consumido aqui e não chega
# aos handlers das funções do usuário.

def _manutencao_ativa_para_usuario(usuario_id):
    try:
        from manutencao import esta_em_manutencao
        from utils import eh_admin
        if not usuario_id or eh_admin(usuario_id):
            return False
        return bool(esta_em_manutencao())
    except Exception as erro:
        print(f"ERRO AO VERIFICAR MANUTENÇÃO: {erro}")
        return False


@bot.callback_query_handler(func=lambda call: True)
def handler_prioritario_manutencao_callback(call):
    usuario = getattr(call, "from_user", None)
    usuario_id = getattr(usuario, "id", None)
    if not _manutencao_ativa_para_usuario(usuario_id):
        return ContinueHandling()

    try:
        bot.answer_callback_query(
            call.id,
            "🛠️ O bot está em manutenção. Tente novamente em alguns minutos.",
            show_alert=True
        )
    except Exception:
        pass
    return


@bot.message_handler(func=lambda message: True)
def handler_prioritario_manutencao_mensagem(message):
    usuario = getattr(message, "from_user", None)
    usuario_id = getattr(usuario, "id", None)
    if not _manutencao_ativa_para_usuario(usuario_id):
        return ContinueHandling()

    chat = getattr(message, "chat", None)
    if not chat:
        return

    try:
        _limpar_mensagens_usuario(chat.id)
    except Exception:
        pass

    try:
        bot.send_message(
            chat.id,
            "🛠️ <b>BOT EM MANUTENÇÃO</b>\n\n"
            "Estamos realizando uma atualização.\n"
            "Tente novamente em alguns minutos.",
            parse_mode="HTML"
        )
    except Exception as erro:
        print(f"ERRO AO ENVIAR MENSAGEM DE MANUTENÇÃO: {erro}")
    return


# ==========================================
# REGISTRAR MÓDULOS
# ==========================================

registrar_manutencao(bot)

registrar_usuario(bot)

registrar_tickets(bot)
registrar_gamificacao(bot)
registrar_avancado(bot)
registrar_premium(bot)
registrar_painel_extra(bot)
registrar_vip(bot)
registrar_codigos(bot)

registrar_saques(bot)

registrar_admin(bot)
registrar_admin_cargos(bot)


# ==========================================
# START
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):

    try:
        cadastrar_usuario(message)
        registrar_atividade(message.from_user.id)
    except Exception as erro:
        print("========== ERRO NO CADASTRO DO /START ==========")
        print(f"USUARIO_ID: {message.from_user.id}")
        print(f"ERRO: {erro}")
        registrar_erro("start", erro, message.from_user.id)
        # Mesmo que uma atualização de cadastro falhe, o /start continua.

    indicador_id = None

    partes = message.text.split(maxsplit=1)
    if len(partes) > 1:
        parametro = partes[1].strip()
        if parametro.startswith("ref_"):
            try:
                indicador_id = int(parametro.replace("ref_", "", 1))
            except ValueError:
                indicador_id = None

    if indicador_id:
        try:
            sucesso, retorno = registrar_indicacao(
                indicador_id,
                message.from_user.id
            )
            print("========== INDICAÇÃO NO /START ==========")
            print(f"INDICADOR_ID: {indicador_id}")
            print(f"INDICADO_ID: {message.from_user.id}")
            print(f"SUCESSO: {sucesso}")
            print(f"RETORNO: {retorno}")
        except Exception as erro:
            print("========== ERRO AO REGISTRAR INDICAÇÃO ==========")
            print(f"ERRO: {erro}")

    try:
        indicacao = buscar_por_indicado(message.from_user.id)

        # A exigência de grupo deve aparecer somente quando o usuário
        # realmente ainda não está no grupo. O /start de um usuário que já
        # foi confirmado não deve voltar a mostrar o convite.
        esta_no_grupo = (not GRUPO_OBRIGATORIO) or usuario_esta_no_grupo(message.from_user.id)
        mostrar_etapa_grupo = not esta_no_grupo
        mensagem_status = None

        if indicacao and esta_no_grupo:
            status_indicacao = indicacao[4]
            grupo_confirmado = indicacao[5]

            if status_indicacao == "APROVADO":
                mostrar_etapa_grupo = False
            elif grupo_confirmado == 1:
                mostrar_etapa_grupo = False
                mensagem_status = """
⏳ <b>INDICAÇÃO EM ANÁLISE</b>

✅ Sua entrada no grupo já foi confirmada.

Sua indicação foi processada automaticamente pelo sistema.
"""

        if mostrar_etapa_grupo:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("👥 Entrar no Grupo", url=GRUPO_LINK_BOTAO))
            markup.add(types.InlineKeyboardButton("✅ Já entrei no grupo", callback_data="confirmar_grupo"))

            texto_start = """
🎉 <b>Bem-vindo!</b>

Seu cadastro foi realizado com sucesso.

Para validar sua indicação:

1️⃣ Entre no grupo.
2️⃣ Volte ao bot.
3️⃣ Clique em <b>✅ Já entrei no grupo</b>.
4️⃣ Aguarde a aprovação do administrador.

Após a aprovação, o saldo será liberado.
"""

            bot.send_message(
                message.chat.id,
                texto_start,
                reply_markup=markup,
                parse_mode="HTML"
            )

        elif mensagem_status:
            bot.send_message(message.chat.id, mensagem_status, parse_mode="HTML")

        else:
            bot.send_message(
                message.chat.id,
                "🎉 <b>Bem-vindo de volta!</b>\n\nSua indicação já foi processada.\n\nVocê não precisa entrar no grupo novamente.",
                parse_mode="HTML"
            )

        # O menu só é liberado depois da confirmação real de entrada no grupo.
        # O /start continua liberado para o usuário conseguir entrar/verificar.
        if not GRUPO_OBRIGATORIO or usuario_esta_no_grupo(message.from_user.id):
            bot.send_message(
                message.chat.id,
                "🏠 Menu Principal",
                reply_markup=menu_principal()
            )

        # VIP ativo aparece também na tela inicial, sem criar um submenu
        # separado para os benefícios.
        try:
            if (not GRUPO_OBRIGATORIO or usuario_esta_no_grupo(message.from_user.id)) and vip_ativo(message.from_user.id):
                bvip = beneficios_vip(message.from_user.id)
                bot.send_message(
                    message.chat.id,
                    "💎 <b>SEU VIP ESTÁ ATIVO</b>\n\n"
                    f"🎰 {bvip['roleta']} giros de roleta por dia\n"
                    f"🎫 {bvip['raspadinha']} raspadinhas por dia\n"
                    f"🍀 {bvip['chance']:g}x mais chances\n"
                    f"⭐ {bvip['xp']:g}x XP\n"
                    f"🪙 +{bvip['coins']} Coins bônus\n"
                    f"💎 +{bvip['gemas']} Gemas bônus",
                    parse_mode="HTML"
                )
        except Exception as erro_vip:
            print(f"ERRO AO MOSTRAR VIP NA TELA INICIAL: {erro_vip}")

    except Exception as erro:
        print("========== ERRO NO /START ==========")
        print(f"USUARIO_ID: {message.from_user.id}")
        print(f"ERRO: {erro}")
        try:
            bot.send_message(
                message.chat.id,
                "🎉 <b>Bem-vindo!</b>\n\nOcorreu uma falha temporária ao carregar seu menu. Tente tocar em /start novamente.",
                parse_mode="HTML",
                reply_markup=menu_principal()
            )
        except Exception as erro2:
            print(f"ERRO AO ENVIAR FALLBACK DO /START: {erro2}")

# ==========================================
# CONFIRMAR ENTRADA NO GRUPO
# ==========================================

@bot.callback_query_handler(func=lambda call: call.data == "confirmar_grupo")
def confirmar_grupo(call):

    usuario_id = call.from_user.id

    try:

        membro = bot.get_chat_member(
            chat_id=GRUPO_ID,
            user_id=usuario_id
        )

        print("========== VERIFICAÇÃO DO GRUPO ==========")
        print(f"GRUPO_ID: {GRUPO_ID}")
        print(f"USUARIO_ID: {usuario_id}")
        print(f"STATUS: {membro.status}")

    except Exception as erro:

        print("========== ERRO AO VERIFICAR GRUPO ==========")
        print(f"GRUPO_ID: {GRUPO_ID}")
        print(f"USUARIO_ID: {usuario_id}")
        print(f"ERRO: {erro}")

        bot.answer_callback_query(
            call.id,
            "❌ Não foi possível verificar o grupo.",
            show_alert=True
        )
        return

    if membro.status in ("left", "kicked"):

        bot.answer_callback_query(
            call.id,
            f"❌ O Telegram informou que você está como: {membro.status}.",
            show_alert=True
        )
        return

    indicacao = buscar_por_indicado(
        usuario_id
    )

    # Se já confirmou anteriormente, não cria outra mensagem.
    if indicacao and indicacao[5] == 1:

        bot.answer_callback_query(
            call.id,
            "✅ Sua entrada já foi confirmada. Aguarde a análise.",
            show_alert=True
        )

        return

    confirmar_entrada_grupo(
        usuario_id
    )

    # Após o Telegram confirmar a entrada, o sistema processa
    # automaticamente a indicação pendente. Não depende de admin.
    try:
        aprovar_indicacao_automatica(usuario_id)
    except Exception as erro: 
        print(f"ERRO AO APROVAR INDICACAO AUTOMATICAMENTE {usuario_id}: {erro}")

    # Força a próxima consulta a buscar o status atual no Telegram.
    _grupo_cache.pop(usuario_id, None)

    # Remove os botões antigos para impedir nova confirmação.
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.answer_callback_query(
        call.id,
        "✅ Grupo confirmado!"
    )

    bot.send_message(
        call.message.chat.id,
        """
🎉 <b>SUA ENTRADA FOI CONFIRMADA!</b>

✅ O sistema confirmou que você está no grupo.

⚡ Sua entrada foi processada automaticamente pelo sistema.

🎉 Se você entrou pelo link de indicação, sua indicação será processada sem precisar aguardar um administrador.

Você não precisará entrar no grupo novamente.
""",
        parse_mode="HTML"
    )

# ==========================================
# NOVO MEMBRO NO GRUPO
# ==========================================

@bot.message_handler(content_types=["new_chat_members"])
def novo_membro(message):

    if message.chat.id != GRUPO_ID:
        return

    print("========== NOVO MEMBRO ==========")
    print(message.json)

    for membro in message.new_chat_members:

        if membro.is_bot:
            continue

        print(f"ID: {membro.id}")
        print(f"NOME: {membro.first_name}")

        confirmar_entrada_grupo(membro.id)
        try:
            aprovar_indicacao_automatica(membro.id)
        except Exception as erro:
            print(f"ERRO AO PROCESSAR INDICACAO AUTOMATICA {membro.id}: {erro}")


# ==========================================
# CRIAR LINK DE CONVITE
# ==========================================

@bot.message_handler(commands=["criarlink"])
def criar_link_teste(message):

    try:

        chat = bot.get_chat(GRUPO_ID)

        convite = bot.create_chat_invite_link(
            chat_id=GRUPO_ID
        )

        bot.send_message(
            message.chat.id,
            f"""
Grupo:
{chat.title}

Link:

{convite.invite_link}
"""
        )

    except Exception as erro:

        bot.send_message(
            message.chat.id,
            str(erro)
        )

# ==========================================
# INICIAR BOT
# ==========================================

print("Bot iniciado com sucesso.")

# =====================================================
# POLLING ROBUSTO
# =====================================================
# infinity_polling já possui tratamento interno de exceções.
# logger_level=None evita o traceback gigante do TeleBot para falhas
# transitórias de rede; o TratadorDeExcecoes acima mantém o processo vivo.
while True:
    try:
        print("🔄 Polling iniciado. Aguardando mensagens...")
        bot.infinity_polling(
            skip_pending=True,
            timeout=20,
            long_polling_timeout=20,
            logger_level=None
        )
        print("⚠️ Polling terminou inesperadamente. Reiniciando...")
        _time.sleep(3)

    except KeyboardInterrupt:
        print("🛑 Bot encerrado manualmente.")
        break

    except Exception as _erro:
        if _erro_de_rede_temporario(_erro):
            print("⚠️ Conexão com o Telegram perdida. Tentando novamente...")
            _time.sleep(5)
        else:
            registrar_erro("polling", _erro)
            print(
                f"❌ Falha inesperada no polling: "
                f"{type(_erro).__name__}: {_erro}"
            )
            _time.sleep(5)
