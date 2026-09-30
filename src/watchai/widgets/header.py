"""Cabeçalho compacto: título na borda + resumo global + relógio + limites.

    ╭─ ◆ WatchAI  SESSION MONITOR ───────────────────────────────────────╮
    │ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  ◆ INPUT 01  ...      17:42:08 │
    │ codex   5h ▓▓░░░░░░░░  18% · 2h14m   7d ▓▓░░░░░░░░  18% · 4d12h    │
    │ claude  5h ▓░░░░░░░░░   8% · 1h02m   7d ▓▓▓░░░░░░░  31% · 2d03h    │
    ╰─────────────────────────────────────────────────────────────────────╯

Zeros ficam apagados; só o que existe ganha cor. O resumo escolhe a variante
mais rica que cabe na largura (com labels → só símbolo + contagem).

As barras de limite moram **aqui, e não no card**: o limite é do plano, não de
um terminal — num card ele repetiria o mesmo número uma vez por sessão. E
aparecem só onde há número de verdade: o agente sem dado não ganha linha, e
ninguém ganha barra derivada de estimativa.
"""

from __future__ import annotations

from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual.message import Message
from textual.widget import Widget

from ..format import fmt_clock, fmt_span
from ..layout import HEADER_ROWS
from ..models import SUMMARY_ORDER, Status
from ..providers.limits import APERTA, ESTOURANDO, IDADE_VISIVEL, Consumo
from ..theme import colors

# A barra é sempre desta largura, nas duas janelas, para os dois números serem
# comparáveis de relance — é para isso que ela existe.
BARRA = 10
BARRA_ESTREITA = 6

CHEIO = "▓"
VAZIO = "░"

# Abaixo desta altura de terminal as barras não aparecem: elas custam uma linha
# por agente, e essa linha sairia do EVENT STREAM. Limite de plano é a
# informação menos urgente da tela — quem manda é o estado das sessões.
ALTURA_MINIMA = 20

# Larguras de cada variante da linha de limite, da mais rica para a mais pobre.
LARGURA_COMPLETA = 96
LARGURA_MEDIA = 58


def blocos(usado: float, largura: int = BARRA) -> tuple[int, int]:
    """Quantos blocos cheios e quantos vazios, para este percentual.

    Qualquer uso acima de zero acende **pelo menos um** bloco: barra vazia com
    número diferente de zero ao lado é a barra mentindo. Quem dá a precisão é o
    número; a barra dá a ordem de grandeza.
    """
    if usado <= 0:
        return 0, largura
    cheios = max(1, min(largura, round(usado / 100 * largura)))
    return cheios, largura - cheios


def barra(usado: float, largura: int = BARRA) -> str:
    """`▓▓░░░░░░░░` — o percentual em blocos, como texto."""
    cheios, vazios = blocos(usado, largura)
    return CHEIO * cheios + VAZIO * vazios


def cor_do_uso(usado: float) -> str:
    """Neon só quando aperta: cinza no começo, amarelo em 75%, vermelho em 90%.

    Segue a regra da casa — cor é para estado, e um limite no fim **é** um
    estado. No começo da janela, um número em cinza é exatamente o que ele vale.
    """
    palette = colors()
    if usado >= ESTOURANDO:
        return palette.red
    if usado >= APERTA:
        return palette.yellow
    return palette.text


class AppHeader(Widget):
    DEFAULT_CSS = f"AppHeader {{ height: {HEADER_ROWS}; }}"

    class Grew(Message):
        """A caixa mudou de altura — o Dashboard precisa refazer a conta do teto
        da área de sessões, senão o EVENT STREAM perde linhas caladas.

        A altura vai **na mensagem**: quando o Dashboard a recebe, o layout
        ainda pode não ter aplicado o novo `styles.height`, e medir o widget
        devolveria o valor de antes.
        """

        def __init__(self, rows: int) -> None:
            super().__init__()
            self.rows = rows

    def on_mount(self) -> None:
        self.border_title = self._title()
        self._limites: list[Consumo] = []
        self._linhas = 0
        self.watch(self.app, "version", lambda _: self._pulso())
        self.watch(self.app, "tick", lambda _: self._pulso())
        self._pulso()

    def on_resize(self) -> None:
        self.border_title = self._title()
        # E as barras, que dependem do tamanho: no `on_mount` o widget ainda não
        # tem largura nenhuma, então é aqui que ele descobre se elas cabem. Sem
        # isto, uma primeira varredura que chegasse antes do layout ficava
        # esperando o próximo `tick` para aparecer — meio segundo em que a tela
        # já tinha o dado e não mostrava.
        self._pulso()

    def _pulso(self) -> None:
        """Uma volta do relógio: acerta a altura, se preciso, e repinta."""
        self._limites = self._visiveis()
        if len(self._limites) != self._linhas:
            self._linhas = len(self._limites)
            self.styles.height = HEADER_ROWS + self._linhas
            self.post_message(self.Grew(HEADER_ROWS + self._linhas))
        self.refresh()

    def _visiveis(self) -> list[Consumo]:
        """Os limites que cabem nesta janela. Lista vazia é resposta boa."""
        limites = getattr(self.app, "consumos", None) or []
        if self.app.size.height < ALTURA_MINIMA or self.size.width < 40:
            return []
        return [c for c in limites if c.janelas]

    def _title(self) -> Text:
        title = Text(no_wrap=True)
        title.append("◆ ", Style(color=colors().cyan))
        title.append("WatchAI", Style(color=colors().cyan, bold=True))
        if self.size.width >= 48:
            title.append("  SESSION MONITOR", Style(color=colors().muted))
        return title

    def _chips(self, full: bool) -> Text:
        counts = self.app.store.counts()
        out = Text(no_wrap=True)
        first = True
        for status in SUMMARY_ORDER:
            n = counts[status]
            if status is Status.STARTING and n == 0:
                continue  # transitório: só aparece quando existe
            if not first:
                out.append("  " if full else " ")
            first = False
            lit = n > 0
            color = status.color if lit else colors().ghost
            out.append(status.symbol, Style(color=color))
            if full:
                out.append(f" {status.label} ", Style(color=colors().muted if lit else colors().ghost))
            else:
                out.append(" ")
            out.append(f"{n:02d}" if full else str(n), Style(color=color, bold=lit and status.attention))
        return out

    def _resumo(self, width: int) -> Text:
        """A primeira linha: quantas sessões, em que estado, e a hora."""
        store = self.app.store
        clock = fmt_clock(datetime.now())

        active = Text(no_wrap=True)
        active.append("ACTIVE ", Style(color=colors().muted))
        active.append(f"{store.active:02d}", Style(color=colors().text, bold=True))
        sep = Text(" │ ", Style(color=colors().line_hi))

        for full in (True, False):
            left = Text(no_wrap=True)
            left.append_text(active)
            left.append_text(sep)
            left.append_text(self._chips(full))
            if left.cell_len + len(clock) + 2 <= width:
                break
        else:
            left = self._chips(False)  # último recurso: só os chips

        gap = max(1, width - left.cell_len - len(clock))
        if left.cell_len + gap + len(clock) > width:
            return left  # sem espaço para o relógio
        left.append(" " * gap)
        left.append(clock, Style(color=colors().muted))
        return left

    def _linha_limite(self, consumo: Consumo, rotulo: int, width: int) -> Text:
        """A linha de um agente, na variante mais rica que cabe na largura."""
        palette = colors()
        agora = datetime.now().timestamp()
        # Completa: barra larga, percentual e quando a janela zera. Média: sem o
        # "zera em". Estreita: só o percentual, que é o dado, sem a barra, que é
        # a ilustração dele.
        if width >= LARGURA_COMPLETA:
            largura, mostra_reset = BARRA, True
        elif width >= LARGURA_MEDIA:
            largura, mostra_reset = BARRA_ESTREITA, False
        else:
            largura, mostra_reset = 0, False

        linha = Text(no_wrap=True)
        linha.append(consumo.kind.ljust(rotulo), Style(color=palette.muted))
        for janela in consumo.janelas:
            linha.append("  ")
            linha.append(f"{janela.label:>3} ", Style(color=palette.muted))
            # Janela vencida não tem percentual para mostrar: o número guardado
            # é de antes de ela virar. Fica o traço, e a idade do dado explica.
            if janela.vencida(agora):
                if largura:
                    linha.append(VAZIO * largura + " ", Style(color=palette.ghost))
                linha.append("  —", Style(color=palette.ghost))
                continue
            cor = cor_do_uso(janela.usado)
            if largura:
                # Cheio e vazio em cores diferentes. Só o glifo (▓ contra ░)
                # separando os dois é distinção fraca: com a mesma cor, a barra
                # vira um bloco só — visível na captura do README antes disto.
                cheios, vazios = blocos(janela.usado, largura)
                linha.append(CHEIO * cheios, Style(color=cor))
                linha.append(VAZIO * vazios, Style(color=palette.line_hi))
                linha.append(" ")
            linha.append(f"{janela.usado:3.0f}%", Style(color=cor, bold=janela.usado >= APERTA))
            falta = janela.falta(agora)
            if mostra_reset and falta is not None:
                linha.append(f" · {fmt_span(falta)}", Style(color=palette.muted))

        # A idade do dado, e só quando ela importa: o número é tão fresco quanto
        # o último uso daquele agente, e um percentual de ontem com cara de agora
        # é pior que percentual nenhum.
        idade = consumo.idade(agora)
        if idade is not None and idade >= IDADE_VISIVEL:
            linha.append(f"  ({fmt_span(idade)} ago)", Style(color=palette.ghost))
        return linha

    def render(self) -> Text:
        width = self.size.width
        linhas = [self._resumo(width)]
        rotulo = max((len(c.kind) for c in self._limites), default=0)
        for consumo in self._limites:
            linhas.append(self._linha_limite(consumo, rotulo, width))
        return Text("\n", no_wrap=True).join(linhas)
