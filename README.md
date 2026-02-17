# Cron Politics

Agregador de notícias sobre política, polêmicas, conflitos e desastres naturais.

## Stack

- **Python 3.11+**
- **Supabase** (PostgreSQL cloud)
- **GitHub Actions** - Cron automático

## Categorias (54 fontes)

| Categoria | Descrição | Fontes |
|-----------|-----------|--------|
| `politics_pt` | Política portuguesa | Observador, RTP, Notícias ao Minuto, ECO, Euronews PT, SIC |
| `politics_br` | Política brasileira | G1, Folha, Poder360, Congresso em Foco, Carta Capital, Brasil de Fato, Nexo, Agência Brasil |
| `politics_world` | Política internacional | BBC, Guardian, The Hill, NPR, DW, ABC, CBS, Sky News, Independent, Washington Post |
| `controversies` | Polêmicas e escândalos | Daily Mail, The Sun, TMZ, Page Six, NY Post, Fox News, Metro UK |
| `conflicts` | Guerras e tensões | Al Jazeera, BBC World, Times of Israel, Ukrinform, SCMP, Defense News, Middle East Eye, Foreign Policy, The Diplomat, War on the Rocks |
| `disasters` | Desastres naturais | ReliefWeb, USGS, NOAA, BBC Science, Guardian Environment, Climate Home News, Mongabay, Phys.org |

## Setup

### 1. Criar projeto no Supabase

1. Acesse [supabase.com](https://supabase.com)
2. Crie um novo projeto
3. Copie a connection string em **Settings > Database > Connection string > URI**

### 2. Criar repositório no GitHub

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create cron-politics --public --source=. --push
```

### 3. Configurar secret no GitHub

Vá em **Settings > Secrets and variables > Actions** e adicione:

| Secret | Valor |
|--------|-------|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/postgres` |

### 4. Executar setup inicial

Vá em **Actions > Setup Database > Run workflow**

## Uso Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Configurar variável de ambiente
export DATABASE_URL="postgresql://..."

# Setup inicial
python main.py setup

# Fetch todas as categorias
python main.py fetch

# Fetch categoria específica
python main.py fetch --category politics_pt

# Ver estatísticas
python main.py stats

# Listar sources
python main.py sources

# Cleanup notícias antigas (> 60 dias)
python main.py cleanup --days 60
```

## Estrutura

```
cron_politics/
├── main.py              # CLI principal
├── fetcher.py           # Coletor RSS
├── database.py          # Driver Supabase/PostgreSQL
├── deduplication.py     # Detecção de duplicatas
├── sources.json         # Feeds RSS por categoria
├── requirements.txt
└── .github/workflows/
    ├── fetch_news.yml   # Cron horário
    ├── cleanup.yml      # Limpeza semanal
    └── setup_db.yml     # Setup inicial
```

## Keywords de Priorização

### Alta prioridade (score +1 a +2)

**Portugal:** assembleia, parlamento, governo, marcelo, montenegro, eleições, demissão, corrupção

**Brasil:** congresso, stf, lula, bolsonaro, impeachment, cpi, operação, pf

**Conflitos:** guerra, ataque, bombardeio, míssil, invasão, ucrânia, gaza, israel

**Desastres:** terremoto, tsunami, furacão, inundação, incêndio, erupção

### Filtradas (ignoradas)
- horóscopo, reality show, fofoca, promoção, bitcoin price

## Workflows

| Workflow | Frequência | Ação |
|----------|------------|------|
| `fetch_news.yml` | A cada hora | Coleta notícias |
| `cleanup.yml` | Domingo 3h | Remove > 60 dias |
| `setup_db.yml` | Manual | Cria tabelas |

## Custos

| Serviço | Uso estimado | Limite grátis |
|---------|--------------|---------------|
| Supabase | ~100MB/mês | 500MB |
| GitHub Actions | ~3000 min/mês | Ilimitado (repo público) |

**Total: $0/mês**
