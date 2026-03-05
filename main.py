import os
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
from telebot import types

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 1532248370
WEBHOOK_URL = "https://bot-salao-production.up.railway.app/"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

usuarios = {}
HORARIOS_DISPONIVEIS = ["10:00", "11:00", "14:00", "15:00", "16:00"]

# ================= MENU =================

def menu_principal(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📅 Agendar"),
        types.KeyboardButton("📋 Meus agendamentos"),
        types.KeyboardButton("❌ Cancelar")
    )
    bot.send_message(chat_id, "Escolha uma opção:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    menu_principal(message.chat.id)

# ================= ADMIN =================

@bot.message_handler(commands=['admin'])
def admin(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ Sem permissão")
        return

    try:
        with open("agendamentos.txt", "r", encoding="utf-8") as f:
            dados = f.read()

        if dados.strip() == "":
            bot.send_message(ADMIN_ID, "Nenhum agendamento.")
        else:
            bot.send_message(ADMIN_ID, "📊 TODOS OS AGENDAMENTOS:\n\n" + dados)
    except:
        bot.send_message(ADMIN_ID, "Nenhum agendamento.")

# ================= AGENDAR =================

@bot.message_handler(func=lambda m: m.text == "📅 Agendar")
def agendar(message):
    chat_id = message.chat.id
    usuarios[chat_id] = {"etapa": "nome"}
    bot.send_message(chat_id, "Qual seu nome?")

@bot.message_handler(func=lambda m: True)
def fluxo(message):
    chat_id = message.chat.id

    if chat_id not in usuarios:
        return

    etapa = usuarios[chat_id]["etapa"]

    if etapa == "nome":
        usuarios[chat_id]["nome"] = message.text
        usuarios[chat_id]["etapa"] = "telefone"
        bot.send_message(chat_id, "Digite seu telefone:")

    elif etapa == "telefone":
        usuarios[chat_id]["telefone"] = message.text
        usuarios[chat_id]["etapa"] = "servico"
        bot.send_message(chat_id, "Qual serviço deseja?")

    elif etapa == "servico":
        usuarios[chat_id]["servico"] = message.text
        usuarios[chat_id]["etapa"] = "data"
        bot.send_message(chat_id, "Digite a data (DD/MM/AAAA):")

    elif etapa == "data":
        try:
            data_escolhida = datetime.strptime(message.text, "%d/%m/%Y")
            hoje = datetime.now()
            limite = hoje + timedelta(days=30)

            if data_escolhida.date() < hoje.date():
                bot.send_message(chat_id, "❌ Não pode agendar para data passada.")
                return

            if data_escolhida > limite:
                bot.send_message(chat_id, "❌ Só é possível agendar até 30 dias à frente.")
                return

            usuarios[chat_id]["data"] = message.text
            usuarios[chat_id]["etapa"] = "horario"

            markup = types.InlineKeyboardMarkup()

            try:
                with open("agendamentos.txt", "r", encoding="utf-8") as f:
                    linhas = f.readlines()
                    horarios_ocupados = [
                        l.split("|")[5].split(":")[1].strip()
                        for l in linhas
                        if f"Data:{message.text}" in l
                    ]
            except:
                horarios_ocupados = []

            for h in HORARIOS_DISPONIVEIS:
                if h in horarios_ocupados:
                    markup.add(types.InlineKeyboardButton(f"{h} ❌", callback_data="ocupado"))
                else:
                    markup.add(types.InlineKeyboardButton(f"{h} ✅", callback_data=h))

            bot.send_message(chat_id, "Escolha o horário:", reply_markup=markup)

        except:
            bot.send_message(chat_id, "Formato inválido. Use DD/MM/AAAA.")

# ================= CALLBACK =================

@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    chat_id = call.message.chat.id
    data_callback = call.data

    if data_callback == "ocupado":
        bot.answer_callback_query(call.id, "Esse horário já está ocupado.")
        return

    nome = usuarios[chat_id]["nome"]
    telefone = usuarios[chat_id]["telefone"]
    servico = usuarios[chat_id]["servico"]
    data_agendada = usuarios[chat_id]["data"]
    horario = data_callback

    try:
        with open("agendamentos.txt", "r", encoding="utf-8") as f:
            linhas = f.readlines()
            for l in linhas:
                if f"Data:{data_agendada}" in l and f"Horário:{horario}" in l:
                    bot.answer_callback_query(call.id, "Horário acabou de ser ocupado.")
                    return
    except:
        pass

    with open("agendamentos.txt", "a", encoding="utf-8") as f:
        f.write(f"ID:{chat_id} | Nome:{nome} | Telefone:{telefone} | Serviço:{servico} | Data:{data_agendada} | Horário:{horario}\n")

    bot.send_message(chat_id, f"✅ Agendado para {data_agendada} às {horario}")
    bot.send_message(ADMIN_ID, f"📢 Novo agendamento!\n{nome} | {servico} | {data_agendada} | {horario}")

    del usuarios[chat_id]
    menu_principal(chat_id)

# ================= RELATÓRIO AUTOMÁTICO =================

def relatorio_diario():
    while True:
        agora = datetime.now()
        if agora.hour == 20 and agora.minute == 30:
            hoje = agora.strftime("%d/%m/%Y")
            relatorio = []
            try:
                with open("agendamentos.txt", "r", encoding="utf-8") as f:
                    for l in f.readlines():
                        if f"Data:{hoje}" in l:
                            relatorio.append(l.strip())
            except:
                pass

            if relatorio:
                texto = f"📊 Relatório do Dia – {hoje}\n\nTotal: {len(relatorio)}\n\n"
                for r in relatorio:
                    partes = r.split("|")
                    nome = partes[1].split(":")[1].strip()
                    servico = partes[3].split(":")[1].strip()
                    horario = partes[5].split(":")[1].strip()
                    texto += f"• {nome} – {horario} – {servico}\n"
                bot.send_message(ADMIN_ID, texto)
            else:
                bot.send_message(ADMIN_ID, f"📊 Relatório do Dia – {hoje}\n\nNenhum agendamento hoje.")

            time.sleep(60)

        time.sleep(30)

threading.Thread(target=relatorio_diario).start()

# ================= WEBHOOK =================

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.stream.read().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

@app.route('/', methods=['GET'])
def check():
    return "Bot ativo", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
