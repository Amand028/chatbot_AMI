import google.generativeai as genai

API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.5-pro")

try:
    response = model.generate_content("Olá, Gemini! Você está funcionando?")
    print("✅ Resposta recebida:")
    print(response.text)
except Exception as e:
    print("❌ Erro:", e)



