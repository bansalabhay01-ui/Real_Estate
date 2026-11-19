# LeadOps results

Measured on 19 Nov 2026 with the model `lgbm-20261107-c41e90` by `ml/evaluate.py`. Run it again after collecting more
sessions; it rewrites this file. Scores leave out sales verdicts, and the three groups are never added together.

## 1. Real people

**No sessions collected yet.** This is the number that matters most, and it needs people, so nothing is claimed here.
Follow "Collecting real test sessions" in the README (target: 30 to 50 sessions), then run this script again.

## 2. Real bots

Playwright bots driving a real browser against the demo site (`ml/bots/run_bots.py`). The team wrote these three bots, so this shows the
engine works on real browsers. It does not show that every bot in the wild would be caught.

- **Bots filtered out:** **15/15** (100.0%; 95% CI 80% to 100%)

| Visitor | Total | Bot | Junk | Review | Cold | Warm | Hot |
|---|---:|---:|---:|---:|---:|---:|---:|
| Naive form bot | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| Scraper | 5 | 5 | 0 | 0 | 0 | 0 | 0 |
| Stealth bot | 5 | 5 | 0 | 0 | 0 | 0 | 0 |

## 3. Simulated traffic

1000 visitors from `ml/simulator.py`: a new random sample (seed 2026), not the visitors the model trained on. The model did learn from the
same simulator, so these numbers are the easiest of the three and are not evidence of real-world accuracy.

- **Fake visitors filtered out (recall):** **600/600** (100.0%; 95% CI 99% to 100%)
- **Genuine buyers kept:** **400/400** (100.0%; 95% CI 99% to 100%)
- **Of everything filtered out, truly fake (precision):** **600/600** (100.0%; 95% CI 99% to 100%)

| Visitor | Total | Bot | Junk | Review | Cold | Warm | Hot |
|---|---:|---:|---:|---:|---:|---:|---:|
| Click bots | 35 | 35 | 0 | 0 | 0 | 0 | 0 |
| Form bots | 97 | 97 | 0 | 0 | 0 | 0 | 0 |
| Scrapers | 113 | 113 | 0 | 0 | 0 | 0 | 0 |
| Slow scrapers | 61 | 61 | 0 | 0 | 0 | 0 | 0 |
| Stealth bots | 94 | 94 | 0 | 0 | 0 | 0 | 0 |
| Casual browsers | 164 | 0 | 0 | 6 | 157 | 1 | 0 |
| Serious buyers | 236 | 0 | 0 | 5 | 7 | 94 | 130 |
| Rival brokers | 53 | 0 | 53 | 0 | 0 | 0 | 0 |
| Fake details | 76 | 0 | 76 | 0 | 0 | 0 | 0 |
| Spam | 35 | 0 | 35 | 0 | 0 | 0 | 0 |
| Renters | 36 | 0 | 36 | 0 | 0 | 0 | 0 |
