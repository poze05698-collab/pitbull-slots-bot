from telebot import types

from config import (
    ADMIN_ID,
    STATUS_PENDENTE,
    GRUPO_ID
)

from database import conn, cursor

from utils import (
    eh_admin,
    dinheiro,
    saldo_usuario,
    adicionar_saldo,
    usuario_existe,
    registrar_historico,
    registrar_movimentacao,
    criar_notificacao
)

from indicacoes import (
    aprovar_indicacao,
    rejeitar_indicacao
)

from saques import (
    aprovar_saque,
    rejeitar_saque,
    listar_saques_pendentes
)

from antifraude import (
    banir_usuario,
    desbanir_usuario
)

from vip import mostrar_admin_vip
from manutencao import esta_em_manutencao, definir_manutencao

from gamificacao import (
    ranking_geral,
    evento_ativo,
    iniciar_evento,
    parar_evento
)


# ==========================================
# VERIFICAR ADMIN
# ==========================================

def admin_autorizado(user_id):

    return eh_admin(user_id)


# ==========================================
# REGISTRAR
# ==========================================

def registrar(bot):

    # Estados temporários do painel de administração.
    estado_adicionar_saldo = {}
    estado_anuncio = {}
    estado_config = {}

    # ==========================================
    # PAINEL ADMIN
    # ==========================================

    @bot.message_handler(commands=["admin"])
    def painel_admin(message):

        if not admin_autorizado(message.from_user.id):

            bot.reply_to(
                message,
                "❌ Você não possui permissão."
            )

            return

        from admin_cargos import menu_admin_por_cargo
        teclado = menu_admin_por_cargo(message.from_user.id)

        bot.send_message(

            message.chat.id,

            """
🔐 <b>PAINEL ADMINISTRATIVO</b>

Escolha uma opção.
""",

            parse_mode="HTML",

            reply_markup=teclado

        )

    # ==========================================
    # CÓDIGOS PROMOCIONAIS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎟️ Códigos" and admin_autorizado(m.from_user.id))
    def painel_codigos_admin(message):
        try:
            from codigos import abrir_painel_admin_codigos
            abrir_painel_admin_codigos(bot, message.chat.id)
        except Exception as erro:
            print(f"ERRO AO ABRIR PAINEL DE CÓDIGOS: {erro}")
            bot.send_message(message.chat.id, "❌ Não foi possível abrir o painel de códigos agora.")

    # ==========================================
    # VIP / MANUTENÇÃO
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💎 Configurar VIP" and admin_autorizado(m.from_user.id))
    def painel_vip_admin(message):
        mostrar_admin_vip(bot, message.chat.id)

    @bot.message_handler(func=lambda m: m.text == "🛠️ Manutenção" and admin_autorizado(m.from_user.id))
    def painel_manut_admin(message):
        status = "🔴 ATIVA" if esta_em_manutencao() else "🟢 DESATIVADA"
        kb = types.InlineKeyboardMarkup()
        kb.row(types.InlineKeyboardButton("🔴 Ativar", callback_data="admin_maint_on"), types.InlineKeyboardButton("🟢 Desativar", callback_data="admin_maint_off"))
        bot.send_message(message.chat.id, f"🛠️ <b>MANUTENÇÃO</b>\n\nStatus: {status}\n\n💾 O banco de dados não é apagado durante manutenção.", parse_mode="HTML", reply_markup=kb)

    @bot.callback_query_handler(func=lambda c: c.data in ("admin_maint_on", "admin_maint_off"))
    def admin_maint_toggle(call):
        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True); return
        ativo = call.data == "admin_maint_on"
        definir_manutencao(ativo)
        bot.answer_callback_query(call.id, "Atualizado.")
        bot.edit_message_text(f"🛠️ <b>MANUTENÇÃO</b>\n\nStatus: {'🔴 ATIVA' if ativo else '🟢 DESATIVADA'}", call.message.chat.id, call.message.message_id, parse_mode="HTML")

    # ==========================================
    # INDICAÇÕES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🎁 Indicações")
    def listar_indicacoes(message):

        if not admin_autorizado(message.from_user.id):
            return

        # Não depende de JOIN e aceita pequenas diferenças de formatação
        # no status gravado no banco.
        cursor.execute(
            """
            SELECT
                i.id,
                i.indicador_id,
                i.indicado_id,
                i.valor,
                i.data,
                i.grupo_confirmado,
                COALESCE(u1.nome, 'Usuário'),
                COALESCE(u2.nome, 'Usuário')
            FROM indicacoes i
            LEFT JOIN usuarios u1 ON u1.id = i.indicador_id
            LEFT JOIN usuarios u2 ON u2.id = i.indicado_id
            WHERE UPPER(TRIM(COALESCE(i.status, ''))) = UPPER(TRIM(?))
            ORDER BY i.id ASC
            """,
            (STATUS_PENDENTE,)
        )

        lista = cursor.fetchall()

        if not lista:
            # Mostra também um diagnóstico útil, sem alterar o banco.
            cursor.execute(
                """
                SELECT status, COUNT(*)
                FROM indicacoes
                GROUP BY status
                ORDER BY status
                """
            )
            estados = cursor.fetchall()

            resumo = "\n".join(
                f"• {status or 'VAZIO'}: {quantidade}"
                for status, quantidade in estados
            ) or "Nenhuma indicação cadastrada."

            bot.send_message(
                message.chat.id,
                "❌ <b>Não existem indicações pendentes.</b>\n\n"
                "📊 Status encontrados no banco:\n" + resumo,
                parse_mode="HTML"
            )
            return

        bot.send_message(
            message.chat.id,
            f"🎁 <b>INDICAÇÕES PENDENTES: {len(lista)}</b>",
            parse_mode="HTML"
        )

        for item in lista:

            teclado = types.InlineKeyboardMarkup()
            teclado.row(
                types.InlineKeyboardButton(
                    "✅ Aprovar",
                    callback_data=f"aprovar_indicacao:{item[0]}"
                ),
                types.InlineKeyboardButton(
                    "❌ Rejeitar",
                    callback_data=f"rejeitar_indicacao:{item[0]}"
                )
            )

            grupo = "✅ Sim" if item[5] else "❌ Não"

            bot.send_message(
                message.chat.id,
                f"""
🎁 <b>INDICAÇÃO #{item[0]}</b>

👤 <b>Indicador:</b>
{item[6]}
🆔 <code>{item[1]}</code>

👤 <b>Indicado:</b>
{item[7]}
🆔 <code>{item[2]}</code>

💰 <b>Valor:</b>
{dinheiro(item[3])}

👥 <b>Entrou no grupo?</b>
{grupo}

📅 <b>Data:</b>
{item[4]}
""",
                parse_mode="HTML",
                reply_markup=teclado
            )

    # ==========================================
    # APROVAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_indicacao:")
    )
    def callback_aprovar_indicacao(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return

        indicacao_id = int(call.data.split(":")[1])

        cursor.execute(
            "SELECT indicador_id, indicado_id FROM indicacoes WHERE id=?",
            (indicacao_id,)
        )
        dados = cursor.fetchone()

        if not dados:
            bot.answer_callback_query(call.id, "Indicação não encontrada.", show_alert=True)
            return

        indicador_id, indicado_id = dados

        try:
            membro = bot.get_chat_member(GRUPO_ID, indicado_id)
            if membro.status in ("left", "kicked"):
                bot.answer_callback_query(
                    call.id,
                    "❌ O usuário ainda não entrou no grupo.",
                    show_alert=True
                )
                return
        except Exception:
            bot.answer_callback_query(
                call.id,
                "❌ Não foi possível verificar o grupo.",
                show_alert=True
            )
            return

        sucesso, retorno = aprovar_indicacao(
            indicacao_id,
            call.from_user.id
        )

        if not sucesso:
            bot.answer_callback_query(call.id, retorno, show_alert=True)
            return

        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            pass

        bot.send_message(call.message.chat.id, "✅ Indicação aprovada com sucesso.")

        try:
            bot.send_message(
                indicador_id,
                "🎉 <b>Sua indicação foi aprovada!</b>\n\n💰 O valor já está disponível em seu saldo.",
                parse_mode="HTML"
            )
        except Exception as erro:
            print(f"Erro ao avisar indicador {indicador_id}: {erro}")

        try:
            bot.send_message(
                indicado_id,
                "🎉 <b>Sua entrada foi aprovada!</b>\n\n✅ Sua indicação foi aprovada pelo administrador.",
                parse_mode="HTML"
            )
        except Exception as erro:
            print(f"Erro ao avisar indicado {indicado_id}: {erro}")

        bot.answer_callback_query(call.id, "✅ Aprovada!")

    # ==========================================
    # REJEITAR INDICAÇÃO
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_indicacao:")
    )
    def callback_rejeitar_indicacao(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        indicacao_id = int(call.data.split(":")[1])

        motivo = "Rejeitada pelo administrador"

        sucesso, retorno = rejeitar_indicacao(
            indicacao_id,
            call.from_user.id,
            motivo
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "❌ Indicação rejeitada."
        )

        try:

            bot.send_message(
                usuario_id,
                f"""
❌ Sua indicação foi rejeitada.

Motivo:

{motivo}
"""
            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # SAQUES PENDENTES
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "💸 Saques")
    def listar_saques(message):

        if not admin_autorizado(message.from_user.id):
            return

        saques = listar_saques_pendentes()

        if not saques:

            bot.send_message(
                message.chat.id,
                "✅ Não existem saques pendentes."
            )

            return

        for saque in saques:

            teclado = types.InlineKeyboardMarkup()

            teclado.row(

                types.InlineKeyboardButton(
                    "✅ Aprovar",
                    callback_data=f"aprovar_saque:{saque[0]}"
                ),

                types.InlineKeyboardButton(
                    "❌ Rejeitar",
                    callback_data=f"rejeitar_saque:{saque[0]}"
                )

            )

            bot.send_message(

                message.chat.id,

                f"""
💸 <b>SAQUE #{saque[0]}</b>

👤 Usuário:

<code>{saque[1]}</code>

💰 Valor:

{dinheiro(saque[2])}

💳 PIX:

<code>{saque[3]}</code>

📅 Data:

{saque[4]}
""",

                parse_mode="HTML",

                reply_markup=teclado

            )

    # ==========================================
    # APROVAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("aprovar_saque:")
    )
    def callback_aprovar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        saque_id = int(call.data.split(":")[1])

        sucesso, retorno = aprovar_saque(
            saque_id,
            call.from_user.id
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "✅ Saque aprovado com sucesso."
        )

        try:

            bot.send_message(

                usuario_id,

                """
🎉 Seu saque foi aprovado!

Em breve o pagamento será realizado.
"""

            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # REJEITAR SAQUE
    # ==========================================

    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("rejeitar_saque:")
    )
    def callback_rejeitar_saque(call):

        if not admin_autorizado(call.from_user.id):

            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )

            return

        saque_id = int(call.data.split(":")[1])

        motivo = "Rejeitado pelo administrador"

        sucesso, retorno = rejeitar_saque(
            saque_id,
            call.from_user.id,
            motivo
        )

        if not sucesso:

            bot.answer_callback_query(
                call.id,
                retorno,
                show_alert=True
            )

            return

        usuario_id = retorno

        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        bot.send_message(
            call.message.chat.id,
            "❌ Saque rejeitado."
        )

        try:

            bot.send_message(

                usuario_id,

                f"""
❌ Seu saque foi rejeitado.

Motivo:

{motivo}
"""

            )

        except:
            pass

        bot.answer_callback_query(call.id)

    # ==========================================
    # USUÁRIOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "👥 Usuários")
    def listar_usuarios(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                id,
                nome,
                username,
                saldo,
                banido,
                data_cadastro
            FROM usuarios
            ORDER BY id DESC
            LIMIT 30
            """
        )

        usuarios = cursor.fetchall()

        if not usuarios:

            bot.send_message(
                message.chat.id,
                "📭 Nenhum usuário cadastrado."
            )

            return

        cursor.execute(
            "SELECT COUNT(*) FROM usuarios"
        )

        total = cursor.fetchone()[0]

        try:
            bot.send_message(
                message.chat.id,
                f"""
👥 <b>GERENCIAMENTO DE USUÁRIOS</b>

📊 Total cadastrado: <b>{total}</b>

Mostrando os últimos 30 usuários.
""",
                parse_mode="HTML"
            )
        except Exception as erro:
            print(f"ERRO AO ENVIAR LISTA DE USUÁRIOS: {erro}")
            return

        for usuario_id, nome, username, saldo, banido, data_cadastro in usuarios:

            status = "🚫 BANIDO" if banido else "🟢 ATIVO"

            markup = types.InlineKeyboardMarkup()

            if banido:

                markup.row(
                    types.InlineKeyboardButton(
                        "✅ Desbanir",
                        callback_data=f"usuario_unban:{usuario_id}"
                    )
                )

            else:

                markup.row(
                    types.InlineKeyboardButton(
                        "🚫 Banir",
                        callback_data=f"usuario_ban:{usuario_id}"
                    )
                )

            markup.row(
                types.InlineKeyboardButton(
                    "🔄 Atualizar",
                    callback_data=f"usuario_atualizar:{usuario_id}"
                )
            )

            bot.send_message(
                message.chat.id,
                f"""
👤 <b>USUÁRIO</b>

🆔 ID:
<code>{usuario_id}</code>

👤 Nome:
{nome or "Sem nome"}

📱 Username:
@{username if username else "Sem username"}

💰 Saldo:
{dinheiro(saldo or 0)}

📌 Status:
{status}

📅 Cadastro:
{data_cadastro}
""",
                parse_mode="HTML",
                reply_markup=markup
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_ban:")
    )
    def callback_ban_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        if usuario_id == ADMIN_ID:
            bot.answer_callback_query(
                call.id,
                "❌ Você não pode banir o administrador.",
                show_alert=True
            )
            return

        sucesso = banir_usuario(usuario_id)

        if sucesso:

            bot.answer_callback_query(
                call.id,
                "Usuário banido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "🚫 <b>Você foi bloqueado.</b>\n\nSeu acesso ao bot foi suspenso pelo administrador.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            atualizar_card_usuario(
                bot,
                call.message.chat.id,
                call.message.message_id,
                usuario_id
            )

        else:

            bot.answer_callback_query(
                call.id,
                "Não foi possível banir.",
                show_alert=True
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_unban:")
    )
    def callback_unban_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        sucesso = desbanir_usuario(usuario_id)

        if sucesso:

            bot.answer_callback_query(
                call.id,
                "Usuário desbanido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "✅ <b>Seu acesso ao bot foi liberado novamente.</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            atualizar_card_usuario(
                bot,
                call.message.chat.id,
                call.message.message_id,
                usuario_id
            )

        else:

            bot.answer_callback_query(
                call.id,
                "Não foi possível desbanir.",
                show_alert=True
            )


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_atualizar:")
    )
    def callback_atualizar_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(
                call.id,
                "Sem permissão.",
                show_alert=True
            )
            return

        usuario_id = int(
            call.data.split(":")[1]
        )

        atualizar_card_usuario(
            bot,
            call.message.chat.id,
            call.message.message_id,
            usuario_id
        )

        bot.answer_callback_query(
            call.id,
            "Dados atualizados."
        )


    def atualizar_card_usuario(
        bot,
        chat_id,
        message_id,
        usuario_id
    ):

        cursor.execute(
            """
            SELECT
                id,
                nome,
                username,
                saldo,
                banido,
                data_cadastro
            FROM usuarios
            WHERE id=?
            """,
            (usuario_id,)
        )

        usuario = cursor.fetchone()

        if not usuario:
            return

        uid, nome, username, saldo, banido, data_cadastro = usuario

        status = "🚫 BANIDO" if banido else "🟢 ATIVO"

        markup = types.InlineKeyboardMarkup()

        if banido:

            markup.row(
                types.InlineKeyboardButton(
                    "✅ Desbanir",
                    callback_data=f"usuario_unban:{uid}"
                )
            )

        else:

            markup.row(
                types.InlineKeyboardButton(
                    "🚫 Banir",
                    callback_data=f"usuario_ban:{uid}"
                )
            )

        markup.row(
            types.InlineKeyboardButton(
                "🔄 Atualizar",
                callback_data=f"usuario_atualizar:{uid}"
            )
        )

        try:

            bot.edit_message_text(
                f"""
👤 <b>USUÁRIO</b>

🆔 ID:
<code>{uid}</code>

👤 Nome:
{nome or "Sem nome"}

📱 Username:
@{username if username else "Sem username"}

💰 Saldo:
{dinheiro(saldo or 0)}

📌 Status:
{status}

📅 Cadastro:
{data_cadastro}
""",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup
            )

        except Exception:
            pass

    # ==========================================
    # BANIMENTOS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🚫 Banimentos")
    def menu_banimentos(message):

        if not admin_autorizado(message.from_user.id):
            return

        bot.send_message(
            message.chat.id,
            """
🚫 <b>SISTEMA DE BANIMENTOS</b>

Envie um dos comandos abaixo:

<code>/ban ID_DO_USUARIO</code>

<code>/unban ID_DO_USUARIO</code>
""",
            parse_mode="HTML"
        )

    @bot.message_handler(commands=["ban"])
    def comando_ban(message):

        if not admin_autorizado(message.from_user.id):
            return

        try:
            usuario_id = int(message.text.split()[1])

        except:
            bot.reply_to(
                message,
                "Uso correto:\n/ban ID_DO_USUARIO"
            )
            return

        sucesso = banir_usuario(usuario_id)

        if sucesso:

            bot.send_message(
                message.chat.id,
                "✅ Usuário banido."
            )

            try:
                bot.send_message(
                    usuario_id,
                    "🚫 Você foi banido do bot."
                )
            except:
                pass

        else:

            bot.send_message(
                message.chat.id,
                "❌ Não foi possível banir."
            )

    @bot.message_handler(commands=["unban"])
    def comando_unban(message):

        if not admin_autorizado(message.from_user.id):
            return

        try:

            usuario_id = int(message.text.split()[1])

        except:

            bot.reply_to(
                message,
                "Uso correto:\n/unban ID_DO_USUARIO"
            )

            return

        sucesso = desbanir_usuario(usuario_id)

        if sucesso:

            bot.send_message(
                message.chat.id,
                "✅ Usuário desbanido."
            )

            try:

                bot.send_message(
                    usuario_id,
                    "✅ Seu acesso ao bot foi liberado novamente."
                )

            except:
                pass

        else:

            bot.send_message(
                message.chat.id,
                "❌ Não foi possível desbanir."
            )

    # ==========================================
    # ESTATÍSTICAS
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "📊 Estatísticas")
    def estatisticas(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM indicacoes")
        indicacoes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM saques")
        saques = cursor.fetchone()[0]

        bot.send_message(

            message.chat.id,

            f"""
📊 <b>ESTATÍSTICAS</b>

👥 Usuários:
{usuarios}

🎁 Indicações:
{indicacoes}

💸 Saques:
{saques}
""",

            parse_mode="HTML"

        )


    # =====================================================
    # DASHBOARD
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "📊 Dashboard")
    def dashboard(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute("SELECT COUNT(*) FROM usuarios")
        usuarios = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE banido=1")
        banidos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM indicacoes")
        indicacoes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM indicacoes WHERE status=?",
            (STATUS_PENDENTE,)
        )
        indicacoes_pendentes = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(valor),0) FROM indicacoes WHERE status='APROVADO'")
        recompensas = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM saques WHERE status='PENDENTE'")
        saques_pendentes = cursor.fetchone()[0]

        cursor.execute("SELECT COALESCE(SUM(valor),0) FROM saques WHERE status='PENDENTE'")
        saques_valor = cursor.fetchone()[0] or 0

        cursor.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('ABERTO','RESPONDIDO')"
        )
        tickets_abertos = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM usuarios WHERE data_cadastro LIKE ?",
            (data_hoje_prefixo(),)
        )
        novos = cursor.fetchone()[0]

        bot.send_message(
            message.chat.id,
            f"""
📊 <b>DASHBOARD ADMINISTRATIVO</b>

━━━━━━━━━━━━━━━━━━━━

👥 <b>USUÁRIOS</b>
👤 Total: <b>{usuarios}</b>
🟢 Ativos: <b>{usuarios - banidos}</b>
🚫 Banidos: <b>{banidos}</b>
🆕 Novos hoje: <b>{novos}</b>

━━━━━━━━━━━━━━━━━━━━

🎁 <b>INDICAÇÕES</b>
📊 Total: <b>{indicacoes}</b>
🟡 Pendentes: <b>{indicacoes_pendentes}</b>
💰 Recompensas aprovadas: <b>{dinheiro(recompensas)}</b>

━━━━━━━━━━━━━━━━━━━━

💸 <b>SAQUES</b>
🟡 Pendentes: <b>{saques_pendentes}</b>
💰 A pagar: <b>{dinheiro(saques_valor)}</b>

━━━━━━━━━━━━━━━━━━━━

🎫 <b>SUPORTE</b>
🟢 Tickets abertos: <b>{tickets_abertos}</b>
""",
            parse_mode="HTML"
        )

    def data_hoje_prefixo():
        from datetime import datetime
        return datetime.now().strftime("%d/%m/%Y") + "%"

    # =====================================================
    # ADICIONAR SALDO MANUAL
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "💰 Adicionar Saldo")
    def iniciar_adicionar_saldo(message):

        if not admin_autorizado(message.from_user.id):
            return

        estado_adicionar_saldo[message.from_user.id] = {
            "etapa": "usuario"
        }

        bot.send_message(
            message.chat.id,
            """
💰 <b>ADICIONAR SALDO</b>

Envie o <b>ID do usuário</b> que receberá o saldo.
""",
            parse_mode="HTML"
        )

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id == ADMIN_ID
            and m.from_user.id in estado_adicionar_saldo
        )
    )
    def fluxo_adicionar_saldo(message):

        estado = estado_adicionar_saldo.get(message.from_user.id)
        texto = (message.text or "").strip()

        if not texto:
            return

        if estado["etapa"] == "usuario":

            try:
                usuario_id = int(texto)
            except ValueError:
                bot.send_message(
                    message.chat.id,
                    "❌ Envie somente o ID numérico do usuário."
                )
                return

            if not usuario_existe(usuario_id):
                bot.send_message(
                    message.chat.id,
                    "❌ Usuário não encontrado. Confira o ID."
                )
                return

            estado["usuario_id"] = usuario_id
            estado["etapa"] = "valor"

            bot.send_message(
                message.chat.id,
                f"""
👤 Usuário:
<code>{usuario_id}</code>

💰 Saldo atual:
<b>{dinheiro(saldo_usuario(usuario_id))}</b>

Agora envie o <b>valor</b> que deseja adicionar.
Exemplo: <code>10</code> ou <code>10,50</code>
""",
                parse_mode="HTML"
            )
            return

        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            bot.send_message(
                message.chat.id,
                "❌ Valor inválido."
            )
            return

        if valor <= 0:
            bot.send_message(
                message.chat.id,
                "❌ O valor precisa ser maior que zero."
            )
            return

        usuario_id = estado["usuario_id"]

        adicionar_saldo(
            usuario_id,
            valor
        )

        registrar_historico(
            usuario_id,
            "ADMIN_CREDITO",
            "Saldo adicionado pelo administrador",
            valor
        )

        registrar_movimentacao(
            usuario_id,
            "ADMIN_CREDITO",
            valor,
            "Saldo adicionado manualmente pelo administrador",
            message.from_user.id
        )

        criar_notificacao(
            usuario_id,
            "💰 Saldo adicionado",
            f"O administrador adicionou {dinheiro(valor)} ao seu saldo."
        )

        novo_saldo = saldo_usuario(usuario_id)

        estado_adicionar_saldo.pop(
            message.from_user.id,
            None
        )

        bot.send_message(
            message.chat.id,
            f"""
✅ <b>SALDO ADICIONADO</b>

👤 Usuário:
<code>{usuario_id}</code>

➕ Valor:
<b>{dinheiro(valor)}</b>

💰 Novo saldo:
<b>{dinheiro(novo_saldo)}</b>
""",
            parse_mode="HTML"
        )

        try:
            bot.send_message(
                usuario_id,
                f"""
💰 <b>SALDO ADICIONADO</b>

O administrador adicionou:

➕ <b>{dinheiro(valor)}</b>

💵 Seu novo saldo:
<b>{dinheiro(novo_saldo)}</b>
""",
                parse_mode="HTML"
            )
        except Exception:
            pass

    # =====================================================
    # RANKING
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "🏆 Ranking")
    def ranking_admin(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            """
            SELECT
                u.id,
                u.nome,
                COUNT(i.id) AS total
            FROM usuarios u
            LEFT JOIN indicacoes i
                ON i.indicador_id=u.id
                AND i.status='APROVADO'
            GROUP BY u.id
            HAVING total > 0
            ORDER BY total DESC
            LIMIT 20
            """
        )

        ranking = cursor.fetchall()

        if not ranking:
            bot.send_message(
                message.chat.id,
                "🏆 Ainda não existem indicações aprovadas."
            )
            return

        linhas = []

        for pos, (uid, nome, total) in enumerate(ranking, 1):
            medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}️⃣")
            linhas.append(
                f"{medalha} {nome or 'Usuário'} — <code>{uid}</code> — {total} indicações"
            )

        bot.send_message(
            message.chat.id,
            "🏆 <b>RANKING DE INDICADORES</b>\n\n" + "\n".join(linhas),
            parse_mode="HTML"
        )

    # =====================================================
    # ANÚNCIOS
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "📢 Anunciar")
    def iniciar_anuncio(message):

        if not admin_autorizado(message.from_user.id):
            return

        estado_anuncio[message.from_user.id] = True

        bot.send_message(
            message.chat.id,
            """
📢 <b>NOVO ANÚNCIO</b>

Digite a mensagem que deseja enviar para os usuários.

⚠️ Depois será mostrada uma confirmação antes do disparo.
""",
            parse_mode="HTML"
        )

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id == ADMIN_ID
            and m.from_user.id in estado_anuncio
        )
    )
    def receber_anuncio(message):

        texto = (message.text or "").strip()

        if not texto:
            return

        estado_anuncio.pop(
            message.from_user.id,
            None
        )

        cursor.execute(
            "SELECT COUNT(*) FROM usuarios WHERE banido=0"
        )
        total = cursor.fetchone()[0]

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(
                "✅ Enviar",
                callback_data="anuncio_confirmar"
            ),
            types.InlineKeyboardButton(
                "❌ Cancelar",
                callback_data="anuncio_cancelar"
            )
        )

        estado_anuncio[message.from_user.id] = {
            "mensagem": texto
        }

        bot.send_message(
            message.chat.id,
            f"""
📢 <b>CONFIRMAR ANÚNCIO</b>

👥 Destinatários: <b>{total}</b>

━━━━━━━━━━━━━━━━━━━━

{texto}

━━━━━━━━━━━━━━━━━━━━

Deseja enviar?
""",
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "anuncio_cancelar"
    )
    def cancelar_anuncio(call):

        if not admin_autorizado(call.from_user.id):
            return

        estado_anuncio.pop(
            call.from_user.id,
            None
        )

        bot.edit_message_text(
            "❌ Anúncio cancelado.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(
        func=lambda c: c.data == "anuncio_confirmar"
    )
    def confirmar_anuncio(call):

        if not admin_autorizado(call.from_user.id):
            return

        estado = estado_anuncio.pop(
            call.from_user.id,
            None
        )

        if not estado:
            bot.answer_callback_query(
                call.id,
                "Anúncio expirado.",
                show_alert=True
            )
            return

        texto = estado["mensagem"]

        cursor.execute(
            "SELECT id FROM usuarios WHERE banido=0"
        )
        usuarios = cursor.fetchall()

        enviados = 0

        for (uid,) in usuarios:

            try:
                bot.send_message(
                    uid,
                    f"📢 <b>AVISO</b>\n\n{texto}",
                    parse_mode="HTML"
                )
                enviados += 1

            except Exception:
                pass

        bot.edit_message_text(
            f"✅ Anúncio enviado.\n\n📨 Entregues: {enviados}/{len(usuarios)}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )

        bot.answer_callback_query(call.id)

    # =====================================================
    # CONFIGURAÇÕES
    # =====================================================

    @bot.message_handler(func=lambda m: m.text == "⚙️ Configurações")
    def configuracoes_admin(message):

        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute(
            "SELECT chave, valor FROM configuracoes ORDER BY chave"
        )

        configs = cursor.fetchall()

        texto = ["⚙️ <b>CONFIGURAÇÕES</b>", ""]

        for chave, valor in configs:
            texto.append(
                f"• <code>{chave}</code> = <b>{valor}</b>"
            )

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "✏️ Alterar valor",
                callback_data="config_alterar"
            )
        )

        bot.send_message(
            message.chat.id,
            "\n".join(texto),
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(
        func=lambda c: c.data == "config_alterar"
    )
    def iniciar_config(call):

        if not admin_autorizado(call.from_user.id):
            return

        estado_config[call.from_user.id] = True

        bot.answer_callback_query(call.id)

        bot.send_message(
            call.message.chat.id,
            """
✏️ <b>ALTERAR CONFIGURAÇÃO</b>

Envie no formato:

<code>chave=valor</code>

Exemplo:
<code>valor_indicacao=2.00</code>
""",
            parse_mode="HTML"
        )

    @bot.message_handler(
        func=lambda m: (
            m.from_user.id == ADMIN_ID
            and m.from_user.id in estado_config
        )
    )
    def receber_config(message):

        texto = (message.text or "").strip()

        if "=" not in texto:
            bot.send_message(
                message.chat.id,
                "❌ Use o formato chave=valor."
            )
            return

        chave, valor = texto.split("=", 1)
        chave = chave.strip()
        valor = valor.strip()

        permitidas = {
            "valor_indicacao",
            "valor_minimo_saque",
            "grupo_obrigatorio",
            "tickets_ativos"
        }

        if chave not in permitidas:
            bot.send_message(
                message.chat.id,
                "❌ Essa configuração não pode ser alterada por aqui."
            )
            return

        cursor.execute(
            """
            INSERT INTO configuracoes(chave, valor)
            VALUES (?, ?)
            ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor
            """,
            (chave, valor)
        )

        conn.commit()

        estado_config.pop(
            message.from_user.id,
            None
        )

        bot.send_message(
            message.chat.id,
            f"✅ Configuração <code>{chave}</code> alterada para <b>{valor}</b>.",
            parse_mode="HTML"
        )

    # ==========================================
    # GAMIFICAÇÃO ADMIN
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🧠 Gamificação")
    def painel_gamificacao_admin(message):
        if not admin_autorizado(message.from_user.id):
            return

        cursor.execute("SELECT COUNT(*) FROM gamificacao")
        total = cursor.fetchone()[0] or 0
        cursor.execute("SELECT AVG(confianca) FROM gamificacao")
        media = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM equipes")
        equipes = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*) FROM conquistas")
        conquistas = cursor.fetchone()[0] or 0

        evento = evento_ativo()
        evento_txt = f"🔥 {evento[1]} (x{evento[2]} + R$ {evento[3]:.2f})" if evento else "Nenhum evento ativo"

        bot.send_message(message.chat.id, f"""
🧠 <b>GAMIFICAÇÃO</b>

👥 Usuários no sistema: <b>{total}</b>
🛡️ Confiança média: <b>{media:.1f}/100</b>
🤝 Equipes: <b>{equipes}</b>
🏅 Conquistas desbloqueadas: <b>{conquistas}</b>

🎁 Evento:
{evento_txt}

Comandos:
/evento NOME [MULTIPLICADOR] [BONUS]
/evento_off

🏆 O ranking geral está disponível no botão de ranking.
""", parse_mode="HTML")

    @bot.message_handler(func=lambda m: m.text == "🔥 Evento")
    def painel_evento_admin(message):
        if not admin_autorizado(message.from_user.id):
            return
        evento = evento_ativo()
        if not evento:
            bot.send_message(message.chat.id, "🎁 Nenhum evento ativo.\n\nUse: /evento NOME MULTIPLICADOR BONUS")
            return
        bot.send_message(message.chat.id, f"🔥 <b>EVENTO ATIVO</b>\n\n{evento[1]}\n💰 Multiplicador: x{evento[2]}\n🎁 Bônus fixo: R$ {evento[3]:.2f}\n\nPara encerrar: /evento_off", parse_mode="HTML")

