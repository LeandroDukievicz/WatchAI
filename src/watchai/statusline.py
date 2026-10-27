"""Ligar (e desligar) o consumo do Claude Code sem estragar o que já existe.

O Claude Code não grava limite em arquivo nenhum: ele **empurra** o dado para
scripts de statusline. Isso obriga uma linha no `settings.json` dele — a única
configuração de agente que o WatchAI tem. Duas coisas tornam isso um comando em
vez de um copiar-e-colar do README:

1. **quem já tem statusline não pode perdê-la.** Mandar a pessoa colar a nossa
   por cima é mandar apagar a dela. Aqui, se já existe uma, o WatchAI **embrulha**
   a original: ele recebe o JSON, guarda o consumo e chama o comando de antes com
   a mesma entrada, imprimindo a saída **dele**. Quem tinha statusline continua
   com a statusline que tinha, e ganha a barra no WatchAI;
2. **o comando escrito tem que funcionar quando o agente o chamar.** Não é a
   mesma coisa que funcionar no seu terminal: o Claude Code executa a statusline
   com o PATH **dele**, e um `watchai` que só existe dentro de um venv ativado
   não está ali. `sh: watchai: not found`, statusline vazia, nenhum erro na tela.
   Quem decide o que escrever é `comando()`, e ele só usa o nome puro quando o
   executável mora num `bin` que qualquer shell acha sozinho.

Também escrevemos no arquivo **certo**: se o `settings.local.json` é quem define
a `statusLine`, é nele que se mexe — escrever no `settings.json` seria escrever
num lugar que o outro sobrescreve, e a barra nunca apareceria, sem erro nenhum na
tela para explicar por quê.

E **sabemos dizer quando deixou de funcionar**: `estado()` olha o
`settings.json` e responde se a linha de lá ainda é a nossa. Essa pergunta tem
resposta porque a falha é silenciosa e acontece de verdade — outro programa que
também quer a statusline sobrescreve a chave, o agente passa a empurrar o
consumo para ele, e o arquivo que alimenta a barra do Claude apenas envelhece.
O painel, que antes mostrava dois traços sem explicar nada, agora mostra o que
rodar; o `--check-statusline` conta a história inteira.

Nada aqui roda sozinho: só pelos comandos `--install-statusline`,
`--uninstall-statusline` e `--check-statusline` (que não escreve nada). Mexer no
arquivo de configuração de outro programa é coisa que se faz quando a pessoa
pede, e uma vez.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config

PASTA_CLAUDE = ".claude"
# Na ordem em que o Claude Code os aplica: o `.local` é o pessoal, e é ele quem
# vale quando os dois dizem a mesma coisa.
ARQUIVOS = ("settings.json", "settings.local.json")
CHAVE = "statusLine"
REFRESH = "refreshInterval"
SUFIXO_BACKUP = ".watchai.bak"

# De quanto em quanto tempo o agente reexecuta a statusline mesmo sem render
# novo. Sem isto o número congela quando a sessão fica parada — e é justamente
# a sessão parada que envelhece o dado.
#
# **Em segundos.** Aqui havia `REFRESH_MS = 30_000`, e o campo não é em
# milissegundos: o esquema do Claude Code o descreve como "re-run the status
# line command every N seconds" e o multiplica por mil para agendar
# (`Math.max(1, n) * 1000`). Trinta mil segundos são oito horas e vinte: o
# refresh que existe justamente para a sessão parada não acontecia uma vez por
# dia de trabalho. Era o conserto mais barato do painel — a barra do Claude
# envelhecia sozinha e virava traço.
REFRESH_SEGUNDOS = 30

# Diretórios cujo conteúdo um shell de login acha sem ajuda nenhuma — é onde o
# O `pipx` e os gerenciadores de pacote põem executável aqui. Estando aqui, vale
# escrever o nome puro, que continua certo depois de uma atualização; fora daqui
# (venv, clone, instalação exótica) só o caminho absoluto é confiável.
BINS_GLOBAIS = ("/usr/local/bin", "/usr/bin", "/bin", "/opt/homebrew/bin")


@dataclass(frozen=True)
class Resultado:
    ok: bool
    mensagem: str


def _citar(caminho: str) -> str:
    return f'"{caminho}"' if " " in caminho else caminho


def _global(pasta: Path) -> bool:
    """Se um executável nesta pasta é achado por qualquer shell, sem PATH extra."""
    try:
        resolvida = pasta.resolve()
    except OSError:
        return False
    conhecidas = [Path(b) for b in BINS_GLOBAIS]
    conhecidas.append(Path.home() / ".local" / "bin")  # pipx, nos três sistemas
    for candidata in conhecidas:
        try:
            if resolvida == candidata.resolve():
                return True
        except OSError:
            continue
    return False


def comando(executavel: str | None = None) -> str:
    """O comando que vai para o `settings.json`, escolhido nesta máquina.

    Três casos, e a ordem importa porque o erro é **silencioso**: comando que o
    agente não acha produz statusline vazia, sem mensagem nenhuma.

    1. instalado num `bin` global (`pipx`, gerenciador de pacote) → nome
       puro, que é legível e continua valendo depois de uma atualização;
    2. instalado num venv ou em lugar incomum → **caminho absoluto** do próprio
       executável. O nome puro funcionaria no seu terminal com o venv ativado e
       falharia quando o agente chamasse, que é o pior dos dois mundos;
    3. sem executável nenhum (rodando de um clone por `python -m watchai`) →
       o interpretador de agora, absoluto.
    """
    achado = shutil.which("watchai") if executavel is None else executavel
    if achado and Path(achado).name.startswith("watchai"):
        if _global(Path(achado).parent):
            return "watchai --statusline"
        # O caminho vai **como veio**: passá-lo por `str(Path(...))` normalizaria
        # as barras, e quem abre o settings.json quer ler o que reconhece.
        return f"{_citar(achado)} --statusline"
    return f"{_citar(sys.executable or 'python3')} -m watchai --statusline"


def e_nosso(valor) -> bool:
    """Se esta `statusLine` já é a do WatchAI."""
    linha = valor.get("command", "") if isinstance(valor, dict) else valor
    return isinstance(linha, str) and "--statusline" in linha and "watchai" in linha.lower()


def _ler(caminho: Path) -> dict:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _gravar(caminho: Path, dados: dict) -> None:
    """Grava preservando o que não é nosso, de forma atômica.

    O arquivo é de outro programa e pode estar aberto: tmp + rename para o
    Claude Code nunca ler um JSON pela metade e perder **todas** as
    preferências de quem nos deixou escrever nele.
    """
    temporario = caminho.with_suffix(f".{os.getpid()}.tmp")
    temporario.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporario, caminho)




def _alvo(base: Path) -> tuple[Path, dict, Path | None]:
    """Em qual arquivo mexer, e se o outro também define uma `statusLine`."""
    existentes = [(base / nome, _ler(base / nome)) for nome in ARQUIVOS if (base / nome).is_file()]
    com_chave = [(c, d) for c, d in existentes if CHAVE in d]
    if com_chave:
        # O último da ordem é o que vale; se os dois definem, o outro fica como
        # aviso, porque mexer num deles não desfaz o que o outro manda.
        caminho, dados = com_chave[-1]
        conflito = com_chave[0][0] if len(com_chave) > 1 else None
        return caminho, dados, conflito
    caminho = base / ARQUIVOS[0]
    return caminho, _ler(caminho), None


def instalar(base: Path | None = None, nosso: str | None = None) -> Resultado:
    """Põe (ou atualiza) a statusline do WatchAI. Rodar duas vezes não estraga."""
    casa = base if base is not None else Path.home() / PASTA_CLAUDE
    if not casa.is_dir():
        return Resultado(False, f"não achei o Claude Code em {casa} — nada a fazer.")

    linha = nosso if nosso is not None else comando()
    caminho, dados, conflito = _alvo(casa)
    atual = dados.get(CHAVE)

    if e_nosso(atual):
        # Já é nossa: atualiza o comando, que pode ter mudado de caminho, e o
        # `refreshInterval` **se ele é nosso** — quem instalou antes do conserto
        # da unidade tem 30000 gravado ali, que são oito horas, não trinta
        # segundos. Rodar o instalar de novo é o que conserta.
        dados[CHAVE] = {**atual, "command": linha} if isinstance(atual, dict) else {"type": "command", "command": linha}
        if _refresh_nosso(dados[CHAVE]):
            dados[CHAVE][REFRESH] = REFRESH_SEGUNDOS
            config.save_statusline_refresh(True)
        try:
            _gravar(caminho, dados)
        except OSError as erro:
            return Resultado(False, f"não consegui escrever em {caminho}: {erro}")
        guardada = config.load_statusline_wrapped()
        extra = f"\n  A sua statusline de antes continua embrulhada: {guardada}" if guardada else ""
        return Resultado(True, f"já estava ligada em {caminho} — comando atualizado para `{linha}`.{extra}")

    aviso = ""
    if atual is not None:
        antigo = atual.get("command") if isinstance(atual, dict) else atual
        if isinstance(antigo, str) and antigo.strip():
            if not config.save_statusline_wrapped(antigo):
                return Resultado(
                    False,
                    "não consegui guardar sua statusline anterior; "
                    "a configuração do Claude Code não foi alterada.",
                )
            aviso = (
                f"\n  Você já tinha uma statusline. Ela **não** foi perdida: o WatchAI chama\n"
                f"  `{antigo}` com a mesma entrada e mostra a saída dela.\n"
                f"  Para voltar ao de antes: watchai --uninstall-statusline"
            )

    backup = caminho.with_name(caminho.name + SUFIXO_BACKUP)
    if caminho.is_file() and not backup.exists():
        try:
            shutil.copy2(caminho, backup)
        except OSError:
            pass  # cópia de segurança é bônus; não pode impedir a instalação

    if isinstance(atual, dict):
        # Embrulhando a de alguém: troca o comando e preserva o resto dela.
        dados[CHAVE] = {**atual, "command": linha}
        dados[CHAVE].setdefault("type", "command")
    else:
        dados[CHAVE] = {"type": "command", "command": linha}
    # O `refreshInterval` é o que mantém o número fresco enquanto a sessão fica
    # parada — e sessão parada é exatamente quando a janela vira e o percentual
    # guardado deixa de valer. Antes ele só entrava no slot vazio, para não
    # deixar chave nossa no arquivo de outro programa; o preço era a barra
    # congelar na máquina de quem já tinha statusline sem o campo. Agora entra
    # sempre, e a marca na config é o que deixa o desinstalar devolver o
    # arquivo exatamente como estava.
    nosso_refresh = REFRESH not in dados[CHAVE]
    if nosso_refresh:
        dados[CHAVE][REFRESH] = REFRESH_SEGUNDOS
    config.save_statusline_refresh(nosso_refresh)
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        _gravar(caminho, dados)
    except OSError as erro:
        return Resultado(False, f"não consegui escrever em {caminho}: {erro}")

    if conflito is not None:
        aviso += (
            f"\n  ⚠️  {conflito.name} também define uma statusLine e tem precedência sobre\n"
            f"  {caminho.name}. Tire a de lá, ou rode este comando com ela já removida."
        )
    return Resultado(True, f"statusline ligada em {caminho} com `{linha}`.{aviso}")


def _refresh_nosso(linha: dict) -> bool:
    """Se o `refreshInterval` desta `statusLine` pode ser reescrito por nós.

    Vale quando a marca da config diz que fomos nós que o pusemos, e também
    quando ele simplesmente não está lá.
    """
    return REFRESH not in linha or config.load_statusline_refresh()


# O que o diagnóstico pode encontrar. São os quatro motivos pelos quais a barra
# do Claude não aparece — e cada um tem uma saída diferente, que é a razão de
# existirem como estados em vez de um booleano.
LIGADA = "ligada"  # a statusline é a nossa: o dado chega
AUSENTE = "ausente"  # não há statusLine nenhuma configurada
DE_OUTRO = "de-outro"  # há uma, e não é a nossa: o dado vai para ela
SEM_CLAUDE = "sem-claude"  # não há Claude Code nesta máquina

# A linha curta que o painel mostra no lugar da barra. Cabe no cabeçalho, diz o
# que fazer e não finge número nenhum.
DICAS = {
    AUSENTE: "no data · run: watchai --install-statusline",
    DE_OUTRO: "statusline is not ours · run: watchai --install-statusline",
}


@dataclass(frozen=True)
class Estado:
    """De onde (e se) o consumo do Claude Code chega nesta máquina.

    O limite do Claude só existe no WatchAI porque o agente o empurra para a
    statusline. Quando essa linha deixa de ser a nossa — desinstalada, ou
    sobrescrita por outro programa que também queria o lugar —, o arquivo que
    alimenta a barra para de ser escrito e envelhece calado. O painel passava a
    mostrar dois traços e a idade do dado, que é a mesma tela de quem nunca
    instalou nada: informação suficiente para ver que algo está errado e
    nenhuma para saber o quê.
    """

    chave: str
    arquivo: Path | None = None
    comando: str = ""  # o que está configurado lá, quando não é o nosso

    @property
    def ligada(self) -> bool:
        return self.chave == LIGADA

    @property
    def dica(self) -> str:
        """A linha curta para o painel. Vazia quando não há nada a dizer."""
        return DICAS.get(self.chave, "")

    @property
    def mensagem(self) -> str:
        """O relato do `--check-statusline`, em uma ou duas linhas."""
        if self.chave == SEM_CLAUDE:
            return "não achei o Claude Code nesta máquina — não há limite dele para ler."
        if self.chave == LIGADA:
            return f"a statusline do WatchAI está ligada em {self.arquivo}."
        if self.chave == DE_OUTRO:
            return (
                f"a statusLine de {self.arquivo} é de outro programa:\n"
                f"    {self.comando}\n"
                "  O consumo do Claude Code vai para ela, e o WatchAI não o vê.\n"
                "  O --install-statusline embrulha a dela: ela continua aparecendo\n"
                "  no agente, e a barra volta ao painel.\n"
                "  Para ligar: watchai --install-statusline"
            )
        return (
            f"não há statusLine configurada em {self.arquivo}.\n"
            "  É por ela que o Claude Code empurra o consumo das janelas de limite;\n"
            "  sem ela o painel mostra o codex e não o Claude.\n"
            "  Para ligar: watchai --install-statusline"
        )


def estado(base: Path | None = None) -> Estado:
    """Se o consumo do Claude Code tem como chegar até aqui, e por que não."""
    casa = base if base is not None else Path.home() / PASTA_CLAUDE
    if not casa.is_dir():
        return Estado(SEM_CLAUDE)
    caminho, dados, _ = _alvo(casa)
    atual = dados.get(CHAVE)
    if e_nosso(atual):
        return Estado(LIGADA, caminho)
    if atual is None:
        return Estado(AUSENTE, caminho)
    linha = atual.get("command") if isinstance(atual, dict) else atual
    return Estado(DE_OUTRO, caminho, linha if isinstance(linha, str) else "")


def desinstalar(base: Path | None = None) -> Resultado:
    """Tira a nossa e devolve a que havia antes, se havia."""
    casa = base if base is not None else Path.home() / PASTA_CLAUDE
    caminho, dados, _ = _alvo(casa)
    atual = dados.get(CHAVE)
    if atual is None:
        return Resultado(True, f"não havia statusline configurada em {caminho}.")
    if not e_nosso(atual):
        return Resultado(False, f"a statusline de {caminho} não é a do WatchAI — deixei como está.")

    guardada = config.load_statusline_wrapped()
    if guardada:
        dados[CHAVE] = {**atual, "command": guardada} if isinstance(atual, dict) else {
            "type": "command",
            "command": guardada,
        }
        # O `refreshInterval` que **nós** pusemos sai junto: devolver a
        # statusline de alguém com um campo que ela não tinha é deixar resíduo.
        if config.load_statusline_refresh():
            dados[CHAVE].pop(REFRESH, None)
        recado = f"statusline devolvida para `{guardada}` em {caminho}."
    else:
        dados.pop(CHAVE)
        recado = f"statusline do WatchAI removida de {caminho}."
    try:
        _gravar(caminho, dados)
    except OSError as erro:
        return Resultado(False, f"não consegui escrever em {caminho}: {erro}")
    config.save_statusline_wrapped(None)
    config.save_statusline_refresh(False)
    return Resultado(True, recado)


__all__ = [
    "AUSENTE",
    "DE_OUTRO",
    "Estado",
    "LIGADA",
    "REFRESH_SEGUNDOS",
    "Resultado",
    "SEM_CLAUDE",
    "comando",
    "desinstalar",
    "e_nosso",
    "estado",
    "instalar",
]
