# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/);
versionamento conforme [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- **Suporte à extensão [Window Calls]** do GNOME: com ela instalada, o `⇧A` foca
  a **janela exata** por PID mesmo no Wayland — é a única forma de foco preciso
  ali. Sem ela, segue o caminho anterior (levantar o terminal + sino na aba).
- **Instalação por `pipx`** como caminho principal, igual nos três sistemas, com
  job no CI que instala e roda o comando em Linux, macOS e Windows.
- Workflow de publicação no PyPI (inerte até a variável `PYPI_READY` existir).

### Corrigido
- **Pensamento longo virava "tarefa concluída".** O diário do agente só é
  escrito quando a mensagem fecha, e um pensamento longo passa dos dois minutos
  do `FRESCOR` sem gastar CPU nenhuma — a espera é do outro lado da rede. Com o
  diário "velho" e o processo parado, o estado caía em READY: o card acendia o
  **verde** e ainda apitava "pode vir buscar" com o agente no meio da rodada.
  Uma rodada em aberto agora é WAITING (âmbar): um turno que termina deixa texto
  no diário, e é esse texto que vira READY.
- **Limite de uso do codex ficava verde.** Ao bater o limite, o codex fecha a
  rodada com `task_complete` — o motivo vem **dentro** do evento, em `error`,
  com `last_agent_message: null`. O leitor olhava só o tipo e dava a sessão como
  concluída. Agora é ERROR (vermelho), com a primeira frase do erro na linha do
  card ("You've hit your usage limit").
- **O mesmo sucesso falso existia no Windows e no macOS.** O `AppActivate`
  devolve `True`/`False`, mas o PowerShell sai com código zero nos dois casos, e
  era só o código que se lia. Agora o script confere com `GetForegroundWindow`
  quem ficou em primeiro plano, restaura a janela minimizada (`SW_RESTORE`) e
  responde `RAISED`/`REFUSED`. No macOS, `set frontmost` levanta o app e não a
  janela, e não tira nada da Dock: o AppleScript passou a escolher a janela pela
  marca da tty, zerar o `AXMinimized`, levantar com `AXRaise` e conferir. Sem
  permissão de Acessibilidade o `osascript` falha, e aí o recado diz isso em vez
  de prometer foco.
- **A identificação por tty vale no X11 também**, com `wmctrl` e `xdotool`: o
  título das janelas tem o mesmo problema ali, e o mecanismo é o mesmo.
- **A dica de instalar a Window Calls só aparece no GNOME.** No KDE ou no sway
  ela mandava o usuário atrás de uma extensão que não existe lá.
- **`⇧A` anunciava foco que não acontecia.** No Wayland, o
  `org.freedesktop.Application.Activate` devolve código zero mesmo quando o
  compositor ignora o pedido — e o WatchAI lia esse zero como sucesso. Agora:
  - com a **[Window Calls]** instalada, a janela é **restaurada** (`Unminimize`,
    que faltava: `Activate` não traz de volta uma janela minimizada), ativada e
    **conferida** relendo o `focus` da lista;
  - **sem** a extensão, no Wayland, o `Activate` do terminal nem é tentado: ali
    ele só produziria sucesso falso. Sobra o sino, e o recado diz o que instalar;
  - **a janela da sessão passou a ser identificada pela tty**, não pelo título:
    com um servidor de terminal todas as janelas têm o mesmo PID, e o título é
    de quem está rodando na aba (o agente, um player, o prompt) — numa máquina
    com quatro janelas abertas o `⇧A` levantava a errada. Agora o WatchAI marca
    a tty com um título único, vê quem ficou com ele e devolve o título de
    antes; quando isso não é possível, o desempate por diretório e nome segue
    valendo.
  - **leitura do GVariant com aspas duplas**: basta uma janela com apóstrofo no
    título para o `gdbus` trocar o delimitador de `'` para `"` e escapar as
    internas. O parser só entendia o primeiro caso, então **um nome de música
    numa aba qualquer** fazia o WatchAI concluir que a extensão não estava
    instalada.
- Os recados do `⇧A` passaram para o inglês, como o resto da interface.

### Mudado
- **Semáforo maior e mais redondo**: cada lâmpada passou a ocupar **duas linhas
  cheias com os cantos cortados** (um octógono, ~10× a área do ponto anterior),
  numa carcaça de 9 colunas. O card foi de 7 para 10 linhas — a 150×36 continuam
  cabendo duas fileiras. No modo estreito entra a versão pequena.
- **Cores do semáforo mais vivas**: vermelho `#FF2A45`, âmbar `#FFC400`, verde
  `#00FF85`.
- O halo da lâmpada acesa foi para **as células ao lado** da bola: atrás dela, o
  fundo preenchia os cantos cortados e a bola virava um retângulo.
- **`G` virou `⇧A`** (Shift+A).
- **Tema claro corrigido na raiz**: os níveis de apagado, tinta e borda passaram
  a depender da polaridade da paleta. No Light, bordas de estado saíram de 1,5:1
  para 2,5:1, lâmpadas apagadas de 1,2:1 para 1,7:1 e o `ghost` do OFFLINE de
  1,8:1 para 2,5:1 — antes, simplesmente não apareciam.
- `.gitignore`: `.env`, `*.log`, `.tox/`, `*.orig`, `*.rej` e o rascunho
  `docs/publicacao-snap.html`.

- **A notificação do sistema agora começa desligada.** Pop-up atravessa a tela
  de quem está trabalhando: quem decide se quer é o usuário (`N`). O bip
  continua ligado por padrão — ele avisa sem atrapalhar.

- **O card inteiro veste a cor da lâmpada**: âmbar em WORKING, WAITING,
  STARTING e INPUT; verde em READY; vermelho em ERROR. Antes só READY, INPUT e
  ERROR tingiam, e os estados "calmos" ficavam propositalmente apagados — a
  regra virou "o card é o semáforo em tamanho grande".
- **Lâmpadas redondas**: as pontas passaram a ser cortadas por **quadrantes**
  (25% nos dois eixos) e a bola encolheu de 5 para 4 células de largura, que na
  proporção do terminal é um quadrado. Antes o corte valia 10% na horizontal
  contra 25% na vertical, e o resultado era um retângulo de cantos lascados.

- **Lâmpadas em octógono regular** (6 células × 3 linhas, cantos cortados em
  diagonal). Com 2 linhas cabia um único degrau por canto, que o olho lê como
  entalhe; com 3, a diagonal aparece. O card foi de 10 para 13 linhas: a 150×36
  passam a caber 3 cards de uma vez, em vez de 6.
- **Semáforo sem fundo próprio**: a carcaça ficou transparente e o card aparece
  através dela, em vez do retângulo escuro que havia atrás das lâmpadas.
- **Lâmpada acesa em neon**: miolo cheio, ponta cortada em tom intermediário e
  o **vazio dos cantos cortados tingido** — é o que faz o halo seguir a forma.
  Desenhar o halo com quadrantes ao lado da bola engrossava a silhueta onde ela
  já é larga e transformava o octógono numa cruz.

- **Registro de agentes ampliado para uso geral**, não para o que está
  instalado numa máquina só: Antigravity, Grok, DeepSeek, Qwen Code, OpenHands,
  Plandex e Continue entraram, e o `gh copilot` passou a ser reconhecido como
  subcomando. São 17 agentes conhecidos.
- **Agentes definidos pelo usuário** em `~/.config/watchai/config.json`
  (`{"agents": {"meu-agente": ["meuprog"]}}`): chave nova cria um tipo, chave
  conhecida vira apelido. O ecossistema ganha CLI nova toda semana e ninguém
  deveria esperar uma release para ver a própria sessão na tela.
- Agente **sem terminal** (dentro de uma IDE) agora vira um card identificado
  pelo próprio processo (`antigravity #4312`) em vez de um card sem nome.

- **Responsividade em dois eixos.** A altura passou a decidir o tamanho do card
  — antes, abaixo de 130×30 o card de 13 linhas não cabia na área de sessões e
  **nenhum card aparecia inteiro**. Agora ele desce em degraus: full (13) →
  short (7) → compact (5) → **micro (1 linha)**, onde sobram só o nome e as três
  lâmpadas deitadas. A 40×12 cabem quatro sessões; antes, nenhuma.
- **Semáforo deitado** (`● ● ●`), o formato para janelas minúsculas.

### Mudado (ciclo de vida)
- **Sessão sem agente agora tem prazo**, mesmo com a aba aberta. Antes, agente
  encerrado com o terminal vivo virava `IDLE` e o card ficava **para sempre** —
  só a aba fechada tinha contagem. O card monitora a sessão de IA, não o
  terminal: sem agente, ela acabou. OFFLINE por 5 minutos, aviso por 2, e sai.
- O estado `IDLE` deixou de existir.

### Corrigido
- **O app morria ao abrir ou fechar um agente** com outro já na tela.
  Reconstruir a lista de cards a cada mudança parecia inofensivo, mas o
  `remove()` do Textual é **assíncrono**: remontar na mesma volta recriava
  `card-1` com o antigo ainda no DOM, e o `DuplicateIds` derrubava tudo. Agora
  a reconciliação tira só quem saiu (aguardando a remoção) e põe só quem
  entrou — quem permanece nem é tocado, então também não pisca nem perde o
  scroll.
- Detalhes abertos de uma sessão que sai do store agora **fecham sozinhos**, em
  vez de estourar `IndexError` ao procurar a sessão que não existe mais.
- Uma varredura que levanta exceção não derruba mais o app: ele segue com o que
  já sabia e registra o erro.
- Matar um processo de notificação que já havia morrido sozinho levantava
  `ProcessLookupError` e chegava como **falha de worker** — o CI do Windows
  quebrou por isso. E a suíte passou a silenciar o notificador do sistema, como
  já silenciava o áudio: rodar os testes não pode disparar toast de verdade.

[Window Calls]: https://extensions.gnome.org/extension/4724/window-calls/

### Adicionado (antes)
- **`G` — ir para a janela da sessão**: põe na frente o terminal onde o agente
  roda (`System Events` no macOS, `AppActivate` no Windows, `wmctrl`/`xdotool`
  no X11, `org.freedesktop.Application.Activate` no Wayland) e toca o **sino na
  tty** para marcar a aba certa. O rodapé diz o que conseguiu fazer, sem fingir
  sucesso onde o sistema não deixou.
- **`N` liga/desliga a notificação do sistema**, com interruptor próprio no
  rodapé e escolha salva — separado do bip (`B`).

### Mudado
- **Semáforo idêntico ao ícone do app**: carcaça de contorno cyan e interior
  escuro, como em `assets/watchai.svg`. A lâmpada acesa mantém o halo.
- **Modo estreito** (abaixo de 60 colunas): ficam o nome, o projeto e o
  semáforo; o resto do texto sai. Antes era o semáforo que saía.

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

- **A notificação do sistema agora começa desligada.** Pop-up atravessa a tela
  de quem está trabalhando: quem decide se quer é o usuário (`N`). O bip
  continua ligado por padrão — ele avisa sem atrapalhar.

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
