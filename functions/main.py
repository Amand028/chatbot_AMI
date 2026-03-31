
import os
import json
import logging
import requests 
import io

import google.generativeai as genai
from google.cloud import firestore #historico
from google.cloud import texttospeech # Voz de resposta
from google.cloud import speech #Transcrição de áudio do usuário

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#variaveis globais
API_KEY = os.environ.get("API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# URLs definidas com as variáveis globais
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
TELEGRAM_API_VOICE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVoice"

# endpoints
db = None
colecao = None 
MODELO_ESCOLHIDO = "gemini-2.5-flash"


# historico
def carregar_historico(user_id):
    if db is None or colecao is None:
        logger.error("ERRO: Firestore client não inicializado globalmente.")
        return []
        
    doc_ref = colecao.document(str(user_id)).collection("historico").order_by("timestamp", direction=firestore.Query.ASCENDING).limit(6)
    docs = doc_ref.stream()

    historico = []
    for d in docs:
        dados = d.to_dict()
        historico.append({
            "usuario": dados.get("mensagem", ""),
            "assistente": dados.get("resposta", "")
        })

    return historico

def salvar_mensagem(user_id, mensagem, resposta):
    if db is None or colecao is None:
        logger.error("ERRO: Firestore client não inicializado globalmente.")
        return
        
    doc_ref = colecao.document(str(user_id)).collection("historico")
    doc_ref.add({
        "mensagem": mensagem,
        "resposta": resposta,
        "timestamp": firestore.SERVER_TIMESTAMP
    })


# prompt base

SYSTEM_INSTRUCTIONS = """
Você é Ami, uma assistente virtual para idosos que responde APENAS dúvidas sobre o uso de celulares Samsung e Redes Sociais.

Regras:
- Sempre comece acolhendo o idoso.
- Use emojis amigáveis.
- quando iniciar uma conversa pela primeira vez, SEMPRE perguntar o nome da pessoa.
- SEMPRE mandar a mensagem em texto.

- **Formato da Resposta (CRÍTICO):**
    - Todas as respostas de passo a passo devem começar com uma introdução acolhedora e, em seguida, usar uma linha separadora (`---`).
    - O passo a passo deve ter um **Título de Nível 3** (`*`) seguido pelo subtítulo da dúvida (ex: "Passo a Passo Rápido: Ligar a Lanterna").
    - Use **Lista Numerada** para cada passo.
    - Use **Negrito** (`**`) para destacar as ações principais (ex: **Toque**, **Deslize**).
    - Use uma linha separadora (`---`) após o passo a passo.
    - Finalize com uma pergunta de acompanhamento e encorajamento.
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


def responder_assistente(historico, entrada_usuario):
    prompt_string = montar_prompt(historico, entrada_usuario)

    try:
        llm = genai.GenerativeModel(model_name=MODELO_ESCOLHIDO)
        resposta = llm.generate_content(prompt_string)
        return resposta.text
        
    except Exception as e:
        logger.error(f"Erro ao gerar conteúdo do Gemini: {e}")
        
        if "API key not valid" in str(e):
            return "ERRO_AMI: Desculpe, a conexão com minha inteligência está temporariamente indisponível (Erro de Chave de API). Por favor, tente novamente mais tarde."
        elif "429" in str(e): 
            return "ERRO_AMI: Opa! Tivemos muitas perguntas de uma vez. Por favor, espere um minuto e tente novamente."
        else:
            return f"ERRO_AMI: Desculpe, ocorreu um erro desconhecido ao responder."


#comunicação telegram
def send_chat_action(chat_id, action="typing"): 
    payload = {
        'chat_id': chat_id,
        'action': action
    }
    action_url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendChatAction"
    requests.post(action_url, data=payload)

def send_text_message(chat_id, text):
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    requests.post(TELEGRAM_API_URL, data=payload)


def send_voice_message(chat_id, text, user_id):
    # Gera e envia o áudio da resposta usando a API Google Cloud TTS 
    try:
        tts_client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="pt-BR",
            name="pt-BR-Wavenet-C" 
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        audio_path = f"/tmp/resposta_{user_id}.mp3"
        with open(audio_path, "wb") as out:
            out.write(response.audio_content)

        # Envia o áudio
        with open(audio_path, "rb") as audio_file:
            files = {'voice': audio_file}
            payload = {'chat_id': chat_id}
            requests.post(TELEGRAM_API_VOICE_URL, data=payload, files=files)

        os.remove(audio_path)
        
    except Exception as e:
        logger.error(f"Erro ao gerar ou enviar áudio com Cloud TTS: {e}")
        send_text_message(chat_id, f"(Erro ao gerar áudio. Enviando apenas texto.)")


def get_file_info(file_id):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token: return None
    
    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('result', {})
    return None

def download_file(file_path):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token: return None
        
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    temp_filename = os.path.join("/tmp", os.path.basename(file_path))
    
    response = requests.get(download_url, stream=True)
    if response.status_code == 200:
        with open(temp_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return temp_filename
    return None

def transcribe_audio(audio_path):
    # Transcreve o áudio usando a API Google Cloud Speech-to-Text (não esta funcionando)
    try:
        speech_client = speech.SpeechClient()
        
        with open(audio_path, 'rb') as audio_file:
            content = audio_file.read()
            
        audio = speech.RecognitionAudio(content=content) 
        
        config = speech.RecognitionConfig(
            language_code="pt-BR",
            sample_rate_hertz=16000,
            model='telephony', 
            use_enhanced=True 
        )
        
        response = speech_client.recognize(config=config, audio=audio)
        
        if response.results:
            return response.results[0].alternatives[0].transcript
            
        logger.warning("Transcrição retornou resultados vazios. Tentativa de fallback.")
        return "Desculpe, não consegui entender o que foi dito no áudio. Pode escrever ou repetir?"
        
    except Exception as e:
        logger.error(f"Erro na transcrição de áudio: {e}")
        return "Erro: Falha na transcrição do áudio."
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

#ponto de entrada webhook
def telegram_webhook(request):
    global db, colecao, API_KEY
    
    # Inicialização do Firestore
    if db is None:
        db = firestore.Client()
        colecao = db.collection("chatbot_ami_mensagens")
        logger.info("Firestore client inicializado.")

    # Configuração do Gemini 
    if API_KEY: 
        genai.configure(api_key=API_KEY)
        
    # Fim da inicialização

    if request.method != 'POST':
        return 'Método não suportado.', 405
    
    data = request.get_json(silent=True)
    
    if not data or 'message' not in data:
        logger.info("Nenhum dado válido ou campo 'message' encontrado.")
        return 'OK', 200 
        
    message = data['message']
    user_id = str(message['chat']['id'])
    
    # Detecção de Áudio 
    texto = message.get('text', '') 

    if 'voice' in message:
        logger.info("Áudio de usuário detectado, iniciando transcrição.")
        send_chat_action(user_id, action="record_voice") 
        
        voice_file_id = message['voice']['file_id']
        file_info = get_file_info(voice_file_id)
        
        if file_info and file_info.get('file_path'):
            temp_path = download_file(file_info['file_path'])
            if temp_path:
                texto = transcribe_audio(temp_path)
    
    if not texto:
        return 'OK', 200
    
    if texto.lower() == '/start':
        bot_response = "👋 Olá! Eu sou Ami, sua assistente virtual. Como posso ajudar com seu celular Samsung ou Redes Sociais?"
        send_text_message(user_id, bot_response)
        return 'OK', 200
        
    try:
        send_chat_action(user_id, action="typing") 
        
        historico = carregar_historico(user_id)
        
        resposta = responder_assistente(historico, texto)
        
        if resposta.startswith("ERRO_AMI:"):
            send_text_message(user_id, resposta.replace("ERRO_AMI:", "").strip())
        else:
            salvar_mensagem(user_id, texto, resposta)

            send_text_message(user_id, resposta)
            send_voice_message(user_id, resposta, user_id)
        
        return 'OK', 200 
        
    except Exception as e:
        logger.error(f"Erro fatal no processamento: {e}")
        send_text_message(user_id, "Desculpe, ocorreu um erro fatal no servidor. Tente novamente mais tarde.")
        return 'Erro interno do servidor.', 500