# Milestones

Onde o WatchAI está e o que falta. Cada item diz **o que é**, **por que importa**
e **onde mexer** — para dar para pegar um e fazer sem redescobrir o contexto.

Atualizado em 2026-09-23.

---

## ✅ Feito

### M0 — camada visual (1.0.0)

- [x] Dashboard: header com resumo global, painel SESSIONS, EVENT STREAM, keybar
- [x] Semáforo de 3 lâmpadas por card (a identidade do produto)
- [x] Visões CARDS e LIST, modal de detalhes, ajuda
- [x] Layout responsivo de 20×10 a 300×80, sem vão morto
- [x] Bip pelo servidor de som (toca com a aba em segundo plano)
- [x] Suíte headless + CI


### M1 — temas

- [x] 8 paletas (WatchAI, Light, Dark, Night Owl, Vampire, Cyberpunk, Steampunk, Grey)
- [x] Preview ao vivo: mover a seleção aplica no dashboard inteiro
- [x] Persistência em `~/.config/watchai/config.json`
- [x] Teste que garante que toda paleta fornece cada variável `$aw-*` do TCSS


### M2 — detecção real

- [x] Varredura de processos (`psutil`), em thread, a cada 2 s
- [x] Um card por terminal (tty; no Windows, o shell ancestral)
- [x] Agentes listados dentro do card, cada um com o seu estado
- [x] Desduplicação da árvore de processos (o `codex` são 3 processos, 1 agente)
- [x] Reconhecimento por programa/pacote — um plugin com "claude" no caminho não conta
- [x] Diário do Claude Code e do Codex: READY · WORKING · INPUT · WAITING
- [x] Ciclo do terminal: IDLE → OFFLINE → aviso aos 5 min → some aos 7
- [x] `--mock`, `--theme`, `--version`
- [x] CI em Ubuntu (3.10–3.14), Windows e macOS


### M3 — o aviso chega em você (1.1.0)

- [x] **Semáforo com mais presença**: carcaça tingida da cor acesa e halo atrás
      da lâmpada (fundo da própria cor), largura de 5 → 7 colunas
- [x] **Aviso em READY, INPUT e ERROR**, com **um timbre por estado** — avisar
      os três com o mesmo som obrigaria a olhar a tela para saber qual foi
- [x] **Notificação do sistema** (`notify-send` · `osascript` · toast por
      PowerShell), **só quando o WatchAI não está em foco**: se você já está
      olhando, o pop-up é ruído
- [x] Debounce **por timbre**: rajada do mesmo aviso vira um bip só, mas
      READY seguido de ERROR toca os dois
- [x] `B` liga/desliga os dois e a escolha fica salva entre execuções
- [x] **Tempo real do estado**: `for MM:SS` conta da hora que o diário registrou,
      não de quando o app abriu (carimbo no futuro é aparado, para não virar
      contador negativo)
- [x] **ERROR de verdade no Claude Code**: `isApiErrorMessage` pega limite de
      uso e token expirado — a sessão que parou e não volta sozinha


### M4 — mais agentes

- [x] **Atividade por ferramenta para qualquer agente**: sem diário, o que ele
      está fazendo é o processo filho que ele abriu (`running npm test`),
      ignorando processos auxiliares do próprio agente
- [x] **OpenCode**: leitor escrito a partir do layout do storage
      (`session/{info,message,part}`) — ⚠️ **não validado contra sessão real**
- [x] ~~**Gemini CLI**~~ — **não dá com o que ele grava hoje**: o
      `~/.gemini/tmp/<projeto>/logs.json` registra só as mensagens do usuário,
      sem resposta, sem ferramenta e sem fim de turno


### M5 — permanência e distribuição

- [x] **Histórico do EVENT STREAM entre execuções** (`~/.config/watchai/events.json`)
- [x] **Instalador no repositório**: `scripts/install-linux.sh` (comando no PATH,
      lançador no menu, atalho opcional na área de trabalho, `--uninstall`)
- [x] Ícone versionado em `assets/watchai.svg`
- [x] Landing page atualizada (`docs/index.html`)
- [x] Metadados do pacote (descrição, URLs) e versão 1.1.0
- [x] **Release 1.1.0** publicada (tag `1.1.0`)

---


### M6 — chegar na janela (pós-1.1.0)

- [x] **Semáforo idêntico ao ícone** (`assets/watchai.svg`): carcaça de contorno
      cyan, interior escuro, lâmpada acesa com halo
- [x] **`G` leva você até a janela** da sessão selecionada — `System Events` no
      macOS, `AppActivate` no Windows, `wmctrl`/`xdotool` no X11 (título
      desempata quando o servidor de terminal hospeda várias janelas) e
      `org.freedesktop.Application.Activate` no Wayland — este último **não
      funciona**, como o M10 descobriu: ele responde sucesso e o compositor
      ignora o pedido
- [x] **Sino na tty da sessão**: marca a aba certa e faz a janela piscar na
      dock — é o que resolve o que o Wayland não deixa resolver
- [x] **`N` liga/desliga a notificação** sem mexer no bip, com interruptor
      próprio no rodapé e escolha salva
- [x] **Modo estreito**: sobram nome, projeto e semáforo — o resto do texto sai,
      porque ler três lâmpadas não precisa de texto


### M7 — o semáforo cresce, o Light funciona, o pipx garante os três

- [x] **Lâmpadas com ~10× a área**: duas linhas cheias com os cantos cortados
      (octógono), carcaça de 9 colunas, cores mais vivas
- [x] **Halo ao lado da bola**, não atrás — atrás, ele preenchia os cantos
      cortados e a bola virava retângulo
- [x] **Tema claro corrigido na raiz**: níveis de apagado/tinta/borda dependem
      da polaridade da paleta; contraste medido antes e depois
- [x] **`⇧A`** no lugar do `G`
- [x] **Window Calls**: foco de janela exato no Wayland quando a extensão existe
- [x] **`pipx` verificado nos três sistemas** por job de CI
- [x] Workflow de publicação no PyPI, inerte até `PYPI_READY`
- [x] `.gitignore` auditado


### M8 — detecção para todo mundo, não só para esta máquina

- [x] **17 agentes conhecidos** no registro (Claude Code, Codex, Gemini,
      Antigravity, OpenCode, Aider, Copilot, Grok, DeepSeek, Qwen, Cursor,
      Crush, Goose, Amp, OpenHands, Plandex, Continue), com `gh copilot` como
      subcomando
- [x] **Agentes definidos pelo usuário** na config — o ecossistema muda toda
      semana e ninguém espera release para ver a própria sessão
- [x] Agente **sem terminal** (dentro de uma IDE) vira card identificado pelo
      processo, em vez de card sem nome
- [x] Teste que percorre o registro inteiro: erro de digitação na tabela viraria
      um agente invisível para quem usa aquele CLI


### M9 — a janela funciona em qualquer tamanho, e o card tem fim

- [x] **Responsividade em dois eixos**: largura manda nas colunas, **altura
      manda no tamanho do card**. Abaixo de 130×30 o card de 13 linhas não
      cabia e nenhum aparecia inteiro
- [x] Escada de formatos: full (13) → short (7) → compact (5) → **micro (1
      linha)**, onde sobram o nome e as três lâmpadas deitadas
- [x] **Semáforo deitado** (`● ● ●`) para janelas minúsculas
- [x] Teste que varre de 20×10 a 300×80: nada estoura, keybar e EVENT STREAM
      nunca somem, semáforo sempre presente
- [x] **Sessão sem agente tem prazo** mesmo com a aba aberta — antes, agente
      encerrado com o terminal vivo deixava o card `IDLE` para sempre


### M10 — o card diz a verdade, e diz de onde

Uma leva inteira de "o app afirmava o que não tinha acontecido". Os dois lados
do produto — o semáforo e o `⇧A` — anunciavam sucesso sem conferir, e cada um
falhava no sentido pior: dizendo que a sessão está livre quando ela não está.

- [x] **`⇧A` prometia foco que não acontecia.** No Wayland, o
      `org.freedesktop.Application.Activate` devolve código zero **mesmo quando
      o compositor ignora o pedido** — e o zero era lido como sucesso. Agora o
      foco é conferido relendo a lista de janelas depois do `Activate`; sem a
      Window Calls, no Wayland, o `Activate` do terminal nem é tentado, porque
      ali ele só produziria sucesso falso. Faltava também o `Unminimize`, sem o
      qual nenhuma janela minimizada volta
- [x] **O mesmo erro existia no Windows e no macOS.** O `AppActivate` devolve
      `True`/`False`, mas o PowerShell sai com código zero nos dois casos; e
      `set frontmost` levanta o **app**, não a janela, e não tira nada da Dock.
      Os dois foram reescritos com restauração da janela minimizada e
      verificação do resultado — ⚠️ **sem execução em máquina real** (ver
      pendências)
- [x] **A janela da sessão passou a ser identificada pela tty.** Com um servidor
      de terminal, todas as janelas têm o mesmo PID, e o título é de quem está
      rodando na aba (o agente escreve o que faz, um player escreve a música).
      O WatchAI escreve um título único na tty, vê qual janela ficou com ele e
      devolve o título de antes. Vale para Window Calls, `wmctrl`, `xdotool` e
      AppleScript
- [x] **Pensamento longo deixou de virar "tarefa concluída".** O diário só é
      escrito quando a mensagem fecha, e um pensamento demorado passa dos dois
      minutos do `FRESCOR` sem gastar CPU — a espera é do outro lado da rede.
      Isso acendia o **verde** e apitava "pode vir buscar" no meio da rodada;
      agora é WAITING (âmbar)
- [x] **Limite de uso do codex virou ERROR.** Ele fecha a rodada com
      `task_complete` e põe o motivo **dentro** do evento (`error.message`, com
      `last_agent_message` nulo) — ler só o tipo dava a sessão como concluída
- [x] **O título do card é o caminho da aba**, igual para todas: `~`,
      `~/Projetos/WatchAI`. Antes era o projeto em maiúsculas, e a aba sem
      projeto legível caía no rótulo da tty (`PTS/9`), que não diz nada sobre de
      qual sessão se trata. Caminho fundo é cortado pela esquerda, porque o que
      identifica está no fim
- [x] **O diretório vem do diário, não do processo.** O `cwd` do processo é onde
      a sessão **abriu**: quem entra no projeto depois mantém o processo na home
      para sempre. No codex isso exigiu duas coisas a mais — ele grava o
      diretório como URI `file://` e só de vez em quando, aninhado, e o último
      registro pode estar megabytes antes do fim do arquivo
- [x] **Antigravity reconhecido**: o executável se chama `agy`, e é binário
      nativo — não há caminho de pacote que sirva de segunda chance
- [x] **`scripts/screenshot.py`**: o caminho para refazer as capturas deixou de
      viver só na cabeça de quem já fez


### M11 — pronto para Windows e macOS, e a tela vazia explica a causa (1.2.0)

Uma leva de "o código trata os três sistemas" para "o código trata os três
sistemas **e avisa quando não consegue**". Nenhum item aqui foi verificado em
máquina Windows ou macOS de verdade — isso continua sendo a pendência número um.

- [x] **O toast do Windows parou de falhar em silêncio.** O `stderr` ia para o
      lixo e o código de saída era ignorado: nada na tela e um processo novo a
      cada mudança de estado. Agora a primeira falha **desliga o mecanismo** e
      guarda o motivo
- [x] **Duas causas prováveis do toast atacadas**: o AUMID passou a ser um
      registrado — com um nome inventado, o Windows cria a notificação e
      simplesmente não a mostra — e ficou anotado que o `pwsh` não projeta
      WinRT, por isso o Windows PowerShell 5.1 vem primeiro
- [x] **Plano B para o bip do Windows**: o `System.Media` não existe no `pwsh`,
      e sem alternativa o aviso sumiria para quem usa o PowerShell novo. Cai em
      `[Console]::Beep`, com uma frequência por estado para os três continuarem
      distinguíveis sem olhar
- [x] **Config do Windows no `%APPDATA%`**, com o caminho antigo preservado
      quando já existe: ninguém perde tema e histórico numa atualização
- [x] **A tela vazia diz a causa certa.** "Nenhum agente aberto" e "não consigo
      ler a tabela de processos" mostravam a mesma frase, e quem caía na segunda
      concluía que o app é quebrado. A varredura passou a informar o porquê
      (`sem-psutil`, `restrito`, `erro`) e cada um tem a sua resposta
- [x] **1.2.0 cortada**: 24 commits e 43 entradas que estavam em `[Não lançado]`


### M12 — a fila curta

- [x] **`S` ordena os cards por atenção**, e não vira o padrão: card que muda
      de lugar sozinho desfaz a memória visual. A seleção segue a sessão, não a
      posição
- [x] **A aba exata, onde ela tem endereço**: a aba de um gnome-terminal não é
      endereçável, mas um painel do tmux é — e de quebra, sessões dentro do
      tmux passaram a ser alcançáveis pelo `⇧A`, que antes não achava janela
      nenhuma porque o agente descende do servidor do tmux
- [x] **Snap empacotado** (`snap/snapcraft.yaml` + build no CI que instala e
      roda o que construiu). Em `classic`, porque sob strict o `⇧A` e a
      notificação ficariam de fora do sandbox — falta só o envio à loja, que
      pede conta e revisão manual

---

## O que ainda falta

- [ ] **Validar Windows e macOS na prática.** É a maior dívida do projeto, e ela
      **cresceu** no M10: além da identidade de terminal pelo shell e do agente
      reconhecido pelo caminho do pacote, agora há o `⇧A` reescrito nos dois —
      P/Invoke no Windows para restaurar a janela minimizada e conferir quem
      está em primeiro plano, AppleScript no macOS com `AXRaise` e
      `AXMinimized`. O M11 tratou o resto do que dava para tratar sem a máquina
      (toast, bip e config), mas **nenhum job de CI abre janela nem mostra
      notificação**: a suíte passar nos três sistemas não diz nada sobre isso. Três perguntas resolvem: janela
      minimizada volta? Com várias janelas do mesmo terminal, vai para a certa?
      Quando falha, o recado diz `refused` em vez de `window raised`? Até lá, é
      código testado, não software verificado. O toast do Windows, em especial,
      falha em silêncio.

- [ ] **Publicar no PyPI** (`pipx install watchai`). O workflow já existe e
      empacota; falta **você** criar o projeto no PyPI, apontar o *trusted
      publisher* para este repositório (workflow `publish.yml`, ambiente `pypi`)
      e definir a variável `PYPI_READY=true`. Enquanto isso, o caminho é
      `pipx install git+https://github.com/LeandroDukievicz/WatchAI.git`.

---

## Fora de escopo (decidido)

- **Validar o leitor do OpenCode e escrever um para o Antigravity.** Tirados da
  lista em 2026-09-23. A ressalva do OpenCode continua onde importa — no
  docstring do leitor e no README —, então quem usar aquele CLI e vir estado
  errado sabe onde olhar; e o Antigravity segue na camada de processos, com
  projeto, tempo e CPU, mas sem estado de diário.

- **Integração por API, hook ou plugin dos agentes.** A regra do produto é não
  conectar nada: só processo e arquivo local.
- **Sessões de outro usuário ou dentro de container.** A varredura vê só os
  processos do usuário que rodou o WatchAI.
- **Ler a tela do terminal** (PTY, scrollback). Resolveria o INPUT com certeza,
  mas é exatamente o tipo de intrusão que o projeto evita.

---

## Limites conhecidos (não são bugs)

- Para agentes **sem diário**, o `for MM:SS` conta da descoberta, não do
  acontecimento — o disco não guarda essa hora.
- Dois agentes **do mesmo tipo no mesmo diretório** compartilham o diário mais
  recente; o segundo cai na camada de processos.
- INPUT é inferido: ferramenta pendente + processo parado há 8 s. Uma ferramenta
  lenta que não gasta CPU aparece como INPUT.
- `cwd` pode ser negado no macOS para processos que não são seus — sem
  diretório, o título do card cai para o rótulo do terminal.
- **Duas abas no mesmo projeto têm o mesmo título**, já que o título é o
  caminho. Quem as distingue é o terminal no canto do card (`pts/4` contra
  `pts/7`) — foi o que deu função a ele.
- O **Antigravity** aparece e mostra projeto, tempo e CPU, mas não estado de
  diário: ele não grava um.
- O aviso não dispara pelas sessões que já estavam abertas quando o WatchAI
  subiu: só pelo que muda depois.
