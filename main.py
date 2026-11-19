import os
import sys
import random
import math
import struct
import tempfile
import wave

# Evita que o Kivy tente interpretar argumentos do Spyder
os.environ["KIVY_NO_ARGS"] = "1"

from kivy.config import Config

# Desactiva o provider de caneta do Windows que pode causar
# o erro WM_PenProvider no encerramento.
if sys.platform == "win32":
    Config.set("input", "wm_pen", "disable")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager

# Tamanho de telemóvel só no PC; no Android o ecrã define o tamanho
if platform in ("win", "linux", "macosx"):
    Window.size = (400, 650)
Window.clearcolor = (0.06, 0.22, 0.15, 1)

# =========================================================
# CONSTANTES
# =========================================================

DURACAO = 30
N_CASAS = 40

MIN_EQUIPAS = 2
MAX_EQUIPAS = 4

CORES_CASAS = [
    (0.86, 0.36, 0.30, 1),
    (0.95, 0.70, 0.22, 1),
    (0.28, 0.60, 0.80, 1),
    (0.42, 0.70, 0.40, 1),
]

CORES_EQUIPAS = [
    (0.20, 0.55, 0.95, 1),
    (0.95, 0.78, 0.20, 1),
    (0.90, 0.25, 0.25, 1),
    (0.25, 0.75, 0.40, 1),
]

NOMES_EQUIPAS = ["AZUL", "AMARELA", "VERMELHA", "VERDE"]

# Deslocamento de cada peão dentro da casa (fracção do tabuleiro),
# para os peões não ficarem uns por cima dos outros.
DESLOCAMENTOS = [
    (-0.018, 0.018),
    (0.018, 0.018),
    (-0.018, -0.018),
    (0.018, -0.018),
]

CONTROLO = [
    (0.09, 0.08), (0.30, 0.06), (0.55, 0.10), (0.78, 0.12),
    (0.91, 0.22), (0.88, 0.36),
    (0.68, 0.42), (0.45, 0.36), (0.22, 0.38),
    (0.09, 0.50), (0.14, 0.63),
    (0.35, 0.62), (0.58, 0.68), (0.80, 0.64),
    (0.91, 0.75), (0.84, 0.88),
    (0.62, 0.92), (0.40, 0.86), (0.20, 0.90), (0.11, 0.88),
]


def curva_suave(pontos, amostras=14):
    """Cria uma curva suave usando interpolação Catmull-Rom."""
    p = [pontos[0]] + pontos + [pontos[-1]]
    saida = []

    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]

        for k in range(amostras):
            t = k / amostras
            t2 = t * t
            t3 = t * t * t
            ponto = []

            for c in (0, 1):
                v = 0.5 * (
                    2 * p1[c]
                    + (-p0[c] + p2[c]) * t
                    + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2
                    + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3
                )
                ponto.append(v)

            saida.append((ponto[0], ponto[1]))

    saida.append(pontos[-1])
    return saida


def espacar_igual(curva, n):
    """Distribui as casas igualmente ao longo da curva."""
    dist = [0.0]

    for (x1, y1), (x2, y2) in zip(curva, curva[1:]):
        distancia = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        dist.append(dist[-1] + distancia)

    total = dist[-1]
    resultado = []
    j = 0

    for i in range(n):
        alvo = total * i / (n - 1)

        while j < len(dist) - 2 and dist[j + 1] < alvo:
            j += 1

        seg = dist[j + 1] - dist[j]
        f = 0 if seg == 0 else (alvo - dist[j]) / seg

        x = curva[j][0] + f * (curva[j + 1][0] - curva[j][0])
        y = curva[j][1] + f * (curva[j + 1][1] - curva[j][1])
        resultado.append((x, y))

    return resultado


def espacar_letras(texto):
    """O Kivy não tem 'letter_spacing'. Isto imita o efeito com espaços."""
    return "   ".join(" ".join(palavra) for palavra in texto.split())


# A fonte padrão do Kivy não tem os ornamentos ꧁ ꧂ (U+A9C1 e U+A9C2).
# No Windows, a fonte "Javanese Text" tem-nos.
FONTE_ORNAMENTOS = "C:/Windows/Fonts/javatext.ttf"


def assinatura_texto(nome):
    """Devolve ꧁NOME꧂ (ornamentos em fonte própria, nome na fonte normal)."""
    if os.path.exists(FONTE_ORNAMENTOS):
        fonte = "[font=" + FONTE_ORNAMENTOS + "]"
        return fonte + "\ua9c1[/font]" + nome + fonte + "\ua9c2[/font]"

    # Sem a fonte, usa ornamentos simples que qualquer fonte tem
    return "~ " + nome + " ~"


CURVA = curva_suave(CONTROLO)
POSICOES = espacar_igual(CURVA, N_CASAS)

CARTAS = [
    {
        "azul": ["Nelson Mandela", "Futebol", "Maputo", "Lua", "África", "Einstein"],
        "amarelo": ["Napoleão", "Praia", "Computador", "Elefante", "Brasil", "Marte"],
    },
    {
        "azul": ["Eusébio", "Marrabenta", "Oceano Índico", "Violino", "Pirâmide", "Xadrez"],
        "amarelo": ["Michael Jackson", "Basquetebol", "Egipto", "Teatro", "Leão", "Saturno"],
    },
    {
        "azul": ["Samora Machel", "Café", "Nampula", "Computador", "Girafa", "Olimpíadas"],
        "amarelo": ["Nelson Mandela", "Chocolate", "Portugal", "Foguetão", "Física", "Medicina"],
    },
    {
        "azul": ["Cristiano Ronaldo", "Matapa", "Vulcão", "Bicicleta", "Pelé", "Newton"],
        "amarelo": ["Messi", "Carro", "Tubarão", "Amazonas", "Galileu", "Cinema"],
    },
    {
        "azul": ["Ilha de Moçambique", "Telescópio", "Mapiko", "Chuva", "Cinema", "Mercado"],
        "amarelo": ["Torre Eiffel", "Rádio", "Dança", "Montanha", "Água", "Internet"],
    },
    {
        "azul": ["Minato", "Naruto", "Kakashi", "Rasengan", "Konoha", "Sharingan"],
        "amarelo": ["Sasuke", "Itachi", "Akatsuki", "Jutsu", "Hokage", "Kurama"],
    },
    {
        "azul": ["Tesla", "Electricidade", "Magnetismo", "Faraday", "Motor", "Bateria"],
        "amarelo": ["Einstein", "Relatividade", "Átomo", "Laser", "Quântica", "Prisma"],
    },
    {
        "azul": ["África", "Deserto", "Girafa", "Nilo", "Safari", "Cairo"],
        "amarelo": ["Europa", "Alpes", "Paris", "Roma", "Londres", "Madrid"],
    },
]


# =========================================================
# SOM
# =========================================================
# Os sons são gerados pelo próprio jogo na primeira execução e guardados
# na pasta "sons" (ao lado deste ficheiro). Para usar sons teus, basta
# substituir os .wav dessa pasta pelos teus, com os mesmos nomes.
# Para voltar aos sons originais, apaga a pasta "sons".

TAXA = 22050  # amostras por segundo


def _tom(freq, dur, vol=0.5, queda=5.0, forma="seno"):
    """Uma nota que começa forte e vai desaparecendo."""
    n = int(TAXA * dur)
    ataque = int(TAXA * 0.004)
    saida = []

    for i in range(n):
        t = i / TAXA
        fase = freq * t

        if forma == "serra":
            onda = 2.0 * (fase % 1.0) - 1.0
        else:
            onda = (
                math.sin(2 * math.pi * fase)
                + 0.25 * math.sin(4 * math.pi * fase)
            ) / 1.25

        env = math.exp(-queda * i / n)
        if i < ataque:
            env *= i / ataque

        saida.append(vol * env * onda)

    return saida


def _acorde(freqs, dur, vol=0.5, queda=4.0):
    """Várias notas ao mesmo tempo."""
    tons = [_tom(f, dur, vol / len(freqs), queda) for f in freqs]
    return [sum(valores) for valores in zip(*tons)]


def _juntar(*partes):
    """Notas uma a seguir à outra."""
    saida = []
    for parte in partes:
        saida.extend(parte)
    return saida


def _normalizar(amostras, pico):
    """Ajusta o volume para o som atingir o pico indicado (0 a 1)."""
    maximo = max(abs(a) for a in amostras) or 1.0
    return [a * pico / maximo for a in amostras]


# Volume de cada som (1.0 = máximo). Cliques e ticks são mais suaves.
PICOS = {"clique": 0.45, "tick": 0.60}
PICO_PADRAO = 0.85


def _guardar_wav(caminho, amostras):
    with wave.open(caminho, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, a)) * 32767))
            for a in amostras
        ))


def definir_sons():
    return {
        # toque num botão
        "clique": _tom(900, 0.05, 0.35, queda=6),

        # início do turno: três notas a subir
        "comecar": _juntar(
            _tom(523.25, 0.09, 0.5, 3),
            _tom(659.25, 0.09, 0.5, 3),
            _tom(783.99, 0.22, 0.5, 4),
        ),

        # equipa acertou: duas notas alegres
        "certo": _juntar(
            _tom(659.25, 0.09, 0.5, 3),
            _tom(987.77, 0.26, 0.5, 5),
        ),

        # contagem dos últimos 5 segundos
        "tick": _tom(1500, 0.07, 0.45, queda=6),

        # fim do tempo: três notas graves a descer
        "fim": _juntar(
            _tom(392.00, 0.20, 0.40, 2, "serra"),
            _tom(311.13, 0.20, 0.40, 2, "serra"),
            _tom(246.94, 0.50, 0.40, 3, "serra"),
        ),

        # vitória: arpejo e acorde final
        "vitoria": _juntar(
            _tom(523.25, 0.12, 0.5, 3),
            _tom(659.25, 0.12, 0.5, 3),
            _tom(783.99, 0.12, 0.5, 3),
            _acorde([783.99, 1046.50, 1318.51], 0.80, 0.7, 3),
        ),
    }


def gerar_ficheiros_de_som(pasta):
    """Cria os .wav que ainda não existem e devolve {nome: caminho}."""
    os.makedirs(pasta, exist_ok=True)
    caminhos = {}

    for nome, amostras in definir_sons().items():
        caminho = os.path.join(pasta, nome + ".wav")
        if not os.path.exists(caminho):
            amostras = _normalizar(amostras, PICOS.get(nome, PICO_PADRAO))
            _guardar_wav(caminho, amostras)
        caminhos[nome] = caminho

    return caminhos


class GestorSom:

    def __init__(self):
        self.activo = True
        self.volume = 0.8
        self._sons = {}

    def preparar(self):
        # No Android, o código fica numa pasta só de leitura; por isso os
        # sons são guardados na pasta de dados da app (sempre gravável).
        try:
            base = App.get_running_app().user_data_dir
        except Exception:
            base = os.path.dirname(os.path.abspath(__file__))

        try:
            caminhos = gerar_ficheiros_de_som(os.path.join(base, "sons"))
        except OSError:
            # Pasta sem permissão de escrita: usa a pasta temporária
            caminhos = gerar_ficheiros_de_som(
                os.path.join(tempfile.gettempdir(), "30seconds_sons")
            )

        for nome, caminho in caminhos.items():
            som = SoundLoader.load(caminho)

            if som is None:
                Logger.warning("Som: não foi possível carregar " + caminho)
                continue

            som.volume = self.volume
            self._sons[nome] = som

    def tocar(self, nome):
        if not self.activo:
            return

        som = self._sons.get(nome)
        if som is None:
            return

        try:
            som.stop()
            som.play()
        except Exception as erro:
            Logger.warning("Som: erro ao tocar " + nome + ": " + str(erro))

    def alternar(self):
        self.activo = not self.activo
        return self.activo


SONS = GestorSom()


def com_clique(funcao):
    """Toca o som de clique e depois chama a função."""
    def _executar(*args):
        SONS.tocar("clique")
        funcao()
    return _executar


# =========================================================
# COMPONENTES COMUNS
# =========================================================

class BotaoArredondado(Button):
    """Botão com fundo arredondado que acompanha a posição e o tamanho."""

    def __init__(self, cor=(0.65, 0.78, 0.48, 1), raio=None, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs["background_color"] = (0, 0, 0, 0)
        super().__init__(**kwargs)

        self._cor_base = cor
        raio = dp(14) if raio is None else raio

        with self.canvas.before:
            self._cor_fundo = Color(*cor)
            self._rect_fundo = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[raio]
            )

        self.bind(
            pos=self._actualizar,
            size=self._actualizar,
            state=self._actualizar_cor,
        )

    def _actualizar(self, *args):
        self._rect_fundo.pos = self.pos
        self._rect_fundo.size = self.size

    def _actualizar_cor(self, *args):
        r, g, b, a = self._cor_base
        f = 0.8 if self.state == "down" else 1
        self._cor_fundo.rgba = (r * f, g * f, b * f, a)


class FundoJogo(FloatLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.035, 0.08, 0.065, 1)
            self.bg = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[0]
            )

            Color(0.10, 0.25, 0.18, 0.35)
            Ellipse(pos=(dp(250), dp(500)), size=(dp(180), dp(180)))

            Color(0.12, 0.30, 0.20, 0.25)
            Ellipse(pos=(dp(-80), dp(30)), size=(dp(190), dp(190)))

            Color(0.45, 0.65, 0.45, 0.12)
            Line(
                points=[dp(20), dp(120), dp(160), dp(250), dp(330), dp(150)],
                width=1
            )
            Line(
                points=[dp(50), dp(540), dp(170), dp(430), dp(360), dp(520)],
                width=1
            )

        self.bind(pos=self.actualizar, size=self.actualizar)

    def actualizar(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


class CartaDecorativa(FloatLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.93, 0.88, 0.68, 0.10)
            self.carta = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(10)]
            )

            Color(0.85, 0.72, 0.35, 0.20)
            self.borda = Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, dp(10)
                ),
                width=1
            )

        self.bind(pos=self.actualizar, size=self.actualizar)

        self.add_widget(Label(
            text="?",
            font_size=sp(42),
            bold=True,
            color=(0.90, 0.75, 0.35, 0.35),
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0}
        ))

    def actualizar(self, *args):
        self.carta.pos = self.pos
        self.carta.size = self.size
        self.borda.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(10)
        )


# =========================================================
# ECRÃ 1: CAPA
# =========================================================

class Capa(FloatLayout):

    def __init__(self, ao_jogar, **kwargs):
        super().__init__(**kwargs)

        self.add_widget(FundoJogo())

        self.add_widget(CartaDecorativa(
            size_hint=(None, None),
            size=(dp(95), dp(130)),
            pos_hint={"x": 0.08, "top": 0.82}
        ))

        self.add_widget(CartaDecorativa(
            size_hint=(None, None),
            size=(dp(90), dp(125)),
            pos_hint={"right": 0.92, "top": 0.77}
        ))

        titulo = Label(
            text="30\nSECONDS",
            font_size=sp(48),
            bold=True,
            halign="center",
            valign="middle",
            color=(0.93, 0.82, 0.48, 1),
            size_hint=(0.80, None),
            height=dp(125),
            pos_hint={"center_x": 0.5, "center_y": 0.62}
        )
        titulo.bind(size=lambda obj, v: setattr(obj, "text_size", v))
        self.add_widget(titulo)

        self.add_widget(Label(
            text=espacar_letras("O JOGO DE PALAVRAS"),
            font_size=sp(12),
            bold=True,
            color=(0.78, 0.82, 0.72, 0.85),
            size_hint=(1, None),
            height=dp(30),
            pos_hint={"center_x": 0.5, "center_y": 0.49}
        ))

        frase = Label(
            text="Pensa rápido.\nFala ainda mais rápido.",
            font_size=sp(13),
            halign="center",
            valign="middle",
            color=(0.70, 0.75, 0.68, 0.75),
            size_hint=(0.8, None),
            height=dp(55),
            pos_hint={"center_x": 0.5, "center_y": 0.42}
        )
        frase.bind(size=lambda obj, v: setattr(obj, "text_size", v))
        self.add_widget(frase)

        jogar = BotaoArredondado(
            text="JOGAR",
            font_size=sp(17),
            bold=True,
            color=(0.05, 0.10, 0.07, 1),
            size_hint=(None, None),
            size=(dp(190), dp(52)),
            pos_hint={"center_x": 0.5, "center_y": 0.28}
        )
        jogar.bind(on_release=com_clique(ao_jogar))
        self.add_widget(jogar)

        self.add_widget(Label(
            text="Pensa • Descreve • Descobre",
            font_size=sp(9),
            color=(0.55, 0.63, 0.55, 0.40),
            size_hint=(1, None),
            height=dp(20),
            pos_hint={"center_x": 0.5, "y": 0.06}
        ))

        self.add_widget(Label(
            text=assinatura_texto("CINESTRO"),
            markup=True,
            font_size=sp(11),
            italic=True,
            color=(0.75, 0.78, 0.72, 0.35),
            size_hint=(None, None),
            size=(dp(110), dp(22)),
            pos_hint={"right": 0.97, "top": 0.985}
        ))


# =========================================================
# ECRÃ 2: ESCOLHA DO NÚMERO DE EQUIPAS
# =========================================================

class EscolhaEquipas(FloatLayout):

    def __init__(self, ao_escolher, ao_voltar, **kwargs):
        super().__init__(**kwargs)

        self.add_widget(FundoJogo())

        titulo = Label(
            text="QUANTAS\nEQUIPAS?",
            font_size=sp(36),
            bold=True,
            halign="center",
            valign="middle",
            color=(0.93, 0.82, 0.48, 1),
            size_hint=(0.80, None),
            height=dp(100),
            pos_hint={"center_x": 0.5, "center_y": 0.76}
        )
        titulo.bind(size=lambda obj, v: setattr(obj, "text_size", v))
        self.add_widget(titulo)

        # Um botão por opção (2, 3 e 4 equipas)
        alturas = [0.58, 0.45, 0.32]
        cores_botao = [
            (0.65, 0.78, 0.48, 1),
            (0.65, 0.78, 0.48, 1),
            (0.65, 0.78, 0.48, 1),
        ]

        for i, n in enumerate(range(MIN_EQUIPAS, MAX_EQUIPAS + 1)):
            nomes = " • ".join(NOMES_EQUIPAS[:n])

            botao = BotaoArredondado(
                text=(
                    "[b]" + str(n) + " EQUIPAS[/b]\n"
                    "[size=" + str(int(sp(10))) + "]" + nomes + "[/size]"
                ),
                markup=True,
                halign="center",
                valign="middle",
                font_size=sp(18),
                color=(0.05, 0.10, 0.07, 1),
                cor=cores_botao[i],
                size_hint=(None, None),
                size=(dp(290), dp(64)),
                pos_hint={"center_x": 0.5, "center_y": alturas[i]}
            )
            botao.bind(
                on_release=lambda *args, n=n: (SONS.tocar("clique"), ao_escolher(n))
            )
            self.add_widget(botao)

        voltar = BotaoArredondado(
            text="VOLTAR",
            font_size=sp(14),
            bold=True,
            color=(0.85, 0.90, 0.82, 1),
            cor=(0.20, 0.32, 0.26, 1),
            size_hint=(None, None),
            size=(dp(140), dp(44)),
            pos_hint={"center_x": 0.5, "center_y": 0.17}
        )
        voltar.bind(on_release=com_clique(ao_voltar))
        self.add_widget(voltar)


# =========================================================
# TABULEIRO
# =========================================================

class Casa(FloatLayout):

    def __init__(self, texto, cor, tamanho=dp(28), fonte=sp(13),
                 cor_texto=(1, 1, 1, 1), **kwargs):
        super().__init__(size_hint=(None, None), size=(tamanho, tamanho), **kwargs)

        with self.canvas.before:
            Color(0, 0, 0, 0.35)
            self.sombra = Ellipse(pos=self.pos, size=self.size)

            Color(1, 0.96, 0.85, 1)
            self.anel = Ellipse(pos=self.pos, size=self.size)

            Color(*cor)
            self.miolo = Ellipse(pos=self.pos, size=self.size)

        self.bind(pos=self.actualizar, size=self.actualizar)

        self.add_widget(Label(
            text=str(texto),
            font_size=fonte,
            color=cor_texto,
            bold=True,
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        ))

        self.actualizar()

    def actualizar(self, *args):
        d = dp(1.5)
        borda = dp(2.5)

        self.sombra.pos = (self.x + d, self.y - d)
        self.sombra.size = self.size
        self.anel.pos = self.pos
        self.anel.size = self.size

        self.miolo.pos = (self.x + borda, self.y + borda)
        self.miolo.size = (self.width - 2 * borda, self.height - 2 * borda)


class Peao(FloatLayout):

    def __init__(self, cor, **kwargs):
        tamanho = dp(20)
        super().__init__(size_hint=(None, None), size=(tamanho, tamanho), **kwargs)

        with self.canvas.before:
            Color(0, 0, 0, 0.4)
            self.sombra = Ellipse(pos=self.pos, size=self.size)

            Color(1, 0.95, 0.80, 1)
            self.anel = Ellipse(pos=self.pos, size=self.size)

            Color(*cor)
            self.corpo = Ellipse(pos=self.pos, size=self.size)

        self.bind(pos=self.actualizar, size=self.actualizar)
        self.actualizar()

    def actualizar(self, *args):
        d = dp(2)

        self.sombra.pos = (self.x + dp(2), self.y - dp(2))
        self.sombra.size = self.size
        self.anel.pos = self.pos
        self.anel.size = self.size

        self.corpo.pos = (self.x + d, self.y + d)
        self.corpo.size = (self.width - 2 * d, self.height - 2 * d)


class Tabuleiro(FloatLayout):

    def __init__(self, n_equipas, **kwargs):
        super().__init__(**kwargs)

        self.n_equipas = n_equipas

        # Casa onde está cada peão (guardada aqui para sobreviver
        # a redimensionamentos da janela)
        self.casa_peoes = [0] * n_equipas
        self.peoes = []
        self.casas_normais = []

        with self.canvas.before:
            Color(0.04, 0.16, 0.11, 1)
            self.painel = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(18)]
            )

            Color(0.85, 0.68, 0.30, 1)
            self.moldura = Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, dp(18)
                ),
                width=dp(2),
            )

            Color(0, 0, 0, 0.35)
            self.sombra = Line(
                points=[], width=dp(21), cap="round", joint="round"
            )

            Color(0.30, 0.19, 0.09, 1)
            self.contorno = Line(
                points=[], width=dp(19), cap="round", joint="round"
            )

            Color(0.87, 0.76, 0.55, 1)
            self.pista = Line(
                points=[], width=dp(16), cap="round", joint="round"
            )

            Color(1, 1, 1, 0.35)
            self.tracejado = Line(
                points=[], width=dp(1), dash_length=dp(5), dash_offset=dp(5)
            )

        for i, (x, y) in enumerate(POSICOES):
            if i == 0:
                casa = Casa(
                    "INÍCIO", (0.15, 0.55, 0.30, 1),
                    tamanho=dp(44), fonte=sp(9)
                )
            elif i == N_CASAS - 1:
                casa = Casa(
                    "META", (0.98, 0.82, 0.30, 1),
                    tamanho=dp(44), fonte=sp(10),
                    cor_texto=(0.25, 0.15, 0.05, 1)
                )
            else:
                casa = Casa(i + 1, CORES_CASAS[i % len(CORES_CASAS)])
                self.casas_normais.append(casa)

            casa.pos_hint = {"center_x": x, "center_y": y}
            self.add_widget(casa)

        # Um peão por equipa, por cima das casas
        for i in range(n_equipas):
            peao = Peao(CORES_EQUIPAS[i])
            self.peoes.append(peao)
            self.add_widget(peao)

        # Só liga o bind depois de tudo existir
        self.bind(pos=self.actualizar, size=self.actualizar)
        self.actualizar()

    def pontos(self, dx=0, dy=0):
        pts = []

        for x, y in CURVA:
            pts.extend([
                self.x + self.width * x + dx,
                self.y + self.height * y + dy,
            ])

        return pts

    def actualizar(self, *args):
        self.painel.pos = self.pos
        self.painel.size = self.size

        self.moldura.rounded_rectangle = (
            self.x, self.y, self.width, self.height, dp(18)
        )

        self.sombra.points = self.pontos(dp(2), -dp(2))
        self.contorno.points = self.pontos()
        self.pista.points = self.pontos()
        self.tracejado.points = self.pontos()

        self.ajustar_casas()
        self.posicionar_peoes()

    def ajustar_casas(self):
        """Encolhe as casas se o tabuleiro for baixo, para não se sobreporem."""
        if not self.width or not self.height:
            return

        dmin = min(
            math.dist(
                (a[0] * self.width, a[1] * self.height),
                (b[0] * self.width, b[1] * self.height),
            )
            for a, b in zip(POSICOES, POSICOES[1:])
        )

        tam = max(dp(18), min(dp(28), dmin * 0.92))

        for casa in self.casas_normais:
            casa.size = (tam, tam)

        self._trigger_layout()

    def posicionar_peao(self, equipa):
        """Coloca um peão na casa onde ele realmente está."""
        x, y = POSICOES[self.casa_peoes[equipa]]
        dx, dy = DESLOCAMENTOS[equipa]

        self.peoes[equipa].center = (
            self.x + self.width * (x + dx),
            self.y + self.height * (y + dy)
        )

    def posicionar_peoes(self, *args):
        for equipa in range(self.n_equipas):
            self.posicionar_peao(equipa)

    def mover_peao(self, equipa, casa):
        self.casa_peoes[equipa] = min(casa, N_CASAS - 1)
        self.posicionar_peao(equipa)

    def reiniciar_peoes(self):
        self.casa_peoes = [0] * self.n_equipas
        self.posicionar_peoes()


# =========================================================
# ECRÃ 3: JOGO
# =========================================================

class Jogo30Seconds(FloatLayout):

    def __init__(self, n_equipas, ao_menu, **kwargs):
        super().__init__(**kwargs)

        self.n_equipas = n_equipas
        self.ao_menu = ao_menu

        self.equipa_atual = 0
        self.posicoes = [0] * n_equipas
        self.tempo = DURACAO
        self.em_jogo = False
        self.fim_de_jogo = False

        self.carta_atual = None
        self.lado_atual = 0
        self.cartas_embaralhadas = []

        self.tabuleiro = None

        self.criar_interface()
        self.preparar_vez()

    def criar_interface(self):
        raiz = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            spacing=dp(8)
        )

        cabecalho = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(60),
            spacing=dp(2)
        )

        self.titulo = Label(
            text="30 SECONDS",
            font_size=sp(25),
            bold=True,
            color=(1, 0.84, 0.35, 1)
        )

        self.info = Label(
            text="Equipa AZUL",
            font_size=sp(15),
            bold=True,
            color=CORES_EQUIPAS[0]
        )

        cabecalho.add_widget(self.titulo)
        cabecalho.add_widget(self.info)
        raiz.add_widget(cabecalho)

        # O tabuleiro ocupa todo o espaço que sobra.
        self.tabuleiro = Tabuleiro(self.n_equipas)
        raiz.add_widget(self.tabuleiro)

        self.painel_carta = FloatLayout(
            size_hint_y=None,
            height=dp(170)
        )

        with self.painel_carta.canvas.before:
            Color(0.10, 0.12, 0.10, 1)
            self.fundo_carta = RoundedRectangle(
                pos=self.painel_carta.pos,
                size=self.painel_carta.size,
                radius=[dp(16)]
            )

            Color(0.85, 0.68, 0.30, 1)
            self.borda_carta = Line(
                rounded_rectangle=(
                    self.painel_carta.x,
                    self.painel_carta.y,
                    self.painel_carta.width,
                    self.painel_carta.height,
                    dp(16)
                ),
                width=dp(2)
            )

            self.cor_fundo = Color(0.20, 0.55, 0.95, 0.18)

            self.faixa_carta = RoundedRectangle(
                pos=self.painel_carta.pos,
                size=self.painel_carta.size,
                radius=[dp(12)]
            )

        self.painel_carta.bind(
            pos=self.actualizar_carta_fundo,
            size=self.actualizar_carta_fundo
        )

        self.label_palavras = Label(
            text="Prima COMEÇAR",
            font_size=sp(18),
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        self.label_palavras.bind(
            size=self.label_palavras.setter("text_size")
        )

        self.painel_carta.add_widget(self.label_palavras)
        raiz.add_widget(self.painel_carta)

        controlos = BoxLayout(
            size_hint_y=None,
            height=dp(52),
            spacing=dp(8)
        )

        self.botao_comecar = Button(
            text="COMEÇAR",
            font_size=sp(17),
            bold=True,
            background_normal="",
            background_color=(0.15, 0.65, 0.32, 1)
        )
        self.botao_comecar.bind(on_release=self.comecar_turno)

        self.botao_passa = Button(
            text="PASSA",
            font_size=sp(17),
            bold=True,
            background_normal="",
            background_color=(0.75, 0.20, 0.15, 1),
            disabled=True
        )
        self.botao_passa.bind(on_release=self.passa)

        controlos.add_widget(self.botao_comecar)
        controlos.add_widget(self.botao_passa)
        raiz.add_widget(controlos)

        self.timer = Label(
            text="30",
            font_size=sp(30),
            bold=True,
            color=(1, 0.85, 0.30, 1),
            size_hint_y=None,
            height=dp(36)
        )

        raiz.add_widget(self.timer)
        self.add_widget(raiz)

        # Botões pequenos e discretos nos cantos do cabeçalho,
        # longe de COMEÇAR e PASSA para não haver toques por engano.
        self.botao_menu = BotaoArredondado(
            text="MENU",
            font_size=sp(10),
            bold=True,
            color=(0.85, 0.90, 0.82, 0.65),
            cor=(0.20, 0.32, 0.26, 0.40),
            raio=dp(8),
            size_hint=(None, None),
            size=(dp(54), dp(24)),
            pos_hint={"x": 0.02, "top": 0.99}
        )
        self.botao_menu.bind(on_release=self.sair_para_menu)
        self.add_widget(self.botao_menu)

        self.botao_som = BotaoArredondado(
            text="SOM" if SONS.activo else "MUDO",
            font_size=sp(10),
            bold=True,
            color=(0.85, 0.90, 0.82, 0.65),
            cor=(0.20, 0.32, 0.26, 0.40),
            raio=dp(8),
            size_hint=(None, None),
            size=(dp(54), dp(24)),
            pos_hint={"right": 0.98, "top": 0.99}
        )
        self.botao_som.bind(on_release=self.alternar_som)
        self.add_widget(self.botao_som)

    def actualizar_carta_fundo(self, *args):
        self.fundo_carta.pos = self.painel_carta.pos
        self.fundo_carta.size = self.painel_carta.size

        self.borda_carta.rounded_rectangle = (
            self.painel_carta.x,
            self.painel_carta.y,
            self.painel_carta.width,
            self.painel_carta.height,
            dp(16)
        )

        self.faixa_carta.pos = (
            self.painel_carta.x + dp(10),
            self.painel_carta.y + dp(10)
        )

        self.faixa_carta.size = (
            self.painel_carta.width - dp(20),
            self.painel_carta.height - dp(20)
        )

    def parar(self):
        """Pára o temporizador (usado ao sair do jogo)."""
        self.em_jogo = False
        Clock.unschedule(self.contar_tempo)

    def sair_para_menu(self, *args):
        SONS.tocar("clique")
        self.parar()
        self.ao_menu()

    def alternar_som(self, *args):
        activo = SONS.alternar()
        self.botao_som.text = "SOM" if activo else "MUDO"
        SONS.tocar("clique")

    def preparar_vez(self):
        """Mostra de quem é a vez SEM revelar as palavras da carta."""
        nome = NOMES_EQUIPAS[self.equipa_atual]

        self.info.text = "Equipa " + nome
        self.info.color = CORES_EQUIPAS[self.equipa_atual]
        self.label_palavras.text = "Vez da equipa " + nome + "\n\nPrima COMEÇAR"
        self.cor_fundo.rgba = (0, 0, 0, 0)
        self.timer.text = str(DURACAO)

    def nova_carta(self):
        if not self.cartas_embaralhadas:
            self.cartas_embaralhadas = CARTAS.copy()
            random.shuffle(self.cartas_embaralhadas)

        self.carta_atual = self.cartas_embaralhadas.pop()
        self.lado_atual = 0
        self.mostrar_carta()

    def mostrar_carta(self):
        if not self.carta_atual:
            return

        if self.lado_atual == 0:
            palavras = self.carta_atual["azul"]
            cor = (0.20, 0.55, 0.95, 1)
        else:
            palavras = self.carta_atual["amarelo"]
            cor = (0.95, 0.75, 0.20, 1)

        self.cor_fundo.rgba = (cor[0], cor[1], cor[2], 0.18)

        self.label_palavras.text = "\n".join(palavras)

    def comecar_turno(self, *args):
        if self.em_jogo:
            return

        # Depois da vitória, o mesmo botão passa a "NOVO JOGO"
        if self.fim_de_jogo:
            SONS.tocar("clique")
            self.novo_jogo()
            return

        SONS.tocar("comecar")

        self.em_jogo = True
        self.tempo = DURACAO
        self.timer.text = str(self.tempo)

        self.botao_comecar.disabled = True
        self.botao_passa.disabled = False

        self.nova_carta()

        Clock.unschedule(self.contar_tempo)
        Clock.schedule_interval(self.contar_tempo, 1)

    def contar_tempo(self, dt):
        if not self.em_jogo:
            return

        self.tempo -= 1
        self.tempo = max(self.tempo, 0)
        self.timer.text = str(self.tempo)

        if self.tempo == 0:
            SONS.tocar("fim")
            self.terminar_turno()
        elif self.tempo <= 5:
            SONS.tocar("tick")

    def passa(self, *args):
        if not self.em_jogo:
            return

        equipa = self.equipa_atual

        self.posicoes[equipa] = min(self.posicoes[equipa] + 1, N_CASAS - 1)
        self.tabuleiro.mover_peao(equipa, self.posicoes[equipa])

        if self.posicoes[equipa] >= N_CASAS - 1:
            self.vitoria()
            return

        SONS.tocar("certo")

        if self.lado_atual == 0:
            self.lado_atual = 1
            self.mostrar_carta()
        else:
            self.nova_carta()

    def terminar_turno(self):
        if not self.em_jogo:
            return

        self.em_jogo = False
        Clock.unschedule(self.contar_tempo)

        self.botao_passa.disabled = True

        self.equipa_atual = (self.equipa_atual + 1) % self.n_equipas

        self.botao_comecar.disabled = False
        self.preparar_vez()

    def vitoria(self):
        self.em_jogo = False
        self.fim_de_jogo = True
        Clock.unschedule(self.contar_tempo)

        SONS.tocar("vitoria")

        self.botao_passa.disabled = True
        self.botao_comecar.disabled = False
        self.botao_comecar.text = "NOVO JOGO"

        nome = NOMES_EQUIPAS[self.equipa_atual]

        self.info.text = "EQUIPA " + nome + " VENCEU!"
        self.label_palavras.text = (
            "META!\n\n"
            "A equipa " + nome + " chegou primeiro."
        )
        self.cor_fundo.rgba = (0, 0, 0, 0)
        self.timer.text = "FIM"

    def novo_jogo(self):
        self.fim_de_jogo = False
        self.equipa_atual = 0
        self.posicoes = [0] * self.n_equipas
        self.tabuleiro.reiniciar_peoes()

        self.botao_comecar.text = "COMEÇAR"
        self.botao_comecar.disabled = False
        self.botao_passa.disabled = True

        self.preparar_vez()


class EcraJogo(Screen):
    """Ecrã que cria um jogo novo com o número de equipas escolhido."""

    def __init__(self, ao_menu, **kwargs):
        super().__init__(**kwargs)
        self.ao_menu = ao_menu
        self.jogo = None

    def iniciar(self, n_equipas):
        self.parar()
        self.clear_widgets()
        self.jogo = Jogo30Seconds(n_equipas, ao_menu=self.ao_menu)
        self.add_widget(self.jogo)

    def parar(self):
        if self.jogo:
            self.jogo.parar()


# =========================================================
# APP
# =========================================================

class JogoApp(App):

    def build(self):
        self.title = "30 Seconds"

        SONS.preparar()

        self.gestor = ScreenManager(transition=FadeTransition(duration=0.2))

        ecra_capa = Screen(name="capa")
        ecra_capa.add_widget(Capa(ao_jogar=lambda: self.ir("equipas")))

        ecra_equipas = Screen(name="equipas")
        ecra_equipas.add_widget(EscolhaEquipas(
            ao_escolher=self.iniciar_jogo,
            ao_voltar=lambda: self.ir("capa"),
        ))

        self.ecra_jogo = EcraJogo(name="jogo", ao_menu=self.voltar_ao_menu)

        self.gestor.add_widget(ecra_capa)
        self.gestor.add_widget(ecra_equipas)
        self.gestor.add_widget(self.ecra_jogo)

        return self.gestor

    def ir(self, nome):
        self.gestor.current = nome

    def iniciar_jogo(self, n_equipas):
        self.ecra_jogo.iniciar(n_equipas)
        self.ir("jogo")

    def voltar_ao_menu(self):
        self.ecra_jogo.parar()
        self.ir("capa")


if __name__ == "__main__":
    JogoApp().run()
