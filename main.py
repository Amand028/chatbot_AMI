from dotenv import load_dotenv
import os
import google.generativeai as genai


load_dotenv()
API_KEY = os.getenv("API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


genai.configure(api_key=API_KEY)
MODELO_ESCOLHIDO = "gemini-2.5-pro"


def responder_assistente(historico, entrada_usuario=None, imagem=None, audio=None):

   
    instrucoes = """ 
    Você é Ami, uma assistente virtual para idosos que responde APENAS dúvidas
    sobre o uso de celulares Samsung.

    Regras:
    - Sempre comece acolhendo o idoso.
    - Primeiro pergunte o nome da pessoa, só depois pergunte no que pode ajudar.
    - Se a fala do idoso parecer uma reclamação, responda de forma empática.
    - Se for neutra ou elogio, use alguns emojis amigáveis.
    - Explique de forma simples, curta e clara como usar o celular.
    - Se receber imagem, use a descrição para ajudar.
    - Se receber áudio, considere o que foi transcrito.
    - Nunca fale de assuntos que não sejam celulares Samsung.
    """

    conteudo = [{"role": "user", "parts": [instrucoes]}]

  
    for h in historico:
        conteudo.append({"role": "user", "parts": [h["usuario"]]})
        conteudo.append({"role": "model", "parts": [h["assistente"]]})

    
    if entrada_usuario:
        conteudo.append({"role": "user", "parts": [entrada_usuario]})

    if imagem:
        conteudo.append({"role": "user", "parts": [f"[Imagem enviada: {imagem}]"]})

    if audio:
        conteudo.append({"role": "user", "parts": [f"[Áudio enviado: {audio}]"]})

    llm = genai.GenerativeModel(model_name=MODELO_ESCOLHIDO)
    resposta = llm.generate_content(conteudo)
    return resposta.text


def main():
    print("Olá! Eu sou Ami, sua assistente virtual.")
    print("Assistente: Qual o seu nome?")
    historico = []

    while True:
        entrada = input("Você: ")

        if entrada.lower() == "/sair":
            print("Assistente: Até logo! Cuide-se")
            break

        imagem, audio, texto = None, None, None

        if entrada.startswith("/img"):
            caminho = entrada.replace("/img", "").strip()
            imagem = caminho
        elif entrada.startswith("/audio"):
            caminho = entrada.replace("/audio", "").strip()
            audio = caminho
        else:
            texto = entrada

        resposta = responder_assistente(
            historico, entrada_usuario=texto, imagem=imagem, audio=audio
        )

        print(f"\nAssistente: {resposta}\n")

        historico.append({"usuario": entrada, "assistente": resposta})


if __name__ == "__main__":   #evita que o chatbot rode automaticamente
    main()
