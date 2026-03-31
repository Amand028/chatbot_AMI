import os
import asyncio
from gtts import gTTS
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# FIREBASE / FIRESTORE
from google.cloud import firestore


# ======================================================
# 1️⃣ CONFIGURAÇÕES INICIAIS
# ======================================================
load_dotenv()

API_KEY = os.getenv("API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configuração do Firestore
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
db = firestore.Client()
colecao = db.collection("chatbot_ami_mensagens")

# Configuração Gemini
genai.configure(api_key=API_KEY)
MODELO_ESCOLHIDO = "gemini-2.5-flash"


# ======================================================
# 2️⃣ FUNÇÕES DO FIRESTORE
# ======================================================
def salvar_mensagem(user_id, mensagem, resposta):
    """Salva a interação no Firestore"""
    doc_ref = colecao.document(str(user_id)).collection("historico")
    doc_ref.add({
        "mensagem": mensagem,
        "resposta": resposta
    })


def carregar_historico(user_id):
    """Carrega histórico do usuário"""
    doc_ref = colecao.document(str(user_id)).collection("historico")
    docs = doc_ref.stream()

    historico = []
    for d in docs:
        dados = d.to_dict()
        historico.append({
            "usuario": dados.get("mensagem", ""),
            "assistente": dados.get("resposta", "")
        })

    return historico


# ======================================================
# 3️⃣ PROMPT BASE (Ami)
# ======================================================
SYSTEM_INSTRUCTIONS = """
Você é Ami, uma assistente virtual para idosos que responde APENAS dúvidas sobre o uso de celulares Samsung e redes sociais.

Regras:
- Sempre comece acolhendo o idoso.
- Pergunte o nome apenas uma vez. Depois, lembre-se dele pelo histórico.
- Se a fala do idoso parecer reclamação, responda com empatia.
- Se for neutra ou dúvida, use emojis amigáveis.
- Explique passo a passo com palavras simples.
- Não fale sobre assuntos fora de celular Samsung e redes sociais.
"""

def montar_prompt(historico, entrada_usuario):
    ultimos = historico[-6:]
    historico_formatado = ""

    for h in ultimos:
        historico_formatado += f"Usuário: {h['usuario']}\nAmi: {h['assistente']}\n"

    prompt = (
        SYSTEM_INSTRUCTIONS.strip() + "\n\n"
        "Histórico recente:\n" + (historico_formatado if historico_formatado else "Nenhum histórico.") + "\n\n"
        "Pergunta atual:\n" + entrada_usuario
    )
    return prompt


# ======================================================
# 4️⃣ RESPOSTA DO GEMINI
# ======================================================
def responder_assistente(historico, entrada_usuario):
    prompt = montar_prompt(historico, entrada_usuario)

    try:
        llm = genai.GenerativeModel(model_name=MODELO_ESCOLHIDO)
        conteudo = [{"role": "user", "parts": [prompt]}]
        resposta = llm.generate_content(conteudo)
        return resposta.text
    except Exception as e:
        return f"Desculpe, ocorreu um erro ao responder: {e}"


# ======================================================
# 5️⃣ HANDLERS TELEGRAM
# ======================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Eu sou Ami, sua assistente virtual.\nQual o seu nome?")


async def mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    texto = update.message.text

    historico = carregar_historico(user_id)

    msg_temp = await update.message.reply_text("💭 Ami está pensando...")
    await asyncio.sleep(1.2)

    resposta = responder_assistente(historico, texto)
    salvar_mensagem(user_id, texto, resposta)

    await msg_temp.edit_text(resposta)

    # Envia áudio
    try:
        audio_path = f"resposta_{user_id}.mp3"
        tts = gTTS(resposta, lang="pt")
        tts.save(audio_path)

        with open(audio_path, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)

        os.remove(audio_path)

    except Exception as e:
        await update.message.reply_text(f"(Erro ao gerar áudio: {e})")


# ======================================================
# 6️⃣ EXECUÇÃO
# ======================================================
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem))

    print("🤖 Ami rodando com Firestore...")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
