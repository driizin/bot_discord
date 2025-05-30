import discord
from discord.ext import commands
import json
import os
import random

TOKEN = os.getenv('DISCORD_TOKEN')

# --- Configurações do Bot ---
intents = discord.Intents.default()
intents.message_content = True # Necessário para ler o conteúdo da mensagem, mesmo que seja para comandos de barra.
bot = commands.Bot(command_prefix="!", intents=intents) # O prefixo "!" é apenas um fallback, foco são comandos de barra.

# --- Variáveis Globais do Jogo ---
PLAYER_DATA_FILE = 'detective_data.json' # Arquivo para salvar o progresso dos jogadores
MAX_ATTEMPTS = 7 # Número máximo de tentativas por caso

# Dicionário de palavras secretas por categoria
# Você pode adicionar mais categorias e palavras aqui!
SECRET_WORDS = {
    "animais": ["ELEFANTE", "GIRAFA", "CACHORRO", "GATO", "PASSARO", "COBRA", "LEAO", "TIGRE", "ZEBRA"],
    "filmes": ["VINGADORES", "MATRIX", "TITANIC", "GUERRA", "AVATAR", "CORINGA", "DUNA", "PARASITA"],
    "comida": ["CHOCOLATE", "PIZZA", "HAMBURGUER", "ARROZ", "FEIJAO", "MACARRAO", "SALADA", "FRANGO"],
    "paises": ["BRASIL", "CANADA", "JAPAO", "ESPANHA", "ITALIA", "INDIA", "MEXICO", "AUSTRALIA"],
    "frutas": ["BANANA", "MACA", "LARANJA", "UVA", "ABACAXI", "MORANGO", "MELANCIA", "PERA"]
}

# Dicionário para armazenar o estado atual dos casos dos jogadores em memória
# Será carregado do arquivo ao iniciar e salvo periodicamente/ao desligar.
# Ex: {user_id: {'word': 'ABC', 'revealed': ['A', '_', '_'], 'guessed_letters': ['A', 'X'], 'attempts_left': 5, 'category': 'FILMES'}}
game_states = {}

# --- Funções de Persistência de Dados ---
def load_game_states():
    """Carrega os dados dos jogos dos jogadores do arquivo JSON."""
    global game_states
    if os.path.exists(PLAYER_DATA_FILE):
        with open(PLAYER_DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                game_states = json.load(f)
                print(f"Estados de jogo carregados de {PLAYER_DATA_FILE}")
            except json.JSONDecodeError:
                print(f"Erro ao decodificar JSON de {PLAYER_DATA_FILE}. Iniciando com dados vazios.")
                game_states = {}
    else:
        print(f"Arquivo {PLAYER_DATA_FILE} não encontrado. Iniciando com dados vazios.")
        game_states = {}

def save_game_states():
    """Salva os dados dos jogos dos jogadores no arquivo JSON."""
    with open(PLAYER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(game_states, f, indent=4)
    print(f"Estados de jogo salvos em {PLAYER_DATA_FILE}")

# --- Eventos do Bot ---
@bot.event
async def on_ready():
    """Executado quando o bot está online e pronto."""
    print(f"Bot conectado como {bot.user}")
    load_game_states() # Carrega os dados dos jogos ao iniciar

    # Sincroniza os comandos de barra com o Discord.
    try:
        synced = await bot.tree.sync() # Sincroniza comandos globais
        print(f"Sincronizei {len(synced)} comando(s) de barra.")
    except Exception as e:
        print(f"Erro ao sincronizar comandos de barra: {e}")

# --- Comandos de Barra do Jogo ---

@bot.tree.command(name="iniciar_caso", description="Inicia um novo mistério para você resolver!")
@discord.app_commands.describe(categoria="Escolha uma categoria (opcional): animais, filmes, comida, paises, frutas")
async def iniciar_caso(interaction: discord.Interaction, categoria: str = None):
    """
    Inicia um novo caso para o jogador.
    Se já houver um caso em andamento, pergunta se deseja reiniciar.
    """
    user_id = str(interaction.user.id)

    if user_id in game_states and game_states[user_id]['attempts_left'] > 0:
        await interaction.response.send_message(
            "Você já tem um mistério em andamento! Deseja reiniciá-lo? "
            "Se sim, use `/iniciar_caso` novamente para um novo caso. "
            "Se não, continue jogando com `/status_caso` ou `/adivinhar`.",
            ephemeral=True
        )
        return

    chosen_category = categoria.upper() if categoria else None
    
    # Valida a categoria
    if chosen_category and chosen_category not in [c.upper() for c in SECRET_WORDS.keys()]:
        available_categories = ", ".join([c.lower() for c in SECRET_WORDS.keys()])
        await interaction.response.send_message(
            f"Categoria '{categoria}' inválida. Categorias disponíveis: {available_categories}. "
            f"Tente `/iniciar_caso [categoria]` ou `/iniciar_caso` para uma categoria aleatória.",
            ephemeral=True
        )
        return

    if chosen_category:
        word_category_key = next(k for k in SECRET_WORDS.keys() if k.upper() == chosen_category)
    else:
        word_category_key = random.choice(list(SECRET_WORDS.keys()))

    word = random.choice(SECRET_WORDS[word_category_key])
    
    # Inicializa o estado do jogo para o jogador
    game_states[user_id] = {
        'word': word,
        'revealed': ['_'] * len(word), # Palavra oculta com sublinhados
        'guessed_letters': [], # Letras já tentadas (corretas ou erradas)
        'attempts_left': MAX_ATTEMPTS, # Tentativas restantes
        'category': word_category_key.capitalize() # Categoria do caso
    }
    save_game_states()

    revealed_word_str = " ".join(game_states[user_id]['revealed'])

    await interaction.response.send_message(
        f"📁 Chefe de Polícia: Temos um novo caso, Detetive {interaction.user.display_name}! "
        f"O mistério é sobre **{game_states[user_id]['category'].upper()}**.\n"
        f"Você tem {game_states[user_id]['attempts_left']} tentativas para desvendar a palavra secreta.\n"
        f"A palavra é: `{revealed_word_str}`\n"
        f"Para saber como jogar, use `/instrucoes`."
    )

@bot.tree.command(name="adivinhar", description="Adivinhe uma letra para o mistério!")
@discord.app_commands.describe(letra="A letra que você quer adivinhar")
async def adivinhar(interaction: discord.Interaction, letra: str):
    """
    Permite ao jogador adivinhar uma única letra.
    Atualiza o estado do jogo e informa o resultado.
    """
    user_id = str(interaction.user.id)

    if user_id not in game_states or game_states[user_id]['attempts_left'] <= 0:
        await interaction.response.send_message("Você não tem um caso ativo. Use `/iniciar_caso` para começar um novo mistério!", ephemeral=True)
        return

    if not letra.isalpha() or len(letra) != 1:
        await interaction.response.send_message("Por favor, adivinhe apenas uma letra (A-Z).", ephemeral=True)
        return

    current_game = game_states[user_id]
    guess = letra.upper()
    word = current_game['word']
    revealed = current_game['revealed']
    guessed_letters = current_game['guessed_letters']

    if guess in guessed_letters:
        await interaction.response.send_message(f"Você já tentou a letra `{guess}` antes. Letras tentadas: `{', '.join(guessed_letters)}`", ephemeral=True)
        return

    guessed_letters.append(guess)
    message_to_send = ""
    
    if guess in word:
        for i, char in enumerate(word):
            if char == guess:
                revealed[i] = guess
        message_to_send = f"🔍 Boa, Detetive! A letra `{guess}` está no mistério!\n"
    else:
        current_game['attempts_left'] -= 1
        message_to_send = f"🚨 Pista Falsa! A letra `{guess}` não está no arquivo.\n"
        message_to_send += f"Você tem **{current_game['attempts_left']}** tentativas restantes.\n"

    revealed_word_str = " ".join(revealed)
    message_to_send += f"A palavra é: `{revealed_word_str}`\n"
    message_to_send += f"Letras já tentadas: `{', '.join(sorted(guessed_letters))}`"

    save_game_states() # Salva o estado do jogo após a adivinhação

    # Verifica se o jogo acabou
    if "_" not in revealed:
        await interaction.response.send_message(
            f"🎉 **CASO RESOLVIDO!** Parabéns, Detetive {interaction.user.display_name}! "
            f"A palavra era: `{word}`. Você desvendou o mistério!"
        )
        del game_states[user_id] # Remove o jogo após a vitória
        save_game_states()
    elif current_game['attempts_left'] <= 0:
        await interaction.response.send_message(
            f"💔 **CASO ARQUIVADO!** Você ficou sem tentativas, Detetive {interaction.user.display_name}. "
            f"A palavra secreta era: `{word}`. Mais sorte na próxima vez!"
        )
        del game_states[user_id] # Remove o jogo após a derrota
        save_game_states()
    else:
        await interaction.response.send_message(message_to_send)


@bot.tree.command(name="resolver", description="Tente resolver o mistério adivinhando a palavra inteira!")
@discord.app_commands.describe(palavra="A palavra inteira que você acha que é a solução")
async def resolver(interaction: discord.Interaction, palavra: str):
    """
    Permite ao jogador adivinhar a palavra inteira.
    Verifica se a adivinhação está correta ou se o jogo termina.
    """
    user_id = str(interaction.user.id)

    if user_id not in game_states or game_states[user_id]['attempts_left'] <= 0:
        await interaction.response.send_message("Você não tem um caso ativo. Use `/iniciar_caso` para começar um novo mistério!", ephemeral=True)
        return

    current_game = game_states[user_id]
    guess_word = palavra.upper()
    actual_word = current_game['word']

    if guess_word == actual_word:
        await interaction.response.send_message(
            f"🎉 **CASO RESOLVIDO!** Parabéns, Detetive {interaction.user.display_name}! "
            f"A palavra era: `{actual_word}`. Você é um gênio!"
        )
        del game_states[user_id] # Remove o jogo após a vitória
        save_game_states()
    else:
        current_game['attempts_left'] -= 1
        message_to_send = f"❌ Essa não é a palavra, Detetive. Mais uma pista falsa!\n"
        message_to_send += f"Você tem **{current_game['attempts_left']}** tentativas restantes.\n"
        message_to_send += f"A palavra atual: `{ ' '.join(current_game['revealed']) }`"

        save_game_states() # Salva o estado do jogo após a adivinhação

        if current_game['attempts_left'] <= 0:
            await interaction.response.send_message(
                f"💔 **CASO ARQUIVADO!** Você ficou sem tentativas, Detetive {interaction.user.display_name}. "
                f"A palavra secreta era: `{actual_word}`. Mais sorte na próxima vez!"
            )
            del game_states[user_id] # Remove o jogo após a derrota
            save_game_states()
        else:
            await interaction.response.send_message(message_to_send)


@bot.tree.command(name="status_caso", description="Mostra o status atual do seu mistério (palavra, tentativas, letras tentadas).")
async def status_caso(interaction: discord.Interaction):
    """
    Mostra o status atual do caso do jogador.
    """
    user_id = str(interaction.user.id)

    if user_id not in game_states or game_states[user_id]['attempts_left'] <= 0:
        await interaction.response.send_message("Você não tem um caso ativo. Use `/iniciar_caso` para começar um novo mistério!", ephemeral=True)
        return

    current_game = game_states[user_id]
    revealed_word_str = " ".join(current_game['revealed'])
    
    status_message = (
        f"🕵️‍♂️ **Status do Seu Caso - Categoria: {current_game['category']}**\n"
        f"Palavra: `{revealed_word_str}`\n"
        f"Tentativas Restantes: **{current_game['attempts_left']}**\n"
        f"Letras já tentadas: `{', '.join(sorted(current_game['guessed_letters']))}`\n"
        f"Para mais detalhes, use `/instrucoes`."
    )
    await interaction.response.send_message(status_message, ephemeral=True)


@bot.tree.command(name="instrucoes", description="Mostra como jogar o 'Detetive da Palavra Secreta'.")
async def instrucoes(interaction: discord.Interaction):
    """
    Comando para exibir o guia completo de como jogar o jogo 'Detetive da Palavra Secreta'.
    A mensagem é enviada como efêmera (visível apenas para o usuário que chamou).
    """
    instructions_message = (
        "**Guia do Detetive da Palavra Secreta** 🕵️‍♂️\n\n"
        "Seu objetivo é desvendar a palavra secreta antes que suas tentativas acabem!\n\n"
        "**Comandos Principais:**\n"
        "➡️ `/iniciar_caso [categoria]`: Começa um novo mistério. (Ex: `/iniciar_caso filmes` ou só `/iniciar_caso` para aleatório)\n"
        "➡️ `/adivinhar <letra>`: Tente adivinhar uma letra que você acha que está na palavra.\n"
        "➡️ `/resolver <palavra>`: Se você acha que sabe a resposta, tente adivinhar a palavra inteira.\n"
        "➡️ `/status_caso`: Veja o progresso atual do seu mistério: a palavra, tentativas restantes e letras já tentadas.\n"
        "➡️ `/instrucoes`: Exibe este guia novamente.\n\n"
        "**O Jogo:**\n"
        " - Você começa com **7 tentativas**. Cada letra errada ou palavra inteira errada remove 1 tentativa.\n"
        " - As letras serão reveladas na palavra à medida que você as adivinha corretamente.\n"
        " - Se acertar a palavra, você ganha! Se acabar as tentativas, o mistério permanece sem solução...\n\n"
        "**Categorias Disponíveis:**\n"
        f"{', '.join([c.capitalize() for c in SECRET_WORDS.keys()])}\n\n"
        "Boa sorte, Detetive!"
    )
    await interaction.response.send_message(instructions_message, ephemeral=True)


# --- Token do Bot ---
# ATENÇÃO: Substitua "SEU_TOKEN_DO_BOT_AQUI" pelo token real do seu bot.
# Mantenha seu token em segredo e nunca o compartilhe publicamente!
if TOKEN is None:
    print("Erro: A variável de ambiente 'DISCORD_TOKEN' não foi definida no sistema.")
    print("Por favor, defina a variável 'DISCORD_TOKEN' com o valor do seu token do bot.")

bot.run("TOKEN")