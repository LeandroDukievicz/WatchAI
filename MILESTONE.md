# Milestones

Onde o WatchAI está e o que falta. Cada item diz **o que é**, **por que importa**
e **onde mexer** — para dar para pegar um e fazer sem redescobrir o contexto.

Atualizado em 2026-09-22.

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
      `org.freedesktop.Application.Activate` no Wayland
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

## O que ainda falta

- [ ] **Validar Windows e macOS na prática.** O código trata os dois (identidade
      de terminal pelo shell quando não há tty, agente reconhecido pelo caminho
      do pacote) e o CI roda a suíte nos três, mas ninguém abriu o app num
      Windows ou num Mac ainda. Até lá, é código testado, não software
      verificado. O toast do Windows, em especial, falha em silêncio.

- [ ] **Confirmar o leitor do OpenCode** contra uma sessão real. O layout veio
      do binário; os nomes dos campos (`directory`, `time.completed`,
      `state.status`) são a melhor leitura disponível, não verificação. Abrir
      uma sessão no OpenCode e conferir `~/.local/share/opencode/storage/`
      resolve em minutos.

- [ ] **Diários dos demais agentes.** Hoje só Claude Code, Codex e OpenCode têm
      leitor; o resto vive da camada de processos. Cada leitor novo é uma classe
      em `providers/transcript.py` com dois métodos. Os formatos precisam ser
      verificados contra uma sessão real de cada um — e nenhum deles está
      instalado nesta máquina, o que torna isto trabalho de quem usa (ou de um
      PR da comunidade).

- [ ] **Cortar a 1.2.0.** O `CHANGELOG` está em `[Não lançado]` com tudo que
      entrou depois da 1.1.0 — semáforo em octógono com neon, tema claro
      corrigido, `⇧A` + Window Calls, pipx verificado nos três sistemas,
      registro de 17 agentes, notificação opt-in, responsividade em dois eixos e
      o ciclo de vida da sessão encerrada. O `pyproject.toml` ainda diz 1.1.0.

- [ ] **Publicar no PyPI** (`pipx install watchai`). O workflow já existe e
      empacota; falta **você** criar o projeto no PyPI, apontar o *trusted
      publisher* para este repositório (workflow `publish.yml`, ambiente `pypi`)
      e definir a variável `PYPI_READY=true`. Enquanto isso, o caminho é
      `pipx install git+https://github.com/LeandroDukievicz/WatchAI.git`.

- [ ] **Focar a aba exata no Wayland.** Com o Window Calls o WatchAI já foca a
      **janela** certa; escolher a **aba** dentro dela continua dependendo de
      cada emulador expor isso (o GNOME Terminal não expõe) — o sino é o que
      resolve na prática.

- [ ] **Dizer por que a lista está vazia.** Hoje, se a varredura não puder ler
      os processos, a tela mostra "no AI session detected" — a mesma mensagem de
      quando realmente não há sessão. O usuário conclui que o app é quebrado.
      São três causas distintas e cada uma tem uma resposta: **sem `psutil`**
      (instalar), **sem permissão** (container, `hidepid`, Snap/Flatpak, macOS —
      dizer o comando) e **nenhum agente rodando** (a mensagem atual). Vale para
      qualquer empacotamento, não só para o Snap.

- [ ] **Empacotar para Snap** em `classic` (`snapcraft.yaml` + job de build no
      CI + pedido de revisão).

- [ ] **Ordenar os cards por atenção** (decidir antes de fazer). Hoje a ordem é
      a de descoberta. Quem pede você primeiro subir ao topo ajuda com muitas
      sessões — mas card que dança de lugar sozinho atrapalha a memória visual.
      Talvez como tecla de ordenação, não como padrão.

---

## Fora de escopo (decidido)

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
- `cwd` pode ser negado no macOS para processos que não são seus — o card cai
  para o rótulo do terminal.
- O aviso não dispara pelas sessões que já estavam abertas quando o WatchAI
  subiu: só pelo que muda depois.
