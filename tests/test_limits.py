"""Consumo das janelas de limite: leitura, validação e barra.

Nada aqui olha o consumo de quem roda a suíte: os rollouts são arquivos de
mentira num `tmp_path` e o recado da statusline é escrito pelo próprio teste. É
também assim que os estados de alerta (95%, 100%) são exercitados — escrevendo o
número, sem gastar cota para chegar nele.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from watchai.format import fmt_span
from watchai.providers import limits
from watchai.providers.limits import (
    APERTA,
    ESTOURANDO,
    Consumo,
    Janela,
    LeitorClaude,
    LeitorCodex,
    Limites,
    consumo,
)
from watchai.providers.transcript import Transcripts
from watchai.widgets.header import barra, cor_do_uso

AGORA = 1_790_700_000.0

# Como o codex grava: `used_percent`, `window_minutes` e `resets_at` em epoch.
CODEX = {
    "limit_id": "codex",
    "limit_name": None,
    "primary": {"used_percent": 16.0, "window_minutes": 300, "resets_at": AGORA + 3600},
    "secondary": {"used_percent": 18.0, "window_minutes": 10080, "resets_at": AGORA + 4 * 86400},
    "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
    "plan_type": "plus",
}


def rollout(tmp_path, nome, rate_limits=None, quando=AGORA, mtime=None):
    """Um rollout do codex, com ou sem o `token_count` que traz o limite."""
    dia = tmp_path / ".codex" / "sessions" / "2026" / "09" / "29"
    dia.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.fromtimestamp(quando, timezone.utc).isoformat().replace("+00:00", "Z")
    linhas = [{"timestamp": carimbo, "type": "session_meta", "payload": {"cwd": "/home/eu/proj"}}]
    if rate_limits is not None:
        linhas.append({
            "timestamp": carimbo,
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {}, "rate_limits": rate_limits},
        })
    caminho = dia / f"rollout-{nome}.jsonl"
    caminho.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(caminho, (mtime, mtime))
    return caminho


# ---- o que o codex já deixa no disco ---------------------------------------


def test_o_codex_entrega_o_limite_do_proprio_rollout(tmp_path):
    """Zero configuração: é o mesmo arquivo que o leitor de diário já abre."""
    rollout(tmp_path, "a", CODEX)
    achado = LeitorCodex(tmp_path).ler(AGORA)
    assert achado is not None
    assert achado.kind == "codex" and achado.plano == "plus"
    assert (achado.curta.usado, achado.curta.minutos) == (16.0, 300)
    assert (achado.longa.usado, achado.longa.minutos) == (18.0, 10080)
    assert achado.curta.label == "5h" and achado.longa.label == "7d"
    assert achado.medido == AGORA  # a hora é a do carimbo, não a do arquivo


def test_rollout_de_sessao_nova_nao_apaga_a_barra(tmp_path):
    """Abrir um codex apagava o número: o rollout recém-criado **não tem**
    `token_count` — o bloco só aparece depois da primeira resposta do servidor.
    Sem cair no arquivo anterior, a barra sumia no pior momento, o de começar a
    trabalhar."""
    rollout(tmp_path, "velho", CODEX, mtime=AGORA - 600)
    rollout(tmp_path, "novinho", None, mtime=AGORA)
    achado = LeitorCodex(tmp_path).ler(AGORA)
    assert achado is not None and achado.curta.usado == 16.0


def test_sem_pasta_do_codex_a_resposta_e_nada(tmp_path):
    assert LeitorCodex(tmp_path).ler() is None


def test_rollout_ilegivel_nao_derruba_nada(tmp_path):
    caminho = rollout(tmp_path, "a", CODEX)
    caminho.write_text("{isso não é json\n", encoding="utf-8")
    assert LeitorCodex(tmp_path).ler() is None


# ---- validação de faixa: o número não é conferível, então é peneirado -------


def test_percentual_fora_da_faixa_nao_vira_barra(tmp_path):
    """O rollout é editável com um `sed`. Isso não dá cota, mas obriga o WatchAI
    a peneirar o que lê em vez de desenhar qualquer coisa."""
    for valor in (150.0, -3.0, "muito", None, True):
        bruto = {"primary": {"used_percent": valor, "window_minutes": 300}}
        assert consumo("codex", bruto) is None, valor


def test_janela_de_tamanho_absurdo_fica_de_fora():
    assert consumo("codex", {"primary": {"used_percent": 10, "window_minutes": 0}}) is None
    assert consumo("codex", {"primary": {"used_percent": 10, "window_minutes": 10**9}}) is None


def test_carimbo_implausivel_perde_o_reset_mas_nao_a_barra():
    """Reset ruim custa o "zera em", não o percentual: são dois dados, e um
    contador que conta para trás é pior que contador nenhum."""
    for carimbo in (0, -1, 1.0, 99_999_999_999_999):
        achado = consumo("codex", {"primary": {"used_percent": 42, "window_minutes": 300, "resets_at": carimbo}})
        assert achado is not None and achado.curta.usado == 42.0, carimbo
        assert achado.curta.zera_em is None, carimbo
        assert achado.curta.falta(AGORA) is None


def test_reset_que_nao_cabe_na_janela_perde_o_contador():
    """Uma janela de 5 h não zera daqui a 70 anos. Só a faixa de época deixava
    passar um carimbo adulterado como "zera em 26755d22h" — número absurdo
    desenhado com cara de informação. O percentual fica; o contador, não."""
    achado = consumo("codex", {
        "primary": {"used_percent": 23, "window_minutes": 300, "resets_at": 4_102_444_000},
    }, medido=AGORA)
    assert achado.curta.usado == 23.0 and achado.curta.zera_em is None
    # E o que cabe continua valendo.
    achado = consumo("codex", {
        "primary": {"used_percent": 23, "window_minutes": 300, "resets_at": AGORA + 3600},
    }, medido=AGORA)
    assert achado.curta.zera_em == AGORA + 3600


def test_carimbo_em_milissegundos_tambem_vale():
    achado = consumo("codex", {"primary": {"used_percent": 42, "window_minutes": 300, "resets_at": AGORA * 1000}})
    assert achado.curta.zera_em == AGORA


def test_bloco_que_nao_e_janela_nao_vira_barra():
    """`credits`, `plan_type` e o `spend_limit` de quem usa gateway moram dentro
    do mesmo `rate_limits` e não são janela nenhuma."""
    achado = consumo("codex", CODEX)
    assert len(achado.janelas) == 2


def test_rate_limits_sem_janela_alguma_e_nada():
    assert consumo("codex", {"plan_type": "plus", "credits": {"balance": "0"}}) is None
    assert consumo("codex", "não é dicionário") is None
    assert consumo("codex", None) is None


# ---- o Claude Code chama o campo de outro jeito ------------------------------


def test_o_nome_do_campo_do_claude_tambem_vale():
    """`used_percent` no codex, `used_percentage` no Claude Code. Esquecer essa
    divergência faria a barra do Claude nunca aparecer — e calada."""
    achado = consumo("claude", {
        "primary": {"used_percentage": 8, "window_minutes": 300},
        "secondary": {"used_percentage": 31, "window_minutes": 10080},
    })
    assert (achado.curta.usado, achado.longa.usado) == (8.0, 31.0)


def test_janela_sem_tamanho_e_reconhecida_pelo_nome():
    """**É o formato real do Claude Code**, confirmado ao ligar a statusline na
    v2.1.278: ele manda `five_hour`/`seven_day` sem `window_minutes` nenhum. Sem
    reconhecer pelo nome, a barra do Claude não existiria — e falharia calada."""
    achado = consumo("claude", {
        "five_hour": {"used_percentage": 8, "resets_at": AGORA + 600},
        "seven_day": {"used_percentage": 31, "resets_at": AGORA + 86400},
    })
    assert achado.curta.minutos == 300 and achado.longa.minutos == 10080


def test_nome_desconhecido_e_sem_tamanho_fica_de_fora():
    """Janela que não se sabe medir não vira barra: rotular de 5 h o que pode ser
    de outro tamanho é inventar."""
    assert consumo("claude", {"quinzena": {"used_percentage": 12}}) is None


# ---- janela vencida: o número existe e não vale mais -------------------------


def test_janela_que_ja_virou_nao_mostra_percentual():
    """O caso comum, não o raro: você usou o codex ontem, a janela de 5 h virou
    de madrugada e o rollout guardou os 18% de antes."""
    janela = Janela(usado=18.0, minutos=300, zera_em=AGORA - 60)
    assert janela.vencida(AGORA)
    assert not Janela(usado=18.0, minutos=300, zera_em=AGORA + 60).vencida(AGORA)
    # Sem carimbo não há como saber que virou — e então não se afirma que virou.
    assert not Janela(usado=18.0, minutos=300).vencida(AGORA)


# ---- retrato que não guarda mais nada ----------------------------------------


def test_retrato_vencido_e_recente_continua_na_tela():
    """O caso normal: você usou o agente de madrugada, a janela de 5 h virou, e
    o percentual guardado não vale mais. Para isso existe o traço — o dado é de
    três horas atrás, a fonte está viva, e a tela diz a idade."""
    vencido = Consumo(
        kind="claude",
        curta=Janela(47.0, 300, AGORA - 3600),
        medido=AGORA - 3 * 3600,
    )
    assert vencido.janelas and not vencido.morto(AGORA)


def test_retrato_de_dias_com_tudo_vencido_sai_da_tela():
    """Dado nenhum com a cara de dado. Quando a fonte para de escrever, o mesmo
    arquivo fica ali por dias e a tela mostra para sempre dois traços e um
    "(2d16h ago)" — que é a tela de quem nunca instalou nada, só mais confusa.

    O retrato é o desta máquina, do dia em que outro programa tomou a
    statusline: medido há quase três dias, as duas janelas viradas."""
    morto = Consumo(
        kind="claude",
        curta=Janela(47.0, 300, AGORA - 2.6 * 86400),
        longa=Janela(87.0, 10080, AGORA - 1.3 * 86400),
        medido=AGORA - 2.7 * 86400,
    )
    assert morto.morto(AGORA)
    # A folga é contra a janela curta: o mesmo retrato, de duas horas atrás,
    # ainda é o caso normal de quem usou o agente de madrugada.
    assert not replace(morto, medido=AGORA - 2 * 3600).morto(AGORA)


def test_uma_janela_ainda_aberta_segura_o_retrato_inteiro():
    """Vencer **todas** é a condição: a semana que ainda corre é informação boa
    mesmo com a janela de 5 h virada."""
    meio = Consumo(
        kind="claude",
        curta=Janela(47.0, 300, AGORA - 86400),
        longa=Janela(87.0, 10080, AGORA + 86400),
        medido=AGORA - 20 * 86400,
    )
    assert not meio.morto(AGORA)


def test_sem_carimbo_de_medida_nao_se_afirma_que_morreu():
    """Quem não sabe quando mediu não pode decidir que o dado venceu de velho."""
    sem = Consumo(kind="claude", curta=Janela(47.0, 300, AGORA - 10 * 86400))
    assert not sem.morto(AGORA)


def test_o_rollout_da_semana_passada_tambem_sai(tmp_path):
    """O codex não precisa de configuração nenhuma, mas envelhece igual: quem
    não o usa há dias não tem notícia dele, e linha de dois traços não é
    notícia."""
    medido = AGORA - 9 * 86400
    rate = {
        "primary": {"used_percent": 22.0, "window_minutes": 300, "resets_at": medido + 3600},
        "secondary": {"used_percent": 17.0, "window_minutes": 10080, "resets_at": medido + 4 * 86400},
    }
    rollout(tmp_path, "velho", rate, quando=medido)
    assert LeitorCodex(tmp_path).ler(AGORA) is None
    # O de hoje continua aparecendo.
    rollout(tmp_path, "hoje", CODEX, quando=AGORA)
    assert LeitorCodex(tmp_path).ler(AGORA) is not None


def test_o_leitor_descarta_o_arquivo_que_nao_diz_mais_nada(tmp_path):
    medido = AGORA - 2.7 * 86400
    limits.gravar(
        {
            "kind": "claude",
            "medido": medido,
            # Como o Claude Code manda, e com os resets que ele mandaria: dentro
            # do próprio tamanho de cada janela a partir da medição.
            "rate_limits": {
                "five_hour": {"used_percentage": 47, "resets_at": medido + 2 * 3600},
                "seven_day": {"used_percentage": 87, "resets_at": medido + 1.3 * 86400},
            },
        },
        pasta=tmp_path,
    )
    leitor = LeitorClaude(tmp_path, tmp_path / "sem-claude")
    assert leitor.ler(AGORA) is None


# ---- por que falta o número --------------------------------------------------


def test_sem_statusline_o_leitor_diz_o_que_rodar(tmp_path):
    """A ausência tinha a mesma cara da falha. Agora ela se explica."""
    casa = tmp_path / "claude"
    casa.mkdir()
    (casa / "settings.json").write_text('{"model": "opus"}', encoding="utf-8")
    leitor = LeitorClaude(tmp_path / "lim", casa)
    assert leitor.ler(AGORA) is None
    assert "--install-statusline" in leitor.motivo


def test_statusline_de_outro_programa_e_dito_com_esse_nome(tmp_path):
    casa = tmp_path / "claude"
    casa.mkdir()
    (casa / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "outro-prog"}}), encoding="utf-8"
    )
    leitor = LeitorClaude(tmp_path / "lim", casa)
    assert leitor.ler(AGORA) is None
    assert "not ours" in leitor.motivo


def test_ligada_e_ainda_sem_arquivo_e_espera_e_nao_falha(tmp_path):
    """Instalou agora: o agente ainda não renderizou tela nenhuma. Dizer "rode o
    instalar" aqui faria a pessoa rodar duas vezes à procura de um problema que
    não existe."""
    casa = tmp_path / "claude"
    casa.mkdir()
    (casa / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "watchai --statusline"}}),
        encoding="utf-8",
    )
    leitor = LeitorClaude(tmp_path / "lim", casa)
    assert leitor.ler(AGORA) is None
    assert "first render" in leitor.motivo


def test_com_numero_na_mao_nao_ha_aviso_nenhum(tmp_path):
    limits.statusline(json.dumps(ENTRADA), pasta=tmp_path, agora=AGORA)
    leitor = LeitorClaude(tmp_path)
    assert leitor.ler(AGORA) is not None
    assert leitor.motivo == ""


def test_os_avisos_andam_junto_com_a_leitura():
    """O painel precisa dos dois na mesma volta: o que há, e por que falta o
    resto."""

    class SemNada:
        kind = "claude"
        motivo = "no data · run: watchai --install-statusline"

        def ler(self):
            return None

    class ComNumero:
        kind = "codex"
        motivo = ""

        def ler(self):
            return Consumo(kind="codex", curta=Janela(16.0, 300), medido=AGORA)

    lim = Limites(leitores=[SemNada(), ComNumero()])
    achados = lim.ler(1000.0)
    assert [c.kind for c in achados] == ["codex"]
    assert lim.avisos == {"claude": "no data · run: watchai --install-statusline"}


def test_leitor_quebrado_nao_inventa_aviso():
    class Quebrado:
        kind = "claude"

        def ler(self):
            raise RuntimeError("sem chance")

    lim = Limites(leitores=[Quebrado()])
    assert lim.ler(1000.0) == [] and lim.avisos == {}


# ---- o modo statusline -------------------------------------------------------


ENTRADA = {
    "workspace": {"current_dir": "/tmp/projeto"},
    "model": {"display_name": "Opus 5"},
    "cost": {"total_cost_usd": 1.2345},
    "rate_limits": {
        "primary": {"used_percentage": 8, "window_minutes": 300, "resets_at": AGORA + 3600},
        "secondary": {"used_percentage": 31, "window_minutes": 10080, "resets_at": AGORA + 86400},
    },
}


def test_a_statusline_grava_o_consumo_e_imprime_a_linha(tmp_path):
    linha = limits.statusline(json.dumps(ENTRADA), pasta=tmp_path, agora=AGORA)
    assert linha == "/tmp/projeto · Opus 5 · 5h 8% · 7d 31% · $1.23"
    gravado = json.loads((tmp_path / limits.ARQUIVO_CLAUDE).read_text(encoding="utf-8"))
    assert gravado["medido"] == AGORA and gravado["kind"] == "claude"
    # O bloco é guardado **como veio**: quando o formato mudar, quem se adapta é
    # o leitor, sem pedir ao usuário para rodar nada de novo.
    assert gravado["rate_limits"] == ENTRADA["rate_limits"]


def test_o_leitor_do_claude_le_o_que_a_statusline_gravou(tmp_path):
    """O caminho inteiro: o agente empurra, o WatchAI lê arquivo local."""
    limits.statusline(json.dumps(ENTRADA), pasta=tmp_path, agora=AGORA)
    achado = LeitorClaude(tmp_path).ler(AGORA)
    assert achado is not None and achado.kind == "claude"
    assert (achado.curta.usado, achado.longa.usado) == (8.0, 31.0)
    assert achado.medido == AGORA


def test_statusline_com_lixo_na_entrada_nao_levanta(tmp_path):
    """Isto roda dentro do agente, a cada render, no lugar do prompt dele: linha
    vazia é a única falha aceitável."""
    for entrada in ("", "não é json", "[]", "null", '{"rate_limits": "torto"}'):
        assert limits.statusline(entrada, pasta=tmp_path, agora=AGORA) == "", entrada
    assert not (tmp_path / limits.ARQUIVO_CLAUDE).exists()


def test_statusline_sem_limite_ainda_serve_de_statusline(tmp_path):
    """Versão de agente sem o campo: a linha continua útil, só sem as janelas."""
    linha = limits.statusline(json.dumps({"cwd": "/tmp/x", "model": {"id": "opus"}}), pasta=tmp_path, agora=AGORA)
    assert linha == "/tmp/x · opus"


def test_statusline_em_pasta_que_nao_da_para_escrever_ainda_imprime(tmp_path):
    """Disco cheio ou pasta sem permissão não pode comer o prompt de quem está
    trabalhando."""
    ocupado = tmp_path / "limits"
    ocupado.write_text("sou um arquivo, não uma pasta\n", encoding="utf-8")
    linha = limits.statusline(json.dumps(ENTRADA), pasta=ocupado, agora=AGORA)
    assert "5h 8%" in linha


def test_a_gravacao_e_atomica(tmp_path):
    """A statusline roda a cada render, e mais de uma sessão pode estar rodando:
    sem tmp + rename o WatchAI leria arquivo pela metade. O que sobra na pasta é
    só o arquivo final."""
    limits.statusline(json.dumps(ENTRADA), pasta=tmp_path, agora=AGORA)
    assert [p.name for p in tmp_path.iterdir()] == [limits.ARQUIVO_CLAUDE]


def test_arquivo_do_claude_ilegivel_nao_derruba_nada(tmp_path):
    (tmp_path / limits.ARQUIVO_CLAUDE).write_text("{quebrado\n", encoding="utf-8")
    assert LeitorClaude(tmp_path).ler() is None
    assert LeitorClaude(tmp_path / "nem existe").ler() is None


# ---- o cache, e o leitor que quebra ------------------------------------------


def test_a_leitura_fica_guardada_por_30_segundos(tmp_path):
    """A varredura roda a cada 2 s; abrir rollouts a cada volta seria pagar disco
    por um número que muda de hora em hora."""

    class Contador:
        def __init__(self):
            self.vezes = 0

        def ler(self):
            self.vezes += 1
            return Consumo(kind="codex", curta=Janela(10.0, 300))

    leitor = Contador()
    lim = Limites(leitores=[leitor])
    assert lim.ler(1000.0) and lim.ler(1001.0) and lim.ler(1029.0)
    assert leitor.vezes == 1
    lim.ler(1031.0)
    assert leitor.vezes == 2
    lim.invalidar()  # o que o `R` faz: vai ao disco sem esperar os 30 s
    lim.ler(1031.5)
    assert leitor.vezes == 3


def test_leitor_que_quebra_apaga_a_barra_dele_e_nao_o_app():
    class Quebrado:
        def ler(self):
            raise RuntimeError("formato novo")

    class Bom:
        def ler(self):
            return Consumo(kind="codex", curta=Janela(10.0, 300))

    achados = Limites(leitores=[Quebrado(), Bom()]).ler(1000.0)
    assert [c.kind for c in achados] == ["codex"]


def test_sem_numero_nenhum_a_lista_vem_vazia(tmp_path):
    assert Limites(home=tmp_path, pasta=tmp_path).ler(1000.0) == []


# ---- a barra ------------------------------------------------------------------


def test_cheio_e_vazio_sao_contados_separados():
    """A tela pinta os dois com cores diferentes: só o glifo separando ▓ de ░ é
    distinção fraca demais, e numa captura os dois viram o mesmo bloco."""
    from watchai.widgets.header import blocos

    assert blocos(0.0) == (0, 10)
    assert blocos(50.0) == (5, 5)
    assert blocos(100.0) == (10, 0)
    assert blocos(0.4) == (1, 9)  # uso acima de zero sempre acende um


def test_a_barra_nunca_fica_vazia_com_numero_ao_lado():
    """Barra vazia ao lado de "3%" é a barra mentindo."""
    assert barra(0.0) == "░" * 10
    assert barra(0.4).startswith("▓") and barra(0.4).count("▓") == 1
    assert barra(50.0) == "▓" * 5 + "░" * 5
    assert barra(100.0) == "▓" * 10
    assert barra(140.0) == "▓" * 10  # nunca transborda a largura


def test_a_cor_avisa_quando_aperta():
    from watchai.theme import colors

    palette = colors()
    assert cor_do_uso(10.0) == palette.text
    assert cor_do_uso(APERTA) == palette.yellow
    assert cor_do_uso(ESTOURANDO) == palette.red
    assert cor_do_uso(100.0) == palette.red


def test_fmt_span_le_de_relance():
    assert fmt_span(0) == "0s"
    assert fmt_span(45) == "45s"
    assert fmt_span(7 * 60) == "7m"
    assert fmt_span(3600) == "1h"
    assert fmt_span(4 * 3600 + 20 * 60) == "4h20m"
    assert fmt_span(4 * 86400 + 12 * 3600) == "4d12h"
    assert fmt_span(7 * 86400) == "7d"
    assert fmt_span(-10) == "0s"  # nunca negativo


# ---- na tela -------------------------------------------------------------------


class LimitesFixos:
    """Um `Limites` que devolve o que o teste mandou, sem tocar em disco."""

    def __init__(self, *consumos, avisos=None):
        self.consumos = list(consumos)
        self.avisos = dict(avisos or {})

    def ler(self, agora):
        return self.consumos

    def invalidar(self):
        pass


def _snapshot(*kinds):
    """Um snapshot com um agente de cada tipo pedido, num terminal cada."""
    from watchai.providers.source import ProcObs, Snapshot, TermObs

    nascimento = time.time() - 3600
    agentes, terminais = [], {}
    for i, kind in enumerate(kinds):
        tty = f"/dev/pts/{i + 1}"
        agentes.append(ProcObs(
            pid=1000 + i, kind=kind, label=kind, terminal=tty,
            terminal_label=tty.replace("/dev/", ""), terminal_started=nascimento,
            created=nascimento, cpu=10.0, cwd="/home/eu/proj", tool_children=0,
            ancestors=(), window_pid=None, window_app="",
        ))
        terminais[tty] = TermObs(tty, tty.replace("/dev/", ""), nascimento)
    return Snapshot(agents=tuple(agentes), terminals=terminais)


def header_texto(*consumos, size=(150, 40), avisos=None, rodando=()):
    """O que o header mostra, como texto, com estes limites."""
    from watchai.app import WatchAIApp
    from watchai.providers.source import Snapshot

    class Fonte:
        def snapshot(self):
            return _snapshot(*rodando) if rodando else Snapshot()

    async def main():
        app = WatchAIApp(mock=False, source=Fonte(), theme_key="watchai",
                         limites=LimitesFixos(*consumos, avisos=avisos))
        # Os diários vêm de uma pasta vazia: com agente na varredura, o leitor
        # iria procurar transcript no `~/.claude` de quem roda a suíte — que é
        # justamente o que nenhum teste daqui faz.
        app.provider.transcripts = Transcripts(Path(tempfile.gettempdir()) / "watchai-sem-diario")
        async with app.run_test(size=size) as pilot:
            app.scan()
            await app.workers.wait_for_complete()
            await pilot.pause()
            await pilot.pause()
            header = app.screen.query_one("#header")
            return str(header.render()), header.outer_size.height, app.screen.header_rows

    return asyncio.run(main())


def test_a_barra_aparece_com_as_duas_janelas_e_o_reset():
    agora = time.time()
    texto, altura, rows = header_texto(Consumo(
        kind="codex",
        curta=Janela(16.0, 300, agora + 2 * 3600),
        longa=Janela(18.0, 10080, agora + 4 * 86400),
        medido=agora,
    ))
    assert "codex" in texto
    assert " 16%" in texto and " 18%" in texto
    assert "5h" in texto and "7d" in texto
    # Quando cada janela zera. O valor exato anda com o relógio do teste; o que
    # importa é que as duas janelas trazem o seu.
    assert len(re.findall(r"· \d+[hdms]", texto)) == 2
    assert "▓" in texto and "░" in texto
    assert altura == 4 and rows == 4  # o header cresceu uma linha, e disse


def test_a_interface_de_95_e_100_por_cento(tmp_path):
    """Exercitar o alerta sem gastar cota para chegar nele: o número vem de um
    rollout escrito aqui, que é a saída que o próprio formato permite."""
    agora = time.time()
    for valor in (95.0, 100.0):
        rate = {"primary": {"used_percent": valor, "window_minutes": 300, "resets_at": agora + 600}}
        rollout(tmp_path, f"p{valor}", rate)
        achado = LeitorCodex(tmp_path).ler()
        assert achado.curta.usado == valor
        texto, _, _ = header_texto(achado)
        assert f"{valor:3.0f}%" in texto
        assert "▓▓▓▓▓▓▓▓▓▓" in texto  # 95% e 100% enchem a barra
        from watchai.theme import colors

        assert cor_do_uso(valor) == colors().red


def test_a_idade_do_dado_fica_a_vista_quando_o_numero_e_velho():
    """O número é tão fresco quanto o último uso daquele agente."""
    agora = time.time()
    velho = Consumo(kind="codex", longa=Janela(18.0, 10080, agora + 86400), medido=agora - 3 * 3600)
    texto, _, _ = header_texto(velho)
    assert "3h" in texto and "ago" in texto

    novo = Consumo(kind="codex", longa=Janela(18.0, 10080, agora + 86400), medido=agora)
    texto, _, _ = header_texto(novo)
    assert "ago" not in texto  # dado fresco não precisa se explicar


def test_janela_vencida_aparece_com_traco_e_nao_com_numero():
    agora = time.time()
    texto, _, _ = header_texto(Consumo(
        kind="codex",
        curta=Janela(18.0, 300, agora - 3600),  # virou há uma hora
        longa=Janela(18.0, 10080, agora + 4 * 86400),
        medido=agora - 5 * 3600,
    ))
    assert texto.count(" 18%") == 1  # só a janela que ainda vale
    assert "—" in texto


def test_o_aviso_ocupa_o_lugar_da_barra_que_nao_veio():
    """A tela de dois traços sem explicação era a mesma de quem nunca instalou
    nada. Agora o painel diz o que rodar."""
    texto, altura, rows = header_texto(
        avisos={"claude": "no data · run: watchai --install-statusline"},
        rodando=("claude",),
    )
    assert "claude" in texto and "--install-statusline" in texto
    assert altura == 4 and rows == 4  # o aviso custa a mesma linha que a barra


def test_aviso_de_agente_que_nao_esta_rodando_nao_aparece():
    """Recado sobre o Claude na tela de quem usa só o codex é ruído."""
    texto, altura, _ = header_texto(
        avisos={"claude": "no data · run: watchai --install-statusline"},
        rodando=("codex",),
    )
    assert "--install-statusline" not in texto
    assert altura == 3


def test_quem_tem_barra_nao_ganha_aviso_tambem():
    """Dizer "sem dado" ao lado do dado é contradição na mesma tela."""
    agora = time.time()
    texto, altura, _ = header_texto(
        Consumo(kind="claude", curta=Janela(12.0, 300, agora + 3600), medido=agora),
        avisos={"claude": "no data · run: watchai --install-statusline"},
        rodando=("claude",),
    )
    assert " 12%" in texto and "--install-statusline" not in texto
    assert altura == 4


def test_terminal_baixo_tambem_nao_paga_o_aviso():
    _, altura, _ = header_texto(
        avisos={"claude": "no data · run: watchai --install-statusline"},
        rodando=("claude",),
        size=(150, 18),
    )
    assert altura == 3


def test_sem_numero_o_header_nao_cresce():
    texto, altura, rows = header_texto()
    assert altura == 3 and rows == 3
    assert "ACTIVE" in texto


def test_terminal_baixo_nao_paga_a_barra_com_linhas_do_stream():
    """Limite de plano é a informação menos urgente da tela."""
    agora = time.time()
    _, altura, rows = header_texto(
        Consumo(kind="codex", curta=Janela(16.0, 300, agora + 3600), medido=agora),
        size=(150, 18),
    )
    assert altura == 3 and rows == 3


def test_o_teto_da_area_de_sessoes_desconta_o_header_que_cresceu():
    from watchai.layout import HEADER_ROWS, sessions_max_height

    base = sessions_max_height(40)
    assert sessions_max_height(40, HEADER_ROWS + 2) == base - 2
    # Header menor que o padrão não dá linhas de presente a ninguém.
    assert sessions_max_height(40, 1) == base
