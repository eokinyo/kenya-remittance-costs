# What it costs to send money to Kenya: World Bank remittance price data

Code to reproduce the charts and numbers in the article [The 1% US tax is not the biggest cost of sending money to Kenya](https://ellyokinyo.com/writing/kenya-remittance-costs-2026.html) by Elly Okinyo (3 October 2026).

The repository holds code only. No data files are committed: the script downloads the data from the World Bank and the Central Bank of Kenya each time it runs (and caches it in `data/`, which is git-ignored). No API keys needed.

## What it reproduces

`remittance_costs.py` runs three steps:

1. **Download** the World Bank's Remittance Prices Worldwide (RPW) complete dataset (2011 to Q3 2025) and the Central Bank of Kenya (CBK) "Remittances by Source" file for August 2026.
2. **Analyse** the cost of sending the equivalent of US$200 to Kenya and print every number used in the article:
   - corridor averages for the six corridors into Kenya in Q3 2025 (USA 4.26% across 40 services, UK, Canada, Tanzania 59.99%, Rwanda, South Africa) and their change since Q2 2016
   - the USA corridor by payment instrument (cash 7.70% against 3.77% for bank- or card-funded transfers) and by receiving method
   - the cash vs bank/card gap on US$200 compared with the US$2 that the 1% US tax adds
   - the Tanzania corridor by provider (bank transfers vs M-Pesa, MoneyGram and Western Union)
   - the global average for Q3 2025, computed from the dataset and compared with the World Bank report
   - CBK, August 2026: Tanzania (US$11.72m) vs Saudi Arabia (US$11.61m)
3. **Chart** the two figures in the article.

## Setup (once)

Requires Python 3.11 or newer.

**Windows (PowerShell)**

    cd path\to\kenya-remittance-costs
    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt

**macOS / Linux (Terminal)**

    cd path/to/kenya-remittance-costs
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt

## Run

**Windows (PowerShell)**

    .venv\Scripts\python remittance_costs.py

**macOS / Linux**

    .venv/bin/python remittance_costs.py

(If you prefer to activate the venv first: `.venv\Scripts\Activate.ps1` on Windows, `source .venv/bin/activate` on macOS/Linux, then `python remittance_costs.py`.)

The first run downloads about 50 MB from the World Bank and takes a minute or so to read the Excel sheet. Later runs reuse the cached files and take a few seconds; add `--refresh` to download them again.

## Outputs (created next to the script)

- `outputs/charts/1_usa_kenya_cost_by_funding.png` (Figure 1): cost of sending US$200 from the USA to Kenya by payment instrument, Q3 2025, with the 1% US tax shown on the cash bar
- `outputs/charts/2_kenya_corridor_costs.png` (Figure 2): corridor averages to Kenya by sending country, Q2 2016 to Q3 2025, in two panels (USA, UK, Canada; Tanzania, Rwanda, South Africa)
- `outputs/kenya_corridor_costs.csv`: quarter, sending country, mean, median and number of services
- `outputs/usa_kenya_by_instrument_2025Q3.csv`: USA corridor by payment instrument
- `data/raw/`: the downloaded Excel files, plus two small CSV extracts of the RPW sheet (a cache)

The charts are 300 dpi PNGs in the same style as [kenya-remittances-2026](https://github.com/eokinyo/kenya-remittances-2026). Every chart's footer reads "Source: World Bank, Remittance Prices Worldwide. Chart: Elly Okinyo."

## Method notes

- Cost is RPW's "total cost": the sender's fee plus the exchange-rate margin, as a percentage of the amount sent, for the US$200-equivalent amount (`cc1 total cost %`).
- Corridor averages are simple means across transparent services in each quarter. Non-transparent services (where the provider did not disclose the exchange rate) are left out, as on the World Bank's corridor pages. This reproduces the published corridor averages (for example USA to Kenya 4.26%, Tanzania to Kenya 59.99%, Rwanda to Kenya 22.56% in Q3 2025). The averages are not weighted by volume, and they are quoted prices, not prices actually paid.
- The global average is the simple mean across all services in the latest round. It matches the 6.36% in the World Bank's Q3 2025 report. The Sub-Saharan Africa average quoted in the article (8.46%) is taken from that report; the script's own calculation gives 8.47% (a rounding difference) and prints both.
- The 3% target (UN SDG 10.c / G20, for the global average by 2030) and the 1% US tax (26 U.S.C. 4475, cash-funded transfers, since 1 January 2026) are constants at the top of the script.
- RPW covers six corridors into Kenya: USA, UK, Canada, South Africa, Tanzania and Rwanda. There are no Gulf corridors. There was no RPW round in Q2 2025; Figure 2 bridges the gap with a dotted line and does not interpolate.
- The download URLs are pinned to the releases used in the article (RPW Q3 2025, CBK August 2026), so the numbers do not change when newer data comes out. To use newer data, change `RPW_URL`, `CBK_URL` and `CBK_YEAR`/`CBK_MONTH` at the top of the script.
- CBK publishes values in USD thousands; the script prints USD millions. CBK revises recent months now and then.

## If the download fails

- **World Bank:** open the [RPW page on the World Bank Data Catalog](https://datacatalog.worldbank.org/search/dataset/0037898/remittance-prices-worldwide), download "Remittance Prices Worldwide (Complete Dataset)" and save it as `data/raw/rpw_dataset_2011_2025_q3.xlsx`.
- **CBK:** open <https://www.centralbank.go.ke/diaspora-remittances/>, click "Remittances by Source ('000 USD Equivalent)" and save the file as `data/raw/August2026.xlsx`.

Then run the script again.

## Data sources

- World Bank, Remittance Prices Worldwide, complete dataset 2011 to Q3 2025 (Excel): <https://datacatalogfiles.worldbank.org/ddh-published/0037898/DR0095523/rpw_dataset_2011_2025_q3.xlsx> (catalog page: <https://datacatalog.worldbank.org/search/dataset/0037898/remittance-prices-worldwide>)
- World Bank, Remittance Prices Worldwide, Issue 54, September 2025 (Q3 2025 report): <https://datacatalogfiles.worldbank.org/ddh-published/0037898/DR0095413/RPW_main_report_and_annex_Q325.pdf>
- World Bank corridor pages: [United States to Kenya](https://remittanceprices.worldbank.org/corridor/United-States/Kenya), [Tanzania to Kenya](https://remittanceprices.worldbank.org/corridor/Tanzania/Kenya)
- Central Bank of Kenya, Remittances by Source, August 2026 (Excel): <https://www.centralbank.go.ke/wp-content/uploads/2026/09/August2026.xlsx>, linked from <https://www.centralbank.go.ke/diaspora-remittances/>
- 26 U.S.C. 4475, remittance transfer tax: <https://www.law.cornell.edu/uscode/text/26/4475>

## License

MIT, see [LICENSE](LICENSE).
