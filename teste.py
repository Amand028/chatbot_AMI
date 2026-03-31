import google.generativeai as genai

# 🔑 Substitua pela sua chave aqui temporariamente só para teste
API_KEY = "AIzaSyAglW2pfFwwo6ewzqgGmdU22F-ZI3hlaXk"

genai.configure(api_key=API_KEY)

# escolher o modelo
model = genai.GenerativeModel("gemini-2.5-pro")

# fazer uma chamada simples
try: #bloco de tentativas
    response = model.generate_content("Olá, Gemini! Você está funcionando?")
    print("✅ Resposta recebida:")
    print(response.text)
except Exception as e:
    print("❌ Erro:", e)



