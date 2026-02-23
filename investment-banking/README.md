# Investment Banking Plugin

Investment banking productivity tools for equity research, valuation, presentations, and deal materials.

## Features

- **Equity Research** - Earnings updates, initiating coverage reports
- **Valuation** - DCF models, comparable company analysis
- **Presentations** - Strip profiles, pitch decks with branded templates
- **Financial Analysis** - Comps with statistics, margin analysis

## Installation

```bash
claude --plugin-dir /path/to/investment-banking
```

Or copy to your project's `.claude-plugin/` directory.

## Commands

| Command | Description |
|---------|-------------|
| `/ib:comps [company]` | Build comparable company analysis with trading multiples |
| `/ib:dcf [company]` | DCF valuation model with comps-informed terminal multiples |
| `/ib:earnings [company] [quarter]` | Quarterly earnings update report (8-12 pages) |
| `/ib:one-pager [company]` | One-page strip profile using PPT template |
| `/ib:ppt-template [path]` | Create a PPT template skill from a PowerPoint file |

## Skills

### Equity Research
| Skill | Description |
|-------|-------------|
| **earnings-analysis** | Quarterly earnings update reports with beat/miss analysis, charts, and updated estimates |
| **initiating-coverage** | Full equity research initiation reports (30-50 pages, 5-task workflow) |

### Valuation
| Skill | Description |
|-------|-------------|
| **comps-analysis** | Comparable company analysis with operating metrics and valuation multiples |
| **dcf-model** | DCF models with WACC, sensitivity analysis, and scenario cases |

### Presentations
| Skill | Description |
|-------|-------------|
| **strip-profile** | Information-dense company profiles for pitch books |
| **omnicell-ppt-template** | Board presentation template (11x8.5 letter size) |
| **ppt-template-creator** | Create template skills from any PowerPoint file |

### Utilities
| Skill | Description |
|-------|-------------|
| **skill-creator** | General skill-building best practices and utilities |

## Example Workflows

### Earnings Analysis
```
/ib:earnings Target Q3 2024

# Generates:
# - 8-12 page DOCX report with beat/miss analysis
# - 8 charts (revenue trend, EPS, margins, segments, etc.)
# - Updated estimates and price target
```

### Comparable Company Analysis
```
/ib:comps Target

# Generates:
# - Excel file with operating metrics and valuation multiples
# - Statistics (Max, 75th, Median, 25th, Min) for all ratios
# - Peer group: Walmart, Costco, Dollar General, BJ's
```

### DCF Valuation
```
/ib:dcf Target

# Workflow:
# 1. Runs comps analysis first for terminal multiple benchmarks
# 2. Builds DCF with Bear/Base/Bull scenarios
# 3. Cross-checks implied multiples vs peers
```

### One-Page Strip Profile
```
/ib:one-pager Target

# Generates:
# - Single-slide company profile using PPT template
# - 4 quadrants: Overview, Business, Financials, Ownership
# - Respects template margins and branding
```

## Formatting Defaults

- **Font**: Times New Roman (for earnings and initiating coverage reports)
- **PPT Templates**: Content starts at OBJECT placeholder y-position (not subtitle)
- **Comps Statistics**: Applied to ratios/margins/multiples, not absolute size metrics

## Key Skills Details

### comps-analysis
- Statistics for comparable metrics (growth %, margins, multiples)
- No statistics for size metrics (revenue, market cap, EV)
- Blue text for inputs, black for formulas

### strip-profile
- Maximum information density per quadrant
- 6-8 bullets per section with specific numbers
- Single textbox per section (not separate header)

### ppt-template-creator
- Analyzes OBJECT placeholder to find true content start
- Documents exact x/y coordinates for content boundaries
- Handles templates with sidebars/borders

## Related Plugins

- **employee** - Office document skills (docx, pdf, pptx, xlsx)
- **sales** - CRM integration and prospect research
- **data-analyst** - BigQuery and data visualization
