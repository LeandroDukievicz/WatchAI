"""Ligar o consumo do Claude Code em **qualquer** máquina, sem estragar nada.

Nenhum teste aqui toca no `~/.claude` de quem roda a suíte: o `settings.json` é
um arquivo de mentira num `tmp_path`, e a config do WatchAI já vem isolada pelo
conftest.

O que está sob teste não é "escreve uma linha no JSON" — é a promessa de que
instalar um monitor **não custa** a statusline que a pessoa já usava.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from watchai import config, statusline
from watchai.providers import limits

# Uma statusline de verdade, do tipo que alguém já teria: lê o JSON do agente na
# entrada padrão e imprime a sua própria linha.
MINHA = (
    f'"{sys.executable}" -c '
    '"import json,sys; d=json.load(sys.stdin); print(\'[meu prompt]\', d[\'model\'][\'display_name\'])"'
)

ENTRADA = json.dumps({
    "model": {"display_name": "Opus 5"},
    "workspace": {"current_dir": "/tmp/projeto"},
    "rate_limits": {"primary": {"used_percentage": 44, "window_minutes": 300}},
})


def claude(tmp_path, **settings):
    """Um `~/.claude` de mentira, com o settings.json que o teste quiser."""
    casa = tmp_path / "claude"
    casa.mkdir(parents=True, exist_ok=True)
    (casa / "settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return casa


def lido(casa, nome="settings.json"):
    return json.loads((casa / nome).read_text(encoding="utf-8"))


# ---- a máquina de quem nunca configurou nada ---------------------------------


def test_maquina_limpa_ganha_a_statusline(tmp_path):
    casa = claude(tmp_path, model="opus")
    r = statusline.instalar(casa, nosso="watchai --statusline")
    assert r.ok
    linha = lido(casa)["statusLine"]
    assert linha["command"] == "watchai --statusline"
    assert linha["type"] == "command"
    # Sem `refreshInterval` o número congela quando a sessão fica parada — e é a
    # sessão parada que envelhece o dado.
    assert linha["refreshInterval"] == statusline.REFRESH_MS


def test_as_outras_preferencias_do_agente_ficam_intactas(tmp_path):
    """Estamos escrevendo no arquivo de configuração de outro programa."""
    casa = claude(tmp_path, model="opus", permissions={"allow": ["Bash(ls)"]}, enabledPlugins=["x"])
    statusline.instalar(casa, nosso="watchai --statusline")
    dados = lido(casa)
    assert dados["model"] == "opus"
    assert dados["permissions"] == {"allow": ["Bash(ls)"]}
    assert dados["enabledPlugins"] == ["x"]


def test_sem_claude_code_nao_cria_pasta_nenhuma(tmp_path):
    ausente = tmp_path / "nao-existe"
    r = statusline.instalar(ausente)
    assert not r.ok and "não achei o Claude Code" in r.mensagem
    assert not ausente.exists()


def test_backup_do_settings_antes_de_mexer(tmp_path):
    casa = claude(tmp_path, model="opus")
    statusline.instalar(casa, nosso="watchai --statusline")
    backup = casa / ("settings.json" + statusline.SUFIXO_BACKUP)
    assert backup.is_file()
    assert "statusLine" not in json.loads(backup.read_text(encoding="utf-8"))


# ---- a máquina de quem JÁ tinha uma statusline --------------------------------


def test_a_statusline_que_ja_existia_nao_e_perdida(tmp_path):
    """O ponto inteiro deste módulo. Antes disto, o README mandava a pessoa
    colar a nossa por cima da dela."""
    casa = claude(tmp_path, statusLine={"type": "command", "command": MINHA, "padding": 0})
    r = statusline.instalar(casa, nosso="watchai --statusline")
    assert r.ok and "não** foi perdida" in r.mensagem
    assert lido(casa)["statusLine"]["command"] == "watchai --statusline"
    assert config.load_statusline_wrapped() == MINHA
    # As opções que eram dela continuam sendo dela.
    assert lido(casa)["statusLine"]["padding"] == 0


def test_a_linha_que_o_agente_mostra_continua_sendo_a_dela(tmp_path):
    """E o consumo é guardado do mesmo jeito: era isso que o WatchAI vinha
    fazer aqui."""
    casa = claude(tmp_path, statusLine={"type": "command", "command": MINHA})
    statusline.instalar(casa, nosso="watchai --statusline")
    saida = limits.statusline(ENTRADA, pasta=tmp_path / "lim", agora=1_790_700_000.0)
    assert saida == "[meu prompt] Opus 5"
    guardado = json.loads((tmp_path / "lim" / limits.ARQUIVO_CLAUDE).read_text(encoding="utf-8"))
    assert guardado["rate_limits"] == {"primary": {"used_percentage": 44, "window_minutes": 300}}


def test_sem_embrulhada_a_linha_e_a_nossa(tmp_path):
    saida = limits.statusline(ENTRADA, pasta=tmp_path, agora=1_790_700_000.0, embrulhada=None)
    assert saida == "/tmp/projeto · Opus 5 · 5h 44%"


def test_embrulhada_que_trava_nao_pendura_o_prompt(tmp_path, monkeypatch):
    """Ela roda a cada render da tela de quem está trabalhando: se demorar, a
    nossa linha assume em vez de a tela travar."""
    monkeypatch.setattr(limits, "ESPERA_EMBRULHADA", 0.5)
    dorminhoco = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    saida = limits.statusline(ENTRADA, pasta=tmp_path, agora=1_790_700_000.0, embrulhada=dorminhoco)
    assert saida == "/tmp/projeto · Opus 5 · 5h 44%"


def test_embrulhada_que_falha_cai_na_nossa_linha(tmp_path):
    for comando in ("watchai-comando-que-nao-existe-de-jeito-nenhum", f'"{sys.executable}" -c ""'):
        saida = limits.statusline(ENTRADA, pasta=tmp_path, agora=1_790_700_000.0, embrulhada=comando)
        assert saida == "/tmp/projeto · Opus 5 · 5h 44%", comando


def test_a_embrulhada_recebe_o_json_igual(tmp_path):
    """Ela espera na entrada padrão exatamente o que o agente mandaria."""
    eco = f'"{sys.executable}" -c "import sys; print(len(sys.stdin.read()))"'
    saida = limits.statusline(ENTRADA, pasta=tmp_path, agora=1_790_700_000.0, embrulhada=eco)
    assert saida == str(len(ENTRADA))


# ---- rodar de novo, e desfazer ------------------------------------------------


def test_instalar_duas_vezes_nao_embrulha_a_nossa_propria(tmp_path):
    casa = claude(tmp_path, statusLine={"type": "command", "command": MINHA})
    statusline.instalar(casa, nosso="watchai --statusline")
    statusline.instalar(casa, nosso="watchai --statusline")
    statusline.instalar(casa, nosso="watchai --statusline")
    assert config.load_statusline_wrapped() == MINHA  # a original, não a nossa
    assert lido(casa)["statusLine"]["command"] == "watchai --statusline"


def test_instalar_de_novo_atualiza_o_caminho_do_comando(tmp_path):
    """Quem trocou de clone por pipx precisa que a linha aponte para o novo."""
    casa = claude(tmp_path)
    statusline.instalar(casa, nosso="/velho/watchai --statusline")
    r = statusline.instalar(casa, nosso="watchai --statusline")
    assert r.ok and "já estava ligada" in r.mensagem
    assert lido(casa)["statusLine"]["command"] == "watchai --statusline"


def test_desinstalar_devolve_a_original(tmp_path):
    casa = claude(tmp_path, statusLine={"type": "command", "command": MINHA, "padding": 0})
    statusline.instalar(casa, nosso="watchai --statusline")
    r = statusline.desinstalar(casa)
    assert r.ok
    assert lido(casa)["statusLine"] == {"type": "command", "command": MINHA, "padding": 0}
    assert config.load_statusline_wrapped() is None


def test_desinstalar_sem_original_so_tira_a_chave(tmp_path):
    casa = claude(tmp_path, model="opus")
    statusline.instalar(casa, nosso="watchai --statusline")
    assert statusline.desinstalar(casa).ok
    dados = lido(casa)
    assert "statusLine" not in dados and dados["model"] == "opus"


def test_desinstalar_nao_mexe_na_statusline_de_outro(tmp_path):
    casa = claude(tmp_path, statusLine={"type": "command", "command": MINHA})
    r = statusline.desinstalar(casa)
    assert not r.ok and "não é a do WatchAI" in r.mensagem
    assert lido(casa)["statusLine"]["command"] == MINHA


def test_desinstalar_em_maquina_sem_nada_nao_reclama(tmp_path):
    casa = claude(tmp_path, model="opus")
    assert statusline.desinstalar(casa).ok


# ---- o arquivo certo, e o comando certo ---------------------------------------


def test_o_arquivo_local_e_quem_manda(tmp_path):
    """Escrever no settings.json quando o `.local` define a statusLine seria
    escrever num lugar que o outro sobrescreve: a barra nunca apareceria, e sem
    erro nenhum na tela explicando por quê."""
    casa = claude(tmp_path, model="opus")
    (casa / "settings.local.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "a-minha"}}), encoding="utf-8"
    )
    r = statusline.instalar(casa, nosso="watchai --statusline")
    assert r.ok
    assert lido(casa, "settings.local.json")["statusLine"]["command"] == "watchai --statusline"
    assert "statusLine" not in lido(casa)  # o settings.json não foi tocado


def test_os_dois_arquivos_com_statusline_viram_aviso(tmp_path):
    casa = claude(tmp_path, statusLine={"type": "command", "command": "a-do-settings"})
    (casa / "settings.local.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "a-do-local"}}), encoding="utf-8"
    )
    r = statusline.instalar(casa, nosso="watchai --statusline")
    assert r.ok and "também define uma statusLine" in r.mensagem


def test_instalado_num_bin_global_vira_nome_puro(monkeypatch):
    """Nome puro é legível e continua certo depois de uma atualização — mas só
    vale onde qualquer shell acha o executável."""
    monkeypatch.setattr(statusline.shutil, "which", lambda _: "/usr/local/bin/watchai")
    assert statusline.comando() == "watchai --statusline"
    monkeypatch.setattr(statusline.shutil, "which", lambda _: str(Path.home() / ".local/bin/watchai"))
    assert statusline.comando() == "watchai --statusline"


def test_instalado_num_venv_vira_caminho_absoluto(monkeypatch):
    """O furo que só aparece na máquina de outra pessoa: `watchai` dentro de um
    venv funciona no terminal de quem ativou o venv e **não** funciona quando o
    Claude Code chama, porque ele executa com o PATH dele. O resultado é
    `sh: watchai: not found`, statusline vazia e nenhum erro na tela."""
    monkeypatch.setattr(statusline.shutil, "which", lambda _: "/home/eu/proj/.venv/bin/watchai")
    assert statusline.comando() == "/home/eu/proj/.venv/bin/watchai --statusline"


def test_caminho_com_espaco_e_citado(monkeypatch):
    monkeypatch.setattr(statusline.shutil, "which", lambda _: "/home/eu/meus projetos/.venv/bin/watchai")
    assert statusline.comando() == '"/home/eu/meus projetos/.venv/bin/watchai" --statusline'


def test_sem_executavel_vale_o_interpretador(monkeypatch):
    """Quem roda de um clone, por `python -m watchai`."""
    monkeypatch.setattr(statusline.shutil, "which", lambda _: None)
    gerado = statusline.comando()
    assert "-m watchai --statusline" in gerado and sys.executable in gerado


def test_reconhece_a_nossa_statusline_em_qualquer_forma():
    assert statusline.e_nosso({"command": "watchai --statusline"})
    assert statusline.e_nosso({"command": '"/opt/venv/bin/python" -m watchai --statusline'})
    assert statusline.e_nosso("watchai --statusline")
    assert not statusline.e_nosso({"command": "starship prompt"})
    assert not statusline.e_nosso({"command": "watchai --mock"})
    assert not statusline.e_nosso(None)
