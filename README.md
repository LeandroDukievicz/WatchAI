<div align="center">

<img src="docs/brand/watchai.png" alt="WatchAI" width="620">

**Monitor de sessões de IA no terminal.**
Claude Code, Codex, Gemini, OpenCode, Aider, Copilot — todas numa tela só.

[![tests](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml/badge.svg)](https://github.com/LeandroDukievicz/WatchAI/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.10%20%E2%80%93%203.14-blue)
![license](https://img.shields.io/badge/license-MIT-green)

[Conheça o projeto e veja como baixar](https://leandrodukievicz.github.io/WatchAI/)

</div>

![WatchAI em 150×36](docs/screenshot.png)

---

> ### Detecção real, sem integrar nada
>
> O WatchAI **descobre sozinho** as sessões abertas na sua máquina: varre a
> tabela de processos e lê os diários que os próprios agentes já gravam no
> disco. Não há API, chave, hook, plugin nem configuração do agente — nada sai
> da sua máquina. Com `--mock` ele volta a rodar com dados simulados, para
> avaliar a interface sem depender do que está aberto.

## O problema

Você dispara uma tarefa no Claude Code, vai para outra janela enquanto ele
trabalha, e esquece. Dez minutos depois descobre que ele terminou em dois — ou
que travou esperando você confirmar um comando. Com três ou quatro sessões de IA
abertas ao mesmo tempo, o custo vira atenção fragmentada.

O WatchAI coloca todas numa tela só e responde de longe, sem leitura:
**quem está trabalhando, quem terminou e quem precisa de você.**

## Instalação

Requisitos: **Python 3.10+** e um terminal com Unicode. A única dependência
além do Textual é o [`psutil`](https://github.com/giampaolo/psutil), que é quem
lê a tabela de processos igual nos três sistemas.

```bash
git clone git@github.com:LeandroDukievicz/WatchAI.git
cd WatchAI
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Uso

```bash
python main.py                 # ou:  watchai  ·  python -m watchai
python main.py --mock          # dados simulados, sem olhar seus processos
python main.py --theme vampire # tema só desta execução
```

Truecolor (`COLORTERM=truecolor`) dá as cores exatas; sem ele o Textual aproxima
para 256/16 cores. Nada depende de ligatures — só símbolos Unicode simples
(`● ○ ◐ ◓ ◑ ◒ ◆ ◇ ▲ ▸ ▶ ─ │ ╭ ╮ ╰ ╯`). Testado com JetBrains Mono, Fira Code,
Cascadia, Hack, Meslo e Ubuntu Mono.

---

# Como ele descobre as sessões

**Um card por terminal.** Cada aba do terminal que tem (ou teve) um agente
rodando vira um card, e os agentes que rodam ali aparecem dentro dele — dois
agentes na mesma aba são um card com dois agentes, não dois cards.

A detecção tem duas camadas, e é a combinação que faz sentido:

| Camada | De onde vem | O que responde |
|---|---|---|
| **Processos** | varredura da tabela de processos (`psutil`), a cada 2 s | quem existe, em que terminal, em que projeto (`cwd`), desde quando — e se está gastando CPU |
| **Diário** | o `.jsonl` que o próprio agente grava (`~/.claude/projects/…`, `~/.codex/sessions/…`) | **o que** ele está fazendo agora, e se terminou ou se travou esperando você |

Nenhuma das duas sozinha resolve. O processo não distingue **READY** ("terminou,
é a sua vez") de **INPUT** ("parou esperando você confirmar"): nos dois casos
ele está dormindo com 0% de CPU. E o diário não sabe se o que ele registrou por
último ainda está acontecendo. Juntos:

```
última entrada do diário     +  processo     =  estado
─────────────────────────────────────────────────────────
texto do assistente             qualquer        READY     terminou
resultado de ferramenta         qualquer        WORKING   voltou a pensar
chamada de ferramenta           gastando CPU    WORKING   a ferramenta roda
chamada de ferramenta           parado há 8 s   INPUT     esperando VOCÊ
chamada de ferramenta           parado agora    WAITING   esperando algo externo
(sem diário legível)            gastando CPU    WORKING
(sem diário legível)            parado          READY
```

Agentes sem diário conhecido (Gemini, OpenCode, Aider…) funcionam pela camada de
processos: aparecem, mostram projeto e tempo, e alternam entre WORKING e READY.

## O que é multiplataforma e o que degrada

| Sinal | Linux | macOS | Windows |
|---|:--:|:--:|:--:|
| PID, linha de comando, início, CPU, filhos | ✅ | ✅ | ✅ |
| `cwd` (o projeto do card) | ✅ | ⚠️ processos seus | ✅ |
| diário local dos agentes | ✅ | ✅ | ✅ |
| tty como identidade do terminal | ✅ | ✅ | ❌ não existe |

Sem tty (Windows), a identidade do terminal passa a ser o **shell ancestral** —
que é o análogo certo, porque cada aba do Windows Terminal abre o seu próprio
shell. O reconhecimento de agente não depende do nome do processo: no Windows o
Claude Code é `node.exe`, e o que identifica é o programa executado ou o caminho
do pacote (`@anthropic-ai/claude-code`).

## Os limites, ditos na cara

- **Só os seus processos.** Sessões de outro usuário (ou dentro de um container)
  não aparecem.
- Dois agentes **do mesmo tipo no mesmo diretório** compartilham o diário mais
  recente; o segundo cai na camada de processos.
- O contador `for MM:SS` começa a contar **quando o WatchAI viu** o estado, não
  quando ele começou de verdade — o disco não guarda essa hora.
- INPUT é inferido, não lido: uma ferramenta lenta que não gasta CPU e não
  responde em 8 s aparece como INPUT.

---

# Funcionalidades

A tela tem quatro regiões fixas:

```
 ╭─ ◆ WatchAI  SESSION MONITOR ─────────────────────────────────╮
 │ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  …         21:25:46     │   ① cabeçalho
 ╰──────────────────────────────────────────────────────────────╯
  ▸ SESSIONS 06 ─────────────────────────── CARDS │ LIST            ② título do painel
 ╭─ ▶ CLAUDE CODE ──────────────╮  ╭─ CODEX ───────────────────╮
 │  ◐ WORKING        for 04:12  │  │  ● READY       for 01:42  │    ③ painel SESSIONS
 ╰──────────────────────── #03 ─╯  ╰───────────────────── #01 ─╯
 ╭─ EVENT STREAM ───────────────────────────────────────────────╮
 │ 21:25:19 ◆ OPENCODE INPUT    waiting for confirmation        │   ④ event stream
 ╰──────────────────────────────────────────────────────────────╯
  ↑↓ NAV │ ENTER OPEN │ TAB PANEL │ T THEMES │ V VIEW │ R REFRESH …    ⑤ keybar
```

## ① Cabeçalho — resumo global

```
╭─ ◆ WatchAI  SESSION MONITOR ──────────────────────────────────────────────────╮
│ ACTIVE 05 │ ◐ WORKING 01  ● READY 01  ◆ INPUT 01  ◇ WAITING 01  ▲ ERROR 01  ○ OFFLINE 01   21:25:46 │
╰───────────────────────────────────────────────────────────────────────────────╯
```

- **ACTIVE** — quantas sessões não estão OFFLINE.
- **Um chip por estado**, em ordem fixa (WORKING, READY, INPUT, WAITING, ERROR,
  OFFLINE), para a posição não dançar quando os números mudam. Estado com zero
  fica apagado; com contagem, acende na cor do estado. Os que pedem você
  (READY, INPUT, ERROR) vêm em negrito.
- **STARTING só aparece quando existe** — é transitório demais para ocupar espaço fixo.
- **Relógio** à direita, atualizado a cada 0,5 s.
- O cabeçalho se adapta à largura: perde o subtítulo `SESSION MONITOR` abaixo de
  48 colunas, depois troca `◐ WORKING 01` por `◐ 1`, e em último caso abandona o
  relógio para manter os chips.

## ② Título do painel

```
 ▸ SESSIONS 06 ─────────────────────────────────────────── CARDS │ LIST
```

Mostra quantas sessões existem, qual visão está ativa (`CARDS` ou `LIST`, em
cyan) e — pelo `▸` e pela régua acesa — se o painel de sessões está em foco ou
se o foco está no EVENT STREAM (`TAB`).

## ③ Painel SESSIONS

### Visão CARDS (padrão)

```
╭─ ▶ DEVS-A-DERIVA ──────────────────────╮
│  ● READY             for 04:12  ╭───╮  │
│                                 │ ● │  │
│  agents   2  ● claude  ◐ codex  │ ● │  │
│  activity claude: task completed│ ● │  │
│  elapsed  03:14:19              ╰───╯  │
╰─────────────────────────────── pts/10 ─╯
```

| Elemento | O que é |
|---|---|
| Título na borda | O **projeto** (a pasta em que os agentes trabalham). Ganha `▶` e vira cyan quando é o card selecionado |
| `pts/10` na borda | O terminal. No Windows, o shell (`pwsh #4312`) |
| `● READY` | Estado do terminal: o do agente que mais pede você (ERROR › INPUT › READY › WAITING › WORKING) |
| `for 04:12` | Há quanto tempo está **neste** estado (não é o tempo de sessão) |
| `agents` | Quantos agentes rodam ali e, em cada um, o símbolo na cor do **seu** estado |
| `activity` | O que o agente que decidiu o estado está fazendo (com o nome dele, quando há mais de um) |
| `elapsed` | Há quanto tempo o terminal está aberto |
| Semáforo | As 3 lâmpadas — ver [seção própria](#o-semáforo) |

- **A moldura carrega o estado**: verde (READY), magenta (INPUT) e vermelho
  (ERROR) acendem forte e ganham uma tinta de fundo; WORKING e WAITING ficam em
  tons apagados (é o estado normal, não deve chamar atenção); OFFLINE quase some.
- **Selecionado** ganha fundo levemente mais claro e título cyan — mas a moldura
  **mantém a cor do estado**: um READY selecionado continua verde.
- **`for MM:SS` fica em negrito depois de 1 minuto** em READY, INPUT e ERROR — é
  o "terminou há dois minutos e você ainda não voltou".
- **Terminal sem agente** fica `IDLE`, apagado: a aba continua aberta, não há
  nada rodando. **Terminal fechado** vira OFFLINE.
- **Terminal fechado não some na hora.** Fica 5 minutos como OFFLINE, depois
  troca a linha dos agentes por `⚠ removing in 01:59` e sai aos 7 — você precisa
  poder ver que a sessão terminou mesmo tendo saído da frente do computador.
- **Textos longos truncam com `…`**, nunca quebram linha.
- Se os cards não couberem na altura, o painel rola (`↑ ↓` seguem a seleção).

### Visão LIST (`V`)

```
   TERMINAL   STATUS      PROJECT                AGENTS              TIME
 ─────────────────────────────────────────────────────────────────────────
 ▶ pts/10     ● READY     devs-a-deriva          ● claude           04:12
   pts/6      ◐ WORKING   ninou-app              ◐ codex            01:42
   pts/3      ◆ INPUT     watchai                ◆ claude ● codex   00:27
   pts/9      · IDLE      —                      —                      —
   pts/2      ○ OFFLINE   —                      —                      —
```

A mesma informação em uma linha por sessão — é a visão mais densa, para quando
há muitas sessões. `TIME` é o mesmo contador dos cards (tempo no estado atual) e
segue a mesma regra de negrito. A linha inteira recebe a tinta do estado, e a
selecionada ganha `▶` e nome em cyan.

## ④ EVENT STREAM

```
╭─ EVENT STREAM ─────────────────────────────────────────────────────────╮
│ 21:25:19 ◆ OPENCODE INPUT    waiting for confirmation                  │
│ 21:24:26 ◐ OPENCODE WORKING  editing files                             │
│ 21:24:04 ● CODEX    READY    task completed                            │
│ 21:23:16 ◐ CODEX    WORKING  applying patch                            │
│ 21:22:55 ▲ AIDER    ERROR    test suite failed (exit 1)                │
╰────────────────────────────────────────────────────────────────────────╯
```

O histórico de todas as sessões junto, **mais novo em cima** (guarda os últimos
200 eventos). O evento mais recente vem em destaque; os demais, apagados.

- **`TAB` move o foco para cá** — a borda acende em cyan e aparece `↑↓ scroll` no
  rodapé da caixa. Com o foco aqui, `↑ ↓` rolam o histórico em vez de trocar de
  sessão. Ao sair (`TAB` de novo) ele volta ao topo, para nunca ficar preso
  mostrando eventos velhos.
- **Cresce com o terminal**: ocupa toda a altura que sobra depois dos cards —
  quanto mais alto o terminal, mais histórico visível.
- **Encolhe por colunas**: abaixo de 56 colunas esconde a coluna de estado;
  abaixo de 34, também o nome da sessão, preservando hora e mensagem.

## ⑤ Keybar

```
 ↑↓ NAV │ ENTER OPEN │ TAB PANEL │ T THEMES │ V VIEW │ R REFRESH │ B BIP │ ? HELP │ Q QUIT
```

Rodapé de atalhos que se adapta à largura: quando não cabe, descarta os itens
menos importantes primeiro (`B`, depois `R`, `T`, `TAB`…) e, em último caso, mostra só
as teclas sem descrição. O item do bip reflete o estado: `B BIP` ligado,
`B MUDO` (apagado) desligado.

## Detalhes da sessão (`ENTER`)

```
╭─ SESSION DETAILS ──────────────────────────────────────────────────────╮
│  GEMINI                                                                │
│  STATUS     ◇ WAITING                    for 03:11  ·  since 21:22:46  │
│  SESSION    #02                                                        │
│  PID        190114                                                     │
│  PROJECT    research-agent                                             │
│  DIRECTORY  ~/research-agent                                           │
│  STARTED    21:16:37                                                   │
│  ELAPSED    00:09:20                                                   │
│                                                                        │
│  AGENTS                                                                │
│  claude     ● READY      pid 1150460   04:12  task completed           │
│  codex      ◐ WORKING    pid 1166198   00:27  Bash: npm test           │
│                                                                        │
│  CURRENT ACTIVITY                                                      │
│  waiting for API response                                              │
│                                                                        │
│  EVENTS                                                                │
│  21:22:46 ◇ waiting for API response                                   │
│  21:21:17 ◐ reading repository                                         │
│  21:19:57 ◐ user prompt                                                │
│                                                                        │
│  ESC back   ←→ prev/next session                                       │
╰────────────────────────────────────────────────────────────────────────╯
```

Modal com tudo sobre um terminal: além do estado (com o horário em que entrou
nele), **um bloco por agente** — PID, estado, há quanto tempo e o que está
fazendo —, o diretório, quando a aba abriu e os **últimos 4 eventos só dela**.

- O dashboard continua vivo atrás, escurecido — os semáforos e contadores seguem
  atualizando enquanto o modal está aberto.
- **`← →` trocam de sessão sem fechar**, circulando (depois da última volta para a
  primeira), e a seleção do dashboard acompanha.
- Sessão OFFLINE mostra `—` nos campos que perderam sentido.

## Ajuda (`?`)

Modal com a lista de teclas. Fecha com `ESC` ou `?`.

## O semáforo

Cada card carrega um semáforo de 3 lâmpadas — é a leitura "de longe", antes de
ler qualquer texto. É também a identidade do produto.

```
╭───╮
│ ● │  vermelha · ERROR
│ ● │  amarela  · WORKING, WAITING, STARTING e INPUT (piscando)
│ ● │  verde    · READY
╰───╯
```

Como num semáforo de verdade, as lâmpadas apagadas não somem: ficam num tom bem
escuro da própria cor. OFFLINE apaga as três e escurece a carcaça. INPUT é o
único que pisca (1 s aceso, 1 s apagado) — é o estado que depende de você.
Abaixo de 60 colunas o semáforo sai (não cabe) e quem dá o estado é a barra
lateral colorida.

## O bip de READY

Quando uma sessão **entra** em READY, o app toca um bip curto — a ideia é você
saber sem estar olhando.

O som sai pelo **servidor de som** (PipeWire/PulseAudio), não pelo bell do
terminal (`\a`). Essa escolha é o ponto todo: bell vira flash visual em vários
emuladores, costuma vir desligado e não ajuda com a aba em segundo plano. Um
stream de áudio normal toca independente de foco.

- `B` liga/desliga; o rodapé mostra `B BIP` ou `B MUDO`. Religar confirma com um bip.
- Uma rajada de READY vira um bip só (janela de 1 s), sem enfileirar áudio.
- Não bipa na abertura por uma sessão que já nasceu READY, nem em outros estados.
- Ordem de preferência: `pw-play` → `paplay` → `ffplay`, tocando um bip do tema do
  sistema. Sem nenhum deles, tenta `canberra-gtk-play`; em último caso, o bell do terminal.
- Para avisar também em INPUT ou ERROR, inclua os estados em `ALERT_STATUSES`
  ([`src/watchai/app.py`](src/watchai/app.py)).

## Temas (`T`)

Oito paletas, trocáveis com o app rodando:

```
╭─ THEMES ─────────────────────────────────╮
│                                          │
│   ▶ WatchAI     ◐ ● ◆ ◇ ▲ ○ ◌  •         │
│     Light       ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Dark        ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Night Owl   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Vampire     ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Cyberpunk   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Steampunk   ◐ ● ◆ ◇ ▲ ○ ◌            │
│     Grey        ◐ ● ◆ ◇ ▲ ○ ◌            │
│                                          │
│   ↑↓ preview   ENTER apply   ESC cancel  │
│                                          │
╰──────────────────────────────────────────╯
```

| Tema | O que é |
|---|---|
| **WatchAI** | o original: fundo quase preto e neon cyan/magenta (padrão) |
| **Light** | fundo claro — as tintas de estado viram pastel em vez de sumir |
| **Dark** | escuro neutro, sem neon |
| **Night Owl** | azul-petróleo com verdes suaves |
| **Vampire** | Dracula (o roxo `#BD93F9` entra como acento secundário) |
| **Cyberpunk** | preto arroxeado, cyan e magenta saturados |
| **Steampunk** | sépia e latão, com verdete no lugar do cyan |
| **Grey** | sem matiz nenhum: os estados se separam só por brilho |

![Light, Vampire, Cyberpunk e Steampunk](docs/themes.png)

- **Mover a seleção aplica o tema na hora** — o dashboard inteiro atrás do modal
  troca de cor, então dá para comparar antes de decidir. `ENTER` confirma,
  `ESC` desfaz e volta para o tema em que você estava.
- Cada linha mostra os símbolos dos estados **nas cores daquela paleta**; o `•`
  marca o tema em que você estava ao abrir.
- A escolha **fica salva** em `$XDG_CONFIG_HOME/watchai/config.json` (ou
  `~/.config/watchai/config.json`) e volta na próxima execução. Arquivo
  corrompido, disco cheio ou tema desconhecido caem no padrão, sem derrubar a TUI.
- O tema **não muda símbolo nem label** — só cor. O **Grey** é a prova: mesmo sem
  matiz nenhum, `◐ WORKING` e `▲ ERROR` continuam distinguíveis, que é a garantia
  de quem não enxerga cor.

## Linguagem visual dos estados

Cor **e** símbolo **e** label — dá para ler sem depender só de cor.

| Estado | Símbolo | Cor | Semáforo | Significado | Card |
|---|---|---|---|---|---|
| READY | `●` (pulso lento) | verde | **verde** | terminou, pronta p/ nova instrução | borda verde + tinta + label/tempo em negrito |
| WORKING | `◐◓◑◒` (giro lento) | cyan | **amarela** | executando | borda cyan apagada, sem negrito (calmo) |
| WAITING | `◇` | amarelo | **amarela** | esperando processo externo | borda âmbar apagada |
| INPUT | `◆` (pulso lento) | magenta | **amarela piscando** | esperando ação do usuário | borda magenta + tinta |
| ERROR | `▲` (estático) | vermelho | **vermelha** | problema detectado | borda vermelha + tinta |
| OFFLINE | `○` (apagado) | cinza escuro | todas apagadas | terminal fechado | quase some no fundo |
| STARTING | `◌ ○` | cyan secundário | **amarela** | acabou de iniciar | borda apagada |
| IDLE | `·` | cinza | todas apagadas | aba aberta, nenhum agente | apagado |

Todas as animações são discretas e guiadas pelo mesmo relógio de 0,5 s: o giro do
WORKING, o pulso lento de READY e INPUT (~4,5 s por ciclo) e o `◌ ○` alternando do
STARTING. ERROR e OFFLINE são estáticos de propósito.

As cores da tabela são as do tema **WatchAI**; os outros temas remapeiam a cor de
cada estado, nunca o símbolo nem o label.

Regra de ouro da paleta: neon só em status, título, seleção e teclas. O resto é
branco suave e cinza.

## Navegação

| Tecla | Ação |
|---|---|
| `↑ ↓` (`k j`) | seleciona sessão — nas colunas do grid, move uma linha inteira |
| `← →` (`h l`) | navega entre cards da mesma linha (sem efeito com 1 coluna) |
| `ENTER` | abre os detalhes da sessão selecionada |
| `ESC` | volta / fecha o modal |
| `TAB` | alterna o painel **SESSIONS ⇄ EVENTS** |
| `T` | abre o seletor de temas (preview ao vivo; `ENTER` salva, `ESC` desfaz) |
| `V` | alterna **CARDS ⇄ LIST** |
| `R` | refresh — varre os processos na hora (no `--mock`, avança a simulação) |
| `B` | liga/desliga o bip de READY |
| `?` | ajuda |
| `Q` / `Ctrl+C` | sai |

Detalhes que o teclado respeita:

- Com o foco no **EVENT STREAM**, `↑ ↓` rolam o histórico e `ENTER` não abre nada —
  o painel de sessões volta com `TAB`.
- Descendo na **última linha incompleta** do grid, a seleção cai no último card em
  vez de não fazer nada.
- A seleção é sempre trazida para a área visível quando o painel rola.
- Dentro dos detalhes, `← →` trocam de sessão em vez de navegar no grid.

**Mouse:** clique seleciona (em card ou em linha da LIST), duplo clique abre os
detalhes.

## Responsividade

Por largura:

| Largura | Layout |
|---|---|
| ≥ 130 | 3 cards por linha |
| 90–129 | 2 cards por linha |
| 60–89 | 1 card por linha |
| < 60 | compacto: sem caixa, barra lateral na cor do estado, 4 linhas por sessão (sem semáforo) |

Por altura: a área de sessões encolhe até o conteúdo e o EVENT STREAM ocupa tudo
que sobra — quanto mais alto o terminal, mais histórico, e nunca um vão morto no
meio. Se as sessões não couberem, a área rola em vez de empurrar o stream para
fora: o stream nunca fica com menos que suas 6 linhas de eventos, e header e
keybar ficam sempre visíveis. Testado de 20×10 a 300×80.

## O modo simulado (`--mock`)

`python main.py --mock` troca a detecção por seis sessões de mentira: um
simulador muda o estado de uma delas a cada **5–12 s**, seguindo transições
plausíveis (de WORKING sai-se mais para READY do que para ERROR; de OFFLINE só
se volta por STARTING, que se resolve em ~4 s).

Serve para avaliar a interface em movimento sem depender do que está aberto na
sua máquina — e é sobre ele que roda boa parte da suíte de testes visuais. Aí o
card volta a ser uma IA, com `project` no lugar de `agents`. Fora do mock, `R`
força uma varredura na hora.

---

## Arquitetura

```
WatchAI/
├── main.py                      # entrada: python main.py
├── pyproject.toml               # pacote, deps e config do pytest
├── src/watchai/
│   ├── app.py                   # App: tema, tick (0,5 s), bindings, bip de READY
│   ├── theme.py                 # as 8 paletas + paleta ativa ($aw-* para o TCSS)
│   ├── layout.py                # breakpoints (LARGE/MEDIUM/SMALL/TINY) + teto da área
│   ├── format.py                # ellipsize, HH:MM:SS, mm:ss
│   ├── sound.py                 # bip (descobre o player do sistema)
│   ├── config.py                # preferências salvas (~/.config/watchai/config.json)
│   ├── models/                  # Status, Agent, Session (= terminal), SessionStore
│   ├── providers/               # ← a detecção real
│   │   ├── agents.py            # quem é agente (e quem só tem o nome parecido)
│   │   ├── source.py            # psutil: a única parte que conhece o SO
│   │   ├── transcript.py        # lê os .jsonl que os agentes já gravam
│   │   └── live.py              # reconcilia processos → terminais e agentes
│   ├── mock/sessions.py         # 6 sessões + MockSimulator (só no --mock)
│   ├── widgets/
│   │   ├── status_light.py      # StatusLight + render_status()  ← fonte única dos estados
│   │   ├── traffic_light.py     # TrafficLight (semáforo de 3 lâmpadas)
│   │   ├── session_card.py      # SessionCard (normal / compacto)
│   │   ├── session_row.py       # linha da visão LIST
│   │   ├── event_stream.py      # EVENT STREAM
│   │   ├── header.py            # cabeçalho + resumo global
│   │   ├── keybar.py            # rodapé de atalhos (responsivo)
│   │   └── panel_title.py       # "▸ SESSIONS 06 ─── CARDS │ LIST"
│   ├── screens/                 # dashboard.py · details.py · help.py · themes.py
│   └── styles/app.tcss          # todo o CSS
├── tests/                       # suíte headless (conftest silencia o áudio)
└── docs/                        # marca e screenshot
```

Três regras que o código segue:

1. **O estado mora no enum.** `Status` carrega label, cor, símbolo e prioridade de
   atenção. Nenhum widget hardcoda cor ou símbolo de estado — todos consultam o enum,
   e todo desenho de estado passa por `status_light.render_status()`.
2. **As cores moram no tema.** `theme.py` é a fonte única: o TCSS recebe as mesmas
   cores como variáveis `$aw-*` e quem desenha com Rich resolve a cor **na hora de
   renderizar** (`colors().cyan`), nunca no import — é isso que deixa trocar de
   tema com o app rodando.
3. **A UI só lê do store.** Os widgets reagem a dois reativos do app — `tick`
   (animação) e `version` (dados mudaram) — e nunca mexem no modelo.
4. **A varredura não mora na thread da UI.** `provider.read()` (≈50 ms de I/O)
   roda numa thread; `provider.apply()` mexe no store na thread da UI. Sem essa
   divisão, a animação engasgaria a cada ciclo.
5. **Nada de detecção pode derrubar a tela.** Varredura que falha vira leitura
   vazia, diário ilegível vira `None`, e o app segue com o que sabe.

## Testes

```bash
pip install -e ".[dev]"
pytest
```

39 testes headless (sem terminal real, **sem tocar áudio**, sem ler nem escrever
a sua config e **sem olhar os processos da máquina** — a tabela de processos é
injetada e o relógio é um argumento, então a suíte dá o mesmo resultado no seu
computador e no CI).

`tests/test_smoke.py` cobre a camada visual: breakpoints e navegação, troca de
visão/painel/modais, semáforo e piscar do INPUT, regras do bip, layout sem vão
morto e os temas (incluindo a checagem de que toda paleta fornece cada variável
`$aw-*` que o TCSS usa — uma faltando derruba a tela inteira).

`tests/test_providers.py` cobre a detecção: reconhecimento de agente (inclusive
o `node.exe` do Windows e o falso positivo de um plugin com "claude" no
caminho), a árvore de três processos do `codex` contando como um agente só, o
agrupamento por terminal, a prioridade de estado entre agentes, o ciclo
IDLE → OFFLINE → aviso → remoção, os estados lidos do diário (terminou,
ferramenta pendente com processo parado = INPUT, com processo ocupado =
WORKING) e a garantia de que diário corrompido ou varredura que explode não
derrubam nada.

CI no GitHub Actions cobrindo Python 3.10, 3.11, 3.12, 3.13 e 3.14.

## Roadmap

O que ainda não existe, em ordem de utilidade:

1. **Diário do Gemini, do OpenCode e do Aider** — hoje eles vivem só da camada de
   processos (WORKING/READY). O formato de cada um é a única coisa que falta;
   `providers/transcript.py` já é uma classe por agente.
2. **Validar Windows e macOS na prática.** O código trata os dois (identidade de
   terminal pelo shell, agente reconhecido pelo caminho do pacote) e o CI roda a
   suíte, mas ninguém abriu o app num Windows de verdade ainda.
3. **Notificação do sistema** além do bip, para quando o WatchAI está numa aba
   que você não vê.
4. **Histórico entre execuções** — hoje o EVENT STREAM começa vazio a cada
   abertura.

## Licença

[MIT](LICENSE) © Leandro Dukievicz
