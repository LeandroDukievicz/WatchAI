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

Nada aqui roda sozinho: só pelos comandos `--install-statusline` e
`--uninstall-statusline`. Mexer no arquivo de configuração de outro programa é
coisa que se faz quando a pessoa pede, e uma vez.
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
SUFIXO_BACKUP = ".watchai.bak"

# De quanto em quanto tempo o agente reexecuta a statusline mesmo sem render
# novo. Sem isto o número congela quando a sessão fica parada — e é justamente
# a sessão parada que envelhece o dado.
REFRESH_MS = 30_000

# Diretórios cujo conteúdo um shell de login acha sem ajuda nenhuma — é onde o
# `pipx`, o snap e os gerenciadores de pacote põem executável. Estando aqui, vale
# escrever o nome puro, que continua certo depois de uma atualização; fora daqui
# (venv, clone, instalação exótica) só o caminho absoluto é confiável.
BINS_GLOBAIS = ("/usr/local/bin", "/usr/bin", "/bin", "/snap/bin", "/opt/homebrew/bin")


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

    1. instalado num `bin` global (`pipx`, snap, gerenciador de pacote) → nome
       puro, que é legível e continua valendo depois de uma atualização;
    2. instalado num venv ou em lugar incomum → **caminho absoluto** do próprio
       executável. O nome puro funcionaria no seu terminal com o venv ativado e
       falharia quando o agente chamasse, que é o pior dos dois mundos;
    3. sem executável nenhum (rodando de um clone por `python -m watchai`) →
       o interpretador de agora, absoluto.
    """
    achado = shutil.which("watchai") if executavel is None else executavel
    if achado and Path(achado).name.startswith("watchai"):
        caminho = Path(achado)
        if _global(caminho.parent):
            return "watchai --statusline"
        return f"{_citar(str(caminho))} --statusline"
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
        # Já é nossa: atualiza só o comando, que pode ter mudado de caminho.
        dados[CHAVE] = {**atual, "command": linha} if isinstance(atual, dict) else {"type": "command", "command": linha}
        _gravar(caminho, dados)
        guardada = config.load_statusline_wrapped()
        extra = f"\n  A sua statusline de antes continua embrulhada: {guardada}" if guardada else ""
        return Resultado(True, f"já estava ligada em {caminho} — comando atualizado para `{linha}`.{extra}")

    aviso = ""
    if atual is not None:
        antigo = atual.get("command") if isinstance(atual, dict) else atual
        if isinstance(antigo, str) and antigo.strip():
            config.save_statusline_wrapped(antigo)
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
        # Embrulhando a de alguém: troca só o comando e **não acrescenta nada**.
        # Chave nossa esquecida ali vira resíduo no arquivo de outro programa, e
        # o desinstalar deixaria de devolver exatamente o que havia antes.
        dados[CHAVE] = {**atual, "command": linha}
        dados[CHAVE].setdefault("type", "command")
    else:
        # Slot vazio: aí sim o `refreshInterval` é nosso, e é ele que mantém o
        # número fresco enquanto a sessão fica parada.
        dados[CHAVE] = {"type": "command", "command": linha, "refreshInterval": REFRESH_MS}
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
        recado = f"statusline devolvida para `{guardada}` em {caminho}."
    else:
        dados.pop(CHAVE)
        recado = f"statusline do WatchAI removida de {caminho}."
    try:
        _gravar(caminho, dados)
    except OSError as erro:
        return Resultado(False, f"não consegui escrever em {caminho}: {erro}")
    config.save_statusline_wrapped(None)
    return Resultado(True, recado)


__all__ = ["REFRESH_MS", "Resultado", "comando", "desinstalar", "e_nosso", "instalar"]
