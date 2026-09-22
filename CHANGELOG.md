# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento conforme [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
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

[1.0.0]: https://github.com/LeandroDukievicz/WatchAI/tree/v1.0.0
