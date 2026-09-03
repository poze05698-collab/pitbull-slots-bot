from telebot import types

from config import (
    ADMIN_ID,
    STATUS_PENDENTE,
    STATUS_REJEITADO,
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
    rejeitar_indicacao,
    reaprovar_indicacao
)

from saques import (
    aprovar_saque,
    rejeitar_saque,
    listar_saques_pendentes
)

from antifraude import (
    banir_usuario,
    desbanir_usuario,
    analisar_risco_saque
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
    # REAPROVAR INDICAÇÃO REJEITADA
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🔄 Reabrir Indicações" and admin_autorizado(m.from_user.id))
    def listar_indicacoes_rejeitadas(message):
        cursor.execute(
            """
            SELECT i.id, i.indicador_id, i.indicado_id, i.valor, i.data,
                   i.grupo_confirmado,
                   COALESCE(u1.nome, 'Usuário'), COALESCE(u2.nome, 'Usuário')
            FROM indicacoes i
            LEFT JOIN usuarios u1 ON u1.id=i.indicador_id
            LEFT JOIN usuarios u2 ON u2.id=i.indicado_id
            WHERE UPPER(TRIM(COALESCE(i.status,''))) = UPPER(TRIM(?))
            ORDER BY i.id DESC
            """,
            (STATUS_REJEITADO,)
        )
        lista = cursor.fetchall()
        if not lista:
            bot.send_message(message.chat.id, "🔄 <b>Não existem indicações rejeitadas para reabrir.</b>", parse_mode="HTML")
            return

        bot.send_message(
            message.chat.id,
            f"🔄 <b>INDICAÇÕES REJEITADAS: {len(lista)}</b>\n\nEscolha uma para reaprovar.",
            parse_mode="HTML"
        )
        for item in lista:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(
                "✅ Reaprovar indicação",
                callback_data=f"reaprovar_indicacao:{item[0]}"
            ))
            grupo = "✅ Sim" if item[5] else "❌ Não"
            bot.send_message(
                message.chat.id,
                f"🔄 <b>INDICAÇÃO #{item[0]}</b>\n\n"
                f"👤 Indicador: {item[6]}\n<code>{item[1]}</code>\n\n"
                f"👤 Indicado: {item[7]}\n<code>{item[2]}</code>\n\n"
                f"💰 Valor original: {dinheiro(item[3])}\n"
                f"👥 Grupo confirmado: {grupo}\n"
                f"📅 Data: {item[4]}",
                parse_mode="HTML",
                reply_markup=kb
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("reaprovar_indicacao:"))
    def callback_reaprovar_indicacao(call):
        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return

        try:
            indicacao_id = int(call.data.split(":", 1)[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "ID inválido.", show_alert=True)
            return

        sucesso, retorno = reaprovar_indicacao(indicacao_id, call.from_user.id)
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

        bot.answer_callback_query(call.id, "✅ Indicação reaprovada!")
        bot.send_message(
            call.message.chat.id,
            f"✅ <b>Indicação #{indicacao_id} reaprovada com sucesso.</b>",
            parse_mode="HTML"
        )

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

{(lambda r: f"{r['emoji']} <b>RISCO: {r['risco']}</b> ({r['score']}/100)" + (f"\n⚠️ {', '.join(r['motivos'])}" if r['motivos'] else ""))(analisar_risco_saque(saque[1], saque[2]))}
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

        _mostrar_lista_usuarios(bot, message.chat.id, 0)


    def _mostrar_lista_usuarios(bot, chat_id, pagina=0, message_id=None):
        """Mostra usuários em páginas, evitando uma lista gigante no painel."""
        POR_PAGINA = 10

        try:
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            total = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE banido=0")
            ativos = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE banido=1")
            banidos = cursor.fetchone()[0] or 0

            total_paginas = max(1, (total + POR_PAGINA - 1) // POR_PAGINA)
            pagina = max(0, min(int(pagina), total_paginas - 1))
            offset = pagina * POR_PAGINA

            cursor.execute(
                """
                SELECT id, nome, username, saldo, banido, data_cadastro
                FROM usuarios
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (POR_PAGINA, offset)
            )
            usuarios = cursor.fetchall()

            texto = [
                "👥 <b>GERENCIAMENTO DE USUÁRIOS</b>",
                "",
                f"📊 Total: <b>{total}</b>  |  🟢 Ativos: <b>{ativos}</b>  |  🚫 Banidos: <b>{banidos}</b>",
                f"📄 Página <b>{pagina + 1}</b> de <b>{total_paginas}</b>",
                "",
            ]

            markup = types.InlineKeyboardMarkup()

            if not usuarios:
                texto.append("📭 Nenhum usuário cadastrado.")
            else:
                for uid, nome, username, saldo, banido, data_cadastro in usuarios:
                    nome_exibicao = (nome or "Sem nome").strip()
                    if len(nome_exibicao) > 24:
                        nome_exibicao = nome_exibicao[:21] + "..."
                    user_exibicao = f"@{username}" if username else "sem @username"
                    if len(user_exibicao) > 20:
                        user_exibicao = user_exibicao[:17] + "..."
                    status = "🚫" if banido else "🟢"
                    texto.append(
                        f"{status} <b>{nome_exibicao}</b> — <code>{uid}</code>\n"
                        f"   {user_exibicao} • {dinheiro(saldo or 0)}"
                    )
                    markup.row(types.InlineKeyboardButton(
                        f"👤 {nome_exibicao[:22]}",
                        callback_data=f"usuario_detalhe:{uid}:{pagina}"
                    ))

            botoes_navegacao = []
            if pagina > 0:
                botoes_navegacao.append(types.InlineKeyboardButton(
                    "⬅️ Anterior", callback_data=f"usuarios_pag:{pagina - 1}"
                ))
            if pagina < total_paginas - 1:
                botoes_navegacao.append(types.InlineKeyboardButton(
                    "Próxima ➡️", callback_data=f"usuarios_pag:{pagina + 1}"
                ))
            if botoes_navegacao:
                markup.row(*botoes_navegacao)

            markup.row(types.InlineKeyboardButton(
                "🔄 Atualizar lista", callback_data=f"usuarios_pag:{pagina}"
            ))

            if message_id is None:
                bot.send_message(
                    chat_id,
                    "\n".join(texto),
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                bot.edit_message_text(
                    "\n".join(texto),
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML",
                    reply_markup=markup
                )

        except Exception as erro:
            print(f"ERRO AO MOSTRAR LISTA DE USUÁRIOS: {erro}")
            if message_id is None:
                bot.send_message(chat_id, "❌ Não foi possível carregar a lista de usuários.")
            else:
                try:
                    bot.answer_callback_query(message_id, "Erro ao atualizar a lista.", show_alert=True)
                except Exception:
                    pass


    def _mostrar_detalhes_usuario(bot, chat_id, message_id, usuario_id, pagina=0):
        cursor.execute(
            """
            SELECT id, nome, username, saldo, banido, data_cadastro, ultimo_acesso
            FROM usuarios
            WHERE id=?
            """,
            (usuario_id,)
        )
        usuario = cursor.fetchone()

        if not usuario:
            try:
                bot.edit_message_text(
                    "❌ Usuário não encontrado.",
                    chat_id=chat_id,
                    message_id=message_id
                )
            except Exception:
                pass
            return

        uid, nome, username, saldo, banido, data_cadastro, ultimo_acesso = usuario
        status = "🚫 <b>BANIDO</b>" if banido else "🟢 <b>ATIVO</b>"
        username_txt = f"@{username}" if username else "Sem username"

        markup = types.InlineKeyboardMarkup()
        if banido:
            markup.row(types.InlineKeyboardButton(
                "✅ Desbanir", callback_data=f"usuario_unban:{uid}"
            ))
        else:
            markup.row(types.InlineKeyboardButton(
                "🚫 Banir", callback_data=f"usuario_ban:{uid}"
            ))
        markup.row(types.InlineKeyboardButton(
            "🔄 Atualizar", callback_data=f"usuario_atualizar:{uid}"
        ))
        markup.row(types.InlineKeyboardButton(
            "⬅️ Voltar à lista", callback_data=f"usuarios_voltar:{pagina}"
        ))

        texto = (
            "👤 <b>DETALHES DO USUÁRIO</b>\n\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👤 Nome: {nome or 'Sem nome'}\n"
            f"📱 Username: {username_txt}\n"
            f"💰 Saldo: {dinheiro(saldo or 0)}\n"
            f"📌 Status: {status}\n"
            f"📅 Cadastro: {data_cadastro or 'Não informado'}\n"
            f"🕐 Último acesso: {ultimo_acesso or 'Não informado'}"
        )

        try:
            bot.edit_message_text(
                texto,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as erro:
            print(f"ERRO AO MOSTRAR DETALHES DO USUÁRIO {uid}: {erro}")


    @bot.callback_query_handler(func=lambda call: call.data.startswith("usuarios_pag:"))
    def callback_usuarios_pag(call):
        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        try:
            pagina = int(call.data.split(":", 1)[1])
        except Exception:
            pagina = 0
        _mostrar_lista_usuarios(bot, call.message.chat.id, pagina, call.message.message_id)
        bot.answer_callback_query(call.id)


    @bot.callback_query_handler(func=lambda call: call.data.startswith("usuario_detalhe:"))
    def callback_detalhe_usuario(call):
        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        try:
            _, uid, pagina = call.data.split(":")
            uid = int(uid)
            pagina = int(pagina)
        except Exception:
            bot.answer_callback_query(call.id, "Dados inválidos.", show_alert=True)
            return
        _mostrar_detalhes_usuario(bot, call.message.chat.id, call.message.message_id, uid, pagina)
        bot.answer_callback_query(call.id)


    @bot.callback_query_handler(func=lambda call: call.data.startswith("usuarios_voltar:"))
    def callback_usuarios_voltar(call):
        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return
        try:
            pagina = int(call.data.split(":", 1)[1])
        except Exception:
            pagina = 0
        _mostrar_lista_usuarios(bot, call.message.chat.id, pagina, call.message.message_id)
        bot.answer_callback_query(call.id)


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

        usuario_id = int(call.data.split(":")[1])

        if usuario_id == ADMIN_ID:
            bot.answer_callback_query(
                call.id,
                "❌ Você não pode banir o administrador.",
                show_alert=True
            )
            return

        sucesso = banir_usuario(usuario_id)

        if sucesso:
            bot.answer_callback_query(call.id, "Usuário banido.")
            try:
                bot.send_message(
                    usuario_id,
                    "🚫 <b>Você foi bloqueado.</b>\n\nSeu acesso ao bot foi suspenso pelo administrador.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            atualizar_card_usuario(bot, call.message.chat.id, call.message.message_id, usuario_id)
        else:
            bot.answer_callback_query(call.id, "Não foi possível banir.", show_alert=True)


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_unban:")
    )
    def callback_unban_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return

        usuario_id = int(call.data.split(":")[1])
        sucesso = desbanir_usuario(usuario_id)

        if sucesso:
            bot.answer_callback_query(call.id, "Usuário desbanido.")
            try:
                bot.send_message(
                    usuario_id,
                    "✅ <b>Seu acesso ao bot foi liberado novamente.</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            atualizar_card_usuario(bot, call.message.chat.id, call.message.message_id, usuario_id)
        else:
            bot.answer_callback_query(call.id, "Não foi possível desbanir.", show_alert=True)


    @bot.callback_query_handler(
        func=lambda call: call.data.startswith("usuario_atualizar:")
    )
    def callback_atualizar_usuario(call):

        if not admin_autorizado(call.from_user.id):
            bot.answer_callback_query(call.id, "Sem permissão.", show_alert=True)
            return

        usuario_id = int(call.data.split(":")[1])
        atualizar_card_usuario(bot, call.message.chat.id, call.message.message_id, usuario_id)
        bot.answer_callback_query(call.id, "Dados atualizados.")


    def atualizar_card_usuario(bot, chat_id, message_id, usuario_id):
        cursor.execute(
            """
            SELECT id, nome, username, saldo, banido, data_cadastro, ultimo_acesso
            FROM usuarios
            WHERE id=?
            """,
            (usuario_id,)
        )
        usuario = cursor.fetchone()
        if not usuario:
            return

        uid, nome, username, saldo, banido, data_cadastro, ultimo_acesso = usuario
        status = "🚫 <b>BANIDO</b>" if banido else "🟢 <b>ATIVO</b>"
        username_txt = f"@{username}" if username else "Sem username"

        markup = types.InlineKeyboardMarkup()
        if banido:
            markup.row(types.InlineKeyboardButton("✅ Desbanir", callback_data=f"usuario_unban:{uid}"))
        else:
            markup.row(types.InlineKeyboardButton("🚫 Banir", callback_data=f"usuario_ban:{uid}"))
        markup.row(types.InlineKeyboardButton("🔄 Atualizar", callback_data=f"usuario_atualizar:{uid}"))
        markup.row(types.InlineKeyboardButton("⬅️ Voltar à lista", callback_data="usuarios_voltar:0"))

        try:
            bot.edit_message_text(
                "👤 <b>DETALHES DO USUÁRIO</b>\n\n"
                f"🆔 ID: <code>{uid}</code>\n"
                f"👤 Nome: {nome or 'Sem nome'}\n"
                f"📱 Username: {username_txt}\n"
                f"💰 Saldo: {dinheiro(saldo or 0)}\n"
                f"📌 Status: {status}\n"
                f"📅 Cadastro: {data_cadastro or 'Não informado'}\n"
                f"🕐 Último acesso: {ultimo_acesso or 'Não informado'}",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as erro:
            print(f"ERRO AO ATUALIZAR CARD DO USUÁRIO {uid}: {erro}")


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
    # USUÁRIOS ONLINE
    # ==========================================

    @bot.message_handler(func=lambda m: m.text == "🟢 Usuários Online")
    def usuarios_online(message):

        if not admin_autorizado(message.from_user.id):
            return

        from datetime import datetime, timedelta

        agora = datetime.now()
        limite_online = agora - timedelta(minutes=5)
        limite_hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)

        cursor.execute("""
            SELECT id, nome, username, ultimo_acesso
            FROM usuarios
            WHERE ultimo_acesso IS NOT NULL
              AND ultimo_acesso != ''
        """)

        online = []
        ativos_hoje = 0

        for usuario_id, nome, username, ultimo_acesso in cursor.fetchall():
            try:
                ultimo = datetime.strptime(
                    ultimo_acesso,
                    "%d/%m/%Y %H:%M:%S"
                )
            except (TypeError, ValueError):
                continue

            if ultimo >= limite_hoje:
                ativos_hoje += 1

            if ultimo >= limite_online:
                segundos = max(0, int((agora - ultimo).total_seconds()))

                if segundos < 60:
                    tempo = f"{segundos}s"
                elif segundos < 3600:
                    tempo = f"{segundos // 60}min"
                else:
                    tempo = f"{segundos // 3600}h"

                nome_exibicao = nome or "Sem nome"
                username_texto = f" @{username}" if username else ""

                online.append(
                    (ultimo, nome_exibicao, username_texto, usuario_id, tempo)
                )

        online.sort(key=lambda item: item[0], reverse=True)

        texto = [
            "🟢 <b>USUÁRIOS ONLINE AGORA</b>",
            "",
            f"🟢 Online nos últimos 5 min: <b>{len(online)}</b>",
            f"📅 Ativos hoje: <b>{ativos_hoje}</b>",
            "",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        if not online:
            texto.extend([
                "",
                "😴 <b>Nenhum usuário está ativo agora.</b>",
                "",
                "O sistema considera online quem",
                "interagiu com o bot nos últimos 5 minutos."
            ])
        else:
            for _, nome_exibicao, username_texto, usuario_id, tempo in online:
                texto.extend([
                    "",
                    f"🟢 <b>{nome_exibicao}</b>{username_texto}",
                    f"🆔 <code>{usuario_id}</code>",
                    f"⏱️ Ativo há: <b>{tempo}</b>"
                ])

        bot.send_message(
            message.chat.id,
            "\n".join(texto),
            parse_mode="HTML"
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

        try:
            cursor.execute("SELECT COUNT(*) FROM missoes_conclusoes WHERE concluida_em LIKE ?", (data_hoje_prefixo(),))
            missoes_hoje = cursor.fetchone()[0] or 0
        except Exception:
            missoes_hoje = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM fraudes")
            fraudes_total = cursor.fetchone()[0] or 0
        except Exception:
            fraudes_total = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE ultimo_acesso LIKE ? AND banido=0", (data_hoje_prefixo(),))
            ativos_hoje = cursor.fetchone()[0] or 0
        except Exception:
            ativos_hoje = 0

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
🟢 Ativos hoje: <b>{ativos_hoje}</b>

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

🎯 <b>ENGAJAMENTO</b>
🏆 Missões concluídas hoje: <b>{missoes_hoje}</b>
🛡️ Ocorrências antifraude: <b>{fraudes_total}</b>

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
    # ANÚNCIOS — SISTEMA AVANÇADO
    # =====================================================

    def _alvos_anuncio(tipo):
        """Retorna IDs dos destinatários sem incluir usuários banidos."""
        if tipo == "online":
            from datetime import datetime, timedelta
            agora = datetime.now()
            limite = agora - timedelta(minutes=5)
            cursor.execute("SELECT id, ultimo_acesso FROM usuarios WHERE banido=0")
            ids = []
            for uid, ultimo in cursor.fetchall():
                if not ultimo:
                    continue
                try:
                    dt = datetime.strptime(str(ultimo), "%d/%m/%Y %H:%M:%S")
                    if dt >= limite:
                        ids.append(int(uid))
                except Exception:
                    pass
            return ids

        if tipo == "vip":
            try:
                cursor.execute("""
                    SELECT DISTINCT u.id
                    FROM usuarios u
                    INNER JOIN vip_assinaturas v ON v.usuario_id=u.id
                    WHERE u.banido=0 AND v.status='ATIVO' AND v.expiracao > datetime('now')
                """)
                return [int(row[0]) for row in cursor.fetchall()]
            except Exception:
                return []

        if tipo == "saldo":
            cursor.execute("SELECT id FROM usuarios WHERE banido=0 AND saldo > 0")
            return [int(row[0]) for row in cursor.fetchall()]

        cursor.execute("SELECT id FROM usuarios WHERE banido=0")
        return [int(row[0]) for row in cursor.fetchall()]

    def _nome_alvo(tipo):
        return {
            "todos": "👥 Todos os usuários",
            "online": "🟢 Usuários online",
            "vip": "💎 Usuários VIP",
            "saldo": "💰 Usuários com saldo",
        }.get(tipo, "👥 Todos os usuários")

    @bot.message_handler(func=lambda m: m.text == "📢 Anunciar")
    def iniciar_anuncio(message):
        if not admin_autorizado(message.from_user.id):
            return

        estado_anuncio[message.from_user.id] = {"etapa": "alvo"}

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("👥 Todos", callback_data="anuncio_alvo_todos"),
            types.InlineKeyboardButton("🟢 Online", callback_data="anuncio_alvo_online")
        )
        markup.row(
            types.InlineKeyboardButton("💎 VIP", callback_data="anuncio_alvo_vip"),
            types.InlineKeyboardButton("💰 Com saldo", callback_data="anuncio_alvo_saldo")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data="anuncio_cancelar"))

        bot.send_message(
            message.chat.id,
            "📢 <b>NOVO ANÚNCIO</b>\n\n"
            "Primeiro escolha quem receberá a campanha:\n\n"
            "👥 <b>Todos</b> — toda a base não banida\n"
            "🟢 <b>Online</b> — atividade nos últimos 5 minutos\n"
            "💎 <b>VIP</b> — VIP atualmente ativo\n"
            "💰 <b>Com saldo</b> — usuários com saldo acima de R$ 0\n\n"
            "Depois você poderá enviar <b>texto, foto, vídeo, áudio ou documento</b>.",
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data.startswith("anuncio_alvo_"))
    def escolher_alvo_anuncio(call):
        if not admin_autorizado(call.from_user.id):
            return

        tipo = call.data.replace("anuncio_alvo_", "", 1)
        if tipo not in {"todos", "online", "vip", "saldo"}:
            bot.answer_callback_query(call.id, "Opção inválida.", show_alert=True)
            return

        ids = _alvos_anuncio(tipo)
        estado_anuncio[call.from_user.id] = {
            "etapa": "mensagem",
            "alvo": tipo,
            "destinatarios": ids,
        }

        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"📢 <b>CAMPANHA</b>\n\n"
            f"🎯 Público: <b>{_nome_alvo(tipo)}</b>\n"
            f"👥 Destinatários: <b>{len(ids)}</b>\n\n"
            "Agora envie a mensagem que deseja disparar.\n\n"
            "📎 Pode ser <b>texto, foto, vídeo, áudio ou documento</b>.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )

    @bot.message_handler(
        content_types=["text", "photo", "video", "audio", "document", "animation", "voice"],
        func=lambda m: (
            admin_autorizado(m.from_user.id)
            and isinstance(estado_anuncio.get(m.from_user.id), dict)
            and estado_anuncio[m.from_user.id].get("etapa") == "mensagem"
        )
    )
    def receber_anuncio(message):
        estado = estado_anuncio.get(message.from_user.id)
        if not estado:
            return

        destinatarios = list(estado.get("destinatarios", []))
        if not destinatarios:
            estado_anuncio.pop(message.from_user.id, None)
            bot.send_message(
                message.chat.id,
                "⚠️ <b>Nenhum usuário encontrado para esse público.</b>",
                parse_mode="HTML"
            )
            return

        estado.update({
            "etapa": "botoes",
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "botoes": []
        })

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("🔘 Adicionar botão", callback_data="anuncio_add_botao"),
            types.InlineKeyboardButton("➡️ Continuar sem botões", callback_data="anuncio_sem_botoes")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data="anuncio_cancelar"))

        try:
            bot.copy_message(
                message.chat.id,
                message.chat.id,
                message.message_id
            )
        except Exception as erro:
            estado_anuncio.pop(message.from_user.id, None)
            print(f"ERRO AO PREVISUALIZAR ANUNCIO: {erro}")
            bot.send_message(message.chat.id, "❌ Não consegui preparar a prévia desse anúncio.")
            return

        bot.send_message(
            message.chat.id,
            "📢 <b>BOTÕES DO ANÚNCIO</b>\n\n"
            "Você pode adicionar até <b>6 botões</b> com links.\n\n"
            "🔘 <b>Adicionar botão</b> — criar botão com URL\n"
            "➡️ <b>Continuar sem botões</b> — finalizar a mensagem sem botões",
            parse_mode="HTML",
            reply_markup=markup
        )

    def _markup_botoes_anuncio(botoes):
        if not botoes:
            return None

        markup = types.InlineKeyboardMarkup(row_width=2)
        linha = []
        for botao in botoes:
            linha.append(
                types.InlineKeyboardButton(
                    botao["texto"],
                    url=botao["url"]
                )
            )
            if len(linha) == 2:
                markup.row(*linha)
                linha = []

        if linha:
            markup.row(*linha)

        return markup

    def _enviar_preview_anuncio(chat_id, estado):
        markup = _markup_botoes_anuncio(estado.get("botoes", []))
        try:
            bot.copy_message(
                chat_id,
                estado["chat_id"],
                estado["message_id"],
                reply_markup=markup
            )
            return True
        except Exception as erro:
            print(f"ERRO AO PREVISUALIZAR ANUNCIO COM BOTOES: {erro}")
            return False

    def _mostrar_confirmacao_anuncio(call, estado):
        botoes = estado.get("botoes", [])
        descricao_botoes = (
            "\n".join(
                f"🔘 {i}. {b['texto']} → {b['url']}"
                for i, b in enumerate(botoes, 1)
            )
            if botoes else "Nenhum botão"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("✅ ENVIAR AGORA", callback_data="anuncio_confirmar"),
            types.InlineKeyboardButton("❌ CANCELAR", callback_data="anuncio_cancelar")
        )

        bot.send_message(
            call.message.chat.id,
            "📢 <b>CONFIRMAR CAMPANHA</b>\n\n"
            f"🎯 Público: <b>{_nome_alvo(estado['alvo'])}</b>\n"
            f"👥 Destinatários: <b>{len(estado['destinatarios'])}</b>\n\n"
            f"🔘 <b>Botões:</b>\n{descricao_botoes}\n\n"
            "A mensagem acima será enviada exatamente como foi recebida.\n"
            "Os botões, se houver, também serão enviados.\n\n"
            "Deseja disparar agora?",
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data == "anuncio_add_botao")
    def adicionar_botao_anuncio(call):
        if not admin_autorizado(call.from_user.id):
            return

        estado = estado_anuncio.get(call.from_user.id)
        if not estado or estado.get("etapa") != "botoes":
            bot.answer_callback_query(call.id, "Campanha expirada.", show_alert=True)
            return

        if len(estado.get("botoes", [])) >= 6:
            bot.answer_callback_query(call.id, "Você já adicionou 6 botões.", show_alert=True)
            return

        estado["etapa"] = "botao_texto"
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "🔘 <b>NOVO BOTÃO</b>\n\n"
            "Digite o <b>nome do botão</b>.\n\n"
            "Exemplo:\n"
            "<code>🎁 ACESSAR AGORA</code>",
            parse_mode="HTML"
        )

    @bot.message_handler(
        content_types=["text"],
        func=lambda m: (
            admin_autorizado(m.from_user.id)
            and isinstance(estado_anuncio.get(m.from_user.id), dict)
            and estado_anuncio[m.from_user.id].get("etapa") == "botao_texto"
        )
    )
    def receber_texto_botao_anuncio(message):
        estado = estado_anuncio.get(message.from_user.id)
        texto_botao = (message.text or "").strip()

        if not estado:
            return

        if not texto_botao:
            bot.send_message(message.chat.id, "❌ O nome do botão não pode ficar vazio.")
            return

        if len(texto_botao) > 64:
            bot.send_message(
                message.chat.id,
                "❌ O nome do botão pode ter no máximo <b>64 caracteres</b>.",
                parse_mode="HTML"
            )
            return

        estado["botao_temp_texto"] = texto_botao
        estado["etapa"] = "botao_url"

        bot.send_message(
            message.chat.id,
            "🔗 <b>LINK DO BOTÃO</b>\n\n"
            "Agora envie a URL que o botão deverá abrir.\n\n"
            "Exemplo:\n"
            "<code>https://t.me/PITBULL_SLOTS_BOT</code>\n\n"
            "⚠️ O link precisa começar com <b>http://</b> ou <b>https://</b>.",
            parse_mode="HTML"
        )

    @bot.message_handler(
        content_types=["text"],
        func=lambda m: (
            admin_autorizado(m.from_user.id)
            and isinstance(estado_anuncio.get(m.from_user.id), dict)
            and estado_anuncio[m.from_user.id].get("etapa") == "botao_url"
        )
    )
    def receber_url_botao_anuncio(message):
        estado = estado_anuncio.get(message.from_user.id)
        url = (message.text or "").strip()

        if not estado:
            return

        if not re.match(r"^https?://\S+$", url, re.IGNORECASE):
            bot.send_message(
                message.chat.id,
                "❌ URL inválida.\n\n"
                "Use um link começando com <b>http://</b> ou <b>https://</b>.",
                parse_mode="HTML"
            )
            return

        estado.setdefault("botoes", []).append({
            "texto": estado.pop("botao_temp_texto", "Abrir"),
            "url": url
        })

        if len(estado["botoes"]) >= 6:
            estado["etapa"] = "confirmacao"
            bot.send_message(
                message.chat.id,
                "✅ <b>6 botões adicionados.</b>\n\n"
                "O limite máximo foi atingido.",
                parse_mode="HTML"
            )
            # Reenvia a prévia com os botões e mostra confirmação.
            _enviar_preview_anuncio(message.chat.id, estado)
            fake = type("Obj", (), {
                "message": type("Msg", (), {"chat": type("Chat", (), {"id": message.chat.id})()})()
            })()
            _mostrar_confirmacao_anuncio(fake, estado)
            return

        estado["etapa"] = "botoes"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            types.InlineKeyboardButton("🔘 Adicionar outro", callback_data="anuncio_add_botao"),
            types.InlineKeyboardButton("✅ Finalizar botões", callback_data="anuncio_finalizar_botoes")
        )
        markup.add(types.InlineKeyboardButton("❌ Cancelar", callback_data="anuncio_cancelar"))

        bot.send_message(
            message.chat.id,
            f"✅ <b>Botão adicionado!</b>\n\n"
            f"🔘 {len(estado['botoes'])}. <b>{estado['botoes'][-1]['texto']}</b>\n"
            f"🔗 {estado['botoes'][-1]['url']}\n\n"
            f"Você pode adicionar mais <b>{6 - len(estado['botoes'])}</b>.",
            parse_mode="HTML",
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda c: c.data == "anuncio_finalizar_botoes")
    def finalizar_botoes_anuncio(call):
        if not admin_autorizado(call.from_user.id):
            return

        estado = estado_anuncio.get(call.from_user.id)
        if not estado or estado.get("etapa") != "botoes":
            bot.answer_callback_query(call.id, "Campanha expirada.", show_alert=True)
            return

        estado["etapa"] = "confirmacao"
        bot.answer_callback_query(call.id)

        if not _enviar_preview_anuncio(call.message.chat.id, estado):
            bot.send_message(call.message.chat.id, "❌ Não consegui preparar a prévia com os botões.")
            estado_anuncio.pop(call.from_user.id, None)
            return

        _mostrar_confirmacao_anuncio(call, estado)

    @bot.callback_query_handler(func=lambda c: c.data == "anuncio_sem_botoes")
    def anuncio_sem_botoes(call):
        if not admin_autorizado(call.from_user.id):
            return

        estado = estado_anuncio.get(call.from_user.id)
        if not estado or estado.get("etapa") != "botoes":
            bot.answer_callback_query(call.id, "Campanha expirada.", show_alert=True)
            return

        estado["etapa"] = "confirmacao"
        estado["botoes"] = []
        bot.answer_callback_query(call.id)

        _mostrar_confirmacao_anuncio(call, estado)

    @bot.callback_query_handler(func=lambda c: c.data == "anuncio_cancelar")
    def cancelar_anuncio(call):
        if not admin_autorizado(call.from_user.id):
            return

        estado_anuncio.pop(call.from_user.id, None)
        try:
            bot.edit_message_text(
                "❌ <b>Campanha cancelada.</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Campanha cancelada.")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "anuncio_confirmar")
    def confirmar_anuncio(call):
        if not admin_autorizado(call.from_user.id):
            return

        estado = estado_anuncio.pop(call.from_user.id, None)
        if not estado or estado.get("etapa") != "confirmacao":
            bot.answer_callback_query(call.id, "Campanha expirada.", show_alert=True)
            return

        destinatarios = list(estado.get("destinatarios", []))
        origem_chat = estado.get("chat_id")
        origem_msg = estado.get("message_id")
        markup = _markup_botoes_anuncio(estado.get("botoes", []))

        bot.answer_callback_query(call.id, "Disparando campanha...")

        enviados = 0
        falhas = 0
        bloqueados = 0

        for uid in destinatarios:
            try:
                bot.copy_message(
                    uid,
                    origem_chat,
                    origem_msg,
                    reply_markup=markup
                )
                enviados += 1
            except Exception as erro:
                falhas += 1
                erro_txt = str(erro).lower()
                if "bot was blocked by the user" in erro_txt or "user is deactivated" in erro_txt:
                    bloqueados += 1
                print(f"ERRO ANUNCIO PARA {uid}: {erro}")

        taxa = (enviados / len(destinatarios) * 100) if destinatarios else 0

        try:
            bot.edit_message_text(
                "📢 <b>CAMPANHA FINALIZADA</b>\n\n"
                f"🎯 Público: <b>{_nome_alvo(estado['alvo'])}</b>\n"
                f"👥 Destinatários: <b>{len(destinatarios)}</b>\n"
                f"🔘 Botões: <b>{len(estado.get('botoes', []))}</b>\n\n"
                f"✅ Entregues: <b>{enviados}</b>\n"
                f"🚫 Bloquearam o bot: <b>{bloqueados}</b>\n"
                f"❌ Outros erros: <b>{falhas - bloqueados}</b>\n\n"
                f"📊 Taxa de sucesso: <b>{taxa:.1f}%</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                f"📢 Campanha finalizada.\n\n"
                f"✅ {enviados} enviados\n"
                f"🚫 {bloqueados} bloquearam o bot\n"
                f"❌ {falhas - bloqueados} outros erros"
            )

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

