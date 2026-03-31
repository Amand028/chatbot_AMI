import google.generativeai as genai

API_KEY = "AIzaSyAglW2pfFwwo6ewzqgGmdU22F-ZI3hlaXk"

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-pro")

try:
    response = model.generate_content("Olá, Gemini! Você está funcionando?")
    print("✅ Resposta recebida:")
    print(response.text)
except Exception as e:
    print("❌ Erro:", e)



