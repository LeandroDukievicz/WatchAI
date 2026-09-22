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

### M5 — permanência e distribuição

- [x] **Histórico do EVENT STREAM entre execuções** (`~/.config/watchai/events.json`)
- [x] **Instalador no repositório**: `scripts/install-linux.sh` (comando no PATH,
      lançador no menu, atalho opcional na área de trabalho, `--uninstall`)
- [x] Ícone versionado em `assets/watchai.svg`
- [x] Landing page atualizada (`docs/index.html`)
- [x] Metadados do pacote (descrição, URLs) e versão 1.1.0
- [x] **Release 1.1.0** publicada (tag `1.1.0`)

---

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

- [ ] **Diário do Aider** — grava `.aider.chat.history.md` na pasta do projeto.
      Não está instalado aqui, então o formato não foi verificado.

- [ ] **Publicar no PyPI** (`pipx install watchai`), para não depender de clonar
      o repositório. Falta conta, token e um `python -m build` no CI.

- [ ] **Focar a aba exata no Wayland.** Hoje o `Activate` levanta a janela do
      terminal e o sino marca a aba; escolher a aba programaticamente depende de
      cada emulador expor isso (o GNOME Terminal não expõe).

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
