"""Paletas e tema do WatchAI.

Fonte única das cores. Um `Palette` descreve um tema inteiro; a paleta ativa
vive em `colors()` e é trocada por `use()`. Quem desenha **resolve a cor na
hora de renderizar** (`colors().cyan`), nunca no import — é isso que permite
trocar de tema com o app rodando.

O TCSS recebe as mesmas cores como variáveis `$aw-*` através do `Theme` do
Textual, então trocar `app.theme` reescreve o CSS inteiro sozinho.

Cada paleta declara ~16 cores base; as derivadas (bordas apagadas e tintas de
fundo) são calculadas a partir delas, e qualquer uma pode ser sobrescrita —
é o que mantém a paleta `watchai` exatamente como foi desenhada.

Se o terminal não suporta truecolor, o Textual faz o downgrade automático para
a paleta de 256 / 16 cores mais próxima.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from functools import lru_cache

from textual.color import Color
from textual.theme import Theme

# Níveis usados para calcular as cores derivadas a partir das base.
EDGE_LEVEL = 0.30  # bordas de estado "calmo" (WORKING/WAITING)
TINT_LEVEL = 0.07  # tinta de fundo dos estados de atenção
TINT_SELECTED = 0.14  # a mesma tinta, no card selecionado

# Campos cujo nome no TCSS não sai da conversão automática `_` -> `-`.
CSS_NAMES = {"bg2": "bg-2", "cyan2": "cyan-2", "text2": "text-2"}


@lru_cache(maxsize=1024)
def blend(color: str, bg: str, level: float) -> str:
    """Mistura `color` com `bg`. level=1.0 -> cor cheia, 0.0 -> só o fundo."""
    level = max(0.0, min(1.0, level))
    return Color.parse(color).blend(Color.parse(bg), 1.0 - level).hex


def fade(color: str, level: float, bg: str | None = None) -> str:
    """`blend` contra o fundo da paleta ativa."""
    return blend(color, bg or colors().bg, level)


@dataclass(frozen=True)
class Palette:
    """Todas as cores de um tema, já resolvidas."""

    key: str
    label: str
    dark: bool

    # -- base ---------------------------------------------------------------
    bg: str  # fundo da tela
    bg2: str  # superfície (keybar)
    cyan: str  # WORKING, seleção, títulos, teclas
    cyan2: str  # acento secundário (régua, seções)
    magenta: str  # INPUT
    green: str  # READY
    yellow: str  # WAITING
    red: str  # ERROR
    gray: str  # label de OFFLINE
    text: str  # texto principal
    text2: str  # texto secundário (activity)
    muted: str  # rótulos
    line: str  # borda neutra
    line_hi: str  # borda neutra em foco
    ghost: str  # OFFLINE: quase some no fundo

    # -- derivadas ----------------------------------------------------------
    edge_working: str
    edge_waiting: str
    tint_select: str
    tint_green: str
    tint_magenta: str
    tint_red: str
    tint_green_sel: str
    tint_magenta_sel: str
    tint_red_sel: str

    def css_variables(self) -> dict[str, str]:
        """As mesmas cores como `$aw-*` para o TCSS."""
        skip = {"key", "label", "dark"}
        return {
            f"aw-{CSS_NAMES.get(f.name, f.name.replace('_', '-'))}": getattr(self, f.name)
            for f in fields(self)
            if f.name not in skip
        }

    def as_theme(self) -> Theme:
        """Embrulha a paleta num `Theme` do Textual."""
        return Theme(
            name=self.key,
            primary=self.cyan,
            secondary=self.magenta,
            accent=self.magenta,
            success=self.green,
            warning=self.yellow,
            error=self.red,
            foreground=self.text,
            background=self.bg,
            surface=self.bg2,
            panel=self.bg2,
            dark=self.dark,
            variables=self.css_variables(),
        )


def palette(
    key: str,
    label: str,
    *,
    dark: bool = True,
    bg: str,
    bg2: str,
    cyan: str,
    cyan2: str,
    magenta: str,
    green: str,
    yellow: str,
    red: str,
    gray: str,
    text: str,
    text2: str,
    muted: str,
    line: str,
    line_hi: str,
    ghost: str,
    **overrides: str,
) -> Palette:
    """Monta uma paleta calculando as derivadas (sobrescrevíveis por `overrides`)."""
    derived = {
        "edge_working": blend(cyan, bg, EDGE_LEVEL),
        "edge_waiting": blend(yellow, bg, EDGE_LEVEL + 0.05),
        "tint_select": blend(cyan, bg, TINT_LEVEL + 0.03),
        "tint_green": blend(green, bg, TINT_LEVEL),
        "tint_magenta": blend(magenta, bg, TINT_LEVEL),
        "tint_red": blend(red, bg, TINT_LEVEL),
        "tint_green_sel": blend(green, bg, TINT_SELECTED),
        "tint_magenta_sel": blend(magenta, bg, TINT_SELECTED),
        "tint_red_sel": blend(red, bg, TINT_SELECTED),
    }
    unknown = set(overrides) - set(derived)
    if unknown:
        raise ValueError(f"override desconhecido em '{key}': {sorted(unknown)}")
    return Palette(
        key=key,
        label=label,
        dark=dark,
        bg=bg,
        bg2=bg2,
        cyan=cyan,
        cyan2=cyan2,
        magenta=magenta,
        green=green,
        yellow=yellow,
        red=red,
        gray=gray,
        text=text,
        text2=text2,
        muted=muted,
        line=line,
        line_hi=line_hi,
        ghost=ghost,
        **{**derived, **overrides},
    )


# ============================================================================
# As paletas
# ============================================================================

WATCHAI = palette(
    "watchai",
    "WatchAI",
    bg="#05070D",
    bg2="#080D16",
    cyan="#00E5FF",
    cyan2="#00AFC8",
    magenta="#FF2BD6",
    green="#39FF88",
    yellow="#FFD166",
    red="#FF4D6D",
    gray="#657080",
    text="#D8E2F0",
    text2="#A9B5C7",
    muted="#7C8799",
    line="#1A2333",
    line_hi="#2A3850",
    ghost="#3A4456",
    # valores desenhados à mão no protótipo original — preservados na íntegra
    edge_working="#0E4652",
    edge_waiting="#54472A",
    tint_select="#0B1626",
    tint_green="#07170F",
    tint_magenta="#170A1C",
    tint_red="#1A0910",
    tint_green_sel="#0A2115",
    tint_magenta_sel="#220E29",
    tint_red_sel="#26101A",
)

LIGHT = palette(
    "light",
    "Light",
    dark=False,
    bg="#FBFCFD",
    bg2="#EFF2F6",
    cyan="#0A7C8A",
    cyan2="#0E5D67",
    magenta="#A626A4",
    green="#1A7F37",
    yellow="#9A6700",
    red="#CF222E",
    gray="#8C959F",
    text="#1F2328",
    text2="#3B424A",
    muted="#656D76",
    line="#D8DEE4",
    line_hi="#AFB8C1",
    ghost="#B6BEC7",
)

DARK = palette(
    "dark",
    "Dark",
    bg="#0D1117",
    bg2="#161B22",
    cyan="#56B6C2",
    cyan2="#3E8A94",
    magenta="#C678DD",
    green="#56D364",
    yellow="#E3B341",
    red="#F85149",
    gray="#6E7681",
    text="#E6EDF3",
    text2="#C9D1D9",
    muted="#8B949E",
    line="#21262D",
    line_hi="#30363D",
    ghost="#484F58",
)

NIGHT_OWL = palette(
    "night-owl",
    "Night Owl",
    bg="#011627",
    bg2="#0B2942",
    cyan="#7FDBCA",
    cyan2="#21C7A8",
    magenta="#C792EA",
    green="#ADDB67",
    yellow="#ECC48D",
    red="#EF5350",
    gray="#5F7E97",
    text="#D6DEEB",
    text2="#A7B6C8",
    muted="#8BA1B3",
    line="#0E2D45",
    line_hi="#1D3B53",
    ghost="#43617B",
)

VAMPIRE = palette(
    "vampire",
    "Vampire",
    bg="#282A36",
    bg2="#21222C",
    cyan="#8BE9FD",
    cyan2="#BD93F9",  # o roxo clássico da paleta
    magenta="#FF79C6",
    green="#50FA7B",
    yellow="#F1FA8C",
    red="#FF5555",
    gray="#6272A4",
    text="#F8F8F2",
    text2="#D3D3CC",
    muted="#9AA0BF",
    line="#343746",
    line_hi="#44475A",
    ghost="#565A70",
)

CYBERPUNK = palette(
    "cyberpunk",
    "Cyberpunk",
    bg="#05010A",
    bg2="#0D0418",
    cyan="#00F0FF",
    cyan2="#00B8C4",
    magenta="#FF00A0",
    green="#00FF9F",
    yellow="#FCEE0A",
    red="#FF2E4C",
    gray="#6B5A82",
    text="#F2E9FF",
    text2="#C9B8E0",
    muted="#9A86BC",
    line="#22103A",
    line_hi="#3A1B5E",
    ghost="#4A3568",
)

STEAMPUNK = palette(
    "steampunk",
    "Steampunk",
    bg="#140F0A",
    bg2="#1F1811",
    cyan="#7FB2A1",  # verdete
    cyan2="#5A8A7C",
    magenta="#C9762F",  # cobre
    green="#9FB055",  # latão esverdeado
    yellow="#D9A441",  # latão
    red="#B0442A",  # ferrugem
    gray="#7A6A55",
    text="#EFE2CC",
    text2="#CDBBA0",
    muted="#9A876C",
    line="#2E2419",
    line_hi="#4A3A28",
    ghost="#5C4A35",
)

# Sem matiz: os estados se separam por brilho (e pelo símbolo, que nunca muda).
GREY = palette(
    "grey",
    "Grey",
    bg="#0E0E0E",
    bg2="#171717",
    cyan="#9C9C9C",  # WORKING — discreto
    cyan2="#7A7A7A",
    magenta="#C2C2C2",  # INPUT
    green="#DADADA",  # READY — claro
    yellow="#828282",  # WAITING
    red="#FFFFFF",  # ERROR — o mais claro de todos
    gray="#5A5A5A",
    text="#E8E8E8",
    text2="#BDBDBD",
    muted="#8C8C8C",
    line="#232323",
    line_hi="#383838",
    ghost="#4A4A4A",
)

# Ordem em que aparecem no seletor.
PALETTES: tuple[Palette, ...] = (
    WATCHAI,
    LIGHT,
    DARK,
    NIGHT_OWL,
    VAMPIRE,
    CYBERPUNK,
    STEAMPUNK,
    GREY,
)
BY_KEY: dict[str, Palette] = {p.key: p for p in PALETTES}
DEFAULT = WATCHAI

# ============================================================================
# Paleta ativa
# ============================================================================

_active: Palette = DEFAULT


def colors() -> Palette:
    """A paleta ativa. Chame no render, nunca guarde a cor num módulo."""
    return _active


def use(key_or_palette: str | Palette) -> Palette:
    """Troca a paleta ativa. Chave desconhecida cai na padrão."""
    global _active
    if isinstance(key_or_palette, Palette):
        _active = key_or_palette
    else:
        _active = BY_KEY.get(key_or_palette, DEFAULT)
    return _active


__all__ = [
    "BY_KEY",
    "DEFAULT",
    "PALETTES",
    "Palette",
    "blend",
    "colors",
    "fade",
    "palette",
    "use",
]
