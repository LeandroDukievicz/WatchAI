# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento conforme [SemVer](https://semver.org/lang/pt-BR/).

## [1.1.0] — 2026-09-22

### Adicionado (avisos e detecção fina)
- **Aviso em READY, INPUT e ERROR**, com um **timbre por estado** — avisar os
  três com o mesmo som obrigaria a olhar a tela para saber qual foi.
- **Notificação do sistema** junto do bip (`notify-send` · `osascript` · toast
  por PowerShell), **só quando o WatchAI não está em foco**.
- **Tempo real do estado**: `for MM:SS` conta da hora registrada no diário do
  agente, não de quando o app abriu. Fechar e reabrir não zera mais os contadores.
- **ERROR de verdade no Claude Code**: limite de uso e token expirado
  (`isApiErrorMessage`) — a sessão que parou e não volta sozinha.
- **Atividade por ferramenta para qualquer agente**: sem diário, mostra o
  processo filho que está rodando (`running npm test`).
- Leitor do **OpenCode** (layout `session/{info,message,part}`) — escrito a
  partir do storage do binário, ainda não validado contra sessão real.
- **Histórico do EVENT STREAM entre execuções** (`~/.config/watchai/events.json`).
- `scripts/install-linux.sh`: comando no PATH, lançador no menu, atalho opcional
  na área de trabalho, `--uninstall`.
- Interruptor dos avisos (`B`) salvo entre execuções.

### Mudado
- **Semáforo com mais presença**: a carcaça toma a cor da lâmpada acesa e a
  lâmpada ganha halo (fundo tingido da própria cor). Largura de 5 → 7 colunas.
- Debounce dos avisos passou a ser **por timbre**: rajada do mesmo estado vira um
  bip só, mas READY seguido de ERROR toca os dois.


### Adicionado
- **Detecção real das sessões**, sem integrar nada: varredura da tabela de
  processos (`psutil`, a cada 2 s, em thread) + leitura dos diários que os
  próprios agentes gravam (`~/.claude/projects/*.jsonl`, `~/.codex/sessions/…`).
  Sem API, hook, credencial ou configuração do agente.
- **Um card por terminal**, com os agentes dentro: quantos rodam ali, o estado
  de cada um e o que cada um está fazendo. O estado do card é o do agente que
  mais pede você (ERROR › INPUT › READY › WAITING › WORKING).
- Estado **IDLE**: aba aberta, nenhum agente rodando.
- Ciclo de vida do terminal fechado: OFFLINE por 5 minutos, aviso
  `⚠ removing in MM:SS` por mais 2, e some.
- `--mock` (dados simulados), `--theme` e `--version` na linha de comando.
- Coluna AGENTS na visão LIST e bloco AGENTS no modal de detalhes.
- CI também em Windows e macOS, já que a detecção trata os três sistemas.
- **Seletor de temas (`T`)** com 8 paletas — WatchAI (padrão), Light, Dark,
  Night Owl, Vampire (Dracula), Cyberpunk, Steampunk e Grey (sem matiz). Mover a
  seleção aplica o tema na hora (preview ao vivo do dashboard inteiro), `ENTER`
  salva e `ESC` desfaz.
- Preferências guardadas em `$XDG_CONFIG_HOME/watchai/config.json`: o tema
  escolhido volta na próxima execução. Arquivo ilegível ou tema desconhecido
  caem no padrão, sem derrubar a TUI.

### Mudado
- As cores deixaram de ser constantes de módulo fixadas no import: quem desenha
  resolve a cor na hora de renderizar (`colors().cyan`), e `Status` guarda a
  *vaga* na paleta em vez da cor — é o que permite trocar de tema com o app
  rodando, sem tocar em widget nenhum.
- `__version__` estava em `0.1.0`, fora de sincronia com o `pyproject.toml`.

### Corrigido
- Rodapé do modal de temas quebrava para a linha de baixo (40 colunas numa caixa
  de 38 úteis).

## [1.0.0] — 2026-09-21

Primeira versão da camada visual. **Todos os dados são mockados** — não há
detecção de processos nem integração com nenhuma IA (ver "Roadmap" no README).

### Adicionado
- Dashboard com header (resumo global + relógio), painel SESSIONS, EVENT STREAM e keybar.
- Semáforo de 3 lâmpadas por card: vermelha (ERROR), amarela (WORKING, WAITING,
  STARTING e INPUT piscando) e verde (READY). OFFLINE apaga as três.
- Bip sonoro quando uma sessão entra em READY, tocado pelo servidor de som para
  funcionar com a aba do terminal em segundo plano. `B` liga/desliga.
- Duas visões: CARDS e LIST (`V`), modal de detalhes (`ENTER`) e ajuda (`?`).
- Layout responsivo: 3 / 2 / 1 coluna e modo compacto abaixo de 60 colunas.
- Simulador que troca os estados sozinho a cada 5–12 s para avaliar a UI em movimento.
- Suíte de testes headless (17 testes) e CI no GitHub Actions.

[1.1.0]: https://github.com/LeandroDukievicz/WatchAI/releases/tag/1.1.0
[1.0.0]: https://github.com/LeandroDukievicz/WatchAI/tree/v1.0.0
