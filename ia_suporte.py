"""
IA do suporte.
- Responde várias mensagens por ticket.
- Usa Gemini com modelos atuais.
- Nunca inventa saldo: saldo deve ser fornecido pelo sistema/banco.
- Pode sinalizar necessidade de atendimento humano.
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime

try:
    from config import GEMINI_API_KEY, GEMINI_MODEL
except Exception:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

MODELOS_GEMINI = []
for _m in [GEMINI_MODEL, "gemini-3.6-flash", "gemini-3.1-flash-lite"]:
    if _m and _m not in MODELOS_GEMINI:
        MODELOS_GEMINI.append(_m)

SYSTEM_PROMPT = """Você é a assistente virtual da Central de Suporte PITBULL SLOTS.
Seja educada, profissional, objetiva e acolhedora.
Cumprimente o usuário somente na abertura do atendimento com Bom dia, Boa tarde ou Boa noite,
seguido de "Seja bem-vindo(a) à Central de Suporte".
Responda em português do Brasil.
Você pode orientar sobre funções simples do bot, saldo, Pix, saque, indicações, grupo, VIP
e funcionamento geral. Quando dados oficiais forem fornecidos pelo sistema, use exatamente
esses dados. Nunca invente saldo, pagamento, status de saque, aprovação, código VIP ou qualquer
outro dado financeiro.
Se a questão exigir uma ação administrativa, acesso que você não possui, contestação financeira,
bloqueio/desbloqueio ou algo que você não consiga confirmar, diga que vai encaminhar para um
atendente humano e inclua exatamente a marca [ENCAMINHAR_HUMANO].
"""

def _gerar_content(prompt):
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY não configurada"

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700}
    }

    last_error = None
    for modelo in MODELOS_GEMINI:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data=json.loads(resp.read().decode("utf-8"))
            text = ""
            for cand in data.get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    if part.get("text"):
                        text += part["text"]
            if text.strip():
                return text.strip(), None
            last_error=f"Resposta vazia no modelo {modelo}"
        except urllib.error.HTTPError as e:
            body=e.read().decode("utf-8","replace")
            last_error=f"HTTP {e.code} no modelo {modelo}: {body[:500]}"
        except Exception as e:
            last_error=str(e)

    return None, last_error or "Gemini indisponível"

def responder_ia(mensagem, historico=None, dados_oficiais=None, saudacao=False):
    historico = historico or []
    dados_oficiais = dados_oficiais or {}
    contexto = ""
    if dados_oficiais:
        contexto += "\nDADOS OFICIAIS DO SISTEMA (não altere nem invente):\n"
        contexto += json.dumps(dados_oficiais, ensure_ascii=False)
    if historico:
        contexto += "\nHISTÓRICO RECENTE DO TICKET:\n"
        for item in historico[-12:]:
            contexto += f"{item.get('autor','usuario')}: {item.get('texto','')}\n"

    abertura = ""
    if saudacao:
        hora = datetime.now().hour
        periodo = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
        abertura = f"Comece a resposta com '{periodo}! Seja bem-vindo(a) à Central de Suporte PITBULL SLOTS.'\n"

    prompt = f"""{abertura}
{contexto}
NOVA MENSAGEM DO USUÁRIO:
{mensagem}
Responda somente ao usuário, de forma profissional.
"""
    resposta, erro = _gerar_content(prompt)
    if resposta:
        return resposta, False, None
    return ("No momento estou com dificuldade para consultar a inteligência artificial. "
            "Vou encaminhar seu atendimento para um atendente humano. [ENCAMINHAR_HUMANO]"), True, erro

# Aliases comuns para compatibilidade com módulos existentes.
gerar_resposta = responder_ia
responder = responder_ia
