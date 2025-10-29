import os
import asyncio
import sqlite3
from gtts import gTTS
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# 🔹 Carrega variáveis de ambiente
load_dotenv()
API_KEY = os.getenv("API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

genai.configure(api_key=API_KEY)
MODELO_ESCOLHIDO = "gemini-1.5"  # modelo compatível com generate_text

# 🔹 Banco de dados SQLite
DB_PATH = "chatbot_ami.db"

def inicializar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            usuario TEXT,
            assistente TEXT
        )
    """)
    conn.commit()
    conn.close()

def salvar_historico(user_id, usuario, assistente):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historico (user_id, usuario, assistente) VALUES (?, ?, ?)",
                   (user_id, usuario, assistente))
    conn.commit()
    conn.close()

def carregar_historico(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT usuario, assistente FROM historico WHERE user_id = ?", (user_id,))
    dados = cursor.fetchall()
    conn.close()
    return [{"usuario": u, "assistente": a} for u, a in dados]

# 🔹 Prompt do assistente
SYSTEM_INSTRUCTIONS = """
Você é Ami, uma assistente virtual para idosos que responde APENAS dúvidas sobre o uso de celulares Samsung e redes sociais.

Regras:
- Sempre comece acolhendo o idoso.
- Primeiro pergunte o nome da pessoa, só depois pergunte no que pode ajudar.
- Se a fala do idoso parecer uma reclamação, responda de forma empática.
- Se for neutra ou elogio, use emojis amigáveis.
- Explique de forma simples e clara como usar o celular.
- Nunca fale de assuntos que não sejam celulares Samsung ou redes sociais.
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

# 🔹 Gerador de respostas (Gemini via generate_text)
def responder_assistente(historico, entrada_usuario):
    prompt = montar_prompt(historico, entrada_usuario)
    try:
        resposta = genai.generate_text(
            model=MODELO_ESCOLHIDO,
            prompt=prompt,
            temperature=0.7
        )
        return resposta.text
    except Exception as e:
        return f"Desculpe, ocorreu um erro ao responder: {e}"

# 🔹 Handlers do Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Olá! Eu sou Ami, sua assistente virtual.\nQual o seu nome?")

async def mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    texto = update.message.text
    historico = carregar_historico(user_id)

    mensagem_pensando = await update.message.reply_text("💭 Ami está pensando...")
    await asyncio.sleep(1.2)

    resposta = responder_assistente(historico, texto)
    salvar_historico(user_id, texto, resposta)

    await mensagem_pensando.edit_text(resposta)

    # Gera áudio TTS
    try:
        tts = gTTS(resposta, lang="pt")
        audio_path = f"resposta_{user_id}.mp3"
        tts.save(audio_path)
        with open(audio_path, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)
        os.remove(audio_path)
    except Exception as e:
        await update.message.reply_text(f"(Erro ao gerar áudio: {e})")

# 🔹 Execução do bot
def main():
    inicializar_banco()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensagem))

    print("🤖 Ami rodando no Render (ou localmente)...")
    port = int(os.environ.get("PORT", 8080))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
